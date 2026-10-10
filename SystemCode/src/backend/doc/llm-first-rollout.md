# LLM-first rollout — Step 7

`POST /api/preferences` now selects `CONVERSATION_FLOW_MODE` in the backend.
Missing or blank configuration selects `llm-first`. Unknown values return a safe
503 so a misspelled rollback cannot silently enable a different path. Restart
workers after changing deployment configuration. The explicit
`/api/preferences/llm-first` evaluation endpoint always runs the new flow.

| Mode | Served behavior | State |
|---|---|---|
| `llm-first` (default) | Bounded model/tool loop, model-authored validated response; fixed service error on failure | One validated commit; at most one consented preference-memory write |
| `shadow` | Retained legacy response, with an inline new-flow comparison | Only legacy persists; shadow stages locally, exports original profile, and never acquires shared history leases or writes memory, history or feedback |
| `legacy` | Previous conversation service and its response contracts | Previous persistence behavior |

`CONVERSATION_AGENT_MODE=agent|shadow|deterministic` and `WEB_RAG_ANSWER_MODE`
configure only the retained legacy implementation. For a controller-only
rollback, set `CONVERSATION_FLOW_MODE=legacy`,
`CONVERSATION_AGENT_MODE=deterministic`, and `WEB_RAG_ANSWER_MODE=deterministic`.
The default new flow never invokes legacy intent routing or fallback, including
for greetings and missing-location questions. School facts, policy, validated
state changes and all calculation algorithms remain backend-owned.

Shadow receives the submitted profile and current authoritative context without
shared transcript access. Its pending mutations are discarded even with consent.
Comparison logs expose only profile/readiness/citation equality, not answers or
profiles. Different wording is expected, so answer equality is not a quality
metric. Shadow failures cannot replace the single legacy answer; cancellation
propagates. Inline shadow adds at most the existing new-loop budget (30 seconds
by default), plus context loading/provider completion. Synchronous reads may
outlive cancellation, but cannot export or persist staged state.

## Observation and cleanup

For the school-demo rollout, retain explicit legacy rollback for at least seven
calendar days after enabling each deployment (repository default changed
2026-10-10; earliest repository review 2026-10-17). Review observed service errors,
latency, cost and semantic failures before retiring it. Retained wrappers, intent
routing and answer substitutions still serve the active rollback/shadow path;
removing them now would break that path. Remove them only after an explicitly
approved retirement, and only when no active caller needs them. This is a later
maintenance decision, not another implementation step in this plan.

Enablement uses the already recorded school-demo gate: 80% completion of 25
fixed cases, all eight integrity checks, mandatory core cases and zero reviewed
critical fee/eligibility/state errors. Strict 95% acceptance is still unmet.
The five failed Step 6 conversations remain visible; switching the route is not
evidence that they improved. No production rollout or production-budget pass is
claimed. The existing loop's 30-second, eight-model-call, twelve-tool-call and
four-mutation limits remain. Seven-day observation is required before cleanup;
no elapsed observation-period pass is claimed in Step 7.

## Operational metadata and cost

`kindercompass.llm_first` emits `llm_first_observation` with mode, elapsed
milliseconds, model invocation count, allowlisted attempted tool names, executed
tool count, validation success, fixed failure category, input/cached/output token
counts, usage completeness, estimated USD cost and scalar shadow comparisons.
Exceptions during session resolution or commit have a fixed failure category.
No raw message, profile, family data, session identifier, model/tool arguments,
results, citation text, or provider error text enters this event. Logs remain
best effort and cannot determine the served response.

Prices checked in official OpenAI documentation on 2026-10-10, standard USD per
million tokens:

| Model | Input | Cached input | Output |
|---|---:|---:|---:|
| [GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini) | 0.15 | 0.075 | 0.60 |
| [GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini) | 0.75 | 0.075 | 4.50 |

Estimates sum uncached input, cached input and output separately. Unknown model
prices or incomplete invocation usage produce null cost, never zero. Token
counts include bounded response repairs. A timed-out invocation may incur cost
without returning usage; recorded cost excludes it and remains null. These are
standard token estimates, not bills, and exclude retrieval embeddings and other
external costs. Update rates from official documentation when model pricing
changes. No arbitrary configured price or provider string is logged.

The Step 6 synthetic capture reports 256,587 input tokens, 200,448 cached tokens
and 7,201 output tokens. At the configured GPT-5.4 mini rates this is **$0.08954235**
for 27 turns (about **$0.00332 per turn**), with recorded p95 latency **6.093s**.
This retrospective estimate excludes missing usage/other providers and does not
establish a production budget. Fresh default-endpoint traces and final test
results are recorded in [backend progress](agents.md).

RAM-only single-worker history, expiry/eviction, lack of stateless cross-request
versioning, separate-store atomicity, prose-grounding limits and absent frontend
transcript consent remain as documented in [HTTP integration](llm-first-http.md).
