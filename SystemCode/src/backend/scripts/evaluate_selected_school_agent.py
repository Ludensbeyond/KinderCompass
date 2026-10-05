"""Compare selected-school deterministic and LangGraph answers offline."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

from SystemCode.src.backend.agents.contracts import EvidenceCitation, SelectedSchoolAgentRequest
from SystemCode.src.backend.agents.graph import run_selected_school_evidence_graph
from scripts.evaluate_web_rag_answers import _answer_cases, _expected_term_matches
from stage1.conversation import _answer_web_evidence
from stage1.web_rag import load_json, save_json


BACKEND_ROOT = Path(__file__).resolve().parents[1]
AgentRunner = Callable[..., Any]


def _deterministic_answer(
    index: dict[str, Any], case: dict[str, Any]
) -> tuple[str, list[dict[str, Any]]]:
    previous_mode = os.environ.get("WEB_RAG_ANSWER_MODE")
    previous_legacy = os.environ.get("OPENAI_WEB_RAG_ANSWERS_ENABLED")
    os.environ["WEB_RAG_ANSWER_MODE"] = "deterministic"
    os.environ["OPENAI_WEB_RAG_ANSWERS_ENABLED"] = "false"
    try:
        answer, citations, _, _ = _answer_web_evidence(
            str(case["question"]),
            [{"school_id": case["school_id"], "name": case["school_name"]}],
            index,
        )
        return answer, citations
    finally:
        for key, value in (
            ("WEB_RAG_ANSWER_MODE", previous_mode),
            ("OPENAI_WEB_RAG_ANSWERS_ENABLED", previous_legacy),
        ):
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _citation_contracts(
    school_id: str, citations: list[dict[str, Any]]
) -> list[EvidenceCitation]:
    return [
        EvidenceCitation(
            citation_id=str(item["chunk_id"]),
            school_id=school_id,
            chunk_id=str(item["chunk_id"]),
            url=str(item["url"]),
            title=str(item["title"]),
            retrieved_at=item["retrieved_at"],
        )
        for item in citations
    ]


def _quality(
    case: dict[str, Any], answer: str, citations: list[EvidenceCitation]
) -> dict[str, bool]:
    folded = answer.casefold()
    expected_terms = [str(term) for term in case.get("expected_terms", [])]
    forbidden_terms = [str(term).casefold() for term in case.get("forbidden_terms", [])]
    return {
        "evidence_correct": bool(citations) == bool(case.get("evidence_expected")),
        "terms_correct": not expected_terms or any(
            _expected_term_matches(answer, term) for term in expected_terms
        ),
        "unsupported_claim_free": not any(term in folded for term in forbidden_terms),
        "concise": len(answer.split()) <= int(case.get("maximum_words", 60)),
        "citations_valid": all(
            citation.school_id == case["school_id"] for citation in citations
        ),
    }


def evaluate(
    index: dict[str, Any],
    labels: dict[str, Any],
    *,
    agent_runner: AgentRunner = run_selected_school_evidence_graph,
) -> dict[str, Any]:
    """Run both paths over the same ordered cases and return safe metrics only."""

    results: list[dict[str, Any]] = []
    for case in _answer_cases(index, labels):
        deterministic_answer, raw_citations = _deterministic_answer(index, case)
        deterministic_citations = _citation_contracts(case["school_id"], raw_citations)
        deterministic_quality = _quality(
            case, deterministic_answer, deterministic_citations
        )
        agent_result = agent_runner(
            index,
            SelectedSchoolAgentRequest(
                question=case["question"],
                school_id=case["school_id"],
                school_name=case["school_name"],
            ),
            deterministic_answer=deterministic_answer,
            deterministic_citations=deterministic_citations,
        )
        agent_quality = _quality(case, agent_result.answer, list(agent_result.citations))
        deterministic_passed = all(deterministic_quality.values())
        agent_passed = all(agent_quality.values())
        results.append(
            {
                "case_id": case["case_id"],
                "deterministic_passed": deterministic_passed,
                "agent_passed": agent_passed,
                "comparison": (
                    "improved" if agent_passed and not deterministic_passed
                    else "regressed" if deterministic_passed and not agent_passed
                    else "tied"
                ),
                "deterministic_quality": deterministic_quality,
                "agent_quality": agent_quality,
                "execution_metadata": agent_result.execution_metadata,
            }
        )

    total = len(results)
    comparison = {
        status: sum(item["comparison"] == status for item in results)
        for status in ("improved", "regressed", "tied")
    }
    return {
        "schema_version": 1,
        "case_count": total,
        "deterministic_pass_rate": round(
            sum(item["deterministic_passed"] for item in results) / total, 4
        ) if total else 0.0,
        "agent_pass_rate": round(
            sum(item["agent_passed"] for item in results) / total, 4
        ) if total else 0.0,
        "agent_fallback_rate": round(
            sum(
                item["execution_metadata"]["answer_method"] == "deterministic_fallback"
                for item in results
            ) / total,
            4,
        ) if total else 0.0,
        "comparison": comparison,
        "results": results,
    }


def main() -> int:
    load_dotenv(BACKEND_ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--index", type=Path,
        default=BACKEND_ROOT / "output" / "web_rag_pilot_index.json",
    )
    parser.add_argument(
        "--labels", type=Path,
        default=BACKEND_ROOT / "resources" / "web_rag" / "answer_quality_labels.json",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate(load_json(args.index), load_json(args.labels))
    if args.output:
        save_json(args.output, report)
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
