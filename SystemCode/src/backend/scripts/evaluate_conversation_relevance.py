"""Read-only provider capture for relevance; semantic review remains explicit."""

import argparse
import asyncio
import json
from pathlib import Path
from time import monotonic

from dotenv import load_dotenv
from langchain_core.messages import ToolMessage

from SystemCode.src.backend.agents.contracts import ConversationExchange
from SystemCode.src.backend.agents.conversation_response import run_validated_conversation
from SystemCode.src.backend.agents.model_factory import create_conversation_agent_model
from SystemCode.src.backend.domain.models import FamilyDetails
from SystemCode.src.backend.repositories.school_repository import SchoolRepository
from SystemCode.src.backend.services.conversation_context_service import ConversationContextService
from SystemCode.src.backend.services.conversation_tool_service import ConversationToolService
from SystemCode.src.backend.services.evaluation_service import EvaluationService
from SystemCode.src.backend.services.location_service import LocationService
from SystemCode.src.backend.services.preference_service import PreferenceService

ROOT = Path(__file__).resolve().parents[4]
DATASET = Path(__file__).resolve().parents[1] / "resources/conversation_relevance_evaluation.json"


class CaptureModel:
    def __init__(self, delegate):
        self.delegate = delegate
        self.calls = []
        self.results = {}

    def bind_tools(self, tools):
        self.delegate = self.delegate.bind_tools(tools)
        return self

    def invoke(self, messages):
        for message in messages:
            if isinstance(message, ToolMessage):
                result = json.loads(message.content)
                if "result_id" in result:
                    self.results[result["result_id"]] = result
        reply = self.delegate.invoke(messages)
        self.calls.extend({"name": c["name"], "presentation": c["args"].get("presentation")}
                          for c in reply.tool_calls)
        return reply


async def capture(output):
    import os
    load_dotenv(ROOT / ".env", override=True)
    dataset = json.loads(DATASET.read_text())
    schools = SchoolRepository(ROOT / "SystemCode/data/processed/kindercompass_master.json")
    evaluation = EvaluationService(schools)
    locations = LocationService(schools, ROOT / "SystemCode/data/raw/PreSchoolsLocation.geojson")
    service = PreferenceService(schools, evaluation, locations, ROOT)
    school_index, general_index = service._resources()
    family = FamilyDetails(dob="2022-06-01", admission_date="2026-11-01",
                           gross_household_income=6000, household_size=4)
    report = {"dataset_id": dataset["dataset_id"], "synthetic_family_only": True,
              "catalogue_version": schools.catalogue_version,
              "semantic_review_required": True, "cases": []}
    for case in dataset["cases"]:
        context = ConversationContextService(schools).build(
            message=case["message"], profile=case.get("profile"), family=family,
            selected_school_ids=case.get("selected_school_ids"))
        context = context.model_copy(update={"recent_exchanges": [
            ConversationExchange.model_validate(e) for e in case.get("recent_exchanges", [])]})
        tools = ConversationToolService(context, schools, evaluation, locations,
            school_index_loader=lambda: school_index,
            general_retriever_loader=lambda: service._knowledge_retriever(general_index))
        initial_profile = tools.staged_profile
        model = CaptureModel(create_conversation_agent_model({**os.environ, "CONVERSATION_AGENT_MODE": "agent"}))
        started = monotonic()
        reply = await run_validated_conversation(context, tools, model=model)
        names = {c["name"] for c in model.calls}
        checks = {
            "served": reply.status == "ok",
            "required_tools": set(case["required_tools"]) <= names,
            "forbidden_tools": not set(case.get("forbidden_tools", [])) & names,
            "any_tools": not case.get("any_tools") or bool(set(case["any_tools"]) & names),
            "profile_preserved": reply.profile == initial_profile if reply.status == "ok" else False,
        }
        if case.get("distinct_names"):
            searches = [r for r in model.results.values() if r["tool_name"] == "search_rank_compare_schools"]
            checks["distinct_names"] = bool(searches) and all(
                r["data"].get("presentation") == "distinct_names" and
                len({"".join(c for c in row["name"].casefold() if c.isalnum())
                     for row in r["data"].get("records", [])}) == len(r["data"].get("records", []))
                for r in searches)
        entry = {"case_id": case["case_id"], "message": case["message"], "answer": reply.answer,
                 "status": reply.status, "validation_errors": reply.validation_errors,
                 "failure_reason": reply.failure_reason, "tool_calls": model.calls,
                 "elapsed_seconds": round(monotonic() - started, 3), "checks": checks,
                 "mechanical_pass": all(checks.values()), "review_criterion": case["review"]}
        report["cases"].append(entry)
        output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(entry), flush=True)
    return 0 if all(c["mechanical_pass"] for c in report["cases"]) else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(capture(args.output)))
