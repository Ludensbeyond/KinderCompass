"""Workstream 2 competency-question and Stage 1 retrieval evaluation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from stage1.nlp_mapper import map_text_to_filters
from stage1.query_builder import build_stage1_query


DEFAULT_LABELS_PATH = (
    Path(__file__).resolve().parents[2] / "resources" / "stage1_graph_evaluation.json"
)
GRAPH_REL_RE = re.compile(r"\[:([A-Z_]+)\]")
PATH_REL_RE = re.compile(r"rel: '([A-Z_]+)'")
FIDELITY_KINDS = {
    "graph_hard",
    "multi_hop",
    "structured_postal",
    "hybrid_graph_plus_pref",
    "score_time",
}


def load_labels(path: Path | None = None) -> dict[str, Any]:
    source = Path(path) if path else DEFAULT_LABELS_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Graph evaluation labels must be a JSON object")
    questions = payload.get("competency_questions") or []
    cases = payload.get("retrieval_cases") or []
    if not isinstance(questions, list) or not isinstance(cases, list):
        raise ValueError("competency_questions and retrieval_cases must be lists")
    return payload


def extract_cypher_rels(query: str) -> list[str]:
    """Return MATCH relationship types, preserving order and dropping duplicates."""
    seen = []
    for rel in GRAPH_REL_RE.findall(query or ""):
        if rel not in seen:
            seen.append(rel)
    return seen


def extract_path_rels(query: str) -> list[str]:
    seen = []
    for rel in PATH_REL_RE.findall(query or ""):
        if rel not in seen:
            seen.append(rel)
    return seen


def resolve_filters(case: dict[str, Any]) -> dict[str, Any]:
    if case.get("filters"):
        return dict(case["filters"])
    if case.get("stage1_filters"):
        return dict(case["stage1_filters"])
    if case.get("text"):
        return map_text_to_filters(case["text"])
    return {}


def precision_recall(predicted: list[str] | set[str], gold: list[str] | set[str]) -> dict[str, float]:
    pred = {item for item in predicted if item}
    expected = {item for item in gold if item}
    if not pred and not expected:
        precision = recall = 1.0
    else:
        overlap = len(pred & expected)
        precision = overlap / len(pred) if pred else 1.0
        recall = overlap / len(expected) if expected else 1.0
    if precision + recall:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "predicted": len(pred),
        "gold": len(expected),
        "true_positives": len(pred & expected),
    }


def _school_ids(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row["school_id"]) for row in rows if row.get("school_id") is not None]


def _path_rel_names(row: dict[str, Any]) -> list[str]:
    path = row.get("retrieval_path") or []
    names = []
    if not isinstance(path, list):
        return names
    for step in path:
        if isinstance(step, dict) and step.get("rel"):
            names.append(str(step["rel"]))
    return names


def evaluate_offline(labels: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = labels or load_labels()
    questions = []
    expressible = 0
    for question in payload["competency_questions"]:
        mode = question["stage1_mode"]
        filters = resolve_filters(question)
        query, _params = build_stage1_query(filters) if filters else ("", {})
        rels = extract_cypher_rels(query)
        if question["schema_expressible"]:
            expressible += 1
        if mode == "match":
            passed = all(rel in rels for rel in question["graph_rels"])
        elif mode == "score_time":
            passed = not any(rel in rels for rel in question["graph_rels"])
        elif mode == "property":
            passed = "p.postal_code = $postal_code" in query and "LOCATED_IN" not in rels
        else:
            passed = not rels
        questions.append({
            "id": question["id"],
            "schema_expressible": question["schema_expressible"],
            "stage1_mode": mode,
            "passed": passed,
            "cypher_rels": rels,
        })

    retrieval = []
    for case in payload["retrieval_cases"]:
        query, _params = build_stage1_query(resolve_filters(case))
        rels = extract_cypher_rels(query)
        path_rels = extract_path_rels(query)
        expected = list(case.get("expected_rels") or [])
        forbidden = list(case.get("forbidden_rels") or [])
        graph_expected = [rel for rel in expected if rel != "POSTAL_CODE"]
        missing = [rel for rel in graph_expected if rel not in rels]
        extra_forbidden = [rel for rel in forbidden if rel in rels]
        path_ok = all(rel in path_rels for rel in expected)
        retrieval_path_present = "retrieval_path" in query
        passed = not missing and not extra_forbidden and path_ok and retrieval_path_present
        if case.get("kind") == "score_time":
            passed = passed and not rels
        retrieval.append({
            "id": case["id"],
            "kind": case["kind"],
            "hops": case.get("hops", 0),
            "passed": passed,
            "cypher_rels": rels,
            "path_rels": path_rels,
            "missing_rels": missing,
            "forbidden_rels_present": extra_forbidden,
        })

    cq_failed = [item["id"] for item in questions if not item["passed"]]
    retrieval_failed = [item["id"] for item in retrieval if not item["passed"]]
    multi_hop = [item for item in retrieval if item["hops"] >= 2]
    return {
        "offline": True,
        "passed": not cq_failed and not retrieval_failed,
        "competency_questions": {
            "total": len(questions),
            "schema_expressible": expressible,
            "coverage": round(expressible / len(questions), 4) if questions else 0.0,
            "passed": len(questions) - len(cq_failed),
            "failed_ids": cq_failed,
            "cases": questions,
        },
        "retrieval_shape": {
            "total": len(retrieval),
            "passed": len(retrieval) - len(retrieval_failed),
            "failed_ids": retrieval_failed,
            "multi_hop": len(multi_hop),
            "cases": retrieval,
        },
    }


def evaluate_live(
    run_query: Callable[[str, dict[str, Any] | None], list[dict[str, Any]]],
    labels: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = labels or load_labels()
    stats_rows = run_query("MATCH (p:Preschool) RETURN count(p) AS preschools", {})
    preschool_count = int((stats_rows[0] or {}).get("preschools") or 0) if stats_rows else 0
    cases = []
    for case in payload["retrieval_cases"]:
        query, params = build_stage1_query(resolve_filters(case), include_base_fee=False)
        predicted_rows = run_query(query, params)
        gold_rows = run_query(case["gold_cypher"], case.get("gold_params") or {})
        predicted_ids = _school_ids(predicted_rows)
        gold_ids = _school_ids(gold_rows)
        metrics = precision_recall(predicted_ids, gold_ids)
        path_rows = [row for row in predicted_rows if isinstance(row.get("retrieval_path"), list)]
        provenance_complete = (
            1.0 if not predicted_rows else round(len(path_rows) / len(predicted_rows), 4)
        )
        expected = [rel for rel in (case.get("expected_rels") or []) if rel]
        hop_hits = 0
        for row in predicted_rows:
            recovered = set(_path_rel_names(row))
            if expected and expected_set_recovered(expected, recovered):
                hop_hits += 1
        multi_hop_success = (
            True if not expected
            else True if not predicted_rows and not gold_ids
            else hop_hits == len(predicted_rows) and bool(predicted_rows)
        )
        ablation = None
        if case.get("ablation_cypher"):
            ablation_ids = _school_ids(run_query(case["ablation_cypher"], case.get("ablation_params") or {}))
            ablation = {
                **precision_recall(ablation_ids, gold_ids),
                "keeps_unknown": len(predicted_ids) > len(ablation_ids),
            }
        fidelity_required = case.get("kind") in FIDELITY_KINDS
        passed = (not fidelity_required) or (
            metrics["precision"] == 1.0
            and metrics["recall"] == 1.0
            and provenance_complete == 1.0
            and multi_hop_success
        )
        if case.get("kind") == "score_time" and ablation:
            passed = passed and ablation["keeps_unknown"]
        cases.append({
            "id": case["id"],
            "kind": case["kind"],
            "hops": case.get("hops", 0),
            "passed": passed,
            "metrics": metrics,
            "provenance_complete": provenance_complete,
            "multi_hop_success": multi_hop_success,
            "ablation": ablation,
            "false_positives": sorted(set(predicted_ids) - set(gold_ids))[:10],
            "false_negatives": sorted(set(gold_ids) - set(predicted_ids))[:10],
        })

    scored = [item["metrics"] for item in cases]
    mean = _mean_metrics(scored)
    failed_ids = [item["id"] for item in cases if not item["passed"]]
    multi_hop_cases = [item for item in cases if item["hops"] >= 2]
    return {
        "live": True,
        "preschool_count": preschool_count,
        "passed": preschool_count > 0 and not failed_ids,
        "failed_ids": failed_ids,
        "macro": mean,
        "multi_hop_success_rate": (
            round(sum(item["multi_hop_success"] for item in multi_hop_cases) / len(multi_hop_cases), 4)
            if multi_hop_cases else 0.0
        ),
        "provenance_complete_rate": round(
            sum(item["provenance_complete"] for item in cases) / len(cases), 4
        ) if cases else 0.0,
        "cases": cases,
    }


def expected_set_recovered(expected: list[str], recovered: set[str]) -> bool:
    return all(rel in recovered for rel in expected)


def _mean_metrics(rows: list[dict[str, float]]) -> dict[str, float]:
    if not rows:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    count = len(rows)
    return {
        "precision": round(sum(item["precision"] for item in rows) / count, 4),
        "recall": round(sum(item["recall"] for item in rows) / count, 4),
        "f1": round(sum(item["f1"] for item in rows) / count, 4),
    }


def combine_report(offline: dict[str, Any], live: dict[str, Any] | None = None) -> dict[str, Any]:
    report = {
        "evaluation": "stage1_graph_p1",
        "gold_definition": (
            "Independent canonical Cypher school_id sets on the live graph. "
            "This is Stage 1 fidelity to the schema, not human relevance labelling."
        ),
        "offline": offline,
        "live": live,
        "passed": bool(offline.get("passed")) and (live is None or bool(live.get("passed"))),
    }
    return report


def markdown(report: dict[str, Any]) -> str:
    offline = report["offline"]
    cq = offline["competency_questions"]
    shape = offline["retrieval_shape"]
    lines = [
        "# Stage 1 graph evaluation (Workstream 2 P1)",
        "",
        report["gold_definition"],
        "",
        f"**Offline shape checks:** {'PASS' if offline['passed'] else 'FAIL'} "
        f"({cq['passed']}/{cq['total']} competency questions, "
        f"{shape['passed']}/{shape['total']} retrieval cases, "
        f"{shape['multi_hop']} multi-hop).",
        "",
        f"**Schema competency coverage:** {cq['schema_expressible']}/{cq['total']} "
        f"({cq['coverage']:.0%} expressible in the graph).",
        "",
    ]
    live = report.get("live")
    if not live:
        lines.append("Live Neo4j evaluation was not run.")
        return "\n".join(lines) + "\n"
    lines.extend([
        f"**Live Neo4j:** {'PASS' if live['passed'] else 'FAIL'} "
        f"({live['preschool_count']} preschool nodes).",
        "",
        f"**Macro precision/recall/F1:** {live['macro']['precision']:.3f} / "
        f"{live['macro']['recall']:.3f} / {live['macro']['f1']:.3f}",
        "",
        f"**Multi-hop path recovery:** {live['multi_hop_success_rate']:.0%}",
        "",
        f"**Provenance completeness:** {live['provenance_complete_rate']:.0%}",
        "",
        "| Case | Kind | P | R | F1 | Multi-hop path | Ablation |",
        "|---|---|---:|---:|---:|---|---|",
    ])
    for item in live["cases"]:
        path_label = "n/a" if item.get("hops", 0) < 2 else ("yes" if item["multi_hop_success"] else "no")
        ablation = item.get("ablation") or {}
        if not ablation:
            ablation_label = ""
        elif item["kind"] in {"score_time", "hybrid_graph_plus_pref"}:
            ablation_label = "keeps unknown" if ablation.get("keeps_unknown") else "drops unknown"
        else:
            ablation_label = (
                f"property P {ablation['precision']:.3f} / R {ablation['recall']:.3f}"
            )
        lines.append(
            f"| {item['id']} | {item['kind']} | {item['metrics']['precision']:.3f} | "
            f"{item['metrics']['recall']:.3f} | {item['metrics']['f1']:.3f} | "
            f"{path_label} | {ablation_label} |"
        )
    if live.get("failed_ids"):
        lines.extend(["", f"Failed cases: {', '.join(live['failed_ids'])}"])
    return "\n".join(lines) + "\n"
