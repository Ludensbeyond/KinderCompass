"""Run the reviewed full-conversation evaluation set against a staged model."""

from __future__ import annotations

import argparse
import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

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
from SystemCode.src.backend.services.decision_state_service import enrich_decision_state
from SystemCode.src.backend.services.preference_service import PreferenceService
from stage1.intent_router import classify_intent
from stage1.web_rag import load_json, save_json


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]


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
        current = deepcopy(case.profile)
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
        )
        with disable_agent_entry_points():
            deterministic = service._handle_deterministic(
                message=case.message,
                current=current,
                before=deepcopy(current),
                conversation_profile=current,
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
                current, agent_response, intent=intent.intent,
            )
        return ConversationEvaluationRun(
            deterministic_intent=intent.intent,
            deterministic_response=deterministic,
            agent_response=agent_response,
            metadata=outcome.metadata,
        )

    return run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases", type=Path,
        default=BACKEND_ROOT / "resources" / "conversation_agent_evaluation.json",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--staged", action="store_true",
        help="Acknowledge that this command invokes the configured model provider.",
    )
    args = parser.parse_args()
    if not args.staged:
        parser.error("--staged is required because this command may call a live provider")

    load_dotenv(REPO_ROOT / ".env")
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
