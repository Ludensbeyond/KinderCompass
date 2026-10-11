# LLM-first Step 1 — baseline and target architecture

Recorded 2026-10-10 against HEAD `d2b018e753b0b5a29bfc8041886f7538e17152d7`
and the inspected working tree. This is an architecture/evaluation baseline;
no request behavior, domain algorithm, public schema, frontend, persistence,
provider configuration or rollout mode changes in this step.

## Reviewed existing behavior map

Paths below are relative to the backend. Reviewed against the implementation,
its contracts, folder guides and existing conversation regression cases.

| Entry or dependency | Current behavior and authority | Target phase owner |
|---|---|---|
| `main.py:preferences`, `POST /api/preferences` | Sole public chat endpoint. Before service dispatch, a `closest` substring without a postal code returns 422. Remember-session requirement is checked after service execution. HTTP errors map repository/domain failures to 404/422. | Steps 4/6: valid messages must reach model before semantic guards; validate request/session/access first. |
| `services/preference_service.py:handle` | Internal service chat entry: standalone greeting/help regex returns fixed text before routing, context, mode or model. Other turns call `classify_intent` first. | Steps 4/6: model controls normal conversational output. |
| `pipeline/stage1/intent_router.py:_rules`, `classify_intent` | Keyword operations, topics and active school name select a single intent. Optional OpenAI intent classification (default enabled) handles only remaining cases; low confidence clarifies, failures use rules. | Step 4: remove semantic route authority from new path. |
| `PreferenceService.build_conversation_context`, `_rebuild`, `_conversation_tools` | Resolves selected/eligible/excluded IDs and active identity via repository; ranks/evaluates and attaches OneMap distances before reasoning. Nearest intent can load full catalogue. Loads evidence indexes and candidate facets. | Step 2 initially bounds context; expensive work moves behind replacement tools as they land in Steps 3/4. |
| `agents/supervisor.py:_authoritative_route`, `_tools_for_intent`, `_allowed_tool_names` | Server intent selects scope without a routing model call; keywords further select structured versus webpage facts. Model sees filtered tools and must call a tool; clarification can terminate before model. | Step 4: permitted capabilities, zero-tool turns, dependent calls. |
| `agents/supervisor.py:_authoritative_arguments` | Discards model preference/scenario args; replaces evidence query with whole original message; structured facts allow operation/IDs. | Step 3: typed patches, focused queries and scenario overrides. |
| `agents/tools.py:create_preference_state_tools` | Update/reset/continue reuse `update_conversation` and optional nested extraction. Each call starts from a fresh context copy; returns full profile and answer candidate. Later calls cannot read previous tool's updated profile. | Step 3: validated request-local staging and read-your-writes. |
| `agents/tools.py:create_decision_and_calculation_tools` | Nine fixed recommendation/assessment/closest/comparison/provenance/trade-off/scenario/exclusion tools reuse controller, evaluation and calculation services. Inputs mostly original message/context; results include prose. | Step 3: structured outputs while retaining underlying algorithms. |
| Structured school and evidence tools in `agents/tools.py` | Allowlisted fields/IDs, repository facts, isolated school passages, general retrieval (curated or configured parent-guide adapter), citations and explicit missing evidence wording. Retrieval is grounded but wrappers compose answers. Parent-guide vector retrieval can call embedding provider. | Steps 3/5: structured data/provenance, model composes prose. |
| `agents/supervisor.py:_authoritative_composition`, `_tool_candidate_answer`, `grounded_answer_is_valid` | Vocabulary membership gates generated wording; selected-school evidence always uses candidates verbatim. Invalid/parsing output uses candidates, clips to 800 chars and replaces citation selection with tool citations. Prompt encourages verbatim copying. | Step 5: value/entity/citation checks and bounded repair. |
| `agents/validation.py:run_conversation_supervisor`, `PreferenceService.handle` exception paths | Validates state, calls, profile invariants, grounding and citations. Rejection/unavailability invokes deterministic controller once with both graph entries disabled. Outer registry/run errors also fallback. | Step 5: explicit service failure with discarded stage; rollback stays separate. |
| `PreferenceService._handle_deterministic`, `pipeline/stage1/conversation.py:update_conversation` | Legacy internal chat entry handles pending importance/queue, contradictions, relaxation, reset, recommendation and evidence via rules and fixed questions. Used by deterministic, shadow served response and rejected agent requests. | Preserve explicit rollback; replace new-flow conversational wrappers only. |
| `PreferenceService._apply_selected_school_answer_mode`, `agents/graph.py` | Optional selected-school graph replaces legacy evidence answer. Disabled in full supervisor shadow/fallback to prevent recursive graph entry. | Keep isolated during migration; cleanup only Step 7. |
| `scripts/evaluate_conversation_supervisor.py:staged_runner` | Offline chat entry bypasses `handle` and HTTP greeting/closest guards; preclassifies intent, builds context, runs deterministic comparator and supervisor. Existing evaluator measures 54 intent/tool/state cases, not all public entry points. | Step 6: evaluate actual new-flow HTTP/service entry and conversational tasks. |
| `pipeline/stage1/runner.py:run_from_text`, `pipeline/pipeline.py:search_and_evaluate`, `/api/search` | Text-to-profile/recommendation operations, not conversational reply entry points; optional extraction, query/ranking, evaluation and generated aggregate traces. | Preserve non-chat contracts/algorithms. |

## Nested model and execution inventory

Beyond supervisor routing/tool selection/composition, optional models occur in
`stage1/llm_extractor.py` (default extraction disabled),
`stage1/grounded_explainer.py` (decision/comparison explanations default disabled;
web answers default enabled outside selected-school agent mode), and
`stage1/intent_router.py` (classification default enabled). Legacy controller
calls these helpers; preference/decision tools reuse that controller. Selected
school graph uses its own model. Parent-guide vector retrieval embeds queries
when configured. Disabling graph entry points does not itself disable every
optional OpenAI helper. The capture explicitly disables optional generation
and uses unavailable evidence plus an injected supervisor model.

Supervisor default limits are three capability calls, one profile mutation,
six graph iterations (configured maximum eight). A tool round is followed by
answer composition rather than a general dependent capability loop. Provider
timeouts bound individual model calls; current counters do not establish the
new phase's total elapsed/context/token/cost budgets.

## State writes and contracts

- Tools use fresh deep copies, not persistent writes. Result assembly selects
  the last mutating result (otherwise last result). `enrich_decision_state`
  modifies returned profile/active context and readiness from server results.
- HTTP returns the new profile for client state. With `remember_preferences`,
  `main.py` saves once to `ConversationMemoryService`; it then records one
  answer for chat feedback. Shadow serves deterministic state only.
- Memory is SQLite upsert by anonymous UUID, allowlisted profile only, 32 KB
  maximum, default 180-day retention; restore prunes expired rows, forget
  deletes one session. No transcript, family or raw chat persistence and no
  session-version conflict check. `/api/memory/save`, `/restore`, `/forget`
  are non-chat operations. Feedback writes do not constitute dialogue history.
- `domain/models.py:PreferenceRequest` accepts message (2–500 characters),
  profile, school ID lists, family, postal code, optional anonymous UUID and
  opt-in memory. `PreferenceResponse` retains profile, understood, readiness,
  question, citations, method/fallback/category and answer ID. Internal
  `ConversationRequestContext` contains full facts and deterministic intent,
  but no transcript/session version. Snapshot hash appears in capture artifact.
- School repository reloads names, programmes, fees and other facts by ID.
  Ranking, Stage 2 age/programme eligibility and dated subsidy/cost rules,
  Stage 3 distance calculations and scoped evidence remain authoritative.

## Target contract decision for this phase

The repository [plan](../../../../docs/llm-first-conversation-plan.md) owns the
seven-step acceptance sequence. For valid chat: request/session/access validation
→ bounded dialogue and minimal application context → LLM/tool loop → structured
results → model answer/clarification → factual/citation/state validation and
bounded repair → one commit. Failures discard staged state and return a fixed
service error, never a domain answer fabricated by fallback.

Typed model inputs represent user choices, queries or hypothetical inputs.
They never replace school facts or arbitrary profiles. Tools return status
(`ok`, `needs_input`, `no_evidence`, `unavailable`), structured data, result IDs,
provenance/citation IDs and validated state deltas. Later tools read staged
updates; scenarios leave saved family inputs unchanged. Context and all loop
resources must be bounded. Dialogue/summary is untrusted context, not evidence.

No history strategy or public/frontend change is approved by Step 1. Step 2
must decide anonymous-session reuse versus minimal extension, stateless behavior,
expiry, isolation, forget, pending decisions and concurrency, and document any
contract change **before** implementing it. Opt-in preference retention must
remain separate from transcript retention. The previous frontend freeze and
no-go protocol are historical readiness constraints; this phase permits only
explicitly documented minimal future history changes under its own steps.

## Pre-existing changes disposition

Before the original baseline edits, four tracked files were modified and the repository plan was
untracked. `services/preference_service.py` and `tests/test_chat_greetings.py`
add standalone help recognition and fixed introductions, preserving pending
state and rejecting mixed-task short circuits. Existing `backend/README.md`
adds the matching seven-line paragraph; `docs/README.md` adds the plan link.
These are included in working-tree baseline observations and regression checks,
but are left untouched and excluded from the Step 1 commit. Step 6 owns
eventual short-circuit removal. The plan and prior baseline artifacts are
clearly part of Step 1 and included in its commit. Only the backend README
phase/baseline links are staged from that file; the greeting/help paragraph
and repository docs-index change remain unstaged. No readiness history is erased.

## Fixed cases and captured evidence

[Fixed v1 dataset](../resources/llm_first_conversation_evaluation.json) defines
25 synthetic conversations / 36 turns, including the plan's 13 case families,
paraphrases, multi-action turns, references, conflicts, expiry/forget/stateless
history, isolation/concurrency, hostile evidence, forged facts, numeric/citation
faults and bounded failures. Fixture/scoring contracts and 95% task completion
plus zero critical integrity errors are frozen; acceptable tool order/prose is
not frozen. This is a target dataset, not a passing evaluation report and not
compatible with the legacy single-intent evaluator. Step 6 builds execution/
scoring support. The existing 54-turn dataset and reports remain unchanged.

[Captured baseline](../output/llm_first_step1_baseline.json) is generated by:

```bash
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python -m SystemCode.src.backend.scripts.capture_llm_first_baseline \
  > /tmp/llm-first-step1-baseline.json
```

Capture measures public-service greeting/help and a carried-profile two-turn
mixed Chinese/Montessori/importance case. Greeting/help have zero model calls.
Mixed request routes to general guidance and binds only that tool; follow-up
binds preference update without dialogue history. Both domain turns route/build
context before two injected model calls. Profile-key changes are normalization/
decision bookkeeping, not proof the Chinese preference was applied. HTTP
`closest` 422 is established by source review and existing startup endpoint
regressions, separately from these service traces. No live-provider quality,
real latency, token usage or cost is inferred. Numeric operational budgets
remain pending real baseline measurement before rollout.

Verification results, including the earlier failed attempts and final fixture
repairs, are recorded in the active [progress record](agents.md). The user
explicitly authorized resolving the recorded blockers to finalize this step.
The repair is limited to test isolation: optional generation is disabled for
deterministic regression fixtures, model-specific tests retain injected models,
and the checkpoint-reuse test supplies a clock matching its retrieval fixture.
Production routing, state, policy, calculations and refresh rules are unchanged.

Step 1 is complete: the required suite passes 382 tests in 37.548s outside the
sandbox; all 143 affected-module tests pass in 0.916s and 29 repository
evaluation tests pass in 4.046s with RAGAS fixture validation. The sandbox
suite timed out at the HTTP test after 40s. Both new captures match the stored
artifact; dataset, syntax, local links, scope/secrets and preservation checks
pass. The fixed target cases are not yet an executed target evaluation.
Live-provider quality and numeric budgets remain unmeasured. Step 2, bounded
conversation context, is next and has not begun. Earlier failed verification
attempts remain available in the progress record as history.
