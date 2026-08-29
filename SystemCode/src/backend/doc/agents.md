# Incremental LangGraph migration

This document is the persistent source of truth for migrating selected-school
webpage answers to LangGraph. It records the architecture boundary, safety
rules, baseline, decisions, test evidence, and the only step a future session
may start.

## Session protocol

Every migration session must read the repository `AGENTS.md`,
`backend/AGENTS.md`, and this document. It must complete only the one step named
under **Next step**, run that step's tests, update the checklist and decision
log, replace the single **Next step** entry, and stop without starting the
following step.

Checklist statuses are `pending`, `in progress`, and `complete`. A step is not
complete until its scoped tests and evidence are recorded here. Generated
outputs are not edited by hand.

## Architecture and safety rules

- The browser sends family inputs and stable school IDs to FastAPI. FastAPI and
  backend services reload authoritative school, policy, and evidence data; the
  graph never trusts browser-supplied school records.
- Preserve the existing `POST /api/preferences` wire contract throughout the
  migration. The agent remains a backend implementation detail: the frontend
  must not import agent contracts or send prompts, evidence records, tool
  configuration, or provider credentials. Agent results map back to the
  existing `PreferenceResponse` fields, including its optional answer metadata.
- The first graph is limited to selected-school webpage evidence. Ranking,
  eligibility, fees, distance, preference extraction, intent classification,
  and other explanations remain outside it.
- LangGraph may orchestrate explicitly registered tools, but it may not control
  authoritative ranking or policy calculations. The first graph may call only
  the selected-school evidence-search tool.
- Retrieval is required before generation. Evidence must be filtered by the
  authoritative school ID before it reaches a model, and every returned
  citation must resolve to that retrieval result.
- Tool calls and graph iterations are bounded. Timeouts, tool failures,
  malformed model output, and invalid citations return the existing grounded
  deterministic answer.
- Deterministic mode is the default and must work without OpenAI credentials or
  eager model-client construction. Tests must mock model access and never call
  a live external service.
- Contracts stay independent of FastAPI and LangGraph internals, reject extra
  fields, bound generated text, and validate school and citation identifiers.
- Credentials, prompts, family information, and retrieved private context are
  never logged or returned as execution metadata. OpenAI and other provider
  access remains backend-only.
- New tools require a typed contract, an authoritative-data boundary,
  deterministic tests, defined failure behavior, and their own checklist step.

## Recorded baseline

### Current OpenAI entry points

All clients are imported and created lazily inside optional functions. Each
capability is disabled unless its own environment flag is truthy, and each
falls back to deterministic behavior on failure.

| Capability | Entry point | Configuration | Existing fallback |
|---|---|---|---|
| Preference extraction | `pipeline/stage1/llm_extractor.py::_extract_with_openai` | `OPENAI_PREFERENCE_EXTRACTION_ENABLED`, `OPENAI_PREFERENCE_MODEL`, `OPENAI_PREFERENCE_TIMEOUT_SECONDS` | Rule extraction; records `rules_fallback` and exception type. |
| Intent classification | `pipeline/stage1/intent_router.py::_classify_with_openai` | `OPENAI_INTENT_CLASSIFICATION_ENABLED`, `OPENAI_INTENT_MODEL`, `OPENAI_INTENT_TIMEOUT_SECONDS` | Protected/rule intent or `update_preferences`, marked `rules_fallback`. |
| Deterministic-decision explanations | `pipeline/stage1/grounded_explainer.py::_explain_with_openai` | `OPENAI_GROUNDED_EXPLANATIONS_ENABLED`, `OPENAI_EXPLANATION_MODEL`, `OPENAI_EXPLANATION_TIMEOUT_SECONDS` | Original deterministic explanation with `deterministic_fallback` and exception type. |
| Selected-school webpage synthesis | `pipeline/stage1/grounded_explainer.py::_answer_web_evidence_with_openai` | `OPENAI_WEB_RAG_ANSWERS_ENABLED`, `OPENAI_WEB_RAG_MODEL`, `OPENAI_WEB_RAG_TIMEOUT_SECONDS` | Original cited deterministic answer with `deterministic_fallback` and exception type. |

These entry points currently instantiate `openai.OpenAI` separately. There is
no shared model factory and no LangGraph invocation at baseline.

### Current selected-school evidence behavior

1. `POST /api/preferences` accepts stable `selected_school_ids` in the existing
   `PreferenceRequest`; `PreferenceService` reloads those schools through the
   authoritative repository rather than accepting browser school facts.
2. `PreferenceService._resources` loads the school evidence index server-side
   from `WEB_RAG_INDEX_PATH` or `output/web_rag_pilot_index.json`. Missing or
   malformed files safely become unavailable evidence.
3. Intent routing selects `ask_selected_school_evidence`. The conversation path
   requires exactly one selected school and an authoritative `school_id`.
4. `stage1.web_rag.retrieve` considers only pages whose `school_id` exactly
   matches that ID, then BM25-ranks at most three relevant chunks and attaches
   URL, title, retrieval date, and chunk ID citations. Operator and general
   evidence use separate retrieval functions and are not included here.
5. `_answer_web_evidence` extracts a concise deterministic passage and cites
   its retrieved chunk. Empty evidence is described as unavailable, explicitly
   not as a negative fact; multiple selections are rejected to prevent mixing.
6. Optional OpenAI synthesis receives only retrieved passages. It must return
   at least one citation ID from those passages. Rejected evidence, missing or
   invented citations, parse errors, timeouts, and other exceptions return the
   deterministic answer.
7. The conversation result exposes internal `web_answer_method` and
   `web_answer_fallback_reason`. They are consumed by evaluation and feedback
   code, but are not currently mapped to the existing
   `PreferenceResponse.answer_method` and `PreferenceResponse.fallback_reason`
   fields. Web evidence never affects ranking.

## Migration checklist

| Step | Status | Owner | Completion date | Files changed | Tests run |
|---|---|---|---|---|---|
| 1. Record baseline | complete | Architecture and progress owner | 2026-08-23 | `backend/AGENTS.md`; `backend/doc/README.md`; `backend/doc/agents.md` | `test_web_rag.py`: 53 passed. Conversation collection was also attempted but is blocked in the available Python 3.9 environment: the project uses Python 3.10+ union annotations, and `neo4j` is absent. No live services were called. |
| 2. Add dependencies and configuration | complete | Graph and configuration owner | 2026-08-23 | `backend/requirements.txt`; `backend/agents/__init__.py`; `backend/agents/config.py`; `backend/tests/test_agent_config.py`; `backend/README.md`; `backend/doc/README.md`; `backend/doc/agents.md` | `test_agent_config.py`: 4 passed under Python 3.12. Dependency resolution and `pip check` passed with `langgraph==1.2.11`, `langchain-openai==1.6.0`, and the existing `openai<3` constraint. No graph or live service was invoked. |
| 3. Define agent contracts | complete | Graph and configuration owner | 2026-08-23 | `backend/agents/contracts.py`; `backend/agents/__init__.py`; `backend/tests/test_agent_contracts.py`; `backend/doc/agents.md` | `test_agent_contracts.py`: 5 passed under Python 3.12. A combined rerun with `test_agent_config.py` was also attempted: all contract and mode tests passed, while the pre-existing dependency import test could not collect `langgraph` because the current virtual environment does not have that declared package installed. No live services were called. |
| 4. Extract the first tool | complete | Retrieval-tool owner | 2026-08-27 | `backend/agents/tools.py`; `backend/agents/__init__.py`; `backend/tests/test_agent_tools.py`; `backend/doc/agents.md` | `test_agent_tools.py`: 4 passed under Python 3.12, covering valid typed evidence, missing school, empty evidence, and cross-school isolation. `test_web_rag.py`: 53 passed. No graph or live service was invoked. |
| 5. Add the shared model factory | complete | Graph and configuration owner | 2026-08-27 | `backend/agents/model_factory.py`; `backend/agents/__init__.py`; `backend/tests/test_agent_model_factory.py`; `backend/README.md`; `backend/doc/agents.md` | `test_agent_model_factory.py`: 5 passed under Python 3.12, covering deterministic lazy behavior, explicit/default configuration, bounded timeouts, missing credentials, and secret-safe initialization errors. A combined run with answer-mode and contract tests passed 13 tests. `py_compile` and `git diff --check` passed. No client or live service was invoked. The dependency import test remains unavailable because the current virtual environment lacks the already-declared LangGraph/LangChain packages. |
| 6. Build the bounded LangGraph | complete | Graph and configuration owner | 2026-08-27 | `backend/agents/graph.py`; `backend/agents/__init__.py`; `backend/tests/test_agent_graph.py`; `backend/doc/agents.md` | `test_agent_graph.py`: 3 passed under Python 3.12, covering the mocked retrieval-to-answer sequence, the one-call tool limit, and the graph-iteration limit. All 21 `test_agent*.py` tests passed; `py_compile` and `git diff --check` passed. The complete backend suite was also attempted and passed through all agent tests, then stalled in the pre-existing `test_nearest_chat_uses_postal_code_and_full_grounded_catalogue` startup test until interrupted. No live model or external service was called by the scoped tests. |
| 7. Add citation validation and fallback | complete | Validation and safety-test owner | 2026-08-27 | `backend/agents/graph.py`; `backend/agents/__init__.py`; `backend/tests/test_agent_validation.py`; `backend/doc/agents.md` | `test_agent_validation.py`: 5 passed under Python 3.12, covering malformed output, model timeout, tool failure, invalid-citation fallback, and a valid grounded answer. All 26 `test_agent*.py` tests and all 53 `test_web_rag.py` tests passed; `py_compile` and `git diff --check` passed. No live model or external service was called. |
| 8. Integrate the vertical slice | complete | Graph and configuration owner | 2026-08-27 | `backend/services/preference_service.py`; `backend/pipeline/stage1/grounded_explainer.py`; `backend/tests/test_agent_integration.py`; `backend/README.md`; `backend/doc/agents.md` | `test_agent_integration.py`: 3 passed under Python 3.12, covering deterministic, successful-agent, and agent-fallback behavior through the FastAPI endpoint handler with `PreferenceRequest` and `PreferenceResponse` validation. All 29 `test_agent*.py`, all 53 `test_web_rag.py`, and all 76 `test_stage_flow.py` tests passed. `py_compile` and `git diff --check` passed. Starlette's deprecated `TestClient` transport was not used because it reproduces the pre-existing request-startup stall in this environment. No live model or external service was called. |
| 9. Add evaluation and observability | complete | Evaluation and observability owner | 2026-08-29 | `backend/agents/graph.py`; `backend/scripts/evaluate_selected_school_agent.py`; `backend/tests/test_agent_observability.py`; `backend/README.md`; `backend/doc/agents.md` | `test_agent_observability.py`, `test_agent_validation.py`, and `test_agent_integration.py`: 11 passed. All 32 `test_agent*.py` tests and all 53 `test_web_rag.py` tests passed under Python 3.12. `py_compile` and `git diff --check` passed. Evaluation uses injected models in tests; no live model or external service was called. |
| 10. Rollout decision | complete | Architecture and progress owner | 2026-08-29 | `backend/doc/agents.md` | No-go: keep `WEB_RAG_ANSWER_MODE=deterministic`. The complete backend suite passed 33 tests, including all 32 agent tests, before the pre-existing `test_nearest_chat_uses_postal_code_and_full_grounded_catalogue` TestClient request stalled and the run was interrupted. The frontend production build passed. The `POST /api/preferences` OpenAPI request/response references and required existing request/response fields were verified. The four-case acceptance evaluation reported deterministic and agent pass rates of 1.0 with no regressions, but every agent result was a `ModelFactoryError` deterministic fallback (fallback rate 1.0, zero tool calls and graph iterations), so it supplied no evidence for enabling agent mode. The documented evaluation command also initially failed to import `SystemCode`; the evaluation ran after adding the repository root to `PYTHONPATH`. No live model or external service was called. |

## Decision log

- 2026-08-23 — Migrate one vertical slice only:
  `ask_selected_school_evidence`. Existing ranking and policy decisions remain
  deterministic and authoritative.
- 2026-08-23 — Preserve deterministic behavior as the default and universal
  safety fallback throughout the migration.
- 2026-08-23 — Use this file as the cross-session gate: exactly one checklist
  step may be completed per session.
- 2026-08-23 — Record the baseline retrieval suite as 53 passing tests. Do not
  treat the unavailable conversation-suite collection as a product failure;
  rerun it under the project's supported Python/dependency environment during
  the first step that changes executable code.
- 2026-08-23 — Pin `langgraph==1.2.11` and `langchain-openai==1.6.0`; dependency
  resolution selects an OpenAI 2.x release compatible with the existing
  `openai>=1.66,<3` constraint.
- 2026-08-23 — Parse `WEB_RAG_ANSWER_MODE` in the backend-only `agents`
  package. Missing, empty, and invalid values resolve to `deterministic`;
  `agent` is recognized but does not invoke a graph in this step.
- 2026-08-23 — Keep the selected-school agent boundary framework-independent
  with strict Pydantic contracts. School, chunk, and citation identifiers use
  the existing colon-delimited identifier format; retrieved evidence must
  match its citation's school and chunk IDs; generated answers have bounded,
  unique citation IDs consistent with whether evidence is available.
- 2026-08-27 — Register `search_selected_school_evidence` as a typed
  `StructuredTool` over the server-supplied evidence index. It delegates to
  the existing school-isolated retriever, returns `RetrievedEvidence`, and
  defensively discards any match whose school ID differs from the authoritative
  request instead of relabelling it.
- 2026-08-27 — Treat frontend/backend compatibility as a rollout gate. Keep
  agent-specific state behind `PreferenceService`, preserve the existing HTTP
  request and response models, exercise deterministic/success/fallback paths
  through FastAPI, and require a successful frontend production build before
  rollout.
- 2026-08-27 — Centralize future agent model construction in a lazy backend
  factory. Deterministic mode returns without reading credentials, importing a
  provider, or constructing a client. Agent mode reuses the selected-school
  model settings, enforces a 1–30 second timeout, and reduces configuration,
  dependency, credential, and initialization failures to stable typed errors
  whose messages do not include provider details or secrets.
- 2026-08-27 — Compile the first graph with one registered evidence-search
  tool, a default one-call tool budget, and a three-iteration model budget.
  Ignore model-supplied retrieval arguments in favor of the authoritative
  request, retain the retrieval transcript for generation, and accept no
  generated answer before the tool has run. Limit termination returns graph
  state without an answer so the next step can apply the deterministic
  fallback consistently.
- 2026-08-27 — Put a single validation boundary around graph construction and
  invocation. Accept an agent answer only after successful graph completion,
  authoritative-school verification, and exact resolution of every citation
  ID to retrieved evidence. Malformed output, timeouts, tool errors, rejected
  retrieved evidence, invalid citations, and execution-limit termination all
  return the caller-supplied deterministic answer and citations. Expose only
  the exception class as the fallback reason so provider messages, prompts,
  and retrieved context cannot escape as metadata.
- 2026-08-27 — Integrate the graph only after the existing conversation path
  has produced its grounded deterministic answer. `PreferenceService` supplies
  the authoritative rebuilt school and server-loaded evidence index, maps the
  internal answer metadata to the existing `PreferenceResponse` fields, and
  preserves that answer and its citations on every agent failure. Agent mode
  supersedes the legacy selected-school OpenAI synthesizer so a request cannot
  invoke two model paths.
- 2026-08-29 — Compare deterministic and agent answers over the same ordered,
  curated selected-school cases. Store only per-case quality booleans, aggregate
  rates, and a fixed execution-metadata allowlist; omit questions, answers,
  prompts, school and family context, credentials, and retrieved evidence text.
  Normalize unknown exception classes to `AgentExecutionError` so provider
  implementation details cannot escape through fallback observability.
- 2026-08-29 — Do not enable the selected-school agent in rollout. Keep
  `WEB_RAG_ANSWER_MODE=deterministic` because the full backend gate did not
  complete and the acceptance run exercised only deterministic fallback, with
  a 1.0 fallback rate caused by `ModelFactoryError`. The frontend build and API
  contract checks passed, and deterministic behavior passed all four acceptance
  cases. A future rollout proposal requires a fully passing backend suite and
  acceptance evidence from actual grounded agent executions with an acceptable
  fallback rate.

## Next step

None — this migration sequence is closed with agent rollout declined and
deterministic mode retained. Define and approve a new checklist before doing
further LangGraph migration or reconsidering rollout.
