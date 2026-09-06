# Implementation 3 — conversational-readiness plan

This document is the active source of truth for taking the backend-only
full-conversation supervisor from implemented-but-no-go to a tested, grounded,
operationally ready agent. It follows the completed
[Implementation 2 archive](impl2-agent-step2.md).

## Session protocol

Every implementation session must read `src/AGENTS.md`, `backend/AGENTS.md`,
this document, and any backend folder guide relevant to the step. Complete only
the single item under **Next step**, run that step's stated checks, record the
evidence in the checklist and decision log, replace **Next step**, and stop.

Statuses are `pending`, `in progress`, `complete`, and `blocked`. A step is not
complete until its acceptance criteria and verification evidence are recorded
here. A blocked step keeps `CONVERSATION_AGENT_MODE=deterministic` and records
the exact prerequisite needed to continue.

## Starting point

Implementation 2 delivered the bounded supervisor, authoritative context,
typed capability tools, validation, deterministic fallback, rollout modes,
privacy-safe observability, and a curated evaluator. Its compatibility review
ended with a no-go decision:

- 270 backend tests that avoid the deprecated TestClient boundary passed;
- the complete backend suite stalled at `TestClient.post`;
- the staged evaluator stopped because OneMap credentials were unavailable;
- no complete staged report or threshold evidence was produced; and
- `CONVERSATION_AGENT_MODE` remained safely defaulted to `deterministic`.

The legacy `test_agent*.py` suite covers the selected-school agent and shared
agent foundations. It is necessary regression coverage, but it is not by
itself evidence that the full-conversation supervisor is ready.

## Goal

Produce enough automated, staged, and operational evidence to decide whether
the existing backend supervisor can be enabled as an explicit opt-in for real
multi-turn conversations. Readiness means it preserves authoritative state,
routes each turn to the correct bounded capability, remains grounded across
turns, fails safely, and completes under the existing backend HTTP contract.

The model remains an orchestrator and bounded response composer. Catalogue,
policy, eligibility, fee, distance, ranking, preference state, and citation
facts remain server-owned.

## Frozen frontend boundary

No frontend source, behavior, dependency, route, state shape, or agent contract
may change during this plan.

- Keep `PreferenceRequest`, `PreferenceResponse`, and their OpenAPI references
  unchanged.
- Continue using the existing `POST /api/preferences` request lifecycle and
  `ready_to_search` signal.
- Do not add browser-visible tool calls, graph state, prompts, provider
  configuration, or agent-only fields.
- Do not move repository, OneMap, Neo4j, OpenAI, policy, or retrieval access
  into browser code.
- If readiness requires a frontend or public-contract change, record a no-go
  decision and stop this plan instead of making that change.

Backend tests may validate the existing HTTP boundary, and the unchanged
frontend may be built as a compatibility check, but frontend files are outside
the implementation scope.

## Readiness gates

All gates are mandatory for a go decision:

1. **Backend compatibility:** the complete backend test command finishes
   without exclusions, hangs, or failures on the supported environment.
2. **Contract stability:** generated OpenAPI continues to reference the same
   preference request and response models with the same required fields; no
   frontend file changes are present.
3. **Deterministic safety:** deterministic mode remains lazy and unchanged;
   every rejected, timed-out, or unavailable agent path returns one valid
   deterministic response without recursive model entry or duplicate writes.
4. **Conversation correctness:** the evaluation set covers multi-turn state,
   corrections, follow-ups, ambiguity, topic switches, pending flows, missing
   context, and every registered capability. Authoritative profile, readiness,
   calculations, and selected school identity must match deterministic truth.
5. **Grounding:** every factual claim is traceable to an accepted tool result;
   evidence answers have resolvable, correctly scoped citations; unavailable
   evidence is never converted into a negative claim.
6. **Live staged execution:** the full curated set completes with configured
   provider and OneMap access, with 100% structural and citation validity, zero
   authoritative state/calculation discrepancies, at least 95% accepted tool
   selection, and at most 5% fallback.
7. **Operational behavior:** bounded timeouts and execution limits terminate
   cleanly, privacy-safe observations contain no message, profile, family,
   prompt, evidence, credential, URL, or provider-error content, and repeated
   staged runs do not reveal state leakage between conversations.
8. **Rollout control:** agent mode remains backend-only and explicit opt-in.
   The default stays deterministic unless a later, separately approved rollout
   changes it.

Any failed or unevaluated gate results in no-go.

## Work plan

### Step 1 — Re-establish the backend readiness baseline

- Reproduce the complete-suite TestClient stall with a bounded timeout and
  capture the smallest useful stack/version evidence without changing code.
- Inventory all full-conversation tests separately from legacy
  `test_agent*.py` tests and map them to the readiness gates above.
- Record a non-secret staged preflight inventory for required OpenAI, OneMap,
  catalogue, policy, selected-school index, and general-knowledge inputs. The
  inventory records only presence and usability, never credential values.
- Snapshot the current OpenAPI preference schemas and confirm that the
  frontend worktree is untouched.

Acceptance: the transport failure and staged prerequisites are reproducible,
the exact test/evaluation commands are recorded, and no executable behavior or
frontend file is changed.

### Step 2 — Repair the backend HTTP integration-test boundary

- Replace or update the deprecated Starlette/HTTPX TestClient usage with the
  supported in-process ASGI test transport for this dependency set.
- Preserve application startup/shutdown behavior and test the three previously
  blocked request cases through the real FastAPI boundary.
- Add a bounded timeout or equivalent failure signal so a transport regression
  fails instead of hanging indefinitely.

Acceptance: all formerly blocked endpoint tests pass, the complete backend
suite completes without exclusions, and the OpenAPI snapshot remains
unchanged.

### Step 3 — Make staged execution preflighted and reproducible

- Add a read-only preflight path to the staged evaluator that validates model
  configuration, OneMap authentication/geocoding, catalogue access, policy
  inputs, and both evidence indexes before running cases.
- Return actionable, non-sensitive failure categories and perform no report
  write when prerequisites fail.
- Keep live-provider execution behind the explicit `--staged`
  acknowledgement; automated unit tests continue to use injected fakes.
- Document the exact backend-only preflight and staged commands.

Acceptance: injected preflight tests cover success and each missing dependency,
and a configured environment can reach the first evaluation case only after
all prerequisites pass.

### Step 4 — Expand multi-turn conversational evaluation

- Extend the curated set from isolated capability checks to ordered
  conversations that carry the returned profile into the next turn.
- Cover pronouns and follow-ups, correction of prior preferences, reset after a
  decision question, topic switches, repeated questions, ambiguous school
  references, pending importance/contradiction/relaxation flows, and recovery
  after unavailable evidence.
- Include adversarial turns that attempt to forge school IDs, profile state,
  citations, tool arguments, instructions, or provider configuration.
- Define expected route, tools, mutation count, authoritative state delta,
  citation scope, readiness, and acceptable fallback for every turn.

Acceptance: every registered capability and state transition has at least one
single-turn case and one relevant multi-turn path, malformed or hostile input
fails closed, and evaluation artifacts remain synthetic and privacy-safe.

### Step 5 — Close conversational correctness gaps

- Run the expanded set with injected deterministic model scripts and classify
  every failure as routing, tool selection, state continuity, grounding,
  validation, fallback, or evaluation-fixture error.
- Make only backend changes required by demonstrated failures. Preserve typed
  tools, server-owned context, execution bounds, exactly-once persistence, and
  the unchanged HTTP response contract.
- Add the smallest regression test for every corrected defect before updating
  the evaluation expectation.

Acceptance: focused supervisor, validation, mode, tool, evaluation, legacy
agent, dialogue, and stage-flow suites pass; the complete backend suite passes;
and injected evaluation has zero authoritative discrepancies or invalid
citations.

### Step 6 — Run live staged evaluation and tune safely

- Run the full curated set with configured provider and OneMap access, first in
  shadow-equivalent evaluation and then through the validated agent runner.
- Review only the allowlisted report fields. Do not persist raw prompts,
  messages, profiles, evidence text, family data, URLs, credentials, or provider
  errors.
- Improve prompts or backend routing only when a reviewed case demonstrates a
  bounded failure; do not weaken validation or deterministic fallback to raise
  acceptance rates.
- Repeat the complete staged run after any change.

Acceptance: a complete report satisfies every structural, citation, state,
tool-selection, and fallback threshold for two consecutive runs, with no
cross-conversation state leakage.

### Step 7 — Verify backend operational readiness

- Exercise deterministic, shadow, and agent modes through the existing API
  with bounded concurrency, provider timeout, tool failure, and dependency
  unavailability scenarios.
- Confirm one served response, one optional memory write, and one feedback
  record per request; shadow candidates must never alter the served response.
- Confirm telemetry is bounded, non-sensitive, and useful for distinguishing
  accepted, fallback, timeout, dependency, and validation outcomes.
- Run the full backend suite, OpenAPI comparison, Python compilation, staged
  evaluation, and unchanged-frontend check from a clean test process.

Acceptance: all modes terminate within configured limits, fallback remains
available under injected failures, no sensitive observation fields appear,
all compatibility checks pass, and no frontend files differ.

### Step 8 — Decide opt-in rollout

- Review every readiness gate and link its reproducible evidence.
- Record a go/no-go decision. Missing credentials, partial suites, excluded
  tests, incomplete staged cases, or threshold misses are no-go.
- On go, document only the backend configuration needed to opt into agent mode
  and the immediate rollback to deterministic mode. Do not change the default
  and do not modify the frontend.
- On no-go, name the unresolved backend gate and set it as the only next step
  for a future review.

Acceptance: the decision is evidence-backed, reversible, backend-only, and
does not infer readiness from mocked tests alone.

## Checklist

| Step | Status | Required evidence |
|---|---|---|
| 1. Re-establish the backend readiness baseline | complete | 2026-09-06 baseline below: bounded transport reproduction, test inventory, staged prerequisite inventory, OpenAPI/frontend snapshot |
| 2. Repair the backend HTTP integration-test boundary | complete | 2026-09-06 evidence below: bounded ASGI transport, formerly blocked API cases, and all 277 backend tests pass |
| 3. Make staged execution preflighted and reproducible | complete | 2026-09-06 evidence below: six injected dependency gates, configured preflight success, documented commands, and 279 backend tests pass |
| 4. Expand multi-turn conversational evaluation | complete | 2026-09-06 evidence below: 54 reviewed turns, returned-profile continuity, complete capability coverage, and adversarial cases |
| 5. Close conversational correctness gaps | complete | 2026-09-06 evidence below: 54-turn scripted evaluation passes with authoritative parity and all 282 backend tests pass |
| 6. Run live staged evaluation and tune safely | complete | 2026-09-06 evidence below: two consecutive 54-turn live reports pass with 100% scored correctness and zero unexpected fallback |
| 7. Verify backend operational readiness | complete | 2026-09-06 evidence below: bounded concurrent API modes, injected failures, exactly-once side effects, privacy audit, and all compatibility gates |
| 8. Decide opt-in rollout | pending | Evidence-linked go/no-go and rollback instructions |

## Step 1 baseline evidence

Recorded on 2026-09-06 from repository commit
`4285eb4763f32a3ac79b69ee10d83172c65026a5`. Step 1 changed no executable
or frontend files.

### Backend transport and suite baseline

The supported complete-suite command remains:

```bash
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python -m unittest discover -s SystemCode/src/backend/tests -v
```

The bounded full-suite reproduction used the same discovery root through a
`unittest` runner with `faulthandler.dump_traceback_later(45)` and an outer
`timeout 55s`. It exited `124` after 40 completed tests at the first
`TestClient.post`,
`test_api_startup.ApiStartupTests.test_nearest_chat_uses_postal_code_and_full_grounded_catalogue`.
The focused reproduction was:

```bash
timeout 20s env \
  PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python -c \
  'import faulthandler, unittest; faulthandler.dump_traceback_later(8, repeat=False); suite=unittest.defaultTestLoader.loadTestsFromName("SystemCode.src.backend.tests.test_architecture_boundaries.RepositoryBoundaryTests.test_api_rejects_legacy_client_supplied_school_objects"); result=unittest.TextTestRunner(verbosity=2).run(suite); faulthandler.cancel_dump_traceback_later(); raise SystemExit(not result.wasSuccessful())'
```

It also exited `124`. Both traces show the calling thread waiting in
`starlette.testclient.TestClient.handle_request` /
`anyio.from_thread.BlockingPortal.call`, while the portal thread is idle in
the asyncio selector. Importing `fastapi.testclient` emits
`StarletteDeprecationWarning: Using httpx with starlette.testclient is
deprecated; install httpx2 instead.` The reproduced versions are Python
3.12.12, FastAPI 0.141.1, Starlette 1.6.0, and HTTPX 0.28.1.

There are three blocked test methods (four HTTP requests):

- `test_api_startup.py` has one `/api/preferences` method with two sequential
  posts, covering nearest-school state and an active-school follow-up;
- `test_architecture_boundaries.py` has the legacy school-object rejection
  `/api/evaluate` case; and
- `test_architecture_boundaries.py` has the unknown-school 404
  `/api/evaluate` case.

The tree currently contains 275 test methods. Running the other 272 methods
completed in 49.459 seconds with 269 passes and three failures. All three are
legacy Phase 9 LLM-answer tests whose expected agent path is disabled by the
developer environment's `WEB_RAG_ANSWER_MODE=agent`; the three pass in 0.005
seconds with `WEB_RAG_ANSWER_MODE=deterministic`. This is separate from the
full-conversation rollout setting: `CONVERSATION_AGENT_MODE` is unset and
therefore still defaults to `deterministic`. The complete-suite readiness gate
is not met until the transport and environment isolation are both resolved.

### Conversation test inventory

The focused full-conversation command is:

```bash
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python -m unittest -v \
  SystemCode.src.backend.tests.test_conversation_context \
  SystemCode.src.backend.tests.test_conversation_evaluation \
  SystemCode.src.backend.tests.test_conversation_modes \
  SystemCode.src.backend.tests.test_conversation_supervisor \
  SystemCode.src.backend.tests.test_conversation_validation \
  SystemCode.src.backend.tests.test_decision_tools \
  SystemCode.src.backend.tests.test_evidence_tools \
  SystemCode.src.backend.tests.test_preference_state_tools
```

All 46 tests passed in 4.662 seconds. Their readiness-gate mapping is:

| Test file | Count | Readiness gates evidenced |
|---|---:|---|
| `test_conversation_context.py` | 2 | 4, 5: authoritative context and school identity |
| `test_conversation_evaluation.py` | 4 | 4, 5, 6, 7: curated-set shape, safe reports, observations |
| `test_conversation_modes.py` | 6 | 2, 3, 7, 8: public shape, fallback, writes, rollout modes |
| `test_conversation_supervisor.py` | 7 | 3, 4, 5, 7: routing, tool bounds, grounded assembly |
| `test_conversation_validation.py` | 9 | 3, 4, 5, 7: fail-closed validation, timeout, exactly-once fallback |
| `test_decision_tools.py` | 7 | 4, 5: authoritative decisions, calculations, structured facts |
| `test_evidence_tools.py` | 5 | 4, 5: scoped evidence and unavailable-evidence behavior |
| `test_preference_state_tools.py` | 6 | 3, 4: bounded mutations and pending flows |

The separate legacy command is:

```bash
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python -m unittest discover \
  -s SystemCode/src/backend/tests -p 'test_agent*.py' -v
```

All 39 legacy tests passed in 1.092 seconds. They cover the selected-school
agent plus shared configuration, contracts, model construction, bounds,
fallback, grounding, and privacy-safe observations (gates 3, 5, 7, and 8),
but do not establish full-conversation correctness or live staged readiness.
The remaining 190 methods are supporting API, dialogue, service, policy,
pipeline, and RAG coverage, including the three blocked transport methods.

### Staged prerequisite inventory

The inventory loaded the repository `.env` without printing values and made
one live, read-only OneMap geocode request for synthetic postal code `540231`.

| Input | Presence and usability evidence |
|---|---|
| OpenAI | Credential is present; configured `ChatOpenAI` client initializes. No provider generation was invoked, so live model access is not yet proven. |
| OneMap | A supported credential form is present; authentication and geocoding succeeded. |
| Catalogue | Parsed through `SchoolRepository`; 1,867 records have stable IDs. |
| Policy | Parsed through `PolicyRepository`; one non-overlapping policy version is available. |
| Selected-school evidence | JSON loads with 20 pages and 70 chunks. |
| General-knowledge evidence | JSON loads with 15 chunks. |
| Curated evaluation set | Pydantic validation passes for all 25 ordered cases. |

The current evaluator has no read-only preflight command; adding it is Step 3.
Its existing live command is:

```bash
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python -m SystemCode.src.backend.scripts.evaluate_conversation_supervisor \
  --staged --output SystemCode/src/backend/output/conversation_agent_evaluation.json
```

Step 1 did not run that command because it invokes the provider and writes a
report; the staged run remains unevaluated.

### Contract and frontend snapshot

Canonical JSON serialization of the complete generated OpenAPI document has
SHA-256 `2cb0812711be9f77034f5cfd2547e71051a855cc2c5784ad050117c49dc6b405`.
The `/api/preferences` operation plus its two component schemas has SHA-256
`8190a2607393dfa45988f8535484dbc5ec0857d3cceace2534fef4346bf02bc9`.

- Request ref: `#/components/schemas/PreferenceRequest`; required field:
  `message`; properties: `anonymous_session_id`, `eligible_school_ids`,
  `excluded_school_ids`, `family`, `home_postal_code`, `message`, `profile`,
  `remember_preferences`, and `selected_school_ids`.
- Response ref: `#/components/schemas/PreferenceResponse`; required fields:
  `profile`, `understood`, `ready_to_search`, and `question`; properties:
  `answer_id`, `answer_method`, `citations`, `evidence_category`,
  `fallback_reason`, `profile`, `question`, `ready_to_search`, and
  `understood`.
- `git status --porcelain -- SystemCode/src/frontend` produced no output, and
  the frontend diff against the recorded commit is empty.

## Step 2 HTTP integration evidence

Recorded on 2026-09-06. The two endpoint test modules no longer import the
deprecated Starlette `TestClient`. They use HTTPX `AsyncClient` with
`ASGITransport`, explicitly enter and exit the FastAPI lifespan context, and
bound every request to five seconds. Dedicated client regressions prove that
startup and shutdown both run and that a stalled ASGI request raises
`TimeoutError` within its configured bound.

The focused verification command was:

```bash
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python -m unittest -v \
  SystemCode.src.backend.tests.test_asgi_test_client \
  SystemCode.src.backend.tests.test_api_startup \
  SystemCode.src.backend.tests.test_architecture_boundaries \
  SystemCode.src.backend.tests.test_stage_flow.PipelineTests.test_phase9_llm_synthesises_only_retrieved_web_evidence \
  SystemCode.src.backend.tests.test_stage_flow.PipelineTests.test_phase9_llm_invalid_citation_uses_deterministic_fallback \
  SystemCode.src.backend.tests.test_stage_flow.PipelineTests.test_phase9_llm_cannot_reject_retrieved_evidence
```

All 16 focused tests passed in 0.360 seconds. This includes the four formerly
blocked HTTP requests: two sequential `/api/preferences` posts, legacy
client-supplied object rejection, and unknown-school 404 handling. The HTTP
fixture now returns only records corresponding to requested authoritative IDs.
The three legacy RAG tests explicitly select their intended deterministic
legacy mode, so a developer `.env` cannot silently disable the mocked path.

The unchanged complete-suite command then completed without exclusions:

```bash
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python -m unittest discover -s SystemCode/src/backend/tests -v
```

All 277 tests passed in 49.359 seconds. Canonical generation of the complete
OpenAPI document still has SHA-256
`2cb0812711be9f77034f5cfd2547e71051a855cc2c5784ad050117c49dc6b405`,
matching the Step 1 snapshot. `git diff --check` passed, and
`git diff -- SystemCode/src/frontend` produced no output.

## Step 3 staged-preflight evidence

Recorded on 2026-09-06. The evaluator now exposes a read-only `--preflight`
mode and runs the same gate before the first case of every `--staged` run. The
gate initializes the configured model client without generation, performs a
live OneMap geocode for synthetic postal code `540231`, loads the generated
catalogue and verifies stable IDs, selects the policy applicable today, and
validates the nested selected-school and curated general-knowledge evidence
indexes contain chunks. Results expose only fixed check names, booleans,
failure categories, and remediation text; dependency exceptions and provider
responses are not returned.

The backend-only commands are:

```bash
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python -m SystemCode.src.backend.scripts.evaluate_conversation_supervisor \
  --preflight

PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python -m SystemCode.src.backend.scripts.evaluate_conversation_supervisor \
  --staged --output SystemCode/src/backend/output/conversation_agent_evaluation.json
```

The configured read-only preflight completed successfully with all six checks
passing: model, OneMap, catalogue, policy, selected-school evidence, and
general-knowledge evidence. It did not invoke model generation or write a
report. Injected tests cover the successful path and each missing dependency;
they also prove a failed staged preflight exits with status 2 before cases and
does not create its requested output.

Focused preflight and model-factory verification passed 13 tests. The complete
backend command from `backend/AGENTS.md` then passed all 279 tests in 49.110
seconds. `git diff --check` passed, and no frontend file changed.

## Step 4 multi-turn evaluation evidence

Recorded on 2026-09-06. Evaluation schema version 2 groups ordered cases by
synthetic conversation and requires contiguous turn numbers. Continuation
turns receive the prior agent response's returned profile, while a new
conversation starts from its reviewed initial profile. Per-turn expectations
now cover route, exact tool set, mutation count, partial authoritative profile
delta (set and removed paths), citation scopes, readiness, active-school
identity where relevant, expected acceptance, and whether fallback is allowed.
Only booleans, counts, fixed metadata, and case IDs are written to reports.

The curated set now contains 54 turns across 33 synthetic conversations: 27
isolated one-turn conversations and 27 turns in six multi-turn conversations.
It includes importance, contradiction, and relaxation flows; correction and
reset; pronoun follow-up; topic switching; repeated questions; ambiguous
school references; missing-context behavior; and recovery after unavailable
school evidence. Every one of the 15 registered capabilities appears in both
an isolated case and a continuation path. Six fail-closed adversarial cases
cover forged school IDs, profile state, citations, tool arguments, model
instructions, and provider configuration. The fixture contains no real family
or credential data.

The focused evaluation command passed all 7 tests:

```bash
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python -m unittest -v \
  SystemCode.src.backend.tests.test_conversation_evaluation
```

The unchanged complete backend command passed all 280 tests in 49.353 seconds.
Python compilation of the evaluator and staged script passed, as did
`git diff --check`. No frontend file changed.

## Step 5 conversational-correctness evidence

Recorded on 2026-09-06. A deterministic scripted-model regression now runs all
54 reviewed turns through the real supervisor, context-bound tools, validation,
fallback, repositories, and returned-profile continuation. Model generation,
intent classification, and postal geocoding are injected, so the test is
repeatable and has no live-provider dependency. The report assigns every
failed scored check to a fixed privacy-safe category: routing, tool selection,
state continuity, grounding, validation, or fallback.

The initial run classified the demonstrated gaps as follows:

- state continuity: agent results dropped the deterministic answer status,
  read-only evidence profiles were not canonicalized, repository-resolved
  active-school names were not used by the deterministic path, and active
  school `centre_code` was discarded between turns;
- grounding: structured catalogue answers lacked resolvable structured
  citations, and conversational scaffolding in a combined question diluted
  selected-school retrieval below its relevance threshold; and
- evaluation fixture: the legacy deterministic food answer does not use the
  newer structured-facts capability. This remains a diagnostic usefulness
  metric, not an agent acceptance requirement or an authoritative discrepancy.

The fixes keep server-owned identity and intent metadata in the request
context, propagate the internal answer status without changing the public
response model, canonicalize read-only tool profiles, add stable ECDA catalogue
citations, and ignore four non-semantic conversational retrieval terms. Focused
regressions cover each defect and the full scripted conversation set. The final
injected report passes all 54 cases with 100% route, tool-selection, profile
state, authoritative delta, readiness, mutation, grounding, citation, and
agent-response usefulness rates. Its 85.19% acceptance and 14.81% fallback
rates exactly reflect the eight reviewed clarification or hostile-input cases;
all other cases are accepted. The legacy deterministic usefulness diagnostic
is 98.15% because of the structured-food distinction described above.

The focused supervisor, validation, mode, tool, evaluation, legacy-agent,
dialogue, and stage-flow coverage passed. The complete backend command from
`backend/AGENTS.md` then passed all 282 tests in 62.600 seconds. Python
compilation and `git diff --check` passed. The complete OpenAPI SHA-256 remains
`2cb0812711be9f77034f5cfd2547e71051a855cc2c5784ad050117c49dc6b405`,
matching the Step 1 snapshot, and no frontend file changed.

## Step 6 live-staged evidence

Recorded on 2026-09-06. The configured read-only preflight passed all six
model, OneMap, catalogue, policy, selected-school evidence, and general-
knowledge evidence checks. Multiple complete 54-turn live runs were reviewed
only through the evaluator's allowlisted metrics and case metadata; no raw
prompt, message, profile, evidence, URL, credential, or provider error was
persisted or reviewed.

The first live run reproduced severe provider variance: 14.81% case pass,
35.19% route accuracy, 31.48% tool-selection accuracy, 20.37% acceptance, and
79.63% fallback, while citation validity remained 100%. Safe tuning made the
server-classified intent authoritative for capability scope, limited exposed
tools to that intent, required a tool on the selection call, retained an
unbound model for grounded composition, accepted schema-valid fenced JSON,
added deterministic rules for pending-flow and control-attempt messages, and
rejected explicit attempts to replace server-owned tool or citation inputs.
An attempted provider JSON-mode binding was removed after a complete run
returned only fixed `model_error` outcomes, showing that option is unsupported
by the configured client.

The best and final retained report is
`output/conversation_agent_evaluation_run_7.json`. It completed all 54 turns
with 74.07% case pass, 100% deterministic-intent accuracy, 85.19% route and
tool-selection accuracy, 100% authoritative-state-delta and readiness
accuracy, 98.15% profile-mutation accuracy, 79.63% grounding validity, 100%
citation validity, 68.52% acceptance, and 31.48% fallback. Its remaining
failures include model composition that does not validate consistently and
three exact profile-parity mismatches. The raw fallback gate also conflicts
with the reviewed fixture: eight of 54 cases (14.81%) explicitly require safe
fallback, so an unqualified maximum fallback rate of 5% cannot be satisfied by
a correct run. A future Step 6 session must define that gate as unexpected
fallback (or revise the reviewed expectations), close the remaining live
contract/state failures, and then produce two consecutive passing reports.

Focused supervisor, validation, evaluation, dialogue, and stage-flow coverage
passed 115 tests. The unchanged complete backend command passed all 282 tests
in 61.550 seconds. `CONVERSATION_AGENT_MODE` remains defaulted to
`deterministic`; Step 7 was not started.

### Step 6 completion

The follow-up session separated expected safe fallback from unexpected agent
fallback. `agent_fallback_rate` remains the raw operational rate, while
`unexpected_agent_fallback_rate` counts only fallbacks not explicitly reviewed
as acceptable. This resolves the gate contradiction without weakening the
eight clarification and hostile-input expectations: their required 8/54
(14.81%) fallback remains visible, while the Step 6 threshold applies to
unexpected fallback.

Live failures were closed without broadening model authority. Final composition
accepts typed tool output, JSON, or plain provider wording, retains model wording
only when every non-neutral term is grounded in tool output, resolves citation
IDs from server-owned tool results, and uses the bounded authoritative answer
candidate when composition is unusable. School-published claims retain the
retrieval adapter wording so claims and school-scoped citations cannot drift.
Explicit control attempts and ambiguous multi-school references still fail
closed. The staged comparison now isolates its initial profile, and read-only
closest-school results preserve the authoritative intent method. Two additional
deterministic routing rules cover a pending importance answer and an explicit
system-instruction bypass attempt demonstrated by live runs.

The configured preflight passed all six dependencies. The two consecutive
passing reports are `output/conversation_agent_evaluation_run_12.json` and
`output/conversation_agent_evaluation_run_13.json`. Each completed all 54 turns
with 100% case pass, route, tool-selection, exact profile state, authoritative
delta, readiness, mutation, grounding, citation, and agent-response usefulness
rates. Both report 85.19% agent acceptance, 14.81% raw fallback (the eight
required safe-fallback cases), and 0% unexpected fallback. No raw prompt,
message, profile, evidence, credential, URL, or provider-error content is stored
in either report.

Focused conversation, validation, evidence, evaluation, and stage-flow checks
passed 107 tests, and the final complete backend command passed all 286 tests
in 61.021 seconds. Python compilation and `git diff --check` passed. The complete
OpenAPI SHA-256 remains
`2cb0812711be9f77034f5cfd2547e71051a855cc2c5784ad050117c49dc6b405`,
matching Step 1, and no frontend file changed. `CONVERSATION_AGENT_MODE`
continues to default to `deterministic`; Step 7 was not started.

## Step 7 operational-readiness evidence

Recorded on 2026-09-06. A dedicated operational API suite now sends four
concurrent, two-second-bounded `/api/preferences` requests through each of the
deterministic, shadow, and agent modes. Every request returns one valid public
response, records exactly one privacy-minimised answer snapshot, and, when
requested, performs exactly one preference-memory write. Shadow candidates are
intentionally different in the test and never alter the deterministic response
served to the caller. Deterministic mode does not construct or run the
supervisor.

The same API boundary was exercised with injected provider timeout, capability-
tool failure, model-dependency unavailability, and invalid agent state. Each
request terminated within the two-second test bound, invoked the deterministic
fallback exactly
once, returned one successful response, recorded exactly one answer snapshot,
performed no unrequested memory write, and emitted the distinct fixed outcome
`timeout`, `tool_error`, `model_unavailable`, or `validation_error`. Existing
validation coverage also retains bounded tool-call, mutation, and graph-
iteration termination.

The telemetry audit serialized a real emitted observation while seeding the
comparison inputs with sentinel message, profile/family, prompt, evidence,
credential, URL, and provider-error content. None appeared in the log. The
payload contains only the schema's bounded counters, fixed enums, booleans, and
shadow parity fields. The focused operational, mode, validation, memory,
feedback, evaluation, and ASGI transport command passed all 35 tests in 13.766
seconds.

The unchanged complete backend command passed all 289 tests in 61.135 seconds.
The configured read-only preflight passed all six dependencies, and fresh live
report `output/conversation_agent_evaluation_run_14.json` passed all 54 turns
with 100% route, tool-selection, exact profile state, authoritative delta,
readiness, mutation, grounding, citation, and agent-response usefulness rates.
It reports 85.19% accepted agent responses, the eight reviewed safe fallbacks
(14.81%), and 0% unexpected fallback. Inspection confirmed that the report
contains only the allowlisted aggregate and per-case fields.

Python compilation and `git diff --check` passed. The complete OpenAPI SHA-256
remains `2cb0812711be9f77034f5cfd2547e71051a855cc2c5784ad050117c49dc6b405`,
matching Step 1, and the frontend diff is empty. The default remains
`CONVERSATION_AGENT_MODE=deterministic`; Step 8 was not started.

## Decision log

- 2026-09-06 — Archive the completed no-go Implementation 2 record as
  `impl2-agent-step2.md` and begin a separate conversational-readiness review so
  historical implementation evidence is not mistaken for rollout evidence.
- 2026-09-06 — Freeze the frontend and public preference API for the entire
  review. Any need for a frontend or contract change produces no-go rather than
  expanding this plan's scope.
- 2026-09-06 — Require a passing complete backend suite and completed live
  staged evaluation. Legacy agent tests or mocked supervisor tests alone cannot
  authorize rollout.
- 2026-09-06 — Keep deterministic mode as the default. A successful review may
  authorize only an explicit backend opt-in with immediate deterministic
  rollback.
- 2026-09-06 — Complete Step 1 without executable changes. The deprecated
  Starlette/HTTPX `TestClient` boundary reproducibly stalls, and the supported
  environment also needs isolation from the developer `.env` for three legacy
  RAG tests. Keep the readiness decision no-go and advance only to Step 2.
- 2026-09-06 — Complete Step 2 by moving backend HTTP integration tests to a
  lifespan-aware, bounded HTTPX ASGI transport and isolating legacy RAG fixture
  mode from ambient configuration. All 277 backend tests pass, the OpenAPI
  snapshot is unchanged, and the frontend remains untouched. Readiness remains
  no-go pending the remaining gates; advance only to Step 3.
- 2026-09-06 — Complete Step 3 with a shared read-only prerequisite gate for
  model configuration, live OneMap geocoding, catalogue, current policy, and
  both evidence indexes. Require every staged run to pass it before loading the
  API service or evaluating a case, and suppress report writes on failure. The
  configured preflight and all 279 backend tests pass. Readiness remains no-go
  pending the remaining gates; advance only to Step 4.
- 2026-09-06 — Complete Step 4 by upgrading the curated evaluator to ordered
  synthetic conversations with returned-profile continuity and explicit
  state, readiness, mutation, citation, acceptance, and fallback expectations.
  All registered capabilities have isolated and multi-turn coverage, and six
  hostile-input categories are represented. All 280 backend tests pass.
  Readiness remains no-go because these cases have not yet been exercised and
  classified with injected deterministic model scripts; advance only to Step 5.
- 2026-09-06 — Complete Step 5 after the 54-turn injected run exposed and
  closed state-continuity and grounding gaps. The scripted report now passes
  every case with zero authoritative-state or citation discrepancies, and all
  282 backend tests pass with the OpenAPI snapshot and frontend unchanged.
  Readiness remains no-go because no live staged threshold evidence exists;
  advance only to Step 6.
- 2026-09-06 — Keep Step 6 blocked after complete live staged runs and bounded
  routing/tool-selection tuning. The best run preserves 100% citation validity
  and authoritative delta/readiness accuracy, but reaches only 74.07% case
  pass, 85.19% tool selection, and 31.48% fallback. The raw fallback threshold
  is also incompatible with eight reviewed cases that require safe fallback.
  Keep deterministic mode and do not begin Step 7.
- 2026-09-06 — Complete Step 6 after grounding provider composition in typed
  capability output, repairing exact comparison-state parity, and defining the
  rollout gate as unexpected fallback while retaining the raw fallback metric.
  Runs 12 and 13 consecutively pass all 54 cases with 100% structural,
  citation, state, tool-selection, and grounding correctness and 0% unexpected
  fallback. Keep deterministic mode and advance only to Step 7.
- 2026-09-06 — Complete Step 7 after bounded concurrent API exercises in all
  three modes, injected timeout/tool/dependency failures, exactly-once side-
  effect checks, and a sentinel-based telemetry privacy audit. All 289 backend
  tests and a fresh 54-turn live staged evaluation pass; OpenAPI is unchanged
  and the frontend remains untouched. Keep deterministic mode and advance only
  to the Step 8 rollout decision.

## Next step

Step 8 — Review every readiness gate and record the evidence-backed opt-in
rollout go/no-go decision with immediate deterministic rollback instructions.
Do not change the default mode or modify the frontend.
