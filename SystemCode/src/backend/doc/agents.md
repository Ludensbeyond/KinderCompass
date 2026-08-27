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
| 6. Build the bounded LangGraph | pending | Graph and configuration owner | — | — | Not run. Required: mocked successful sequence and termination-limit tests. |
| 7. Add citation validation and fallback | pending | Validation and safety-test owner | — | — | Not run. Required: malformed output, timeout, tool failure, and invalid-citation fallback tests. |
| 8. Integrate the vertical slice | pending | Graph and configuration owner | — | — | Not run. Required: deterministic, successful-agent, and agent-fallback endpoint tests using the frontend-compatible `PreferenceRequest` and `PreferenceResponse` wire contract. |
| 9. Add evaluation and observability | pending | Evaluation and observability owner | — | — | Not run. Required: reproducible comparison and safe-metadata tests/evaluation. |
| 10. Rollout decision | pending | Architecture and progress owner | — | — | Not run. Required: complete backend suite, frontend production build, API contract verification, and acceptance evaluation. |

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

## Next step

Step 6 — Build the bounded LangGraph around the selected-school evidence tool
and shared model factory. Enforce explicit tool-call and graph-iteration limits,
and add mocked successful-sequence and termination-limit tests. Do not integrate
the graph into `PreferenceService` or the HTTP endpoint yet.
