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
| 1. Re-establish the backend readiness baseline | pending | Bounded transport reproduction, test inventory, staged prerequisite inventory, OpenAPI/frontend snapshot |
| 2. Repair the backend HTTP integration-test boundary | pending | Formerly blocked API tests and complete backend suite pass |
| 3. Make staged execution preflighted and reproducible | pending | Preflight tests, documented commands, configured preflight success |
| 4. Expand multi-turn conversational evaluation | pending | Reviewed single-turn, multi-turn, and adversarial case coverage |
| 5. Close conversational correctness gaps | pending | Focused and complete suites plus injected evaluation pass |
| 6. Run live staged evaluation and tune safely | pending | Two consecutive complete staged reports meet thresholds |
| 7. Verify backend operational readiness | pending | Mode/failure exercises, privacy audit, compatibility gates |
| 8. Decide opt-in rollout | pending | Evidence-linked go/no-go and rollback instructions |

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

## Next step

Step 1 — Re-establish the backend readiness baseline. Do not begin Step 2 in
the same implementation session.
