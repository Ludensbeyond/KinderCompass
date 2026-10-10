# Bounded conversation context — Step 2

This is the backend foundation for the new flow, not a change to the served
legacy supervisor. HTTP integration remains Step 6 and selectable rollout
remains Step 7. The existing controller still needs evaluated records and
distance context; its eager preparation is retained until structured tools
replace those dependencies in Step 3.

## History and boundary decision (recorded before implementation)

Reuse the existing anonymous UUID as a session capability. Possession of the
UUID grants access to that session; it is not an authenticated identity. The
new-flow HTTP integration will add an explicit `remember_conversation` boolean
(default false) to `PreferenceRequest`, requiring `anonymous_session_id` when
true. This is separate from `remember_preferences`. No frontend or public
schema change is made in Step 2; Step 6 must wire the field and document the UI
choice before enabling history. Supplying a UUID alone must not retain chat.

History is opt-in, process-local RAM only, with a 30-minute idle expiry, a
maximum of 1,000 sessions per worker, and eviction of the oldest idle session
at capacity. Deployments must use one worker or sticky routing; worker restart
or worker changes lose history and produce an empty window. There is no disk
transcript, persistent summary, or change to the 180-day preference memory.
Expiry is enforced and expired entries removed on the next begin/commit
operation; no background erasure timer is provided in this process-local store.
Family objects and tool outputs are not stored separately, but user/assistant
text can contain personal inputs; explicit opt-in is therefore required.

Retain at most six complete user/assistant exchanges and 8,000 characters.
Messages are at most 500 characters; assistant replies at most 800. Drop whole
old exchanges, never half a turn. Record that older turns were omitted; do not
generate an older-turn summary in this step. The model must clarify a reference
outside the retained window. Dialogue is untrusted conversational context and
cannot override current profile, family inputs, catalogue or policy evidence.

One request may lease a session at a time. An overlapping request fails with
`ConversationHistoryConflict` rather than overwriting state. A lease/version
token is required to commit the validated exchange; failed turns abort without
recording it. Forget invalidates even in-flight leases. No session ID or token
is included in model context. Stateless turns neither read nor write history.
The Step 6 integration must abort in a `finally` block and commit only after
response/state validation; abandoned leases expire within 30 minutes.

`/api/memory/forget` clears both opt-in preference memory and ephemeral history
for the UUID. Restore/save remain preference-only and never restore transcripts.

## Initial model context

`InitialConversationContext` includes the newest message, bounded recent
exchanges, omission marker, current profile, typed unresolved decisions, family
inputs, postal code, selected/active school IDs and repository-resolved names,
catalogue version and a fixed capability list. No ranking, evaluation,
geocoding, evidence-index load or model call occurs while preparing it.
Full authoritative facts and calculations must be loaded through Step 3 tools.
Selected and active school identities are reloaded on every turn. Cached
dialogue names, costs and profile assertions are never authoritative.

Pending decisions are explicit `preference_strength`, `contradiction` or
`relaxation` records copied from the current validated profile. Reference
interpretation remains model work in Step 4. Preparation does not interpret the
message, resolve a pronoun, select tools or construct a conversational reply.

Each profile/pending JSON payload is bounded structurally and the complete
serialized initial context is limited to 24,000 UTF-8 bytes; overflow fails
validation instead of silently truncating authoritative state. Tool-result and
overall execution budgets remain the responsibility of Steps 3–4.

## Verification and limitations

Tests use an injected clock, actual catalogue repository and injected model
consumer to cover reference context, absent/expired history, isolation, forget
and concurrent leases, aborted turns, bounded windows/capacity, hostile or stale
dialogue, pending decisions and context overflow. Greeting context can be
passed directly to the injected model without any domain preparation.
These establish the context boundary, not live conversational quality or the
Step 4 requirement that every served new-flow turn calls the model first.
