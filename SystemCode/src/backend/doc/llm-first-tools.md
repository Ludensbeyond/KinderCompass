# Structured capabilities and staged state — Step 3

`agents/structured_contracts.py` and `services/conversation_tool_service.py`
implement the new-flow tool boundary. Construct one service per turn from the
Step 2 initial context and server-owned repositories/services. They do not yet
change the served supervisor, HTTP contracts or rollout; Steps 4–6 consume this
foundation. Legacy answer wrappers remain for the existing path.

## Arguments and results

The eight names in `ConversationContextService.CAPABILITIES` have registered
LangChain tools and a direct validated `invoke` interface:

| Capability | Arguments | Result |
|---|---|---|
| `read_school_facts` | Repository IDs, allowlisted fact operation | Fact projection, availability, freshness, source and catalogue version |
| `search_school_evidence` | Up to five repository IDs, focused query | School-attributed passages, citations and IDs lacking evidence |
| `search_general_guidance` | Focused query | Typed general passages, authority and citations |
| `search_rank_compare_schools` | Search/rank/compare, optional IDs, limit | Current-profile scores, match evidence, trade-offs and truncation |
| `calculate_fees_scenario` | IDs, typed optional family overrides | Deterministic Stage 2 results, policy provenance and inputs actually used |
| `find_nearby_schools` | Optional postal code/radius, limit | Repository records, calculated Haversine distances and missing-location count |
| `update_preferences` | Typed set/remove patch | Validated staged profile, changed fields and unresolved decisions |
| `reset_continue_preferences` | Reset or pending operation, typed choice | Validated staged profile and resolution status |

Arguments forbid extra fields, coercive booleans/integers, duplicate IDs/patch
attributes, unsupported operations/values, non-finite values and arbitrary
profile/fact replacements. School IDs resolve against the repository. Access
comes from server-owned capabilities, never the newest message's keywords.
Set choices carry attribute, value, importance and desired direction; evidence
metadata is constructed by `make_preference_item`, never accepted from a model.
Existing schema-v2 and backward-compatible profile representations are retained.

Each output is a `StructuredToolResult` with request-local result ID, explicit
`ok`, `needs_input`, `no_evidence` or `unavailable` status, structured data,
missing inputs, citations, catalogue version and staged-state revision. There
is no answer candidate or generated wording. Missing evidence never means an
attribute is absent. Calculation records retain dated policy and assumptions
from the existing evaluator; dialogue cannot supply authoritative facts.

## Transaction and dependency behavior

Every successful mutation updates the private working profile; subsequent
search/scoring/calculation tools reload current data and read that profile.
There is no ranked-result cache to invalidate. Hypothetical income, citizenship,
programme, working hours, household size, dependants and special-approval
overrides are applied to a fresh validated family object. They never change
the saved family or context. Dates use the current authoritative family inputs.

Changing a required language/teaching approach stages a contradiction instead
of applying it. Pending decisions block new patches until an explicit typed
resolution. A conflicting patch stages only the conflict; other entries remain
unapplied and must be resubmitted after resolution. Existing pending strength,
contradiction and relaxation shapes remain supported through deterministic
validation/adapters. Reset clears preferences and pending state while retaining
the current school reference. Removal is an explicit model-selected user action.

The service deep-copies inputs, results and exports. Failed argument validation,
provider failure, result overflow or exceeded bounds aborts the entire turn,
discards staged changes and prevents export. LangChain argument validation has
the same abort behavior as direct invocation. An unvalidated final response
also aborts; shadow export yields only the original profile. There are no
memory, transcript or database writes. `export_validated_state` returns a
detached candidate once; it is not a persistence commit. Steps 5–6 must validate
the response before export and coordinate the history lease/state commit.

School evidence and general retrievers load only when called; ranking,
evaluation and geocoding occur only inside relevant tools. Existing hard level,
language and distance filtering precedes the unchanged scorer for searches;
comparison preserves all requested records and scores them without filtering.
Nearby search reports catalogue proximity; it does not assert family eligibility.

Bounds: 12 invocations, four mutations, 64,000 UTF-8 bytes per result, at most
20 returned schools, three passages per school/general query, and bounded JSON
structure. Provider exceptions propagate as turn failures after rollback.
Step 4 must add overall elapsed-time, model iteration and total-context budgets;
this synchronous service does not cancel a blocking external provider.

## Verification and remaining limits

Injected-provider integration tests use a real synthetic `SchoolRepository`,
the existing `EvaluationService` and curated retrieval adapter. They compare
scenario outputs to the deterministic evaluator, exercise update-then-search,
read-your-writes, pending resolutions, missing inputs/evidence, per-school
citations, invalid IDs/forged facts/patches, state and family isolation, shadow
export, single export and rollback on tool/output/argument/final failure.

This verifies capability contracts and request-local state, not live model tool
selection or HTTP writes. The served legacy flow retains its eager preparation
until HTTP integration selects the new builder/service. Repository catalogue
search uses the existing generated authoritative catalogue; it does not add a
new Neo4j query interface. Transcript/session concurrency remains the Step 2
lease contract, with HTTP coordination in Step 6.
