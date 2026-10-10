# Staged HTTP integration — Step 6 (school-demo complete)

`POST /api/preferences/llm-first` uses `PreferenceService.handle_llm_first`
with the bounded context, structured transaction, model loop and validated
response layer. It bypasses the legacy greeting/help and closest-keyword gates.
`/api/preferences` retains its existing rollout pending Step 7. Response fields
include profile, understood, ready_to_search, question, citations and answer_id.
Citation chunk_id aliases preserve UI rendering. Model/tool failures return the
fixed service message, original submitted profile and no memory/history commit.
Context/ID errors return 422/404; overlapping, stale or forgotten sessions 409;
storage failures return a safe 503. No provider exception text reaches HTTP.

The additive remember_conversation field defaults false. Either retention
consent requires a UUID. See [the prior boundary decision](llm-first-context.md).
Every supplied UUID acquires a lease and compares submitted state to the last
committed profile; only consented dialogue enters the model. A validated public
response commits the profile/exchange once and makes at most one authorized
preference-memory write. Finally releases leases on errors and cancellation.
Forget serializes history invalidation and preference deletion with commit.
Single-worker RAM expiry/eviction and restart limitations remain. Stateless
requests have no cross-request state versioning. Separate SQLite stores are
not atomic together: an orphan privacy-safe answer metadata row is possible
when the subsequent memory write fails. No frontend history opt-in is shipped.

## Evaluation

The fixed 25-conversation/36-turn dataset remains unchanged. The user authorized
a school-project acceptance profile on 2026-10-10: school-demo requires 75%
completion across all 25 cases, zero critical state/fee/eligibility errors and
all eight injected integrity checks. Greeting, help, mixed request, stateless
clarification and forget must pass. Other conversation failures are reported.
Strict scoring retains 95% and the original required conversations. Runtime
argument, numeric, citation, state and execution validation remain enforced.

```bash
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python -m SystemCode.src.backend.scripts.evaluate_llm_first_conversation \
  --staged --output /tmp/llm-first-live.json
```

This capture uses the configured model, synthetic repository-owned schools,
existing deterministic evaluator, synthetic distances, a hostile school passage,
and the configured general-guidance retriever. It does not measure production
OneMap or Neo4j availability. Each ordinary turn records server tool results,
model-call/tool metadata, tokens, time, answer and state for semantic review.
Fault/concurrency cases require the named injected regression checks. It exits
2 and marks passed false until separate review/scoring is complete: successful
HTTP responses alone cannot establish task completion or prose grounding.
Reports contain only synthetic fixture inputs and outputs and belong in /tmp
until reviewed; provider exceptions are reduced to safe categories.

`tests/test_llm_first_http.py` verifies served model-first behavior, legacy and
OpenAPI compatibility, state/history/memory writes, failure rollback, consent,
isolation, overlap/forget, storage failure and cancellation. Existing response,
loop, context and tool tests provide adversarial integrity coverage.

Step 6 requires the selected evaluation profile to pass; school-demo completion
does not claim strict evaluation or production readiness. See [backend progress](agents.md) for the current run and blockers.
Numeric production latency/cost/failure budgets and rollout remain Step 7.

## Continuation findings

Live evaluation required explicit capability descriptions and preference attribute
enums. Omitted importance now stages one pending preference using the existing
profile shape; explicit follow-up resolution preserves desired direction. Multiple
pending choices and unresolved replacement of a required choice are rejected.
`needs_input` mutation results may support acknowledgements through validated
`/data/staged_profile/` scalars; other missing-input data remains unsupported.
These are model/tool contract corrections within Step 6, with no calculation or
legacy-controller changes. Capture reports include synthetic model output/tool
arguments and fixed-category validation feedback. Do not use this capture wrapper
for real family inputs or production telemetry.

The earlier live captures failed strict evaluation. The latest school-demo
scoring passes at 80% overall / 70.59% ordinary completion with all eight integrity
cases passing. Step 6 is complete for the authorized demo scope; see backend
progress for failed conversations, commands, reviewed limits and verification.

## Repair and scoring contract

The model loop prevalidates arguments and allows one correction in the original
turn budget; direct tool validation stays strict. Invalid arguments cannot
execute, and all attempted calls count toward limits. Newly staged pending choices
need a later turn before resolution. Scalar support paths are bounded model
context aids, with server results remaining authoritative. Recent exchanges
retain actual speaker order. Current validated preference fields can support
unchanged acknowledgements through context:current; arbitrary profile metadata
and school facts are excluded. Shared spans need validated support for every
reported number. Pending state without a question receives bounded repair.

Capture runs the eight injected integrity checks. To score reviewed synthetic
turns, supply the capture and a JSON review with capture_sha256 and turns keyed
case_id:turn. Each turn requires task, tool_use, state, grounding, critical_error
booleans and an evidence reason. Complete dataset and matching hash are mandatory:

```bash
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python -m SystemCode.src.backend.scripts.evaluate_llm_first_conversation \
  --staged --capture /tmp/step6-finish-live5.json \
  --review /tmp/step6-finish-review5.json --output /tmp/step6-finish-scored5.json
```

Scoring uses manual semantic assessment, not response status as task completion.
The earlier strict result was 76%; see the completion record for the school-demo result. The capture/scoring reports
are synthetic-only and must not be reused as production transcript logging.

Select the explicitly authorized demo profile when scoring:

```bash
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python -m SystemCode.src.backend.scripts.evaluate_llm_first_conversation \
  --staged --capture /tmp/step6-school-live.json \
  --review /tmp/step6-school-review.json --evaluation-profile school-demo \
  --output /tmp/step6-school-scored.json
```

Reports retain the original gates and record effective threshold, required
conversations, ordinary live completion and failed cases. SHA-bound complete
manual reviews remain required; HTTP success alone cannot pass scoring.

Latest evidence: `/tmp/step6-school-live.json`, `/tmp/step6-school-review.json`
and `/tmp/step6-school-scored.json` (scoring exit 0). Strict acceptance remains
unmet; the endpoint remains explicitly selectable pending Step 7.
