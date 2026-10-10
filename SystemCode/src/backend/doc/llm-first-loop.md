# LLM-controlled tool loop — Step 4

`agents/conversation_loop.py:run_conversation_loop` consumes the Step 2 minimal
context and its matching Step 3 transaction. Every valid invocation calls the
injected tool-capable model before interpreting the message or executing a
capability. All server-permitted registered capabilities are exposed without
keyword/intent filtering or a required tool choice. Context mismatch fails
before reasoning, preventing accidental cross-turn state or access scope use.

The same model receives subsequent structured results and chooses further
calls or a direct answer/clarification. Calls execute sequentially, including
within a model batch, so search/calculation reads earlier staged updates.
Queries, patches, IDs, operations and scenario overrides retain the Step 3
validation boundary. A `needs_input`, `no_evidence` or `unavailable` result goes
back to the model; it can clarify, use user-supplied inputs, or explain the gap.
No deterministic semantic routing, nested answer wrapper or answer substitution
runs in this loop. Dialogue and application context use data messages, not
system instructions; retrieved passages remain tool data.

The returned `ConversationLoopCandidate` contains bounded model wording,
detached structured results and execution counts. It is **not** a validated
response or a committed profile. Step 5 must validate wording, values,
attribution and citation references, add bounded repair, and only then authorize
state export. Step 6 coordinates the HTTP response/history/memory commit.
The legacy served supervisor and all current HTTP/frontend contracts remain
unchanged; Step 6 integrates this foundation and Step 7 selects rollout modes.

## Execution and failure boundaries

Defaults are eight model invocations, twelve tool calls, four mutations through
the existing transaction, 30 seconds for the entire loop, 128,000 UTF-8 bytes
of cumulative messages plus exposed tool schemas per model invocation, 16,000
bytes per model response and 800 characters of final wording. Limits validate
strict finite ranges; they do not silently drop authoritative state/results.
Result size retains the Step 3 64,000-byte bound. Intermediate model content,
tool arguments and call history count toward total context. A final-iteration
tool request fails before executing an action that cannot receive a final reply.

Binding, model calls and synchronous tools run under the remaining overall
deadline in worker threads. No loop retry resets that budget. Timeout,
cancellation, invalid calls/arguments, duplicate call IDs, forbidden tools,
provider failure, malformed output and resource overflow abort the transaction.
Errors expose only a fixed category, never provider details or family inputs.
No legacy fallback, transcript write, profile export or persistent write occurs.

A synchronous external read may finish after timeout; Python cannot forcibly
cancel that provider. Transaction closure and the mutation lock prevent late
worker staging or export from restoring discarded changes. Existing provider
timeouts remain necessary; Step 7 operational observation must measure pending
reads, latency and cost. The byte limits bound application-supplied context and
accepted output, not provider token generation before an oversized response is
rejected. Provider token/cost budgets remain rollout work.

## Verification scope

`tests/test_llm_first_loop.py` uses injected models and a real synthetic
catalogue to verify model-first direct replies, unfiltered access scopes,
multi-part paraphrases, ambiguous-reference clarification, dependent calls,
read-your-writes, missing-input recovery, structured unavailable results,
invalid/forged calls, duplicate IDs, cumulative context/output/call/mutation
bounds, safe failures, rollback, deadlines, cancellation and late-worker closure.
These establish orchestration behavior; they do not establish live model
selection quality, semantic grounding or HTTP rollout gates. Exact regression
results are in [backend progress](agents.md).
