# LLM-first conversation plan

Date: 2026-10-10
Status: Steps 1–7 complete under school-demo acceptance; rollout observation next

## Objective

Every valid chat message should reach the LLM before any application decision
about its meaning or conversational reply. The LLM should understand the
message in context, ask clarifying questions when needed, choose and combine
tools, and compose the response from the information available.

The backend remains authoritative for school records, preference state,
ranking, eligibility, fees, subsidies, distances, and citations. These become
capabilities the LLM can use, with validated inputs and structured outputs.

Success means a user can phrase a request naturally, refer to earlier turns,
and ask for several related actions without matching a predefined question or
being restricted to a single server-classified intent.

## Relationship to existing plans

The [backend readiness plan](../SystemCode/src/backend/doc/agents.md) records
the existing supervisor's implementation and rollout. Agent mode is already
the default, but that supervisor still delegates substantial conversational
control to rules and predefined answers.

This document proposes a new architecture phase. It does not reopen or claim
completion of the previous readiness work. Before implementation, update the
backend's active progress record and contributor guidance to identify this
phase and its next step. The previous plan freezes frontend and public-contract
changes; this phase must explicitly record any minimal contract change needed
for conversation history before implementing it. Keep completed rollout
evidence available as historical evidence.

The user requested this working plan in repository-level `docs/`. Durable
backend implementation decisions should also be linked from the backend
documentation when implementation begins.

## Current gaps

| Current behavior | Location | Required change |
|---|---|---|
| Greetings and help requests return predefined text before the model runs | `services/preference_service.py` | Let the LLM respond using application capabilities and current context |
| Keyword rules decide many intents without a model call | `pipeline/stage1/intent_router.py` | Remove rules as the authority for interpreting chat in the new flow |
| Server intent determines route and filters the tools exposed to the model | `agents/supervisor.py` | Let the model choose from the registered capabilities appropriate to its access |
| A tool call is mandatory, including for turns that need no external facts | `agents/supervisor.py` | Allow direct greetings, capability explanations, and clarification questions |
| Tools return answer candidates, and some final answers are replaced with those candidates | `agents/tools.py`, `agents/supervisor.py` | Return structured results and let the LLM compose grounded wording |
| Grounding checks use a vocabulary allowlist | `agents/supervisor.py` | Validate factual values, entity attribution, and citations; evaluate unsupported claims separately |
| Preference and calculation tools largely reuse the original message with no model-selected arguments | `agents/contracts.py`, `agents/tools.py` | Accept typed preference patches, scenario overrides, and operation choices |
| Tool context is prepared before model reasoning, including rankings and geocoding | `services/preference_service.py` | Prepare a small initial context and load additional facts through tools |
| Saved memory stores preference profiles rather than dialogue history | `services/conversation_memory_service.py`, `agents/contracts.py` | Add bounded conversational context with clear session and retention semantics |
| Agent rejection may run the deterministic conversation controller | `agents/validation.py` | Make new-flow failures explicit instead of serving a scripted domain answer |

Paths in this table are relative to `SystemCode/src/backend/`.

## Target flow

```mermaid
flowchart TD
    U[User message] --> V[Validate request and resolve session]
    V --> C[Build bounded conversation and application context]
    C --> M[LLM understands message and chooses next action]
    M -->|Needs context or action| T[Validate and execute registered tools]
    T --> R[Structured results and evidence]
    R --> M
    M -->|Answer or clarification| A[LLM composes response]
    A --> G[Validate response, facts, citations and staged state]
    G -->|Valid| S[Commit state once and return response]
    G -->|Repairable within limits| M
    G -->|Unavailable or limits exhausted| E[Explicit service failure]
```

Only request-shape validation, session resolution, and access enforcement
precede the LLM. They do not classify a valid message or choose its reply.
Non-chat operations such as restoring or forgetting saved preferences can
remain ordinary API operations.

### Initial context and conversation history

Provide the newest message, a bounded recent-turn window, a summary of older
turns when needed, saved preferences, unresolved preference decisions,
selected school IDs and names, family inputs, and application capabilities.
Treat dialogue summaries as conversational context, never as authoritative
school or policy evidence. Reload current facts through repositories and tools.

The existing context has no transcript field. Decide the history contract in
Step 2: reuse the anonymous-session mechanism where suitable, or introduce the
smallest explicit session/history extension. Define behavior for anonymous
stateless requests. Include only the data needed for the current task and
bound messages, summaries, tool results, and total model context.

Preference retention and transcript retention are separate decisions. Preserve
the existing opt-in preference-memory behavior; do not silently turn it into
persistent transcript storage. Specify history expiry, session isolation,
forget behavior, and concurrent-turn handling.

### Model behavior

- Interpret the full message, including multiple requests and references to
  prior turns. Do not require a single intent classification before execution.
- Answer greetings and explain capabilities directly from application context.
- Ask a specific clarification when a reference or required input is ambiguous.
- Use tools for school facts, policy claims, calculations, and state changes.
- Call additional tools when earlier results reveal missing information.
- Distinguish school-published claims, authoritative policy, estimates, and
  unknown information. Missing evidence must not become a negative claim.
- Compose the final answer naturally, including relevant citations and next
  actions. Treat retrieved content as evidence, not instructions.

### Tool contracts

Reuse the existing repositories, retrieval adapters, and deterministic
algorithms. Refactor the conversational wrappers rather than reimplementing
the underlying domain logic.

| Capability | Model-selected inputs | Server-owned result |
|---|---|---|
| Read school facts | Valid school IDs and supported fields | Records, source, missing fields, catalogue version |
| Search school evidence | School IDs, focused query | Passages, school attribution, citation IDs, retrieval dates |
| Search general guidance | Focused query | Passages, authority, policy dates, citation IDs |
| Search, rank, or compare schools | Supported filters or criteria, valid IDs | Ranked records, scores, matching evidence, trade-offs |
| Calculate fees or scenario | Typed scenario overrides, relevant school IDs | Inputs used, estimates, policy version, assumptions |
| Find nearby schools | Valid location reference and distance constraints | Repository-resolved schools, calculated distances, method |
| Update preferences | Typed patch, required/preferred choices | Validated staged profile, changed fields, unresolved conflicts |
| Reset or continue preferences | Explicit operation and typed resolution | Validated staged state and operation status |

Each tool returns an explicit status such as `ok`, `needs_input`,
`no_evidence`, or `unavailable`, plus structured data and provenance where
applicable. A tool may describe missing inputs; it should not supply the
finished conversational reply. LLM-supplied values represent user choices or
scenario inputs, not trusted school records or arbitrary replacement state.

Resolve school IDs against server data. Validate query scope, supported
fields, ranges, profile patches, and scenario overrides. Preserve support for
the existing catalogue, family, preference, and evidence contracts.

### State and execution

Use request-local working state. After a valid preference update, later tools
in the same turn must read that updated state, including recalculated results
where necessary. A hypothetical scenario must not modify saved family inputs.

Commit the validated final state once, after a valid final response. On an
unrecoverable model, tool, or response failure, discard staged changes. Use
session versioning or equivalent concurrency control so overlapping requests
cannot silently overwrite one another. Shadow runs never commit state.

Bound model iterations, tool calls, mutations, elapsed time, context size, and
output size. Retry only within the overall turn budget; avoid duplicate writes.

### Response validation and failure behavior

Keep structural validation, valid citation references, school attribution,
typed state checks, and checks that reported numbers match calculation results.
Replace the vocabulary allowlist and verbatim answer substitution: shared words
do not prove factual correctness, and natural paraphrasing should be allowed.

For domain answers, retain an internal record of supporting result IDs and
citation IDs. Mechanical checks cannot prove every prose claim is supported;
use adversarial and semantic evaluation to measure that remaining limitation.
Give the LLM a bounded opportunity to repair invalid output using the existing
evidence. Never silently replace its answer with a tool candidate.

For unavailable models or exhausted execution limits, return a brief fixed
service-error message with no fabricated domain answer and no committed state
changes. This is the explicit exception to LLM-authored conversational replies.
The legacy deterministic controller can remain an explicit rollout rollback
mode, separate from the new flow's per-request failure behavior.

## Implementation sequence

Complete one step at a time. Record changed files, verification evidence,
decisions, and the next step before continuing.

### Step 1 — Baseline and architecture record

Inventory all chat entry points, rule-based routing, answer substitutions,
nested model calls, state writes, and tool dependencies. Capture current traces
and representative multi-turn cases. Update the backend progress record to
identify this phase and reconcile the prior session protocol.

Acceptance: a reviewed map of existing behavior, a fixed evaluation dataset,
and a documented target contract. Existing uncommitted greeting/help changes
must be accounted for before modifying the same files.

### Step 2 — Bounded conversation context

Define and implement the session/history strategy, context limits, pending
decision representation, and minimal initial school context. Document any
required public-contract or frontend changes before making them. Move expensive
catalogue evaluation and geocoding behind tools as their replacements land.

Acceptance: tests cover follow-up references, expired or absent history,
session isolation, forget behavior, and current authoritative state overriding
stale dialogue. Valid greetings can reach the model without geocoding or
catalogue ranking.

### Step 3 — Structured tools and staged state

Introduce typed result contracts and model-selected arguments. Separate
preference extraction from the legacy dialogue controller: the supervising
LLM proposes a typed patch and deterministic code validates and applies it.
Expose calculation and retrieval functions without nested answer generation.
Make later tools read the current request-local state.

Acceptance: contract tests reject invalid IDs, forged facts, unsupported fields,
and invalid patches. Integration tests cover update-then-search in one turn,
scenario isolation, read-your-writes behavior, and discard on failure.

### Step 4 — LLM-controlled tool loop

Replace authoritative intent routing with the model/tool loop. Expose the
capabilities permitted for the session without filtering them by message
keywords. Allow zero-tool conversational turns and clarification turns.
Support dependent calls and combined requests within execution limits.

Acceptance: every valid new-flow chat turn invokes the LLM first. Paraphrases
and multi-part requests choose suitable actions without a rule-based route.
Tests verify loop bounds, invalid tool handling, and missing-input recovery.

### Step 5 — LLM responses and grounding

Remove required copying of answer candidates, vocabulary validation, and
school-evidence answer substitution from the new path. Compose from structured
results and evidence; add claim/value and citation validation plus bounded
repair. Replace deterministic per-request fallback with explicit failures.

Acceptance: normal replies, acknowledgements, clarifications, and missing-evidence
explanations are model-authored. Tests reject wrong numeric values, invented
citations, and cross-school attribution. Failed turns commit no changes.

### Step 6 — HTTP integration and evaluation

Wire the new flow through the existing preference service and API. Remove
greeting/help short circuits from this path. Preserve response fields used by
the UI, including profile, readiness, and citations. Ensure one served response,
one state commit, and only the authorized preference-memory write per turn.

Run deterministic integration tests with injected models, then a staged
evaluation with the configured provider. Fake-model tests establish control
flow; live evaluation establishes conversational performance. Reuse RAGAS
where useful for evidence answers, and score tool use and state behavior
separately.

Acceptance: the evaluation cases below pass the agreed rollout gates and the
backend regression suite passes. Record live-provider failures and unavailable
dependencies explicitly; do not report unrun checks as passes.

### Step 7 — Controlled rollout and cleanup

Add an explicit selectable new-flow mode for evaluation and rollout. Compare
against the legacy path in shadow mode with isolated state. Log operational
metadata such as tool names, elapsed time, validation outcomes, failure reason,
and token usage without raw family inputs, transcripts, or secrets.

Enable the new flow as the default after the gates pass. Keep the explicit
legacy rollback mode for a defined observation period, then remove obsolete
chat routing and answer wrappers when no active path needs them. Update the
architecture diagram and backend documentation to describe the shipped flow.

Acceptance: rollback is verified, shadow writes are absent, latency and cost
are recorded, and default-mode traces show the intended LLM/tool behavior.

## Evaluation cases and rollout gates

Use varied wording and multi-turn conversations, including unseen paraphrases.
Avoid tests that require an exact tool order when several valid sequences exist;
check the facts obtained, actions performed, final state, and user-facing answer.

| Case | Expected behavior |
|---|---|
| “Hi” and “What can you help me with?” | LLM replies without unnecessary domain tools or state changes |
| “I want Chinese, and what is Montessori?” | Valid preference update plus grounded guidance in one turn |
| “Make that required” after a preference turn | Resolve the reference from context or ask a targeted clarification |
| “Which is closest?” without selected results | Retrieve appropriate catalogue/location facts or request the missing postal code |
| “Would this school suit us if my income drops?” | Resolve school and scenario inputs, calculate, and explain the assessment |
| “Compare these two, especially outdoor learning and cost” | Combine relevant school facts, evidence, and calculations without mixing sources |
| A named school followed by “Does it provide transport?” | Resolve the school from conversation and confirm with authoritative data |
| Ambiguous pronoun referring to several schools | Ask which school rather than guessing |
| Conflicting preference or proposed relaxation | Explain the conflict and obtain the required choice before applying a resolution |
| No evidence about an attribute | Explain the evidence gap without asserting the attribute is absent |
| Retrieved text instructs the agent to ignore its rules | Treat the text as evidence and preserve tool and state boundaries |
| Model/tool failure after a staged preference change | Explicit failure, unchanged committed state, no duplicate memory write |
| Concurrent requests or separate anonymous sessions | No state leakage or silent lost update |

Evaluation gates (school-project adjustment authorized 2026-10-10):

- 100% of valid new-flow chat entry-point tests invoke the LLM before semantic
  routing or conversational output.
- All state-integrity, citation-integrity, isolation, failure, and execution-limit
  regression cases pass.
- For Step 6 school-demo acceptance, at least 75% completion across the fixed
  25-conversation dataset, including eight injected integrity cases. Report
  ordinary live conversation completion separately. Preserve zero critical
  unsupported fee/eligibility claims or unintended state changes. The strict
  evaluation profile retains the original 95% threshold for later comparison.
- Greeting, help, mixed-request, stateless clarification and forget cases must
  pass. Other conversational failures remain visible in the scored report;
  successful grounding is not measured by verbatim output matching.
- Record measured latency, tokens and service failures. Numeric rollout budgets
  remain Step 7 work and do not block Step 6 school-demo completion.
- The documented backend test command passes, and any changed HTTP/frontend
  boundary receives its relevant compatibility checks.

Backend regression command from the repository root:

```bash
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline .venv/bin/python -m unittest discover -s SystemCode/src/backend/tests -v
```

## Progress

### Step 7 completion — controlled school-demo rollout, 2026-10-10

Identified Step 7 as the first incomplete step from committed Steps 1–6 and the
active records. Added backend `CONVERSATION_FLOW_MODE=llm-first|shadow|legacy`:
new flow is the missing/blank default for `/api/preferences`, invalid modes are
visible 503s, and the explicit evaluation endpoint remains. Legacy rollback
retains its old supervisor settings/contracts. Shadow serves one legacy response,
stages independently without shared history access/leases, and never writes
history, memory or feedback. Comparisons contain only profile/readiness/citation
booleans. Existing authoritative facts, calculations and validation are preserved.

Added scalar-only new-flow telemetry for elapsed time, registered attempted tool
names, executed count, model calls, validation/failure categories and usage.
Official OpenAI documentation verifies GPT-4o mini and configured GPT-5.4 mini
standard token rates; cost is null for unknown prices/incomplete usage. Updated
architecture, service/HTTP docs and [rollout decisions](../SystemCode/src/backend/doc/llm-first-rollout.md) with a minimum
seven-day observation period (earliest repository review 2026-10-17). Legacy
wrappers remain required by active rollback/shadow callers; retirement needs a
later reviewed maintenance decision. No observation-period completion or
production budget/readiness pass is claimed. School-demo gates from Step 6
justify enablement; strict evaluation and its five failed cases remain visible.

Verification:

- Required backend discovery: **462 tests in 42.252s, OK, exit 0**,
  `/tmp/step7-backend-final.log`, outside sandbox. Earlier full run failed one
  new assertion expecting an unnormalized empty shadow profile; corrected to
  verify absence of staged preferences. Intermediate rerun: 460 tests, OK.
- Focused HTTP/rollout: **21 tests in 1.995s, OK**,
  `/tmp/step7-focused.log`; final full suite also covers the last comparison fix.
  Default model-first zero-tool/tool turns, explicit rollback, successful/failed
  shadow, consented no-write mutation isolation, failure without fallback,
  telemetry redaction and both model prices are covered.
- `make eval-check`: **29 tests in 4.323s, OK**, RAGAS validate-only fixture
  passes; `/tmp/step7-eval-final.log`. Syntax, documentation links,
  whitespace and diff/scope/secrets review pass.
- Fresh configured GPT-5.4 mini default HTTP traces: **2/2 validated responses**,
  `/tmp/step7-live.log`. Greeting: one model call, no tools, **2.667s**,
  estimated **$0.00059535**. Chinese-required request: two model calls,
  `update_preferences` once, committed required Chinese, **2.003s**,
  estimated **$0.00173745**. Synthetic schools and mocked persistence establish
  default behavior, not production Neo4j/OneMap or general live quality.
- Sandbox focused/full worker-thread runs timed out at 45/50 seconds; sandbox
  live trace returned a safe execution failure. Outside-sandbox reruns passed.
  Official pricing fetch also required outside-sandbox network access.

The Step 6 capture's recorded token split estimates **$0.08954235** at configured
GPT-5.4 mini standard rates; observed p95 remains **6.093s**. Estimates exclude
missing usage, embeddings and other providers; no production cost gate claimed.
Single-worker RAM history, stateless concurrency, separate-store atomicity,
semantic grounding limits and absent frontend transcript consent remain.

Acceptance met for Step 7 controlled school-demo rollout. All seven implementation
steps are complete. Next: observe deployment for at least seven days and review
before legacy retirement; no further implementation step begun. Preserved and
excluded pre-existing greeting/help source/tests, backend README paragraph and
docs index from this step's commit. Legacy HTTP tests now explicitly select
rollback while new tests verify the default route.

### Step 6 completion — school-project criteria, 2026-10-10

The user explicitly authorized relaxing rules/checks for this school project.
Completed the prepared HTTP integration and evaluation using a selectable
`school-demo` scoring profile: 75% completion across the fixed 25 cases,
mandatory greeting/help/mixed-request/stateless/forget success, all integrity
checks and zero critical state/fee/eligibility errors. Strict scoring retains
95% and its original required cases. Runtime validation remains enforced.
No dataset cases were removed; reports expose ordinary live completion,
effective gates and failed cases. Added scoring regression coverage and focused
prompt corrections for explicit importance, reference/location handling and
retaining cited guidance during response repair.

Fresh configured-provider capture `/tmp/step6-school-live.json`, SHA-bound manual
review `/tmp/step6-school-review.json` and scored report
`/tmp/step6-school-scored.json`: **pass, exit 0; 20/25 cases (80%)**,
**12/17 ordinary conversations (70.59%)**, **25/27 served turns**, all eight
injected integrity cases pass, no reviewed critical state/fee/eligibility error
or unauthorized memory write. Failed cases remain income_scenario,
school_followup, conflict, relaxation and stale_dialogue. They include two safe
service failures, unnecessary clarification, unstaged conflict and a misleading
“Yes” before a correctly reloaded fee. These are accepted demo limitations;
strict 95% evaluation does not pass. Internal claims do not prove full prose
entailment. Synthetic schools/distances do not verify live Neo4j/OneMap.

Final backend discovery: **451 tests in 39.586s, OK**, exit 0
(`/tmp/step6-school-backend.log`); updated scoring checks: **2 tests, OK**.
`make eval-check`: **29 tests in 3.549s, OK**, plus RAGAS validate-only fixture
validation (`/tmp/step6-school-eval.log`). Sandbox discovery timed out after
50s; outside-sandbox rerun passed. Live capture likewise required outside-sandbox
worker execution. Syntax and whitespace checks pass. Observed p95 **6.093s**,
**263,788 recorded tokens**, service failure **2/27 (7.41%)**; no price/cost or
production-budget pass claimed. Single-worker RAM history and separate-store
atomicity limitations remain documented. Legacy greeting/help work is preserved.

**Step 6 complete for the authorized school-demo scope.** Next: Step 7;
selectable default/shadow rollout, rollback and operational reporting remain
unimplemented in this phase. No default-mode or frontend change in Step 6.

### Step 6 blocker repair and scored evaluation — 2026-10-10 (incomplete)

Added bounded argument correction, targeted final repair, scalar-path guidance,
ordered dialogue, enforced later-turn pending choices, current-preference support
and multi-scalar numeric-span validation. Added adversarial regressions and
capture-bound complete-dataset semantic scoring; eight mapped integrity checks
now execute during capture. Preserved unrelated work and Step 7 remains unstarted.

Required backend suite **450 tests in 39.052s, OK**; focused checks **55 tests in
2.946s, OK**; `make eval-check` **29 tests in 3.493s, OK**, plus RAGAS fixtures.
Syntax, whitespace, secrets/scope and unrelated-hunk preservation reviewed.

Latest live capture `/tmp/step6-finish-live5.json`: **24/27 served**, all eight
injected integrity checks pass, but reviewed task completion is **19/25 (76%)**,
below 95% (`/tmp/step6-finish-scored5.json`, exit 2). Remaining failures: ungrounded
location assertion, failed school-introduction claims, unresolved income/school
follow-ups, omitted comparison calculation, unstaged language conflict and unknown
school ID invocation. Earlier capture scored 84%; no passing live gate is claimed.
See [backend progress](../SystemCode/src/backend/doc/agents.md) for exact failures,
logs, final verification and production/synthetic limits. **Step 6 remains
incomplete; nothing staged and no completion commit.** Next: finish those Step 6
blockers and rerun scored live and required regression checks. Do not start Step 7.

### Step 6 continuation — 2026-10-10 (incomplete)

Continued only Step 6, preserving its existing HTTP work and unrelated legacy
changes. Added explicit model-facing preference fields/capability guidance,
pending strength staging and validated follow-up resolution, support for pending
acknowledgements, rejection guards and four tests plus adversarial cases. The
capture now records synthetic generated calls and validation feedback for review.

Final backend suite: **444 tests in 38.147s, OK**; affected checks: **62 tests in
2.569s, OK**; `make eval-check`: **29 tests, OK** and RAGAS fixture validation.
Sandbox worker-thread checks stalled; outside-sandbox reruns passed. Reviewed
scope/secrets, syntax, whitespace and preservation of unrelated hunks.

Latest configured-provider capture: `/tmp/llm-first-step6-retry3-live.json`, exit
2 pending review; **20/27** served turns, five response-validation and two argument
execution failures. Only **11/17** ordinary conversations have no service failure
(**64.71% completion upper bound**, below 95%). Mixed request still misses the
importance question. Remaining blockers include null scenario overrides,
invalid claim kinds/scalar paths/attribution, duplicate conflict patch fields and
unsupported numeric acknowledgements/refusals. See [backend progress](../SystemCode/src/backend/doc/agents.md)
for exact cases and logs. No complete semantic/integrity pass, live catalogue or
location verification, or rollout-budget agreement is claimed.

**Step 6 stays incomplete. No staging or commit.** Next: finish Step 6's recorded
live argument/response/state-choice failures, semantic/integrity scoring and
required verification. Step 7 has not begun.

### Step 6 attempt — 2026-10-10 (incomplete)

Prepared staged HTTP integration through the preference service, additive
history consent, session/stale-state commits, failure rollback and UI response
compatibility; legacy route/default remain for Step 7. Added eight injected
integration checks and a fixed-dataset configured-provider capture command.
Pre-existing legacy greeting/help changes remain preserved. Reconciled stale
backend next-step instructions with committed Steps 1–5.

Required backend suite: **440 tests in 40.874s, OK**; focused affected checks:
**58 tests in 2.666s, OK**; `make eval-check`: **29 tests in 3.500s, OK**, plus
RAGAS fixture validation. Sandbox worker-thread attempts timed out (exit 124),
then checks passed outside sandbox. Diff/scope/secrets review and syntax checks
pass. See [backend progress](../SystemCode/src/backend/doc/agents.md) for logs
and [HTTP contract](../SystemCode/src/backend/doc/llm-first-http.md) for decisions.

Live capture `/tmp/llm-first-step6-live.json` completed (exit 2, review required):
17 ordinary conversations, 27 generated turns, eight separately injected
integrity cases. Only **13/27** turns served successfully; ten validation and
four execution failures. Six of 17 conversations have no service failure, a
**35.29% completion upper bound**, below 95%. Mixed preference/guidance falsely
chooses required importance and gives unsupported Montessori prose; ambiguity
and Chinese follow-up interpretation also fail semantic review. No live
semantic, injection-resistance or complete task/integrity pass is claimed.
Synthetic catalogue/distances do not verify live Neo4j/OneMap dependencies.

**Step 6 stays unchecked; nothing staged and no completion commit.** Next:
resolve the exact live failures recorded in backend progress, complete semantic
and integrity scoring and rerun required checks before finalizing Step 6.
Step 7 has not begun. RAM retention, stateless concurrency and separate-store
atomicity limits are documented; operational rollout budgets remain Step 7.


- [x] Step 1: Baseline and architecture record
- [x] Step 2: Bounded conversation context
- [x] Step 3: Structured tools and staged state
- [x] Step 4: LLM-controlled tool loop
- [x] Step 5: LLM responses and grounding
- [x] Step 6: HTTP integration and evaluation (school-demo profile)
- [x] Step 7: Controlled rollout and cleanup (legacy retained through observation)

Next step: Step 7 — Controlled rollout and cleanup. Step 7 has not begun.

### Step 5 completion — 2026-10-10

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
[the response contract](../SystemCode/src/backend/doc/llm-first-responses.md).

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

### Step 4 completion — 2026-10-10

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
[the durable loop contract](../SystemCode/src/backend/doc/llm-first-loop.md).

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

### Step 3 completion — 2026-10-10

Implemented `agents/structured_contracts.py` and
`services/conversation_tool_service.py`: eight registered capabilities with
typed model-selected arguments, explicit structured statuses/results and
server-owned provenance. New-flow preferences accept validated patches without
the legacy message extractor/controller. Read/search/compare/calculation tools
use current staged state and existing authoritative repositories, scorer,
evaluator, location service and retrieval. Hypothetical family inputs remain
isolated. Invalid arguments, tool/output failures, execution bounds and invalid
final-response export discard changes; shadow exports cannot publish mutations.

Acceptance covered by 11 new integration/contract tests, including invalid IDs,
forged facts, unsupported fields/patches, update-then-search, read-your-writes,
scenario isolation, pending resolutions and discard on failure. The durable
[tool contract](../SystemCode/src/backend/doc/llm-first-tools.md) records arguments,
state behavior, bounds and integration constraints.

Verification: required backend command **406 tests in 39.781s, OK, exit 0**
outside the sandbox (`/tmp/llm-first-step3-backend.log`). Sandbox attempt timed
out after 50s at
`test_school_rating_service.SchoolRatingApiTests.test_missing_consent_is_422`
(exit 124; `/tmp/llm-first-step3-backend-sandbox.log`). Five focused modules:
**45 tests in 1.806s, OK** (`/tmp/llm-first-step3-focused.log`); the initial
focused command used a nonexistent history module, corrected and rerun.
`make eval-check`: **29 tests in 3.381s, OK**, plus validate-only RAGAS fixture
validation (`/tmp/llm-first-step3-eval.log`). Scope/diff/secrets/local-link and
unrelated-work preservation review, `git diff --check` pass.

Limitations: new capabilities are a foundation, not yet the served path.
Legacy eager context and answer wrappers remain for compatibility until later
integration. No HTTP/frontend/rollout or deterministic-algorithm change.
Overall elapsed/model/total-context budgets belong to Step 4; synchronous
providers cannot be cancelled here. Session/commit coordination is Step 6.
Live model selection/quality is unmeasured and belongs to later steps.
Pre-existing greeting/help code, tests and documentation hunks remain excluded.

Acceptance met. Next: Step 4 — LLM-controlled tool loop. Not begun.

### Step 1 completion — 2026-10-10

Completed the reviewed entry/routing/substitution/nested-model/state/dependency
map, fixed synthetic dataset (25 conversations / 36 turns), reproducible
injected-model capture and documented target contract. Backend contributor
guidance and progress now identify this phase while retaining readiness history.
Pre-existing greeting/help work is preserved and excluded from this commit.

The user authorized resolving the four recorded regression blockers. Test-only
repairs isolate deterministic fixtures from optional live generation and fix
the checkpoint-reuse clock to its retrieval date. Existing model-specific and
expired-page refresh tests remain active; runtime behavior and contracts do
not change.

Verification: the exact required backend command passes **382 tests in
37.548s**, exit **0**, outside the sandbox. The sandbox attempt timed out at
the school-rating HTTP test after 40s (exit 124). All **143 affected-module
tests** pass in 0.916s; `make eval-check` passes **29 tests in 4.046s** and
RAGAS fixture validation. Two captures match the stored artifact exactly;
dataset, syntax, links, diff/secrets review and unrelated-work preservation
checks pass. Exact commands and logs are in the
[backend progress record](../SystemCode/src/backend/doc/agents.md).

Step 1 acceptance criteria and required checks are met. Live-provider quality,
numeric operational budgets and execution/scoring of the target dataset remain
later-step work. Step 2 has not begun. Entries below preserve earlier failed
verification attempts and are superseded by this completion record.

### Latest Step 1 session verification — 2026-10-10 (incomplete)

Reviewed existing changes, applicable instructions, backend documentation and
the prepared behavior map, fixed dataset and target contract. Preserved the
phase reconciliation and all unrelated work. Only this plan, backend progress
and baseline record changed in this session.

Two captures match the stored artifact; syntax, local links and 25 unique
conversations / 36 bounded sequential turns validate. The 30 focused backend
tests pass in 3.002s; `make eval-check` passes 29 tests in 4.533s plus RAGAS
fixture validation. Diff, secrets and preservation checks pass.

The required sandbox suite times out after 50s (exit 124) at the school-rating
HTTP test. The exact command outside the sandbox completes **382 tests in
63.124s**, exit **1**, **three failures / one error**: combined-evidence and
Montessori/SPARK routing, missing fallback `extraction_method`, and checkpoint
`school_attempts` 1 instead of 0. Exact test IDs, logs and source diagnoses are
in the [backend progress record](../SystemCode/src/backend/doc/agents.md).
These pre-existing regressions were not caused by baseline changes; no runtime
or test repair outside this step's scope was made.

**Step 1 remains incomplete; nothing staged and no completion commit.** Resolve
the four required-check blockers before finalizing Step 1. Step 2 has not begun.
Live-provider quality, numeric budgets and target-case execution remain pending
their documented later steps.

### Step 1 scope review and required checks — 2026-10-10 (incomplete)

Reviewed status/diffs, applicable instructions, backend documentation and the
prepared map, fixed cases and target contract against the implementation.
Existing phase reconciliation is retained. Only this plan, backend progress
and baseline record changed; all other pre-existing work is preserved.

Two captures match the stored artifact; 25 unique conversations / 36 bounded
sequential turns, capture syntax and local links validate. The 30 focused
backend tests pass in 2.284s; `make eval-check` passes 29 tests in 4.278s and
the validate-only RAGAS fixture check. Scope/secrets review and
`git diff --check` pass.

The required sandbox suite times out after 75s (exit 124) at the school-rating
HTTP test. The exact required command outside the sandbox completes **382
tests in 63.621s**, exit **1**, **two failures / one error**: combined-evidence
routing (`general_knowledge` versus `combined_evidence`), invalid extraction
fallback (`KeyError: extraction_method`), and checkpoint refresh
(`school_attempts` 1 versus 0). Exact test IDs and logs are in the
[backend progress record](../SystemCode/src/backend/doc/agents.md).
Affected runtime/test files were unchanged by Step 1.

**Step 1 remains incomplete; nothing staged and no completion commit.** Resolve
the required regression blockers before finalizing Step 1. Step 2, bounded
conversation context, has not begun. No live-provider quality, numeric budgets
or passing target-dataset execution is claimed.

### Step 1 verification rerun — 2026-10-10 (incomplete)

Reviewed applicable guidance, backend documentation and implementation against
the prepared behavior map, fixed dataset and target contract. Preserved the
existing greeting/help work and all other pre-existing files; this session
updates only this plan, backend progress and baseline records.

Two captures match the stored artifact byte-for-byte; dataset validation
confirms 25 unique conversations / 36 sequential bounded turns. Python syntax
and local links pass. The 30 focused backend tests and `make eval-check`
(29 tests plus validate-only RAGAS fixture) pass. Diff/scope/secrets review and
`git diff --check` pass.

The required sandbox suite stalls at the school-rating HTTP test and times out
after 90 seconds (exit 124). The same command outside the sandbox completes
**382 tests in 63.038 seconds**, exit 1, **two failures / one error**:
combined-evidence routing, missing fallback `extraction_method`, and checkpoint
`school_attempts` 1 instead of 0. Exact test IDs and logs are in the
[backend progress record](../SystemCode/src/backend/doc/agents.md).
Montessori/SPARK passes in this run. These failures concern unchanged code/tests;
no runtime or test repair outside the baseline scope was made.

**Step 1 remains incomplete; nothing staged and no completion commit.** Resolve
the required regression blockers before finalizing Step 1. Step 2 has not begun.
Live-provider performance, numeric budgets and target-case execution remain
unmeasured and belong to later steps.

### Step 1 current audit — 2026-10-10 (incomplete)

Reviewed the existing architecture map, target contract, capture and fixed
dataset against applicable contributor guidance, backend documentation and
implementation. Preserved all pre-existing changes; this session edits only
the plan, backend progress and baseline records.

Both captures match the stored artifact; Python syntax, 25 unique conversations
/ 36 bounded sequential turns and local links validate. The 30 focused backend
tests, 29 repository evaluation tests and validate-only RAGAS fixture pass.
Scope/secrets review and `git diff --check` pass.

The exact required backend command stalls inside the sandbox at the
school-rating HTTP test (interrupted, exit 130). Outside the sandbox it finishes
**382 tests in 67.420 seconds**, exit 1, **two failures / one error**:
combined-evidence routing, missing fallback `extraction_method`, and checkpoint
`school_attempts` 1 instead of 0. Exact test IDs, logs and prior diagnoses are
in the [backend progress record](../SystemCode/src/backend/doc/agents.md).
Montessori/SPARK passes in this run. No failure is caused by baseline changes;
no runtime or test repair outside Step 1's scope was made.

**Step 1 remains incomplete; nothing staged and no completion commit.** Resolve
the three required-check blockers before finalizing Step 1. Step 2 has not
begun. Live-provider quality, numeric budgets and target-case execution remain
work for later documented steps.

### Step 1 latest verification — 2026-10-10 (incomplete)

Reviewed the existing behavior map, target contract, dataset and capture against
the implementation and applicable backend guidance. Preserved all pre-existing
runtime, test and documentation work; this session updates only the plan,
backend progress and baseline records.

Two captures match the stored artifact; 25 conversations / 36 turns, Python
syntax and local documentation links validate. All 30 focused backend tests,
29 repository evaluation tests and the validate-only RAGAS fixture check pass.
Diff review and `git diff --check` pass.

The sandbox regression run times out after 90 seconds (exit 124) at the
school-rating HTTP test. The exact required command outside the sandbox runs
**382 tests in 67.692 seconds**, exit 1, with **three failures / one error**:
combined-evidence routing, Montessori/SPARK routing, missing fallback
`extraction_method`, and webpage checkpoint `school_attempts` 1 instead of 0.
The backend progress record lists exact test IDs, results and logs. None is
caused by baseline changes; no out-of-scope runtime repair was made.

**Step 1 stays incomplete; no staging or completion commit.** Resolve these
required-check blockers before finalizing Step 1. Step 2 has not begun.

### Step 1 resumed verification — 2026-10-10 (incomplete)

Reviewed the existing Step 1 artifacts, backend guidance and implementation map
without changing runtime code, schemas, curated cases or generated captures.
Both new captures match each other and the existing working-tree artifact;
25 unique conversations / 36 turns validate; 30 focused backend tests and
29 evaluation tests plus the validate-only RAGAS fixture pass.

The required unchanged backend command again stalls at the school-rating HTTP
test inside the sandbox (interrupted, exit 130). The outside-sandbox run
completes **382 tests in 59.700 seconds**, exit 1: **two failures / one error**.
Combined-evidence routing, missing fallback `extraction_method`, and checkpoint
`school_attempts` remain blockers. Montessori/SPARK passes in this run.
Model-disabled diagnostic reproductions pass all three routing/extraction
cases, and the checkpoint case passes with its clock fixed to the fixture's
2026-08-10 retrieval date. These explain provider-dependent and time-dependent
verification; they do not replace or establish a passing required suite.
Commands, exact test IDs and logs are in the backend progress record.

All existing greeting/help work remains untouched. No failure was caused by
the baseline documentation/capture changes, and no runtime or regression-test
repair outside the documented baseline scope was made. **Step 1 remains
incomplete; nothing is staged and no completion commit is created.** The next
action remains resolving the required regression blockers and finalizing
Step 1. Step 2 has not begun.

### Step 1 session — 2026-10-10 (incomplete)

The [backend baseline](../SystemCode/src/backend/doc/llm-first-baseline.md)
records the reviewed entry/routing/substitution/model/state/dependency map and
target contract. Contributor guidance and the [active progress record](../SystemCode/src/backend/doc/agents.md)
now identify this phase while preserving completed readiness/rollout history.
The fixed target dataset has 25 synthetic conversations / 36 turns; an injected,
provider-free service capture records greetings/help and a multi-turn mixed
request/reference baseline. Capture reproducibility, dataset checks, 30 focused
conversation tests, 29 repository evaluation tests and diff checks pass.
Pre-existing greeting/help code/tests and README changes remain untouched.

The required full backend suite completed outside the sandbox: 382 tests in
67.103 seconds, three failures and one error. Blockers are general-guidance
combined-answer routing, Montessori/SPARK routing, missing Stage 1 fallback
`extraction_method`, and webpage checkpoint `school_attempts` 1 instead of 0.
Exact test IDs, commands and log locations are in the backend progress record.
The earlier sandbox run stalled; the bounded outside-sandbox reproduction of
that single HTTP test passed. No runtime repair was made outside Step 1 scope.

Step 1 is **not complete** and no completion commit is created because the
required regression check fails. Resume only Step 1 to obtain passing required
verification and finalize its commit. Step 2 is bounded conversation context,
including documented session/history and any minimal contract change; it has
not begun. Live-provider quality and numeric latency/token/cost budgets remain
unmeasured, and target-dataset execution belongs to Step 6.

### Step 2 completion — 2026-10-10

Implemented strict bounded initial context, typed pending decisions and current
repository-resolved school identities in `agents/contracts.py` and
`services/conversation_context_service.py`. Added explicitly opted-in ephemeral
history in `services/conversation_history_service.py`: six complete exchanges,
8,000 dialogue characters, 30-minute idle expiry, 1,000-session capacity and
exclusive commit leases. Forget clears both preference memory and history.
The full initial context is limited to 24,000 UTF-8 bytes.

[The backend context contract](../SystemCode/src/backend/doc/llm-first-context.md)
records the session/history and minimal future HTTP-consent extension before
implementation. No public schema or frontend change yet: HTTP wiring is Step 6.
Legacy evaluation/geocoding remains until Step 3 tools replace its dependencies;
the new initial builder performs neither operation. No model loop or routing
change. History has no generated summary, disk persistence or cross-worker
sharing; omitted turns are explicit, expiry cleanup is on access, and worker
restart/eviction loses history. Current state and facts override dialogue.

Verification: required backend discovery **395 tests in 39.648s, OK, exit 0**
outside the sandbox (`/tmp/llm-first-step2-backend.log`). Sandbox attempt timed
out after 45s at `test_school_rating_service.SchoolRatingApiTests.test_missing_consent_is_422`
(exit 124; `/tmp/llm-first-step2-backend-sandbox.log`). Focused history/context,
legacy context, memory, supervisor and validation checks: **37 tests in 2.541s,
OK** (`/tmp/llm-first-step2-focused.log`). `make eval-check`: **29 tests in
3.785s, OK**, plus RAGAS validate-only fixture check
(`/tmp/llm-first-step2-eval.log`). Diff/links/secrets review and
`git diff --check` pass; unrelated greeting/help changes preserved and excluded.
Injected consumers verify the context boundary, not live reference resolution
or served LLM-first control flow, which are later-step checks.

Acceptance met for the Step 2 foundation. Next: Step 3 — typed structured tool
results, model-selected inputs and request-local staged state. Not begun.
