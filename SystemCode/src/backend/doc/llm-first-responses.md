# Model-authored responses and grounding — Step 5

`agents/conversation_response.py:run_validated_conversation` is the validated
new-flow entry point. It uses the Step 4 loop with the same Step 2 context and
Step 3 transaction. The model authors all successful wording, including direct
greetings, capability explanations, clarifications, preference acknowledgements
and evidence-gap explanations. No vocabulary allowlist, candidate copying,
answer substitution, nested answer generation or legacy controller fallback
runs here. The raw Step 4 candidate API remains available for orchestration tests;
it does not establish response validation and must not serve HTTP replies.

## Internal final contract

The final model message is strict JSON: `answer` (1–800 characters), `kind`
(`conversation`, `clarification`, `grounded`, `evidence_gap`), and up to 30
`claims`. Each claim identifies an exact answer substring, a server result ID,
a JSON-pointer scalar field, its value, school attribution and citation IDs.
This contract is internal; no public API or frontend schema changes in Step 5.
Successful responses return the model's wording, detached typed claims, only
referenced server-owned citations, execution counts and one validated profile
export. Profile export is not a persistence commit; Step 6 owns HTTP, history
leases and the authorized preference-memory write.

The validator checks strict structure, known results, scalar paths, exact typed
values (numeric int/float equivalence allowed), successful result status, school
ID matching the containing record/passage, explicit school names, resolvable
citations and passage-specific citation markers. Repository names are included
in school passages for attribution; no model-supplied identity is authoritative.
Preference, ranking and calculation claims cannot use results from an earlier
state revision. Evidence gaps require a supporting `no_evidence`, `needs_input`
or `unavailable` status. Reported numeric tokens must occur in supported claim
spans and match that claim's scalar value; thousands separators are accepted,
rounding and unit conversion are deliberately unsupported. Citation markers and
known school names are excluded from numeric scanning. Conversation and
clarification output may have no factual claims, for conversational wording and
questions. Grounded replies require claims.

## Repair, state and failures

Invalid final structures, values or citations receive fixed-category feedback
and up to two model repair attempts using the existing evidence. Repair cannot
execute tools or mutations. Attempts share the original model-call, elapsed-time,
context and output bounds; no retry resets a turn budget. The 800-character
limit applies to final wording; the existing 16,000-byte model-message limit
also includes claim metadata. Empty/non-text/oversized provider messages and
invalid calls fail immediately at the loop boundary.

Only a validated reply authorizes the transaction's single state export. A
provider/tool failure, exhausted repair, timeout or limit failure discards all
staged changes and returns `unavailable`, no profile/citations/claims and the
fixed message `The conversation service is unavailable. Please try again.`
Failure metadata contains a category only. Cancellation aborts and propagates.
Shadow export returns original state. There are no transcript, memory or database
writes, and no deterministic domain answer on a failed turn.

## Verification and limits

`tests/test_llm_first_response.py` covers model-authored conversational turns,
preference acknowledgements, missing-source explanations, numeric and boolean
value mismatches, stale calculation results, fabricated support/citations,
cross-school records/citations, paraphrased evidence, bounded repair without
replayed tools, provider/tool failure after mutation, rollback, shadow export,
single export, and shared deadline/context bounds. These injected-model tests
establish validation/control flow, not live quality. Exact checks are recorded
in [backend progress](agents.md).

Mechanical checks cannot prove that a paraphrased span follows from a passage,
that every prose claim was annotated, or that a boolean/status description is
semantically faithful. A model could omit support and mislabel prose as a
conversation or question; unsupported nonnumeric assertions remain a semantic
evaluation risk. A matching number does not establish the right unit or time
period. School-name substring checks can conservatively reject overlapping
names. Step 6's fixed adversarial/live dataset must evaluate these limitations
and the rollout gates; this record does not claim full semantic grounding.
Live provider quality, latency/token/cost budgets, HTTP integration and shipped
mode selection remain Steps 6–7. Authoritative repositories, deterministic
algorithms, public contracts and the served legacy path retain their contracts.
