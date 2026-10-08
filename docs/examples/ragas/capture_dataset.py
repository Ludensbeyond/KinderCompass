"""Capture the frozen starter set offline; raw artifacts stay outside Git."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import platform
import subprocess
from unittest.mock import patch

from capture_one import RecordingModel
from dotenv import load_dotenv
from SystemCode.src.backend.agents.evaluation import ConversationEvaluationCase
from SystemCode.src.backend.agents import tools as agent_tools
from SystemCode.src.backend.scripts.evaluate_conversation_supervisor import (
    REPO_ROOT, staged_model_factory, staged_runner,
)
from SystemCode.src.backend.repositories.school_repository import SchoolRepository
from SystemCode.src.backend.services.evaluation_service import EvaluationService
from SystemCode.src.backend.services.location_service import LocationService
from SystemCode.src.backend.services.preference_service import PreferenceService
from stage1 import conversation
from score import prepare, read_jsonl


def execution_case(item):
    """Allow only execution fields; evaluator expectations never reach the agent."""
    if set(item) != {"case_id", "user_input", "setup"}:
        raise ValueError("execution input must contain only case_id, user_input and setup")
    setup = item["setup"]
    if set(setup) != {"profile", "selected_school_ids", "conversation_history"}:
        raise ValueError("unsupported setup fields")
    if setup["conversation_history"]:
        raise ValueError("starter runner supports independent single turns only")
    return ConversationEvaluationCase(
        case_id=item["case_id"], sequence=1, conversation_id=item["case_id"], turn=1,
        message=item["user_input"], profile=deepcopy(setup["profile"]),
        selected_school_ids=deepcopy(setup["selected_school_ids"]),
        # Required schema placeholders; staged_runner does not consume expectations.
        expected_intent="unused", expected_route_scope="clarification",
    )


def composer_evidence(invocations, observed):
    compositions = [entry for entry in invocations if any(
        message["type"] == "tool" for message in entry["messages"]
    )]
    payloads = [json.loads(message["content"]) for message in (
        compositions[-1]["messages"] if compositions else []
    ) if message["type"] == "tool"]
    facts = [fact for payload in payloads for fact in payload["grounding_facts"]]
    passages = []
    # Preserve all facts in model order, even uncited/irrelevant evidence. Match
    # original text independently of the answer's final citation selection.
    for payload in payloads:
        for fact in payload["grounding_facts"]:
            candidates = [passage for passage in observed if passage["text"] == fact]
            citation_ids = {c.get("citation_id") for c in payload.get("citations", [])}
            candidates = [p for p in candidates if p["chunk_id"] in citation_ids]
            # Repeated searches can observe the same passage more than once.
            candidates = list({json.dumps(p, sort_keys=True): p for p in candidates}.values())
            if len(candidates) != 1:
                raise ValueError("composer evidence cannot be mapped uniquely to observed retrieval")
            passages.append(deepcopy(candidates[0]))
    return payloads, facts, passages


def capture(service, item, model):
    case = execution_case(item)
    initial = deepcopy(case.profile)
    recorder = RecordingModel(model)
    observed, controller = [], []
    original_search = agent_tools.CuratedGeneralKnowledgeRetriever.search
    original_school = agent_tools.retrieve
    original_controller = conversation._answer_general_knowledge

    def search(retriever, question, *, limit=3):
        passages = original_search(retriever, question, limit=limit)
        observed.extend(p.model_dump(mode="json") for p in passages)
        return passages

    def school_search(*args, **kwargs):
        matches = original_school(*args, **kwargs)
        observed.extend(deepcopy(matches))
        return matches

    def controller_answer(text, index, *args, **kwargs):
        answer, citations = original_controller(text, index, *args, **kwargs)
        # This deterministic boundary selects passages by its returned citations,
        # including direct-index comparison branches that bypass retrieval.
        for citation in citations:
            matches = [chunk for chunk in index.get("chunks", [])
                       if chunk["chunk_id"] == citation["chunk_id"]]
            if len(matches) != 1:
                raise ValueError("controller evidence has ambiguous provenance")
            controller.append({"chunk_id": citation["chunk_id"],
                               "text": matches[0]["text"], "citation": deepcopy(citation)})
        return answer, citations

    row = {"case_id": case.case_id, "response": None, "retrieved_contexts": [],
           "status": "execution_error", "started_at": datetime.now(timezone.utc).isoformat()}
    try:
        with patch.object(agent_tools.CuratedGeneralKnowledgeRetriever, "search", search), \
                patch.object(agent_tools, "retrieve", school_search), \
                patch.object(conversation, "_answer_general_knowledge", controller_answer):
            run = staged_runner(service, model_factory=lambda: recorder)(case)
        row.update(response=run.agent_response["question"],
                   agent_response=run.agent_response, deterministic_response=run.deterministic_response,
                   metadata=run.metadata.model_dump(mode="json"))
        fallback = not run.metadata.validation_succeeded
        row["status"] = "fallback" if fallback else "agent"
        payloads, facts, passages = composer_evidence(recorder.invocations, observed)
        row.update(composer_tool_payloads=payloads, composer_grounding_facts=facts)
        if fallback:
            passages = controller
        row.update(passages=passages, retrieved_contexts=[p["text"] for p in passages],
                   context_basis="controller_passages" if fallback else "composer_grounding_facts")
        if not isinstance(row["response"], str) or not row["response"].strip():
            raise ValueError("execution returned an empty answer")
        if case.profile != initial:
            raise ValueError("execution mutated its input profile")
        row["input_profile_unchanged"] = True
        provider_errors = [entry["error_type"] for entry in recorder.invocations if "error_type" in entry]
        if provider_errors or run.metadata.fallback_reason in {
            "model_error", "model_unavailable", "timeout", "tool_error",
        }:
            row["execution_error"] = {"type": "ProviderOrToolFailure",
                                      "reason": run.metadata.fallback_reason,
                                      "model_error_types": provider_errors}
    except Exception as error:
        row["status"] = "execution_error"
        # Never print exception text, which may contain credentials/provider inputs.
        row["execution_error"] = {"type": type(error).__name__}
    row.update(agent_retrievals=observed, controller_passages=controller,
               model_invocations=recorder.invocations,
               finished_at=datetime.now(timezone.utc).isoformat())
    return row


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_dataset(inputs, output, metadata, execute):
    ids = [item["case_id"] for item in inputs]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("execution IDs must be nonempty and unique")
    for item in inputs:
        execution_case(item)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = output.with_suffix(".manifest.json")
    manifest = {**metadata, "started_at": datetime.now(timezone.utc).isoformat(),
                "status": "running", "expected_case_ids": ids, "attempted": 0, "failed": 0,
                "results": []}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    rows = []
    with output.open("w") as stream:
        for item in inputs:
            try:
                row = execute(deepcopy(item))
            except Exception as error:
                row = {"case_id": item["case_id"], "status": "execution_error", "response": None,
                       "retrieved_contexts": [], "execution_error": {"type": type(error).__name__}}
            stream.write(json.dumps(row, default=str) + "\n")
            stream.flush()
            rows.append(row)
            manifest["results"].append({"case_id": row["case_id"], "status": row["status"],
                                        "execution_error": row.get("execution_error")})
            manifest["attempted"] += 1
            manifest["failed"] += int(bool(row.get("execution_error")))
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
            print(json.dumps(manifest["results"][-1]), flush=True)
    manifest.update(status="incomplete" if manifest["failed"] else "complete",
                    finished_at=datetime.now(timezone.utc).isoformat(), capture_sha256=sha256(output),
                    executed=len(rows) - manifest["failed"],
                    agent_count=sum(row["status"] == "agent" for row in rows),
                    fallback_count=sum(row["status"] == "fallback" for row in rows))
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return rows, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", required=True, action="store_true",
                        help="Invoke configured agent provider (incurs charges; no judge).")
    parser.add_argument("--output", type=Path, default=Path("/tmp/kindercompass-ragas-runs.jsonl"))
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(REPO_ROOT):
        parser.error("raw captures must be written outside the repository")
    load_dotenv(REPO_ROOT / ".env")
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    directory = Path(__file__).parent
    frozen = json.loads((directory / "manifest.json").read_text())
    for name, record in frozen["files"].items():
        if sha256(directory / name) != record["sha256"]:
            parser.error(f"frozen dataset hash mismatch: {name}")
    index = REPO_ROOT / frozen["evidence_snapshot"]["path"]
    if sha256(index) != frozen["evidence_snapshot"]["sha256"]:
        parser.error("frozen general evidence snapshot hash mismatch")
    inputs = read_jsonl(directory / "inputs.jsonl")
    if len(inputs) != frozen["case_count"]:
        parser.error("input count differs from frozen manifest")
    dependencies = {}
    for package in ("langchain-core", "langchain-openai", "langgraph", "openai", "pydantic"):
        try:
            dependencies[package] = version(package)
        except PackageNotFoundError:
            dependencies[package] = "not_installed"
    metadata = {
        "dataset_version": frozen["dataset_version"], "dataset_id": frozen["dataset_id"],
        "dataset_files": frozen["files"], "evidence_snapshot": frozen["evidence_snapshot"],
        "git_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip(),
        "git_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True).strip()),
        "collector_sha256": sha256(Path(__file__)),
        "recording_model_sha256": sha256(directory / "capture_one.py"),
        "python": platform.python_version(), "dependencies": dependencies,
        "model_settings": {"model": os.getenv("OPENAI_WEB_RAG_MODEL", "gpt-4o-mini"),
                           "timeout_seconds": os.getenv("OPENAI_WEB_RAG_TIMEOUT_SECONDS", "8.0"),
                           "temperature": "provider_default"},
    }
    snapshot_paths = [
        REPO_ROOT / "SystemCode/data/processed/kindercompass_master.json",
        REPO_ROOT / "SystemCode/data/raw/PreSchoolsLocation.geojson",
        Path(os.getenv("WEB_RAG_INDEX_PATH") or
             str(REPO_ROOT / "SystemCode/src/backend/output/web_rag_pilot_index.json")),
        *sorted((REPO_ROOT / "SystemCode/src/backend/resources/policy").glob("*.json")),
    ]
    metadata["supporting_snapshots"] = [
        {"path": str(path), "sha256": sha256(path) if path.is_file() else None}
        for path in snapshot_paths
    ]

    def execute(item):
        # Fresh service and model prevent caches or mutable state crossing cases.
        schools = SchoolRepository(REPO_ROOT / "SystemCode/data/processed/kindercompass_master.json")
        service = PreferenceService(schools, EvaluationService(schools), LocationService(
            schools, REPO_ROOT / "SystemCode/data/raw/PreSchoolsLocation.geojson"), REPO_ROOT)
        return capture(service, item, staged_model_factory())

    rows, manifest = run_dataset(inputs, output, metadata, execute)
    # References are loaded only AFTER every execution, for format validation.
    cases = read_jsonl(directory / "cases.jsonl")
    successful = [row for row in rows if not row.get("execution_error")]
    subset = [case for case in cases if case["case_id"] in {row["case_id"] for row in successful}]
    prepared, _, behaviour = prepare(subset, successful)
    print(json.dumps({"status": manifest["status"], "attempted": manifest["attempted"],
                      "failed": manifest["failed"], "validated_ragas": len(prepared),
                      "validated_behaviour": len(behaviour), "output": str(output),
                      "manifest": str(output.with_suffix('.manifest.json'))}))
    return 2 if manifest["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
