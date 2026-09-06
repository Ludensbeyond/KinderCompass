"""Run the reviewed full-conversation evaluation set against a staged model."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from dotenv import load_dotenv

from SystemCode.src.backend.agents.config import disable_agent_entry_points
from SystemCode.src.backend.agents.evaluation import (
    ConversationEvaluationCase,
    ConversationEvaluationRun,
    ConversationEvaluationSet,
    evaluate_conversation_cases,
)
from SystemCode.src.backend.agents.model_factory import create_conversation_agent_model
from SystemCode.src.backend.agents.validation import run_conversation_supervisor
from SystemCode.src.backend.domain.models import FamilyDetails
from SystemCode.src.backend.repositories.policy_repository import PolicyRepository
from SystemCode.src.backend.repositories.school_repository import SchoolRepository
from SystemCode.src.backend.services.decision_state_service import enrich_decision_state
from SystemCode.src.backend.services.preference_service import PreferenceService
from stage1.intent_router import classify_intent
from stage1.proximity import geocode_postal_code
from stage1.web_rag import load_json, save_json


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
PREFLIGHT_POSTAL_CODE = "540231"


@dataclass(frozen=True)
class PreflightDependency:
    """One injectable, privacy-safe staged prerequisite check."""

    name: str
    failure_category: str
    remediation: str
    check: Callable[[], None]


def _require_configured_model() -> None:
    if staged_model_factory() is None:
        raise RuntimeError("configured model was not created")


def _require_onemap() -> None:
    coordinates = geocode_postal_code(PREFLIGHT_POSTAL_CODE)
    if not all(
        isinstance(coordinates.get(key), (int, float))
        and math.isfinite(float(coordinates[key]))
        for key in ("latitude", "longitude")
    ):
        raise RuntimeError("OneMap returned invalid coordinates")


def _require_catalogue() -> None:
    path = REPO_ROOT / "SystemCode/data/processed/kindercompass_master.json"
    records = SchoolRepository(path).all()
    if not records or any(not record.school_id for record in records):
        raise RuntimeError("catalogue contains no stable school records")


def _require_policy() -> None:
    directory = BACKEND_ROOT / "resources" / "policy"
    repository = PolicyRepository(directory)
    repository.policies()
    repository.for_date(dt.date.today())


def _require_evidence_index(path: Path, collections: tuple[str, ...]) -> None:
    index = load_json(path)
    if not isinstance(index, dict):
        raise RuntimeError("evidence index has an invalid shape")
    chunk_count = 0
    for collection in collections:
        items = index.get(collection)
        if not isinstance(items, list):
            raise RuntimeError("evidence index has an invalid shape")
        if collection == "chunks":
            chunk_count += len(items)
        else:
            if any(
                not isinstance(item, dict)
                or not isinstance(item.get("chunks"), list)
                for item in items
            ):
                raise RuntimeError("evidence index has an invalid shape")
            chunk_count += sum(len(item["chunks"]) for item in items)
    if not chunk_count:
        raise RuntimeError("evidence index contains no chunks")


def default_preflight_dependencies() -> tuple[PreflightDependency, ...]:
    """Return checks for every live or curated staged dependency."""

    configured_web_index = os.getenv("WEB_RAG_INDEX_PATH", "").strip()
    web_index = (
        Path(configured_web_index) if configured_web_index
        else BACKEND_ROOT / "output" / "web_rag_pilot_index.json"
    )
    general_index = BACKEND_ROOT / "resources" / "web_rag" / "general_knowledge_index.json"
    return (
        PreflightDependency(
            "model", "model_unavailable",
            "Configure OPENAI_API_KEY and valid OPENAI_WEB_RAG model settings.",
            _require_configured_model,
        ),
        PreflightDependency(
            "onemap", "onemap_unavailable",
            "Configure usable OneMap credentials or a token and retry geocoding.",
            _require_onemap,
        ),
        PreflightDependency(
            "catalogue", "catalogue_unavailable",
            "Restore a valid generated school catalogue with stable school IDs.",
            _require_catalogue,
        ),
        PreflightDependency(
            "policy", "policy_unavailable",
            "Restore a valid, non-overlapping policy applicable today.",
            _require_policy,
        ),
        PreflightDependency(
            "selected_school_evidence", "selected_school_evidence_unavailable",
            "Configure a readable selected-school evidence index containing chunks.",
            lambda: _require_evidence_index(web_index, ("pages", "operator_pages")),
        ),
        PreflightDependency(
            "general_knowledge_evidence", "general_knowledge_evidence_unavailable",
            "Restore the curated general-knowledge evidence index containing chunks.",
            lambda: _require_evidence_index(general_index, ("chunks",)),
        ),
    )


def run_staged_preflight(
    dependencies: Sequence[PreflightDependency] | None = None,
) -> dict[str, Any]:
    """Check staged prerequisites without generating answers or writing a report."""

    results: list[dict[str, Any]] = []
    for dependency in dependencies or default_preflight_dependencies():
        try:
            dependency.check()
        except Exception:
            results.append({
                "name": dependency.name,
                "passed": False,
                "failure_category": dependency.failure_category,
                "remediation": dependency.remediation,
            })
        else:
            results.append({
                "name": dependency.name,
                "passed": True,
                "failure_category": None,
                "remediation": None,
            })
    return {
        "schema_version": 1,
        "passed": all(result["passed"] for result in results),
        "checks": results,
    }


def staged_model_factory() -> Any:
    """Construct the staged model without changing the production rollout mode."""

    return create_conversation_agent_model({
        **os.environ,
        "CONVERSATION_AGENT_MODE": "agent",
    })


def staged_runner(
    service: PreferenceService,
    *,
    model_factory: Callable[[], Any] | None = None,
) -> Callable[[ConversationEvaluationCase], ConversationEvaluationRun]:
    """Build a runner using real repositories and an injected or configured model."""

    def run(case: ConversationEvaluationCase) -> ConversationEvaluationRun:
        family = FamilyDetails.model_validate(case.family) if case.family else None
        initial_profile = deepcopy(case.profile)
        current = deepcopy(initial_profile)
        intent = classify_intent(
            case.message, (current.get("active_school") or {}).get("name"),
        )
        context = service.build_conversation_context(
            message=case.message,
            profile=current,
            selected_school_ids=case.selected_school_ids,
            eligible_school_ids=case.eligible_school_ids,
            excluded_school_ids=case.excluded_school_ids,
            family=family,
            home_postal_code=case.home_postal_code,
            include_full_catalogue=intent.intent == "find_closest_preschool",
            intent=intent,
        )
        with disable_agent_entry_points():
            deterministic = service._handle_deterministic(
                message=case.message,
                current=deepcopy(initial_profile),
                before=deepcopy(initial_profile),
                conversation_profile=deepcopy(initial_profile),
                intent=intent,
                context=context,
                selected_school_ids=case.selected_school_ids,
                eligible_school_ids=case.eligible_school_ids,
                excluded_school_ids=case.excluded_school_ids,
                family=family,
            )
        outcome = run_conversation_supervisor(
            context,
            service._conversation_tools(context),
            lambda: deepcopy(deterministic),
            model_factory=model_factory,
        )
        agent_response = outcome.response
        if outcome.metadata.validation_succeeded:
            agent_response = enrich_decision_state(
                initial_profile, agent_response, intent=intent.intent,
            )
        return ConversationEvaluationRun(
            deterministic_intent=intent.intent,
            deterministic_response=deterministic,
            agent_response=agent_response,
            metadata=outcome.metadata,
        )

    return run


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases", type=Path,
        default=BACKEND_ROOT / "resources" / "conversation_agent_evaluation.json",
    )
    parser.add_argument("--output", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--preflight", action="store_true",
        help="Check staged dependencies without model generation or report writes.",
    )
    mode.add_argument(
        "--staged", action="store_true",
        help="Acknowledge that this command invokes the configured model provider.",
    )
    args = parser.parse_args(argv)
    if args.preflight and args.output:
        parser.error("--output is only valid with --staged")

    load_dotenv(REPO_ROOT / ".env")
    preflight = run_staged_preflight()
    print(json.dumps(preflight, indent=2))
    if not preflight["passed"]:
        return 2
    if args.preflight:
        return 0

    # Importing the API service is deferred until every staged prerequisite is
    # healthy, so a failed preflight cannot reach an evaluation case.
    from SystemCode.src.backend.main import PREFERENCE_SERVICE

    cases = ConversationEvaluationSet.model_validate(load_json(args.cases))
    report = evaluate_conversation_cases(
        cases,
        staged_runner(PREFERENCE_SERVICE, model_factory=staged_model_factory),
    )
    if args.output:
        save_json(args.output, report)
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
