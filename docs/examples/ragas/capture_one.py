"""Capture only the step-3 nel_age turn through the existing staged runner.

All instrumentation is local to this offline process; production code and
privacy-safe evaluation reports remain unchanged.
"""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from unittest.mock import patch

from dotenv import load_dotenv
from SystemCode.src.backend.agents.evaluation import ConversationEvaluationCase
from SystemCode.src.backend.agents.tools import CuratedGeneralKnowledgeRetriever
from SystemCode.src.backend.scripts.evaluate_conversation_supervisor import (
    REPO_ROOT, staged_model_factory, staged_runner,
)
from SystemCode.src.backend.repositories.school_repository import SchoolRepository
from SystemCode.src.backend.services.evaluation_service import EvaluationService
from SystemCode.src.backend.services.location_service import LocationService
from SystemCode.src.backend.services.preference_service import PreferenceService
from stage1 import conversation


class RecordingModel:
    """Delegate unchanged calls and retain exact messages at the model boundary."""

    def __init__(self, delegate, invocations=None):
        self.delegate = delegate
        self.invocations = [] if invocations is None else invocations

    def bind_tools(self, *args, **kwargs):
        return RecordingModel(
            self.delegate.bind_tools(*args, **kwargs), self.invocations,
        )

    def invoke(self, messages):
        entry = {"messages": [message.model_dump(mode="json") for message in messages]}
        self.invocations.append(entry)
        try:
            response = self.delegate.invoke(messages)
        except Exception as error:
            entry["error_type"] = type(error).__name__
            raise
        entry["response"] = response.model_dump(mode="json")
        return response


def capture(service, execution_input, model):
    # This deliberately handles one independent case, not the dataset runner
    # planned for step 4. Reject setup that this collector cannot replay.
    if execution_input["case_id"] != "nel_age" or execution_input["setup"] != {
        "profile": {}, "selected_school_ids": [], "conversation_history": [],
    }:
        raise ValueError("step-3 capture supports only nel_age with fresh empty state")
    case = ConversationEvaluationCase(
        case_id="nel_age", sequence=1, conversation_id="nel_age", turn=1,
        message=execution_input["user_input"],
        expected_intent="ask_general_knowledge", expected_route_scope="general_knowledge",
    )
    initial = deepcopy(case.profile)
    recorder = RecordingModel(model)
    retrieved = []
    fallback_retrieval = []
    original_search = CuratedGeneralKnowledgeRetriever.search
    original_fallback_search = conversation.retrieve_general_evidence

    def search(retriever, question, *, limit=3):
        passages = original_search(retriever, question, limit=limit)
        retrieved.append([item.model_dump(mode="json") for item in passages])
        return passages

    def fallback_search(*args, **kwargs):
        matches = original_fallback_search(*args, **kwargs)
        fallback_retrieval.append(deepcopy(matches))
        return matches

    with patch.object(CuratedGeneralKnowledgeRetriever, "search", search), patch.object(
        conversation, "retrieve_general_evidence", fallback_search,
    ):
        run = staged_runner(service, model_factory=lambda: recorder)(case)

    # ToolMessage order is the order actually seen by the answering model.
    composition = [entry for entry in recorder.invocations if any(
        message["type"] == "tool" for message in entry["messages"]
    )]
    payloads = [json.loads(message["content"]) for message in (
        composition[-1]["messages"] if composition else []
    ) if message["type"] == "tool"]
    supplied = [text for payload in payloads for text in payload["grounding_facts"]]
    passages = [passage for batch in retrieved for passage in batch]
    fallback = not run.metadata.validation_succeeded
    if fallback:
        # For this single question _answer_general_knowledge uses matches[:1].
        # These are observed controller retrievals, never labelled references.
        passages = [
            {"chunk_id": item["chunk_id"], "text": item["text"],
             "citation": item["citation"]}
            for batch in fallback_retrieval for item in batch[:1]
        ]
        contexts = [item["text"].strip() for item in passages]
    else:
        contexts = supplied
        if contexts != [item["text"] for item in passages]:
            raise ValueError("retrieval and composer evidence differ; inspect before exporting")
    if case.profile != initial:
        raise ValueError("evaluation changed the input profile")
    return {
        "case_id": "nel_age",
        "response": run.agent_response["question"],
        "retrieved_contexts": contexts,
        "context_basis": "controller_passages" if fallback else "composer_grounding_facts",
        "passages": passages,
        "agent_retrievals": retrieved,
        "controller_retrievals": fallback_retrieval,
        "composer_tool_payloads": payloads,
        "composer_grounding_facts": supplied,
        "model_invocations": recorder.invocations,
        "status": "fallback" if fallback else "agent",
        "metadata": run.metadata.model_dump(mode="json"),
        "agent_response": run.agent_response,
        "deterministic_response": run.deterministic_response,
        "input_profile_unchanged": case.profile == initial,
        "profile_matches_controller": (
            run.agent_response.get("profile") == run.deterministic_response.get("profile")
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", required=True, action="store_true",
                        help="Invoke the configured agent provider (incurs charges).")
    parser.add_argument("--output", type=Path,
                        default=Path("/tmp/kindercompass-ragas-nel-age.jsonl"))
    args = parser.parse_args()
    load_dotenv(REPO_ROOT / ".env")
    # Avoid optional external trace export of raw evaluation messages.
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    inputs = Path(__file__).with_name("inputs.jsonl")
    execution_input = next(json.loads(line) for line in inputs.read_text().splitlines()
                           if json.loads(line)["case_id"] == "nel_age")
    schools = SchoolRepository(REPO_ROOT / "SystemCode/data/processed/kindercompass_master.json")
    service = PreferenceService(
        schools, EvaluationService(schools),
        LocationService(schools, REPO_ROOT / "SystemCode/data/raw/PreSchoolsLocation.geojson"),
        REPO_ROOT,
    )
    row = capture(service, execution_input, staged_model_factory())
    index = REPO_ROOT / "SystemCode/src/backend/resources/web_rag/general_knowledge_index.json"
    row["run_settings"] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True,
        ).strip(),
        "git_dirty": bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True,
        ).strip()),
        "evidence_sha256": hashlib.sha256(index.read_bytes()).hexdigest(),
        "requested_model": os.getenv("OPENAI_WEB_RAG_MODEL", "gpt-4o-mini"),
        "timeout_seconds": os.getenv("OPENAI_WEB_RAG_TIMEOUT_SECONDS", "8.0"),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(row, default=str) + "\n")
    print(json.dumps({"case_id": row["case_id"], "status": row["status"],
                      "contexts": len(row["retrieved_contexts"]), "output": str(args.output)}))


if __name__ == "__main__":
    main()
