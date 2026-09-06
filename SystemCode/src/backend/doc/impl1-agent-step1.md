# Implementation 1 archive — selected-school evidence agent

This is the closed historical record for the first LangGraph implementation:
the selected-school webpage-answer vertical slice. The next completed phase is
preserved in [Implementation 2 — full-conversation supervisor](impl2-agent-step2.md),
and active work continues in the [conversational-readiness plan](agents.md).

## Architecture and safety rules

- The browser sends family inputs and stable school IDs to FastAPI. FastAPI and
  backend services reload authoritative school, policy, and evidence data; the
  graph never trusts browser-supplied school records.
- Preserve the existing `POST /api/preferences` wire contract. Agent contracts,
  prompts, evidence records, tool configuration, and provider credentials stay
  behind the backend boundary.
- This graph is limited to selected-school webpage evidence. Ranking,
  eligibility, fees, distance, preference extraction, intent classification,
  and other explanations remain outside it.
- Retrieval is required before generation. Evidence is filtered by the
  authoritative school ID, and every citation resolves to a retrieval result.
- Tool calls and graph iterations are bounded. Timeouts, tool failures,
  malformed model output, and invalid citations return the existing grounded
  deterministic answer.
- Deterministic mode is the default and works without OpenAI credentials or
  eager model-client construction. Tests mock model access and never call a
  live external service.
- Contracts remain independent of FastAPI and LangGraph internals, reject extra
  fields, bound generated text, and validate school and citation identifiers.
- Credentials, prompts, family information, and retrieved private context are
  never logged or returned as execution metadata.

## Recorded baseline

### OpenAI entry points

At baseline, clients were imported and created lazily inside optional
functions. Each capability was disabled unless its environment flag was
truthy, and each fell back to deterministic behavior on failure.

| Capability | Entry point | Configuration | Existing fallback |
|---|---|---|---|
| Preference extraction | `pipeline/stage1/llm_extractor.py::_extract_with_openai` | `OPENAI_PREFERENCE_EXTRACTION_ENABLED`, `OPENAI_PREFERENCE_MODEL`, `OPENAI_PREFERENCE_TIMEOUT_SECONDS` | Rule extraction; records `rules_fallback` and exception type. |
| Intent classification | `pipeline/stage1/intent_router.py::_classify_with_openai` | `OPENAI_INTENT_CLASSIFICATION_ENABLED`, `OPENAI_INTENT_MODEL`, `OPENAI_INTENT_TIMEOUT_SECONDS` | Protected/rule intent or `update_preferences`, marked `rules_fallback`. |
| Deterministic-decision explanations | `pipeline/stage1/grounded_explainer.py::_explain_with_openai` | `OPENAI_GROUNDED_EXPLANATIONS_ENABLED`, `OPENAI_EXPLANATION_MODEL`, `OPENAI_EXPLANATION_TIMEOUT_SECONDS` | Original deterministic explanation with `deterministic_fallback` and exception type. |
| Selected-school webpage synthesis | `pipeline/stage1/grounded_explainer.py::_answer_web_evidence_with_openai` | `OPENAI_WEB_RAG_ANSWERS_ENABLED`, `OPENAI_WEB_RAG_MODEL`, `OPENAI_WEB_RAG_TIMEOUT_SECONDS` | Original cited deterministic answer with `deterministic_fallback` and exception type. |

These entry points instantiated `openai.OpenAI` separately. There was no shared
model factory and no LangGraph invocation.

### Selected-school evidence behavior

1. `POST /api/preferences` accepted stable `selected_school_ids` in the existing
   `PreferenceRequest`; `PreferenceService` reloaded those schools through the
   authoritative repository rather than accepting browser school facts.
2. `PreferenceService._resources` loaded the school evidence index server-side
   from `WEB_RAG_INDEX_PATH` or `output/web_rag_pilot_index.json`. Missing or
   malformed files safely became unavailable evidence.
3. Intent routing selected `ask_selected_school_evidence`. The conversation
   path required exactly one selected school and an authoritative `school_id`.
4. `stage1.web_rag.retrieve` considered only pages whose `school_id` exactly
   matched that ID, then BM25-ranked at most three relevant chunks with URL,
   title, retrieval date, and chunk ID citations.
5. `_answer_web_evidence` extracted a concise deterministic passage and cited
   its retrieved chunk. Empty evidence was described as unavailable, not as a
   negative fact; multiple selections were rejected to prevent mixing.
6. Optional OpenAI synthesis received only retrieved passages and had to return
   at least one citation ID from those passages. Invalid output and failures
   returned the deterministic answer.
7. The conversation result exposed internal `web_answer_method` and
   `web_answer_fallback_reason`, but they were not yet mapped to the existing
   `PreferenceResponse` answer metadata fields. Web evidence did not affect
   ranking.

## Completed checklist

| Step | Status | Completion date | Evidence |
|---|---|---|---|
| 1. Record baseline | complete | 2026-08-23 | `test_web_rag.py`: 53 passed. Conversation collection was blocked by the available Python 3.9 environment and missing `neo4j`; no live services were called. |
| 2. Add dependencies and configuration | complete | 2026-08-23 | `test_agent_config.py`: 4 passed under Python 3.12. Dependency resolution and `pip check` passed with `langgraph==1.2.11`, `langchain-openai==1.6.0`, and `openai<3`. |
| 3. Define agent contracts | complete | 2026-08-23 | `test_agent_contracts.py`: 5 passed under Python 3.12. Contract and mode tests passed in a combined rerun; the environment lacked the declared LangGraph package for the dependency import test. |
| 4. Extract the first tool | complete | 2026-08-27 | `test_agent_tools.py`: 4 passed and `test_web_rag.py`: 53 passed under Python 3.12. |
| 5. Add the shared model factory | complete | 2026-08-27 | `test_agent_model_factory.py`: 5 passed; combined answer-mode and contract tests passed 13 tests; `py_compile` and `git diff --check` passed. |
| 6. Build the bounded LangGraph | complete | 2026-08-27 | `test_agent_graph.py`: 3 passed and all 21 `test_agent*.py` tests passed. The backend suite later stalled in a pre-existing TestClient startup test. |
| 7. Add citation validation and fallback | complete | 2026-08-27 | `test_agent_validation.py`: 5 passed, all 26 `test_agent*.py` tests passed, and all 53 `test_web_rag.py` tests passed. |
| 8. Integrate the vertical slice | complete | 2026-08-27 | `test_agent_integration.py`: 3 passed, all 29 `test_agent*.py`, 53 `test_web_rag.py`, and 76 `test_stage_flow.py` tests passed. |
| 9. Add evaluation and observability | complete | 2026-08-29 | Observability, validation, and integration tests passed 11 tests; all 32 agent tests and all 53 web-RAG tests passed. |
| 10. Rollout decision | complete | 2026-08-29 | No-go: retain `WEB_RAG_ANSWER_MODE=deterministic`. Frontend build and API contract checks passed, but the backend suite stalled and all acceptance agent results used `ModelFactoryError` fallback. |

All scoped tests used injected or deterministic behavior and made no live model
or external-service calls.

## Decision log

- 2026-08-23 — Migrate only the `ask_selected_school_evidence` vertical slice;
  keep ranking and policy decisions deterministic and authoritative.
- 2026-08-23 — Preserve deterministic behavior as the default and universal
  safety fallback.
- 2026-08-23 — Pin `langgraph==1.2.11` and `langchain-openai==1.6.0`; dependency
  resolution selects an OpenAI 2.x release compatible with `openai>=1.66,<3`.
- 2026-08-23 — Parse `WEB_RAG_ANSWER_MODE` in the backend-only `agents` package.
  Missing, empty, and invalid values resolve to `deterministic`.
- 2026-08-23 — Keep the agent boundary framework-independent with strict
  Pydantic contracts and validated school, chunk, and citation identifiers.
- 2026-08-27 — Register `search_selected_school_evidence` as a typed
  `StructuredTool` over the server-supplied evidence index, and discard any
  cross-school result.
- 2026-08-27 — Treat frontend/backend compatibility as a rollout gate and keep
  agent-specific state behind `PreferenceService`.
- 2026-08-27 — Centralize agent model construction in a lazy backend factory;
  deterministic mode neither reads credentials nor constructs a client.
- 2026-08-27 — Bound the first graph to one evidence-search tool call and three
  model iterations, using authoritative rather than model-supplied retrieval
  arguments.
- 2026-08-27 — Accept an agent answer only after graph completion,
  authoritative-school verification, and exact citation resolution. Return the
  deterministic answer on every validation or execution failure.
- 2026-08-27 — Run the graph only after the existing path produces its grounded
  deterministic answer. Agent mode supersedes the legacy selected-school
  OpenAI synthesizer to prevent duplicate model paths.
- 2026-08-29 — Store only privacy-safe evaluation booleans, aggregate rates,
  and allowlisted execution metadata; normalize unknown exceptions.
- 2026-08-29 — Do not enable the selected-school agent. A future rollout needs
  a fully passing backend suite and actual grounded-agent acceptance evidence
  with an acceptable fallback rate.
