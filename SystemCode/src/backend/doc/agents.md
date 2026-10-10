# Backend conversation progress

## Active phase — LLM-first conversation, 2026-10-10

The [repository plan](../../../../docs/llm-first-conversation-plan.md) governs
the current phase. Steps 1–5 are **complete**, including passing required
regressions. Step 6 has not started. The Implementation 3 readiness plan below is retained as history,
including its completed checks and subsequent default-agent rollout.

Current sessions read contributor/folder guidance, this record and the new
plan; implement only the recorded next step, verify, update both records,
commit only step-owned changes when all required checks pass, then stop.
The old blocked-mode instruction and frontend freeze are historical; do not
change the shipped rollout for a documentation baseline failure. Step 2 must
document any minimal history contract/frontend change before implementation.

### LLM-first Step 5 completion — 2026-10-10

Implemented `agents/conversation_response.py` and bounded final-response repair
in `agents/conversation_loop.py`. Successful wording is model-authored: direct
conversation, clarifications, preference acknowledgements and evidence-gap
explanations. Strict internal claims reference server result IDs, scalar paths,
values, schools and citations. Mechanical checks reject mismatched values and
reported numbers, fabricated citations/support, cross-school attribution and
stale state-dependent results. Retrieved school passages now include repository
names for attribution. No answer copying, vocabulary allowlist, substitution or
legacy fallback runs in the validated new path. Validation authorizes one
profile export; failures discard state and return a fixed service error.
Repair uses existing evidence only, at most twice within the original budgets,
and cannot replay tools or mutations. See
[the response contract](llm-first-responses.md).

Acceptance covered by 11 new injected-model tests plus existing loop/tool
regressions: **37 tests in 0.873s, OK, exit 0** outside the sandbox
(`/tmp/llm-first-step5-focused-escalated.log`). Initial sandbox focused attempt
stalled in worker-thread loop cases; the first outside-sandbox run passed 35
checks before two additional adversarial cases were added. Required backend
command: **432 tests in 40.809s, OK**, exit 0, outside the sandbox
(`/tmp/llm-first-step5-backend.log`). Sandbox discovery timed out **exit 124
at 50s** after `test_llm_first_loop.LlmFirstLoopTests.test_access_scope_invalid_arguments_and_duplicate_call_ids_fail_closed`
(`/tmp/llm-first-step5-backend-sandbox.log`). `make eval-check`: **29 tests in
3.412s, OK**, plus RAGAS validate-only fixture check
(`/tmp/llm-first-step5-eval.log`). Diff/scope/secrets/local links and
`git diff --check` reviewed; pre-existing greeting/help source/tests, README
paragraph and docs-index changes preserved and excluded from the commit.

Limitations: mechanical validation does not prove semantic entailment or complete
claim annotation, including unsupported nonnumeric prose mislabeled as dialogue.
Units/periods and boolean/status wording need semantic evaluation. Exact numeric
values are supported; rounding/unit conversion is not. School-name checks may
reject overlapping names. Injected models establish control flow, not live
quality. HTTP/history/memory integration and staged provider evaluation remain
Step 6; mode rollout and operational budgets remain Step 7. No public/frontend
contract, authoritative facts, deterministic algorithm or served rollout change.

Acceptance met for Step 5. Next: Step 6 — HTTP integration and evaluation.
Not begun in this session.

### LLM-first Step 4 completion — 2026-10-10

Implemented `agents/conversation_loop.py`: every valid new-flow invocation
calls the injected model before semantic decisions or tools, exposes all
server-permitted capabilities without intent/keyword filtering, permits direct
replies and clarifications, and executes combined/dependent calls sequentially
against current staged state. Structured missing-input and unavailable results
return to the model. Invalid calls, duplicate IDs, provider failures, timeout,
cancellation and execution/context/output overflow abort the transaction.
Added transaction closure locking so late synchronous workers cannot stage or
export discarded state. The loop returns an unvalidated candidate and never
exports state or writes history/memory.

Acceptance covered by 15 new injected-model tests, including varied mixed
requests, ambiguous references, zero-tool turns, dependent calls, missing-input
recovery, access and argument rejection, rollback and resource bounds. See
[the durable loop contract](llm-first-loop.md).

Verification: required backend command **421 tests in 40.533s, OK, exit 0**
outside the sandbox (`/tmp/llm-first-step4-backend.log`). Sandbox attempt
**exit 124 after 50s**, stalled after the first `test_llm_first_loop` case
(`/tmp/llm-first-step4-backend-sandbox.log`). Final focused loop/tools checks:
**26 tests in 0.667s, OK** (`/tmp/llm-first-step4-focused-escalated.log`).
The first focused run exposed an invalid empty-capability fixture; corrected
and rerun. `make eval-check`: **29 tests in 3.463s, OK**, plus validate-only
RAGAS fixture validation (`/tmp/llm-first-step4-eval.log`). Diff/scope/secrets,
local links, `git diff --check` and unrelated-work preservation review pass.

Limitations: injected models establish control flow, not live conversational
quality. Candidates require Step 5 factual/citation validation and bounded
repair; HTTP/history/memory integration remains Step 6. Synchronous external
reads may finish after timeout, but cannot restore staged state. Accepted-byte
bounds do not cap provider generation cost. No frontend/public contract,
authoritative facts, deterministic algorithm or served rollout change.
Pre-existing greeting/help code/tests and documentation hunks remain excluded.

Acceptance met. Next: Step 5 — LLM responses and grounding. Not begun.

### LLM-first Step 3 completion — 2026-10-10

Implemented the [structured capability and staged-state contract](llm-first-tools.md)
in `agents/structured_contracts.py` and `services/conversation_tool_service.py`.
Eight registered tools accept typed patches, operations, IDs, focused queries
and scenario overrides. Results contain explicit statuses, data, result IDs,
state revisions and provenance without answer generation. Existing repositories,
scorer, evaluator, distance and retrieval algorithms remain authoritative.
Later tools read updated working state; hypothetical family inputs are isolated.
Failures discard staged changes, invalidate export and never write memory.
Pending choices have typed resolutions; conflicting requirements remain staged
until resolved. Shadow exports return the original state.

Acceptance covered by 11 new tests: invalid IDs, forged facts, unsupported
fields/patches, update-then-search, current-profile calculation, deterministic
scenario equality, family isolation, typed pending resolution, detached results,
single export, failures/limits/overflow rollback, lazy providers and citations.

Required backend discovery: **406 tests in 39.781s, OK, exit 0**, outside the
sandbox (`/tmp/llm-first-step3-backend.log`). Sandbox attempt: **exit 124** after
50s at `test_school_rating_service.SchoolRatingApiTests.test_missing_consent_is_422`
(`/tmp/llm-first-step3-backend-sandbox.log`). Five focused modules: **45 tests
in 1.806s, OK** (`/tmp/llm-first-step3-focused.log`), after correcting a nonexistent
history module in the first command. `make eval-check`: **29 tests in 3.381s,
OK**, plus RAGAS validate-only fixture validation (`/tmp/llm-first-step3-eval.log`).
Diff/scope/secrets/local links, `git diff --check` and preservation review pass.

Limitations: capabilities remain separate from the served legacy supervisor;
HTTP/session commit wiring is Step 6, model loop/overall time/context bounds
are Step 4 and final grounding validation is Step 5. No frontend, public schema,
deterministic algorithm or rollout change. Live-provider quality remains
unmeasured. Pre-existing greeting/help implementation/tests and documentation
hunks are preserved and excluded from this step's commit.

**Historical Step 3 next step: Step 4 — LLM-controlled tool loop.**
Superseded by the Step 4 completion above.

### LLM-first Step 2 completion — 2026-10-10

Implemented the bounded context/history foundation documented in
[the context contract](llm-first-context.md), with strict initial context and
pending-decision models, repository-resolved selected/active school identities,
and an independent ephemeral history service. Exclusive leases reject concurrent
turns, forgotten/expired leases and duplicate commits; failed turns abort.
`/api/memory/forget` invalidates history as well as opt-in preference memory.

Acceptance covered by 13 new tests: follow-up preference and school context,
ambiguous references, absent/expired history, separate sessions, forget through
HTTP, aborted/stale/duplicate turns, capacity/window limits, current authoritative
state over stale dialogue, explicit omissions, context overflow and greeting
context passed to an injected model consumer without ranking/geocoding.

Required backend command: **395 tests in 39.648s, OK, exit 0**, outside
the sandbox; `/tmp/llm-first-step2-backend.log`. Sandbox attempt: exit 124
after 45s at `test_school_rating_service.SchoolRatingApiTests.test_missing_consent_is_422`;
`/tmp/llm-first-step2-backend-sandbox.log`. Five focused modules: **37 tests
in 2.541s, OK**; `/tmp/llm-first-step2-focused.log`. `make eval-check`: **29
tests in 3.785s, OK**, plus validate-only RAGAS fixture validation;
`/tmp/llm-first-step2-eval.log`. Scope/diff/secrets and local-link review,
`git diff --check`, and unrelated-work preservation checks pass.

Limitations: history requires explicit opt-in and single-worker/sticky routing;
RAM-only retention expires on access, has no generated summary, and is lost on
restart/eviction. The documented future `remember_conversation` consent field
and new-flow HTTP integration belong to Step 6. The current controller still
needs eager domain context until Step 3 replacements land. No frontend/public
schema, deterministic algorithms, served routing or rollout changes. Existing
greeting/help code/tests and matching README/docs-index changes are excluded.

**Historical Step 2 next step: Step 3 — structured tools and staged state.**
Superseded by the Step 3 completion above. Model
reference interpretation/control-flow and live quality remain later-step checks.

### LLM-first Step 1 completion — 2026-10-10

Acceptance met: reviewed chat entry/routing/substitution/nested-model/state/tool
dependency map and target contract in [the baseline](llm-first-baseline.md),
fixed 25-conversation / 36-turn dataset, reproducible captured traces, and phase
reconciliation in contributor guidance. Existing greeting/help code and tests,
the matching README paragraph and repository docs-index change are preserved
and excluded from the Step 1 commit. Prior baseline changes clearly belonging
to Step 1 are included. No frontend, public schema, runtime algorithm, provider
configuration, persistence or rollout change.

The user explicitly authorized resolving the recorded regression blockers.
`tests/test_general_knowledge_rag.py` and `tests/test_stage_flow.py` now disable
optional generation in deterministic fixtures, restoring the environment with
cleanup. Model-specific cases still explicitly enable and inject models; their
assertions pass. `tests/test_web_rag.py` gives the checkpoint-reuse case a clock
matching its 2026-08-10 retrieval fixture. Separate expired-page refresh tests
still pass. Production routing and the 30-day refresh rule are unchanged.

Verification from the repository root:

- Exact `AGENTS.md` backend command: **382 tests in 37.548s**, **OK**, exit 0,
  outside the sandbox. Log: `/tmp/llm-first-step1-finalize-backend.log`.
  Sandbox attempt with `timeout 40s` exited 124 at
  `test_school_rating_service.SchoolRatingApiTests.test_missing_consent_is_422`;
  log: `/tmp/llm-first-step1-finalize-backend-sandbox.log`.
- `PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline
  .venv/bin/python -m unittest -v
  SystemCode.src.backend.tests.test_general_knowledge_rag
  SystemCode.src.backend.tests.test_stage_flow
  SystemCode.src.backend.tests.test_web_rag`: **143 pass in 0.916s**.
  Log: `/tmp/llm-first-step1-finalize-affected.log`.
- `make eval-check`: **29 pass in 4.046s**, plus validate-only RAGAS fixture
  validation. Log: `/tmp/llm-first-step1-finalize-eval.log`.
- Two documented captures to `/tmp/llm-first-step1-finalize-baseline-a.json`
  and `-b.json` match the stored output byte-for-byte. Syntax, dataset
  uniqueness/turn bounds/checks, local links and synthetic scope validate.
- Diff/scope/secrets review, `git diff --check` and unrelated-work preservation
  hashes pass; initial hashes: `/tmp/llm-first-step1-finalize-start.json`.

**Historical Step 1 next step: Step 2 — bounded conversation context.**
Superseded by the Step 2 completion above.
Decide/document session/history semantics and any minimal contract change
before implementation. Live-provider quality, numeric budgets and execution
of the fixed target dataset remain unmeasured and belong to later steps.

### Earlier Step 1 verification attempts (historical)

The incomplete/blocked statuses below describe earlier attempts and are
superseded by the completion evidence above.

#### Latest session verification — 2026-10-10

Step 1 remains the first incomplete step. Reviewed the plan, applicable
contributor instructions, relevant backend guides and existing diffs before
editing. The prepared behavior map, fixed cases, target contract and phase
reconciliation match the inspected implementation. This session changes only
this record, the plan and baseline record; all other pre-existing work is
preserved, including greeting/help implementation and tests.

- Required backend discovery command from `AGENTS.md`, bounded with
  `timeout 50s` in the sandbox: exit **124**, stalled at
  `test_school_rating_service.SchoolRatingApiTests.test_missing_consent_is_422`.
  Log: `/tmp/llm-first-step1-session-backend-sandbox.log`.
- Exact required command outside the sandbox: **382 tests in 63.124s**,
  exit **1**, **three failures / one error**. Log:
  `/tmp/llm-first-step1-session-backend-escalated.log`. Exact blockers:
  `test_general_knowledge_rag.GeneralKnowledgeRagTests.test_combined_answer_keeps_school_and_general_sources_distinct`
  (`general_knowledge` instead of `combined_evidence`);
  `test_general_knowledge_rag.GeneralKnowledgeRagTests.test_montessori_and_spark_are_explained_as_different_concepts`
  (`comparison` instead of `general_knowledge`);
  `test_stage_flow.PipelineTests.test_stage1_rejects_invalid_llm_value_and_falls_back`
  (`KeyError: extraction_method`);
  `test_web_rag.WebRagPilotTests.test_incremental_run_checkpoints_and_skips_completed_pages`
  (`school_attempts` 1 instead of 0). Source review confirms optional live
  intent routing in the first three cases and a fixed 2026-08-10 retrieval
  fixture older than the production 30-day refresh interval in the last.
  These are pre-existing blockers; no runtime/test repair outside Step 1
  scope was made, and prior diagnostics do not replace required verification.
- Documented four-module focused command below: **30 pass in 3.002s**.
  Log: `/tmp/llm-first-step1-session-focused.log`.
- `make eval-check`: **29 pass in 4.533s**, plus validate-only RAGAS fixture
  validation. Log: `/tmp/llm-first-step1-session-eval.log`.
- Two documented captures, `/tmp/llm-first-step1-session-baseline-a.json`
  and `-b.json`, match the stored artifact byte-for-byte. Capture syntax,
  25 unique conversations / 36 sequential bounded turns with nonempty checks,
  local links, and zero recorded provider calls/persistent writes validate.
- `git diff --check`, scope/correctness/secrets review and preservation hashes
  pass. Hash record: `/tmp/llm-first-step1-session-start-hashes.json`.

**Step 1 remains incomplete; nothing staged and no completion commit.** Next:
resolve the four required regression blockers, then finalize only Step 1.
Step 2 has not begun. Live-provider quality, numeric operational budgets and
target-dataset execution remain later-step work.

#### Step 1 scope review and required checks — 2026-10-10

Inspected status/diffs before editing: nine modified tracked files and five
untracked artifacts. Step 1 is still the first incomplete step. Re-read the
plan, contributor instructions and relevant backend folder guides; reviewed
the prepared entry-point/routing/substitution/model/state/dependency map,
fixed evaluation dataset and target contract against the implementation.
Existing phase reconciliation is applicable; Implementation 3 remains history.
This session updates only this progress record, the plan and baseline record.

- Required backend discovery command from `AGENTS.md`, bounded by `timeout
  75s` in the sandbox: exit **124** at
  `test_school_rating_service.SchoolRatingApiTests.test_missing_consent_is_422`.
  Log: `/tmp/llm-first-step1-review-backend.log`.
- Exact required command rerun outside the sandbox: **382 tests in 63.621s**,
  exit **1**, **two failures / one error**. Log:
  `/tmp/llm-first-step1-review-backend-escalated.log`. Exact blockers:
  `test_general_knowledge_rag.GeneralKnowledgeRagTests.test_combined_answer_keeps_school_and_general_sources_distinct`
  (`general_knowledge` instead of `combined_evidence`);
  `test_stage_flow.PipelineTests.test_stage1_rejects_invalid_llm_value_and_falls_back`
  (`KeyError: extraction_method`);
  `test_web_rag.WebRagPilotTests.test_incremental_run_checkpoints_and_skips_completed_pages`
  (`school_attempts` 1 instead of 0). The HTTP test and Montessori/SPARK pass.
  The affected runtime/tests were not changed by the baseline step. Source
  review reconfirms unisolated optional-provider routing and the checkpoint's
  fixed 2026-08-10 retrieval date versus the production 30-day refresh interval;
  prior diagnostic passes below do not establish a passing required suite.
- Documented four-module focused command: **30 pass in 2.284s**. Log:
  `/tmp/llm-first-step1-review-focused.log`.
- `make eval-check`: **29 pass in 4.278s**, plus validate-only RAGAS fixture
  validation. Log: `/tmp/llm-first-step1-review-eval.log`.
- Two documented captures, `/tmp/llm-first-step1-review-baseline-a.json` and
  `-b.json`, match the stored artifact byte-for-byte. Validation confirms
  25 unique conversations / 36 sequential bounded turns with nonempty checks,
  capture Python syntax and baseline/plan local links. Captured provider calls
  and persistent writes are zero; injected traces do not measure live quality.
- `git diff --check` passes. Diff reviewed for scope, correctness, accidental
  changes and secrets. Initial hashes verify every other pre-existing changed
  file is unchanged; greeting/help code, tests and README additions preserved.

**Step 1 remains incomplete; nothing staged and no completion commit.** The
baseline artifacts meet the map/dataset/target-contract requirements, but the
required regression check remains unmet. Resolve the exact blockers before
finalizing Step 1. No runtime repair outside baseline scope was made. Step 2
has not begun; live-provider quality, operational budgets and target-dataset
execution remain later-step work.

#### Verification rerun — 2026-10-10

Inspected git status and existing diffs before editing. Re-read applicable
guidance and relevant backend documentation; checked the prepared map against
HTTP/service entry points, routing, answer substitution, nested models, tool
dependencies, state writes and contracts. The map, dataset and target contract
are prepared; required regression verification remains unmet. Only this record,
the repository plan and baseline record changed in this session.

- Required backend command in `AGENTS.md`, bounded with `timeout 90s` inside
  the sandbox: exit **124**, stalled at
  `test_school_rating_service.SchoolRatingApiTests.test_missing_consent_is_422`.
  Log: `/tmp/llm-first-step1-final-audit-backend.log`.
- Same required command outside the sandbox: **382 tests in 63.038 seconds**,
  exit **1**, **two failures / one error**. Log:
  `/tmp/llm-first-step1-final-audit-backend-escalated.log`. Exact blockers:
  `test_general_knowledge_rag.GeneralKnowledgeRagTests.test_combined_answer_keeps_school_and_general_sources_distinct`
  (`general_knowledge` instead of `combined_evidence`);
  `test_stage_flow.PipelineTests.test_stage1_rejects_invalid_llm_value_and_falls_back`
  (`KeyError: extraction_method`);
  `test_web_rag.WebRagPilotTests.test_incremental_run_checkpoints_and_skips_completed_pages`
  (`school_attempts` 1 instead of 0). Montessori/SPARK passes. Prior diagnoses
  below explain optional-provider and fixture-date dependencies; these failures
  were not caused by baseline changes. No affected runtime or test file changed.
- Documented four-module focused command below: **30 pass in 2.122 seconds**.
  Log: `/tmp/llm-first-step1-final-audit-focused.log`.
- `make eval-check`: **29 pass in 3.609 seconds**, plus validate-only RAGAS
  fixture validation. Log: `/tmp/llm-first-step1-final-audit-eval.log`.
- Two documented captures, `/tmp/llm-first-step1-final-audit-baseline-a.json`
  and `-b.json`, match each other and the stored artifact byte-for-byte.
  Validation confirms 25 unique cases / 36 sequential bounded turns with
  nonempty checks, Python syntax, local links, and zero captured provider
  calls/persistent writes.
- `git diff --check` passes. Reviewed diffs for correctness, scope, accidental
  changes and secrets. Initial/final file hashes confirm every other pre-existing
  changed file is preserved. No credentials or real family/transcript data added.

**Step 1 remains incomplete; nothing staged and no completion commit.** Resolve
the three required regression blockers before finalizing Step 1. No runtime/test
repair outside baseline scope was made. Step 2 has not begun. Live-provider
quality, numeric budgets and target-dataset execution remain later-step work.

#### Current audit — 2026-10-10

Re-read the active plan, applicable contributor guidance and backend folder
guides; reviewed the existing map against request guards, intent routing,
supervisor tool selection/composition, fresh-copy preference tools, memory
writes and domain contracts. Step 1 remains the first incomplete step. Its
map, fixed dataset and target contract are prepared, but required regression
verification still fails. This session changes only this record, the plan and
baseline record; all other pre-existing work is preserved.

- Exact required backend command from `AGENTS.md`: sandbox run stalled at
  `test_school_rating_service.SchoolRatingApiTests.test_missing_consent_is_422`
  and was interrupted (exit 130). Log:
  `/tmp/llm-first-step1-audit-backend.log`.
- Same command outside the sandbox: **382 tests in 67.420 seconds**, exit 1,
  **2 failures / 1 error**. Log:
  `/tmp/llm-first-step1-audit-backend-escalated.log`. Exact blockers:
  `test_general_knowledge_rag.GeneralKnowledgeRagTests.test_combined_answer_keeps_school_and_general_sources_distinct`
  (`general_knowledge` instead of `combined_evidence`);
  `test_stage_flow.PipelineTests.test_stage1_rejects_invalid_llm_value_and_falls_back`
  (`KeyError: extraction_method`);
  `test_web_rag.WebRagPilotTests.test_incremental_run_checkpoints_and_skips_completed_pages`
  (`school_attempts` 1 instead of 0). The previously failing Montessori/SPARK
  case passed. The routing/extraction cases depend on optional provider
  behavior; the checkpoint fixture is older than the refresh interval, as
  diagnosed below. No affected runtime or test file was changed by Step 1.
- Documented four-module focused command: **30 pass in 2.066 seconds**.
  Log: `/tmp/llm-first-step1-audit-focused.log`.
- `make eval-check`: **29 pass in 4.592 seconds**, plus validate-only RAGAS
  fixture validation. Log: `/tmp/llm-first-step1-audit-eval.log`.
- Two documented captures, `/tmp/llm-first-step1-audit-baseline-a.json` and
  `-b.json`, match the stored artifact byte-for-byte. Python syntax, 25 unique
  conversations / 36 sequential bounded turns with checks, zero captured
  provider calls/persistent writes and baseline/plan local links validate.
- `git diff --check` passes. Diff reviewed for correctness, scope and secrets;
  file hashes confirm unrelated existing changes are unchanged.

**Step 1 remains incomplete; nothing staged and no completion commit.** Next:
resolve the three required regression blockers, then finalize Step 1. Step 2
has not started. Live-provider performance, numeric operational budgets and
target-dataset execution remain deferred to the later documented steps.

#### Latest verification — 2026-10-10

Inspected the nine modified tracked files and five untracked Step 1 artifacts
before editing. Reviewed the behavior map against HTTP/service entry points,
supervisor composition and routing, tool state copies, memory and feedback
writes, and optional model defaults. The existing map, target contract and
fixed dataset satisfy the baseline artifact requirements; required regressions
still prevent completion. Only this record, the repository plan and baseline
record were edited in this session. All other existing changes are preserved,
including the unrelated greeting/help implementation and tests.

- Required backend command from `AGENTS.md`, bounded in the sandbox with
  `timeout 90s`: exit **124**, stalled at
  `test_school_rating_service.SchoolRatingApiTests.test_missing_consent_is_422`.
  Log: `/tmp/llm-first-step1-current-tests.log`.
- Outside-sandbox rerun of the exact required command: **382 tests in
  67.692 seconds**, exit **1**, **3 failures / 1 error**. Log:
  `/tmp/llm-first-step1-current-tests-escalated.log`. Exact blockers:
  `test_general_knowledge_rag.GeneralKnowledgeRagTests.test_combined_answer_keeps_school_and_general_sources_distinct`
  (`general_knowledge` instead of `combined_evidence`);
  `test_general_knowledge_rag.GeneralKnowledgeRagTests.test_montessori_and_spark_are_explained_as_different_concepts`
  (`comparison` instead of `general_knowledge`);
  `test_stage_flow.PipelineTests.test_stage1_rejects_invalid_llm_value_and_falls_back`
  (`KeyError: extraction_method`);
  `test_web_rag.WebRagPilotTests.test_incremental_run_checkpoints_and_skips_completed_pages`
  (`school_attempts` 1 instead of 0). These are the previously diagnosed
  provider-dependent routing/extraction and date-dependent checkpoint cases;
  no affected runtime or test file was changed by the baseline step.
- The same four-module focused command below: **30 pass in 1.967 seconds**.
  Log: `/tmp/llm-first-step1-current-focused.log`.
- `make eval-check`: **29 pass in 3.606 seconds**, plus validate-only RAGAS
  fixture validation. Log: `/tmp/llm-first-step1-current-eval.log`.
- Two documented captures, `/tmp/llm-first-step1-current-baseline-a.json` and
  `-b.json`, match each other and the stored artifact byte-for-byte. Python
  syntax, 25 unique conversations / 36 sequential bounded turns with checks,
  zero captured provider calls/persistent writes, and baseline/plan local links
  validate. `git diff --check` passes; diff reviewed for scope and secrets.

**Step 1 remains incomplete; nothing staged and no completion commit.** The
next action is to resolve the four required regression blockers before
finalizing Step 1. Step 2 has not begun. Live-provider performance and numeric
operational budgets remain unmeasured; target-dataset execution is Step 6 work.

#### Resumed verification — 2026-10-10

Reviewed all existing Step 1 artifacts against contributor/folder guidance and
the backend implementation. No runtime, test, provider, public-contract or
rollout change. The pre-existing greeting/help work remains untouched.

- Required command (exact command remains in `AGENTS.md`): sandbox run again
  stalled at
  `test_school_rating_service.SchoolRatingApiTests.test_missing_consent_is_422`
  and was interrupted, exit 130. Log:
  `/tmp/llm-first-step1-resume-tests.log`.
- Outside-sandbox rerun of that same command: **382 tests in 59.700 seconds**,
  exit 1, **2 failures / 1 error**. Log:
  `/tmp/llm-first-step1-resume-tests-escalated.log`. Exact blockers:
  `test_general_knowledge_rag.GeneralKnowledgeRagTests.test_combined_answer_keeps_school_and_general_sources_distinct`
  (`general_knowledge` versus `combined_evidence`);
  `test_stage_flow.PipelineTests.test_stage1_rejects_invalid_llm_value_and_falls_back`
  (`KeyError: extraction_method`);
  `test_web_rag.WebRagPilotTests.test_incremental_run_checkpoints_and_skips_completed_pages`
  (`school_attempts` 1 versus 0). The Montessori/SPARK case passes this time.
- Diagnostic only: run the three routing/extraction cases listed in the prior
  attempt with `OPENAI_INTENT_CLASSIFICATION_ENABLED=false`,
  `OPENAI_GROUNDED_EXPLANATIONS_ENABLED=false`, and
  `OPENAI_WEB_RAG_ANSWERS_ENABLED=false`, using the documented `PYTHONPATH` and
  `.venv/bin/python -m unittest -v` with their fully qualified test IDs:
  **3 pass in 0.009 seconds**. The extraction test itself enables its injected
  extractor. Unisolated optional routing can bypass extraction or change intent;
  these diagnostic passes are not a passing unchanged required command.
- Diagnostic only: run the checkpoint case via `unittest.TextTestRunner`,
  wrapping its imported `run_incremental` to pass
  `now=datetime(2026, 8, 10, tzinfo=timezone.utc)`: **1 pass in 0.004 seconds**.
  The fixture's `retrieved_at` is 2026-08-10; the current date exceeds the
  production 30-day refresh interval, correctly triggering a refresh.
  This diagnosis leaves the existing regression test and refresh rules intact.
- Two runs of the documented capture command to
  `/tmp/llm-first-step1-resume-baseline-a.json` and `-b.json` compare
  byte-for-byte with each other and `output/llm_first_step1_baseline.json`.
  JSON validation confirms 25 unique cases, 36 sequential valid turns, nonempty
  checks and synthetic-only scope; capture Python syntax parses successfully.
- Same four-module focused command recorded below: **30 pass in 1.877 seconds**.
  Log: `/tmp/llm-first-step1-resume-focused.log`.
- `make eval-check`: **29 pass in 4.111 seconds**, plus validate-only RAGAS
  fixture check. `git diff --check`: pass. Step diff reviewed for scope and
  secrets; no credentials or real family/chat data added.

Required regressions remain unmet in unchanged runtime/tests. This baseline
step does not authorize changing conversation routing or ingestion behavior,
and no such repair was made. **Step 1 stays incomplete; nothing staged and no
completion commit.** Resolve the required-check blockers before finalizing
Step 1; Step 2 has not begun. Live-provider quality and operational budgets
remain unmeasured.

#### Prior attempt — 2026-10-10

[Architecture record](llm-first-baseline.md) inventories chat entry points,
semantic short circuits, substitutions, nested model calls, dependencies and
state writes; specifies the target contract and reconciles pre-existing
greeting/help work without modifying it. Fixed curated input:
`resources/llm_first_conversation_evaluation.json` (25 conversations / 36 turns).
Reproducible injected capture: `output/llm_first_step1_baseline.json`, generated
by `scripts/capture_llm_first_baseline.py`. Two captures compare byte-for-byte;
JSON uniqueness/turn/check validation and Python syntax parsing pass.

Verification from repository root:

- Required unchanged backend command in `AGENTS.md`: sandbox attempt stalled
  at `test_school_rating_service.SchoolRatingApiTests.test_missing_consent_is_422`
  and was interrupted (130). Outside-sandbox rerun completed **382 tests in
  67.103 seconds**, exit 1, **3 failures / 1 error**. Exact blockers:
  `test_general_knowledge_rag.GeneralKnowledgeRagTests.test_combined_answer_keeps_school_and_general_sources_distinct`
  (`general_knowledge` versus `combined_evidence`);
  `test_general_knowledge_rag.GeneralKnowledgeRagTests.test_montessori_and_spark_are_explained_as_different_concepts`
  (`comparison` versus `general_knowledge`);
  `test_stage_flow.PipelineTests.test_stage1_rejects_invalid_llm_value_and_falls_back`
  (`KeyError: extraction_method`);
  `test_web_rag.WebRagPilotTests.test_incremental_run_checkpoints_and_skips_completed_pages`
  (`school_attempts` 1 versus 0). Log: `/tmp/llm-first-step1-backend-tests-escalated.log`.
  These tests/runtime files were not edited by this step; no broad regression
  repair was attempted. Their causes remain unclassified.
- Bounded outside-sandbox single school-rating reproduction passed 1 test in
  0.010 seconds; the initial stall was not reproduced there.
- `PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline
  .venv/bin/python -m unittest -v
  SystemCode.src.backend.tests.test_chat_greetings
  SystemCode.src.backend.tests.test_conversation_context
  SystemCode.src.backend.tests.test_conversation_supervisor
  SystemCode.src.backend.tests.test_conversation_validation`: **30 pass**,
  1.862 seconds. Includes pre-existing greeting/help assertions.
- `make eval-check`: **29 pass**, plus validate-only RAGAS fixture check.
- `git diff --check`: pass; reviewed step files for scope/secrets; frontend
  untouched. No credentials, real family data or transcripts added.

No live-provider run or latency/token/cost measurement is required/claimed for
this architecture baseline. Target dataset execution is deferred to Step 6.
Optional Ruff is not installed (`No module named ruff`); syntax validation
passed and repository instructions mandate no Ruff check.

**Step 1 remains incomplete. No staging or completion commit.** Required next
action: obtain a passing required backend regression run, classifying/resolving
the four listed failures within authorized scope before marking Step 1 complete.
Then update evidence and commit only this step. Next implementation step after
completion is Step 2, bounded conversation context.

# Implementation 3 — conversational-readiness plan (historical)

## Current rollout configuration — 2026-10-07

Following the completed readiness review and the user's confirmation that the
code works, the user authorized making the full-conversation supervisor the
default. `CONVERSATION_AGENT_MODE` now resolves missing, blank, and invalid
values to `agent`. An explicit `deterministic` value restores the existing
controller; `shadow` retains its existing behavior. Restart the backend after
changing deployment configuration. Removing the variable now enables agent
mode and is no longer a rollback operation.

The context-local fallback override still forces both graph entry points to
deterministic mode, so rejected or unavailable agent execution retains the
existing controller fallback without recursive graph entry. No frontend or
public-contract change is part of this rollout. The Implementation 3 steps and
decision records below describe the earlier opt-in rollout and remain historical.

Rollout verification: 24 configuration, model-factory, selected-school endpoint,
and conversation-mode tests pass, including unset-mode dispatch and exactly-once
fallback with both graph entries disabled. Another 21 supervisor, validation,
and operational tests pass. `git diff --check` passes. Full-suite attempts did
not complete in this environment; the bounded run exited after 120 seconds.
This change does not claim a fresh complete-suite or live-provider evaluation.

This historical plan was the source of truth for taking the backend-only
full-conversation supervisor from implemented-but-no-go to a tested, grounded,
operationally ready agent. It follows the completed
[Implementation 2 archive](impl2-agent-step2.md).

## Session protocol (historical Implementation 3)

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
   selection, and at most 5% unexpected fallback. The raw fallback rate still
   includes reviewed clarification and hostile-input cases that are required
   to fail closed.
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
| 8. Decide opt-in rollout | complete | 2026-09-06 evidence below: all eight gates pass; explicit backend opt-in approved with immediate deterministic rollback |

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

## Step 8 rollout decision

Recorded on 2026-09-06. The decision is **go for an explicit backend-only
opt-in** to the full-conversation agent. This does not authorize changing the
default, enabling it for every deployment, or modifying the frontend. The
decision is supported by the following gate review:

| Gate | Decision evidence |
|---|---|
| 1. Backend compatibility | [Step 2](#step-2-http-integration-evidence) repaired the stalled HTTP boundary and passed the complete suite; [Step 7](#step-7-operational-readiness-evidence) most recently passed all 289 backend tests without exclusions. |
| 2. Contract stability | Steps 2, 5, 6, and 7 reproduce the complete OpenAPI SHA-256 `2cb0812711be9f77034f5cfd2547e71051a855cc2c5784ad050117c49dc6b405`; every step reports an empty frontend diff. |
| 3. Deterministic safety | [Step 5](#step-5-conversational-correctness-evidence) verifies bounded validation and exactly-once fallback; Step 7 verifies deterministic laziness and one valid fallback response for timeout, tool, dependency, and validation failures. |
| 4. Conversation correctness | [Step 4](#step-4-multi-turn-evaluation-evidence) covers 54 reviewed turns, all 15 capabilities, state transitions, ambiguity, pending flows, and hostile inputs; Step 5 passes the complete scripted set with authoritative parity. |
| 5. Grounding | Steps 5 and 6 establish server-resolved citations, scoped selected-school evidence, fail-closed unavailable evidence, and 100% grounding and citation validity in the passing live reports. |
| 6. Live staged execution | [Step 6](#step-6-completion) records two consecutive passing 54-turn reports, `output/conversation_agent_evaluation_run_12.json` and `output/conversation_agent_evaluation_run_13.json`, with 100% scored correctness and 0% unexpected fallback. Step 7 adds a third passing run, `output/conversation_agent_evaluation_run_14.json`. The 14.81% raw fallback is exactly the eight reviewed cases required to fail closed. |
| 7. Operational behavior | Step 7 verifies bounded concurrent execution in all modes, clean injected failures, exactly-once answer and optional memory writes, shadow isolation, and telemetry free of seeded sensitive values. |
| 8. Rollout control | `get_conversation_agent_mode` fails closed to `deterministic` for missing or invalid configuration. Step 7 verifies deterministic, shadow, and agent behavior through the unchanged API; no frontend change is required. |

### Opt-in and rollback

Before opting in, run the read-only preflight command documented in
[`scripts.md`](scripts.md) from the repository root and require all six checks
to pass. The backend environment must contain a usable `OPENAI_API_KEY` and
the already-preflighted OneMap, catalogue, policy, and evidence inputs.
`OPENAI_WEB_RAG_MODEL` and `OPENAI_WEB_RAG_TIMEOUT_SECONDS` remain optional;
their validated defaults are `gpt-4o-mini` and eight seconds.

To opt in for a deliberately selected backend deployment, set
`CONVERSATION_AGENT_MODE=agent` in that deployment's backend environment and
restart the backend process. Do not expose this variable to the browser and do
not change `WEB_RAG_ANSWER_MODE`; the full-conversation supervisor owns model
orchestration for the request.

For immediate rollback, set `CONVERSATION_AGENT_MODE=deterministic` and restart
the backend process. Under the subsequent 2026-10-07 rollout, removing the
variable, leaving it blank, or supplying an invalid value enables agent mode.
The existing API contract and persisted profile shape do not require migration
in either direction.

The decision-session verification reran the unchanged complete backend command
and passed all 289 tests in 61.566 seconds. Runs 12, 13, and 14 were parsed
again: each contains 54 cases, reports `passed: true`, and has 0% unexpected
fallback. Regenerated canonical OpenAPI still has SHA-256
`2cb0812711be9f77034f5cfd2547e71051a855cc2c5784ad050117c49dc6b405`.
`git diff --check` passed, and the frontend diff remains empty.

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
- 2026-09-06 — Complete Step 8 with a go decision for explicit backend-only
  opt-in. Every readiness gate is backed by complete-suite, contract,
  deterministic-fallback, multi-turn, grounding, live-staged, operational, and
  rollout-control evidence. Opt-in requires a passing preflight followed by
  `CONVERSATION_AGENT_MODE=agent` for the selected backend deployment;
  rollback is `CONVERSATION_AGENT_MODE=deterministic`. Keep deterministic as
  the repository and deployment default, and require separate approval for
  any default-on rollout.

## Next step

LLM-first Step 1 remains the only active step: resolve the required-check
blockers above, rerun checks, and finalize the baseline; do not start Step 2.

Implementation 3 is complete. The separately authorized 2026-10-07 rollout
makes agent mode the default while preserving the explicit deterministic
rollback path. No implementation step remains.
