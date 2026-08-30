# Incremental LangGraph migrations

This document is the persistent source of truth for backend LangGraph
migrations. The selected-school webpage-answer migration is closed and retained
below as historical evidence. The active migration will move every natural-
language turn submitted to `POST /api/preferences` behind a backend conversation
supervisor without changing the frontend or HTTP wire contract.

## Session protocol

Every migration session must read `src/AGENTS.md`, `backend/AGENTS.md`, and this
document. It must complete only the one step named under **Next step**, run that
step's tests, update the active checklist and decision log, replace the single
**Next step** entry, and stop without starting the following step.

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

## Selected-school migration checklist (closed)

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

## Full-conversation migration

### Goal and scope

Every natural-language message submitted to `POST /api/preferences` will enter
a backend conversation supervisor when shadow or agent mode is enabled. The
supervisor decides which registered capability tools to call and what grounded
answer to return. It orchestrates only: deterministic backend code remains
authoritative for preference state, ranking, eligibility, fees, distance,
school facts, and citations.

No frontend change is permitted. The browser continues to call `/api/search`,
`/api/evaluate`, map, route, memory, and feedback endpoints through the existing
UI flow. In particular, the supervisor cannot initiate a browser search or UI
transition through the current `PreferenceResponse`; `ready_to_search` remains
the existing signal that lets the user proceed with Show recommendations.

### Architecture and safety additions

- Preserve the exact `PreferenceRequest`, `PreferenceResponse`, and OpenAPI
  shapes. Agent prompts, tool arguments, execution state, retrieved passages,
  and provider configuration remain backend-only.
- Add a backend-only `CONVERSATION_AGENT_MODE` with `deterministic`, `shadow`,
  and `agent` values. Missing, empty, or invalid configuration resolves to
  `deterministic`. Model clients remain lazy and unavailable in deterministic
  mode.
- In shadow mode, the existing deterministic result is the only served result.
  The agent runs without request-time writes, and comparison telemetry cannot
  contain conversation text, family data, prompts, evidence text, credentials,
  or provider error messages.
- All tool context comes from the validated request and authoritative backend
  repositories. Model-supplied school records, IDs, family values, policy
  values, rankings, prices, distances, citations, or tool configuration are
  rejected or replaced by server-owned context.
- Every turn must execute at least one registered capability tool before an
  agent answer can be accepted. A turn may make at most three tool calls, at
  most one of which may mutate preference state, and graph iterations remain
  independently bounded.
- Tools return an authoritative profile/state result, a deterministic answer
  candidate, grounding facts, and allowed citations. The model may select
  tools, compose bounded wording from those results, and select citation IDs;
  it may not generate or override profile state, calculations, action fields,
  evidence provenance, or other authoritative output.
- Multiple read-only tools are allowed only when the request genuinely needs
  more than one evidence scope, such as combined selected-school and general
  guidance. Existing mixed-message behavior continues to prioritize the
  requested immediate action rather than silently applying multiple state
  changes.
- Unknown tools, invalid arguments, missing required context, conflicting tool
  results, multiple mutations, malformed output, unsupported citations,
  timeouts, and execution-limit termination fail closed to the current
  deterministic conversation controller.
- The fallback path must disable conversation and selected-school agent
  re-entry so one request cannot recurse or invoke duplicate model paths.
  Memory persistence and answer-feedback recording remain outside the graph and
  occur once, after the served result is selected.
- Tests use injected models and tools and never call live providers. A rollout
  decision requires separate staged evidence from actual grounded agent
  executions in addition to deterministic automated tests.

### Capability coverage

The migration is incomplete until the supervisor covers all current
`IntentName` values and the state transitions that precede intent handling:

| Capability group | Required behavior |
|---|---|
| Preference state | Update and reset preferences; resolve pending language or pedagogy priority, contradictions, and proposed constraint relaxations; request clarification when needed. |
| Recommendation decisions | Find the closest preschool; explain the top-ranked result; compare selections; explain trade-offs and provenance; recommend or assess selected preschools. |
| Calculated scenarios | Run fee or eligibility what-if scenarios and explain Stage 2 exclusions using authoritative family, school, and policy inputs. |
| Evidence answers | Retrieve selected-school webpage evidence, curated general guidance, or both while preserving school/general evidence scopes and resolvable citations. |
| Missing context | Return the existing actionable guidance when a school selection, eligible result set, excluded result set, family details, postal code, or evidence index is unavailable. |

### Full-conversation migration checklist

| Step | Status | Owner | Completion date | Files changed | Tests run |
|---|---|---|---|---|---|
| 1. Record the full-conversation baseline | pending | Architecture and progress owner | — | — | — |
| 2. Define supervisor configuration, contracts, and authoritative context | pending | Graph and configuration owner | — | — | — |
| 3. Extract preference-state tools | pending | Conversation-state tool owner | — | — | — |
| 4. Extract decision and calculation tools | pending | Decision-tool owner | — | — | — |
| 5. Complete the evidence toolset | pending | Evidence-tool owner | — | — | — |
| 6. Build the bounded conversation supervisor | pending | Graph and configuration owner | — | — | — |
| 7. Add result validation and legacy fallback | pending | Validation and safety-test owner | — | — | — |
| 8. Integrate deterministic, shadow, and agent modes | pending | Service integration owner | — | — | — |
| 9. Add full-conversation evaluation and observability | pending | Evaluation and observability owner | — | — | — |
| 10. Run compatibility gates and decide rollout | pending | Architecture and progress owner | — | — | — |

### Step definitions

#### Step 1 — Record the full-conversation baseline

- Inventory every current intent and every pre-intent state transition in
  `PreferenceService` and the Stage 1 conversation controller. Record the
  authoritative inputs, output fields, missing-context response, side effects,
  and existing test coverage for each capability in the table above.
- Snapshot the `POST /api/preferences` OpenAPI request and response references
  and all currently required fields so later steps can prove compatibility.
- Run the complete backend suite and frontend production build without changing
  executable code. Investigate and record the known TestClient startup stall;
  do not treat a partial run as a passing baseline.

#### Step 2 — Define supervisor configuration, contracts, and context

- Add strict framework-independent contracts for a server-built conversation
  request context, capability-tool result, generated answer, public citations,
  execution limits, and privacy-safe metadata. Extra fields are forbidden and
  all text and collections are bounded.
- Add `CONVERSATION_AGENT_MODE=deterministic|shadow|agent`, defaulting safely to
  `deterministic`, and reuse the lazy shared model factory without constructing
  a client in deterministic mode.
- Build one authoritative context in `PreferenceService` from the request's
  stable IDs, repository data, evaluated schools, family details, postal-code
  distances, current profile, and server-loaded evidence indexes. No agent
  contract is added to the HTTP models.

#### Step 3 — Extract preference-state tools

- Register typed tools for updating preferences, resetting preferences, and
  continuing pending clarification, contradiction, and relaxation flows.
- Refactor existing deterministic functions rather than duplicating their
  rules. Each tool operates on a copy and returns the complete proposed profile
  plus its deterministic answer candidate; it performs no persistence.
- Mark these tools as state-mutating so graph validation can enforce the
  one-mutation-per-turn rule and preserve existing mixed-message precedence.

#### Step 4 — Extract decision and calculation tools

- Register typed read-only tools for closest-school lookup, top-ranking
  explanation, selected-school comparison, trade-offs, provenance,
  recommendation, suitability, what-if scenarios, and exclusion explanations.
- Inject selected, eligible, and excluded schools plus family and distance
  context server-side. Tools must delegate to existing ranking, evaluation,
  policy, and location logic and return deterministic answer candidates.
- Cover missing selections, family details, postal codes, eligible results, and
  excluded results with the current actionable responses rather than allowing
  the model to infer absent facts.

#### Step 5 — Complete the evidence toolset

- Reuse `search_selected_school_evidence` and add a typed curated-general-
  knowledge retrieval tool. Both accept the user's bounded question but use
  server-owned indexes and authoritative school scope.
- Support combined evidence by calling both read-only tools. Preserve school
  and general citation metadata, reject cross-school evidence, and distinguish
  unavailable information from negative evidence.
- Retain deterministic answer candidates for selected, general, and combined
  evidence so validation or model failure always has a grounded fallback.

#### Step 6 — Build the bounded conversation supervisor

- Compile a supervisor graph that receives the authoritative context, requires
  a registered capability tool, and lets the model choose the next applicable
  tool based on the newest message and bounded profile context.
- Enforce three total tool calls, one state mutation, and a separately bounded
  model-iteration count. Ignore or reject model arguments that conflict with
  authoritative context.
- After tool execution, require structured output containing only bounded
  answer wording and citation IDs. Assemble all other response fields from the
  accepted tool result.

#### Step 7 — Add result validation and legacy fallback

- Validate tool identity, call counts, mutation counts, profile invariants,
  authoritative result consistency, answer bounds, and exact citation
  resolution before accepting an agent result.
- Reduce failures to a fixed non-sensitive reason vocabulary. On every failure,
  invoke the existing controller once with both agent entry points disabled and
  return its complete deterministic result.
- Test malformed output, unknown tools, forged IDs or facts, cross-school and
  mixed-scope citations, multiple mutations, tool/model exceptions, timeouts,
  and both execution limits.

#### Step 8 — Integrate deterministic, shadow, and agent modes

- Make `PreferenceService.handle` the single mode dispatcher for every
  `/api/preferences` message. Deterministic mode retains the existing path;
  shadow mode serves that exact result while evaluating the agent without
  writes; agent mode serves only a validated graph result or legacy fallback.
- Ensure the existing selected-school answer mode cannot cause nested graph or
  duplicate model execution. Keep conversation memory and answer-feedback
  writes after served-result selection.
- Validate results through the unchanged `PreferenceResponse` and add endpoint-
  level tests proving identical frontend-visible shapes in every mode.

#### Step 9 — Add evaluation and observability

- Create an ordered, curated evaluation set covering every intent, combined
  evidence, missing context, ambiguous requests, and multi-turn pending,
  contradiction, relaxation, and reset transitions.
- Compare deterministic and agent tool choice, profile/state output, grounding,
  citations, and response usefulness. Tests use injected models; a documented
  staged command is reserved for real grounded executions.
- Emit only allowlisted aggregate and per-case booleans, tool names, bounded
  counts, latency, termination reason, validation outcome, and normalized
  fallback reason. Do not emit request or response content or private context.

#### Step 10 — Run compatibility gates and decide rollout

- Require a complete backend suite, frontend production build, unchanged
  OpenAPI request/response schemas, and confirmation that no frontend files or
  frontend agent contracts changed.
- Require staged results with 100% structural and citation validity, zero
  authoritative profile/calculation discrepancies, at least 95% accepted tool
  selection, and at most 5% agent fallback across the curated suite.
- Record a go/no-go decision. Keep `CONVERSATION_AGENT_MODE=deterministic` on
  any failed or unevaluated gate; if every gate passes, make agent mode an
  explicit backend opt-in rather than the default.

### Full-conversation decisions

- 2026-08-29 — Define “all conversation” as every natural-language turn sent
  to `POST /api/preferences`. Preserve the browser-controlled search,
  evaluation, map, route, memory, and feedback flows because changing those
  flows would require a new frontend contract.
- 2026-08-29 — Use the model as a bounded supervisor and response composer,
  not as an authority for profile state, ranking, eligibility, fees, distance,
  school facts, or evidence provenance.
- 2026-08-29 — Preserve the current deterministic conversation controller as
  the universal fallback and introduce the supervisor through deterministic,
  shadow, and explicit opt-in agent modes.
- 2026-08-29 — Split the migration into ten independently testable steps and
  retain the one-step-per-session gate.

## Next step

Step 1 — Record the full-conversation baseline. Do not begin Step 2 in the same
session.
