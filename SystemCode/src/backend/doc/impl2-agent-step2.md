# Implementation 2 archive — full-conversation agent

This document preserves the completed Implementation 2 migration of every
natural-language turn submitted to `POST /api/preferences` behind a backend
conversation supervisor. Active conversational-readiness work is tracked in
[the current agent plan](agents.md), and the completed selected-school evidence
migration is preserved in [the Implementation 1 archive](impl1-agent-step1.md).

## Session protocol

Every migration session must read `src/AGENTS.md`, `backend/AGENTS.md`, and this
document. It must complete only the one step named under **Next step**, run that
step's tests, update the checklist and decision log, replace the single
**Next step** entry, and stop without starting the following step.

Checklist statuses are `pending`, `in progress`, and `complete`. A step is not
complete until its scoped tests and evidence are recorded here. Generated
outputs are not edited by hand.

## Goal and scope

Every natural-language message submitted to `POST /api/preferences` will enter
a backend conversation supervisor when shadow or agent mode is enabled. The
supervisor decides which registered capability tools to call and what grounded
answer to return. It orchestrates only: deterministic backend code remains
authoritative for preference state, ranking, eligibility, fees, distance,
school facts, and citations.

The supervisor's primary responsibility is intent and data-source routing. At
the start of each turn it must distinguish among:

1. application workflow, such as changing preferences, comparing results, or
   running a fee scenario;
2. structured KinderCompass facts, such as a school's food policy, programmes,
   fees, or available vacancy data, which must come from the authoritative
   catalogue/knowledge-graph boundary;
3. general early-childhood or Singapore policy guidance, such as how government
   preschool subsidies work, which must come from a separately cited general-
   knowledge retrieval boundary; and
4. a combined question that requires more than one of these sources.

The model is not the source of facts in any route. It selects one or more
registered tools, the backend executes them, and the final answer is composed
only from their returned facts and citations. The current curated general-
knowledge index is an initial implementation of the general retrieval boundary;
it may later be replaced by a vector store without changing the supervisor or
public API contracts.

No frontend change is permitted. The browser continues to call `/api/search`,
`/api/evaluate`, map, route, memory, and feedback endpoints through the existing
UI flow. In particular, the supervisor cannot initiate a browser search or UI
transition through the current `PreferenceResponse`; `ready_to_search` remains
the existing signal that lets the user proceed with Show recommendations.

## Architecture and safety rules

- Preserve the exact `PreferenceRequest`, `PreferenceResponse`, and OpenAPI
  shapes. Agent prompts, tool arguments, execution state, retrieved passages,
  and provider configuration remain backend-only.
- Add a backend-only `CONVERSATION_AGENT_MODE` with `deterministic`, `shadow`,
  and `agent` values. Missing, empty, or invalid configuration resolves to
  `deterministic`. Model clients remain lazy and unavailable in deterministic
  mode.
- In shadow mode, the existing deterministic result is the only served result.
  The agent runs without request-time writes, and comparison telemetry cannot
  contain conversation text, family data, prompts, evidence text, credentials,
  or provider error messages.
- All tool context comes from the validated request and authoritative backend
  repositories. Model-supplied school records, IDs, family values, policy
  values, rankings, prices, distances, citations, or tool configuration are
  rejected or replaced by server-owned context.
- Every turn must execute at least one registered capability tool before an
  agent answer can be accepted. A turn may make at most three tool calls, at
  most one of which may mutate preference state, and graph iterations remain
  independently bounded.
- Intent classification and tool routing are distinct contracts. The routing
  result identifies application-workflow, structured-KinderCompass,
  general-knowledge, or combined scope; the selected tool then validates its
  own typed operation and server-owned context. Low-confidence or unsupported
  routing asks for clarification or falls back rather than querying every
  source.
- Tools return an authoritative profile/state result, a deterministic answer
  candidate, grounding facts, and allowed citations. The model may select
  tools, compose bounded wording from those results, and select citation IDs;
  it may not generate or override profile state, calculations, action fields,
  evidence provenance, or other authoritative output.
- Multiple read-only tools are allowed only when the request genuinely needs
  more than one evidence scope, such as combined selected-school and general
  guidance. Existing mixed-message behavior continues to prioritize the
  requested immediate action rather than silently applying multiple state
  changes.
- Unknown tools, invalid arguments, missing required context, conflicting tool
  results, multiple mutations, malformed output, unsupported citations,
  timeouts, and execution-limit termination fail closed to the current
  deterministic conversation controller.
- The fallback path must disable conversation and selected-school agent
  re-entry so one request cannot recurse or invoke duplicate model paths.
  Memory persistence and answer-feedback recording remain outside the graph and
  occur once, after the served result is selected.
- Tests use injected models and tools and never call live providers. A rollout
  decision requires separate staged evidence from actual grounded agent
  executions in addition to deterministic automated tests.
- New tools require a typed contract, an authoritative-data boundary,
  deterministic tests, defined failure behavior, and their own checklist step.

## Capability coverage

The migration is incomplete until the supervisor covers all current
`IntentName` values and the state transitions that precede intent handling:

| Capability group | Required behavior |
|---|---|
| Preference state | Update and reset preferences; resolve pending language or pedagogy priority, contradictions, and proposed constraint relaxations; request clarification when needed. |
| Recommendation decisions | Find the closest preschool; explain the top-ranked result; compare selections; explain trade-offs and provenance; recommend or assess selected preschools. |
| Calculated scenarios | Run fee or eligibility what-if scenarios and explain Stage 2 exclusions using authoritative family, school, and policy inputs. |
| Structured school facts | Query typed, allowlisted school facts through the authoritative catalogue/knowledge-graph boundary, including food, programmes, fees, and vacancy fields when that data exists; never allow model-generated Cypher or unrestricted database access. |
| General guidance | Retrieve cited general guidance through a replaceable retrieval interface. Start with the current curated index and permit a later vector-store implementation without changing agent or HTTP contracts. |
| Combined answers | Call both structured-school and general-guidance tools when a question genuinely spans them, while keeping their evidence scopes and citations distinct. |
| School-published evidence | Retrieve selected-school webpage evidence for claims that are not authoritative structured fields, preserving school scope and resolvable citations. |
| Missing context | Return the existing actionable guidance when a school selection, eligible result set, excluded result set, family details, postal code, or evidence index is unavailable. |

## Step 1 baseline — 2026-08-31

### Request lifecycle and authoritative boundaries

`POST /api/preferences` validates the HTTP body, rejects a message containing
`closest` when no six-digit postal code is supplied, and calls
`PreferenceService.handle`. The service classifies the newest message, rebuilds
every supplied selected or eligible stable school ID through
`SchoolRepository`, optionally evaluates those records with the submitted
validated `FamilyDetails`, and attaches server-calculated distances. It then
calls the Stage 1 conversation controller. Exclusion and what-if intents are
handled directly by the service before that controller.

At this baseline, `family` and the top-level request fields are typed, and all
school facts are reloaded for stable IDs. By contrast, `profile` is an
unstructured request dictionary: the controller canonicalizes preference
fields, but `PreferenceService` also reads `active_school.school_id` and
`active_school.name` from it before repository resolution. Unknown explicit or
remembered school IDs become 404 responses; service `RuntimeError` and
`ValueError` failures become 422 responses.

The endpoint always records privacy-minimised answer metadata through
`ChatFeedbackService` and adds `answer_id`. When `remember_preferences` is true,
it also persists the returned structured profile through
`ConversationMemoryService`; a missing `anonymous_session_id` is a 422. These
are the only request-time writes. Every service result is enriched with bounded
`profile.decision_state` containing the current goal, recent intent names,
structured preference changes, unresolved-question metadata, and the internal
status. It does not store the conversation text.

The public response always requires `profile`, `understood`, `ready_to_search`,
and `question`. It may also expose `citations`, `answer_method`,
`fallback_reason`, `evidence_category`, and `answer_id`. Internal controller
fields such as `status`, `evidence_scope`, `ranking_affected`, and
`web_answer_method` are removed by FastAPI response-model serialization.

### Pre-intent state-transition inventory

These controller transitions take precedence over normal intent handling in
the order shown, except that service-level what-if and exclusion handling has
already returned before the controller is entered.

| Transition | Authoritative inputs and result | Missing or unresolved response | Side effects | Existing coverage |
|---|---|---|---|---|
| Pending constraint relaxation | Request profile's server-created `pending_relaxation` plus explicit approval/decline text. Approval changes distance, downgrades required language, or downgrades one required preference; decline removes the proposal unchanged. Returns the common fields and a ready-to-search answer. | Any other reply repeats the stored proposal with `ready_to_search=false`. | Mutates the returned profile only; endpoint persistence occurs only when requested. | `test_dialogue_manager.py`: `test_relaxation_requires_explicit_approval`, `test_declining_preserves_constraints`, `test_proposes_smallest_distance_change_without_applying_it`. |
| Pending contradiction | Request profile's `pending_contradiction` plus an explicit keep/use reply. Resolution applies the selected language or pedagogy value and clears the pending record. | An unrecognised reply repeats the contradiction question with `ready_to_search=false`. | Mutates the returned profile only. | `test_dialogue_manager.py`: conflicting-language and conflicting-pedagogy tests. |
| Finish preference collection | Existing supported preferences plus “use/based on preferences” or an exact no/no-thanks reply, with no pending importance question and no eligible results. | Not applicable; unmatched text continues routing. | Adds intent metadata and returns `ready_to_search=true`; no search is initiated. | `test_stage_flow.py`: `test_stage1_uses_understood_preferences_after_clarification`, `test_stage1_no_means_finish_preferences_when_profile_is_ready`. |
| Router clarification | `IntentResult` with confidence below 0.7 and its bounded clarification. | Uses “Could you clarify what you would like me to do?” when the classifier supplies no question. | Adds intent metadata; no preference mutation. | Intent fallback and LLM routing tests in `test_stage_flow.py`; no dedicated low-confidence assertion. |
| Pending language/pedagogy importance | Existing `pending`/`pending_queue` plus required/preferred markers. A valid answer converts the item to a hard constraint or weighted preference, then advances the queue or becomes ready. | A reply without either marker repeats “required/essential or merely preferred”. | Mutates the returned profile only. | `test_stage_flow.py`: follow-up, queued-follow-up, and understood-after-clarification tests. |
| New contradiction detection | Current canonical profile, deterministic extraction of the newest text, and explicit required markers. Stores a language or pedagogy repair choice instead of overwriting state. | Returns the repair question with `ready_to_search=false`. | Adds `pending_contradiction` to the returned profile. | `test_dialogue_manager.py`: conflicting-language, unresolved-overwrite, and pedagogy-repair tests. |
| Preference extraction clarification | Current profile and optional structured OpenAI extraction; deterministic extraction is authoritative fallback. | A low-confidence extractor question is returned with `ready_to_search=false`. | Adds extraction method/fallback metadata and possible `clarification_needed` to the returned profile. | `test_stage_flow.py`: valid extraction, extraction failure, and invalid-value fallback tests. |
| Unsupported or empty preference | Deterministic/validated extracted preference items and the supported schema. | Unsupported-only input names the unranked attributes; empty input asks for a supported preference. | Retains unsupported items in the returned profile but they cannot affect ranking. | `test_stage_flow.py`: unsupported-only and unsupported-with-existing-profile tests. |
| New importance clarification / next-best question | Newly extracted language or pedagogy without explicit importance creates `pending` (and possibly `pending_queue`). Otherwise catalogue-wide facet counts select an unanswered optional question. | If no informative facet remains, asks whether to add a preference or show recommendations. | Mutates only returned conversational profile metadata. | `test_stage_flow.py`: language, explicit-preference, and queued-follow-up tests; `test_dialogue_manager.py`: next-question tests. |

### Intent and capability inventory

All rows return the common public fields above and receive bounded decision
state. “Catalogue” below means the generated
`SystemCode/data/processed/kindercompass_master.json` reloaded by stable ID,
not browser-supplied records.

| Intent / capability | Authoritative inputs and actual runtime source | Intent-specific output and missing-context behavior | State or write effects | Existing coverage |
|---|---|---|---|---|
| `update_preferences` | Newest message, current profile, deterministic schema/rules, optional bounded extractor, and catalogue facet summary. | Updates `profile`/`understood`; asks importance or another useful preference; unsupported-only or empty input remains not ready. | Preference state changes only in returned profile; optional endpoint memory write. | Broad Stage 1 coverage in `test_stage_flow.py`, including extraction, accumulation, distance, unsupported evidence, and clarification tests. |
| `reset_preferences` | Explicit reset phrase and the deterministic preference mapper. | Clears preference state, then returns the standard “Tell me a preference…” clarification with `ready_to_search=false`. | Returned profile is reset; optional endpoint memory write. | `test_stage_flow.py::test_stage1_chat_can_reset_preferences`. |
| `needs_clarification` | Low-confidence typed router result. | Returns the router clarification and leaves search disabled. | Intent metadata only. | Indirect classifier fallback coverage; no dedicated response test. |
| `find_closest_preschool` | Eligible IDs, or the full catalogue when none are supplied; catalogue records; postal-code geocode plus authoritative location GeoJSON; haversine distance. | Returns the nearest name and distance and labels it a location result. With no records: asks for grounded records/distances; with no distances: says comparison is unavailable. A literal `closest` without postal code is rejected by the endpoint with 422; `nearest` currently reaches the no-distance response. | Sets `profile.active_school`; does not search, rank for recommendation, or change preferences. | `test_api_startup.py::test_nearest_chat_uses_postal_code_and_full_grounded_catalogue` (currently blocked by TestClient stall); closest routing and missing-candidate tests in `test_stage_flow.py`. |
| `explain_top_ranked_preschool` | Eligible IDs rebuilt from catalogue, optional family evaluation from catalogue plus policy repository, and existing ranking metrics/evidence metadata. Optional grounded wording cannot change the facts. | Explains the first eligible result; without eligible results asks the user to show recommendations first. | Explanation metadata only. | `test_stage_flow.py`: top-ranked and grounded-explanation validation/fallback tests. |
| `compare_selected_preschools` | Selected stable IDs rebuilt from catalogue, optional policy evaluation, distances when a postal code exists, and deterministic comparison facts. | Compares every selection; fewer than two asks for at least two Results-panel selections. | Explanation metadata only. | `test_stage_flow.py`: comparison, required-school grounding, and missing-selection tests. |
| `explain_selected_tradeoffs` | Selected rebuilt catalogue/evaluation records and their scorer-produced trade-offs. | Explains recorded mismatches; no selection asks for at least one Results-panel selection. | Explanation metadata only. | `test_stage_flow.py::test_phase5_explains_selected_tradeoffs` plus grounded comparison tests. |
| `explain_evidence_provenance` | Selected rebuilt records and `match_breakdown` provenance created by Stage 1 scoring from catalogue/Neo4j-compatible fields. | Lists source, reliability, and freshness, or evidence unavailable; no selection asks for a Results-panel selection. | Explanation metadata only. | `test_stage_flow.py::test_phase8_chat_explains_selected_school_sources` and evidence metadata/audit tests. |
| `recommend_selected_preschool` | Selected rebuilt records; deterministic order is match score, then estimated fee, distance, and name. Optional grounded wording cannot select a different winner. | Recommends the winning selected school; no selection asks for at least one selection. | No preference mutation; explanation metadata only. | Recommendation and deterministic-winner grounding/fallback tests in `test_stage_flow.py`. |
| `assess_selected_preschool` | Exactly one selected rebuilt record, score, strengths, trade-offs, optional evaluated fee, and optional distance. | Gives a deterministic suitability band; zero selections asks for one, multiple selections asks the user to narrow or request a recommendation. | No preference mutation; explanation metadata only. | Suitability and one-selection requirement tests in `test_stage_flow.py`. |
| `run_what_if_scenario` | Selected IDs, falling back to eligible IDs; catalogue/service fee records; submitted family; dated subsidy policy repository. Only hypothetical income and working-hours changes are parsed. | Returns baseline-versus-scenario fees/status for up to five schools. Missing family or IDs asks to show recommendations; missing hypothetical values asks for income or hours. `citations=[]`, `evidence_category=calculated_estimate`. | Copies family details and never changes saved family or profile. | `test_dialogue_manager.py::test_what_if_is_routed_and_does_not_mutate_family`; policy calculations in `test_stage2_policy.py`. |
| `explain_school_exclusion` | Excluded stable IDs reloaded from catalogue, submitted family, evaluation engine, and dated policy repository. | Returns the Stage 2 `reason`/status for a named school or first three exclusions. Missing IDs or family says no exclusions are available. `citations=[]`, `evidence_category=authoritative_fact`. | No preference mutation. | `test_dialogue_manager.py::test_exclusion_uses_stage2_reason` and Stage 2 policy tests. |
| `ask_selected_school_evidence` | Exactly one selected stable ID rebuilt from catalogue, then server-loaded `WEB_RAG_INDEX_PATH` or generated `output/web_rag_pilot_index.json`; retrieval is restricted to that school. Optional selected-school graph changes wording only after validated retrieval. | Returns school-scoped resolvable citations and `school_published_claim`. Zero/multiple selections, missing index, no matching chunks, or no concise passage produce explicit actionable/unavailable wording; absence is not treated as “no”. | No ranking/profile change; answer method/fallback metadata may be exposed. | `test_stage_flow.py` selected-school evidence tests; `test_web_rag.py`; selected-school agent tool, graph, validation, and integration tests. |
| `ask_general_knowledge` | Server-loaded curated `resources/web_rag/general_knowledge_index.json`; topic-aware deterministic retrieval. | Returns general-scoped citations and `authoritative_fact`; missing index or no relevant passage reports unavailable/not found. | Intent metadata only; no ranking change. | All routes, retrieval, comparison, semantic-priority, and subsidy cases in `test_general_knowledge_rag.py`. |
| `ask_combined_evidence` | Both the selected-school webpage index and curated general-knowledge index, with their scopes retained separately. | Prefixes school evidence and general guidance and concatenates scoped citations. Each component independently reports its own missing selection/index/evidence condition. | No ranking/profile change. | `test_general_knowledge_rag.py::test_combined_answer_keeps_school_and_general_sources_distinct`. |

### Factual-source reachability

| Source | Current `/api/preferences` use | Structured facts present but not directly answerable |
|---|---|---|
| Generated school catalogue | Direct runtime source for selected, eligible, excluded, fee/programme, ranking, and catalogue-wide closest-school records. `SchoolRecord` permits extra generated fields, but there is no allowlisted fact-query operation. | Food, service model, operating hours, transport, contact details, location, update date, and 42 level/month vacancy fields plus `has_vacancy_data` exist in the current 1,867-record file. A factual question about them is currently routed to webpage evidence rather than these fields. |
| Live Neo4j | Not queried by `/api/preferences`. It is queried by `/api/search`; IDs returned by the browser are subsequently reloaded from the generated catalogue for conversation. | The loader/query schema includes `food_offered`, `weekday_full_day`, `provision_of_transport`, `service_model`, fees, care levels, language, pedagogy, SPARK, location, and `last_updated`. These fields have no typed factual-answer route. The current graph loader does **not** copy `has_vacancy_data` or the 42 vacancy values, so those values exist only in the generated catalogue at this baseline, not in the declared Neo4j schema. |
| Dated policy repository | Used by `EvaluationService` for what-if, exclusion, and any selected/eligible rebuild that includes family details. | It supplies eligibility and subsidy calculations, not the prose used by general-guidance answers. |
| Selected-school webpage index | Used only for `ask_selected_school_evidence` and the school portion of combined answers. | It is school-published evidence, not the authority for structured catalogue fields. |
| Curated general-knowledge index | Used only for `ask_general_knowledge` and the general portion of combined answers. | It currently supplies pedagogy/framework and dated subsidy guidance; it does not establish facts about a selected school. |

Optional OpenAI intent classification, preference extraction, grounded decision
wording, and webpage synthesis are not factual sources. Each is bounded by
deterministic inputs and has a deterministic fallback.

### OpenAPI compatibility snapshot

The generated OpenAPI document references
`#/components/schemas/PreferenceRequest` for the required JSON request body and
`#/components/schemas/PreferenceResponse` for a 200 response; 422 references
`HTTPValidationError`.

| Schema | Required fields | Optional/defaulted fields at baseline |
|---|---|---|
| `PreferenceRequest` | `message` (string, 2–500 characters) | `profile`; `selected_school_ids=[]`; `eligible_school_ids=[]`; `excluded_school_ids=[]`; `family`; `home_postal_code` (six digits); `anonymous_session_id` (UUID); `remember_preferences=false`. |
| `FamilyDetails` | `dob` (date), `admission_date` (date), `gross_household_income` (number, at least 0) | `citizenship=SC`; `programme_type=full_day`; `working_hours_per_month=56`; `household_size=1`; `non_earning_dependants=0`; `special_approval=false`. |
| `PreferenceResponse` | `profile`, `understood`, `ready_to_search`, `question` | `citations=[]`; nullable `answer_method`, `fallback_reason`, `evidence_category`, and `answer_id`. `evidence_category`, when set, is one of `authoritative_fact`, `school_published_claim`, `calculated_estimate`, `parent_sentiment`, or `unknown`. |

### Baseline verification

- Full backend command: **incomplete / not passing**. It passed the first 33
  tests and then stalled for more than 60 seconds in
  `test_api_startup.ApiStartupTests.test_nearest_chat_uses_postal_code_and_full_grounded_catalogue`.
- Isolated reproduction: the same test stalled at the first
  `TestClient(main.app).post(...)`. A 15-second `SIGABRT` stack capture showed
  the test thread waiting in `starlette.testclient.handle_request` /
  `anyio.from_thread`, while the AnyIO portal thread was idle in its asyncio
  selector. The environment has FastAPI 0.141.1, Starlette 1.6.0, and HTTPX
  0.28.1 and emits Starlette's warning that its `httpx` TestClient integration
  is deprecated in favor of `httpx2`. No application handler frame appeared in
  the dump, so the evidence points to the test transport boundary rather than
  `PreferenceService` or a live external call.
- Backend isolation run: **219 tests passed in 50.183 seconds** after excluding
  all three tests that instantiate `TestClient`. The other two blocked tests are
  `test_api_rejects_legacy_client_supplied_school_objects` and
  `test_unknown_school_id_is_a_404_before_evaluation`; a verbose run reached
  the first of these and stalled in the same way. This isolation result does
  not count as a complete-suite pass.
- Frontend production build: **passed** with Next.js 14.2.31; compilation,
  lint/type checking, page-data collection, and four static pages completed.
- OpenAPI schema generation: **passed** by importing `main.app` and reading
  `app.openapi()` without a live service or TestClient.

## Step 2 implementation — 2026-08-31

The backend now parses `CONVERSATION_AGENT_MODE` as `deterministic`, `shadow`,
or `agent`; missing, empty, and invalid values fail closed to deterministic.
The conversation model entry point constructs no client in deterministic mode.
Shadow and agent modes reuse the selected-school agent's lazy, bounded provider
configuration and non-sensitive failure path.

Framework-independent, extra-forbidden contracts now cover the authoritative
conversation context, family snapshot, repository-resolved school facts,
server-loaded evidence indexes, routing decision, capability result, generated
wording and citation IDs, public citations, execution limits, and privacy-safe
metadata. Text, identifiers, collections, recursive JSON context, calls,
mutations, and iterations are bounded. Routing distinguishes application
workflow, structured KinderCompass, general knowledge, combined, and
clarification scopes.

`PreferenceService` builds one backend-only context per turn. It resolves
selected, eligible, excluded, and remembered active-school IDs through the
repository/evaluation boundary, attaches server-calculated distances, copies
validated family and profile state, records the catalogue version, and loads
both evidence indexes server-side. Closest-school requests use the full
authoritative catalogue when no eligible IDs are supplied. Existing
deterministic handling consumes these resolved schools and indexes. The HTTP
models remain unchanged.

Verification evidence:

- Step-scoped configuration, contract, model-factory, and context tests: **22
  passed**.
- Complete backend suite attempted: **stalled after 38 passes** at the known
  first `TestClient.post` boundary; interrupted after 60 seconds.
- Backend isolation run excluding the same three baseline `TestClient` tests:
  **227 tests passed in 50.485 seconds**.
- OpenAPI generation: **passed**. `/api/preferences` still references
  `PreferenceRequest` and `PreferenceResponse`, with the same required fields.
- `git diff --check`: **passed**.

## Step 3 implementation — 2026-09-06

Three typed, explicitly named preference-state tools are now registered for
updating preferences, resetting preferences, and continuing pending importance,
contradiction, or constraint-relaxation flows. Their argument contract contains
no message or profile fields: each tool is bound to the validated
`ConversationRequestContext`, so model-authored calls cannot replace the newest
message or authoritative profile state.

Every invocation deep-copies the context profile and delegates to the existing
deterministic `update_conversation` controller. This preserves extraction,
canonical schema synchronization, clarification queues, contradiction repair,
relaxation approval, next-question selection, and mixed-message precedence
without creating a second set of preference rules. Results are translated to
the shared `CapabilityToolResult`, include the complete proposed profile and
deterministic answer candidate, carry no citations, are marked as profile
mutations, and perform no memory or other persistence writes. The continuation
tool fails closed when no pending state exists.

Verification evidence:

- New preference-state tool suite: **6 tests passed**.
- Step-scoped agent contract/tool suites: **17 tests passed**.
- Existing dialogue-manager and Stage 1 regression suites: **91 tests passed**.
- Backend isolation run excluding the three known `TestClient` transport-stall
  tests: **233 tests passed in 54.368 seconds**.
- OpenAPI preference request/response references: **unchanged**.
- `git diff --check`: **passed**.

## Step 4 implementation — 2026-09-06

Nine fixed-name, read-only decision and calculation tools now cover closest-
school lookup, top-ranking explanation, selected-school comparison, trade-offs,
provenance, recommendation, suitability, fee/eligibility what-if scenarios,
and Stage 2 exclusion explanations. Each tool is bound to the validated
`ConversationRequestContext`; its argument contract contains no school,
family, distance, profile, or policy fields. The tools deep-copy authoritative
context, reuse the existing conversation controller and extracted calculation
helpers, return deterministic answer candidates and bounded grounding facts,
and perform no persistence or preference mutation.

What-if and exclusion calculations were moved into a shared service module so
the existing deterministic HTTP path and agent tools use exactly the same
family, evaluation, policy, and missing-context behavior. The saved family and
request context remain unchanged during hypothetical evaluation.

An allowlisted structured-school-facts operation is now exposed through
`SchoolRepository`. It supports food, programmes, fees, vacancy, operating
hours, transport, contact, and location projections for stable IDs already
resolved into the server context. The tool rejects unknown IDs, arbitrary
fields, and unsupported operations; no Cypher or query language crosses the
tool boundary. Catalogue results include source/version provenance, explicit
availability, and current/stale/unknown freshness. Vacancy responses include
the available monthly fields only when the catalogue marks vacancy data as
present.

Verification evidence:

- New decision, calculation, and structured-fact tool suite: **7 tests passed**.
- Step-scoped agent, context, dialogue, Stage 1, and Stage 2 regressions:
  **124 tests passed**.
- Complete backend suite attempted: **stalled after 39 passes** at the known
  first `TestClient.post` boundary; stopped by the 70-second guard.
- Backend isolation run excluding the same three baseline `TestClient` tests:
  **240 tests passed in 53.187 seconds**.
- OpenAPI preference request/response references and required fields:
  **unchanged**.
- `git diff --check`: **passed**.

## Step 5 implementation — 2026-09-06

Two context-bound, read-only evidence tools now expose selected-school webpage
retrieval and general early-childhood retrieval to the future conversation
supervisor. Both accept only a bounded question. Selected-school identity and
both indexes remain server-owned in `ConversationRequestContext`; the school
tool requires exactly one authoritative selection and reuses the existing
school-isolated `search_selected_school_evidence` implementation.

General retrieval now has a typed `GeneralKnowledgeRetriever` interface and a
`CuratedGeneralKnowledgeRetriever` adapter for the existing reviewed JSON
index. Its result contract bounds passage text and requires a matching,
general-scoped public citation with authority metadata. A later vector adapter
can implement the same interface without changing the tool or HTTP contracts.

Both tools return `CapabilityToolResult` with deterministic answer candidates,
grounding passages, and resolvable citations. Missing selection, missing index,
and no-match cases produce explicit unavailable guidance with no citations and
never turn missing evidence into a negative claim. Combined questions are
supported by calling both tools: school citations retain the authoritative
selected school ID, general citations forbid school IDs, and neither tool can
mutate the profile or persist data. The original selected-school graph tool
contract remains intact.

Verification evidence:

- New conversation evidence-tool suite: **5 tests passed**.
- Focused evidence, contract, retrieval, graph, and validation suites:
  **31 tests passed**.
- Complete backend suite attempted: **stalled after 39 passes** at the known
  first `TestClient.post` boundary; stopped by the 70-second guard.
- Backend isolation run excluding the same three known `TestClient` transport-
  stall tests: **245 tests passed**.
- OpenAPI preference request/response references and required fields:
  **unchanged**.
- Python compilation and `git diff --check`: **passed**.

## Step 6 implementation — 2026-09-06

A backend-only full-conversation supervisor graph now performs a distinct typed
routing model step before capability selection. It provides the model only the
newest bounded message, a bounded profile representation, and context-presence
signals; school records, family values, calculations, evidence, and provider
configuration remain behind the registered tools. Application-workflow,
structured-KinderCompass, general-knowledge, combined, and clarification routes
have explicit applicable-tool sets. Clarification routing terminates without
accepting an ungrounded agent answer.

The graph is compiled for one authoritative `ConversationRequestContext` and
its context-bound tool registry. It strips model-authored arguments from fixed
workflow and decision tools, replaces evidence queries with the authoritative
newest message, and leaves only the allowlisted structured-fact operation and
context-approved school IDs for repository validation. Combined routes may
execute multiple read-only tools while preserving their separate results and
citations.

Independent server-owned limits enforce at most three total tool calls, one
profile mutation, and the configured model-iteration count. No answer is
accepted before a tool runs. Final model output is restricted to bounded answer
wording and citation IDs; profile, understood preferences, readiness, evidence
category, and resolvable citation objects are assembled from capability-tool
results into a strict backend candidate contract. Universal validation,
failure normalization, and deterministic fallback remain Step 7 work.

Verification evidence:

- New supervisor graph suite: **7 tests passed**, covering structured facts,
  general retrieval, combined school/general retrieval, route/tool matching,
  authoritative argument replacement, mandatory tool use, clarification, and
  all three execution bounds.
- Focused existing and new agent contract, graph, tool, integration, and
  validation suites: **47 tests passed**.
- Complete backend suite attempted: **stalled after 39 passes** at the known
  first `TestClient.post` boundary; stopped by the 70-second guard.
- Backend isolation run excluding the same three known `TestClient` tests:
  **252 tests passed in 52.675 seconds**.
- OpenAPI preference request/response references and required fields:
  **unchanged**.
- Python compilation and `git diff --check`: **passed**.

## Step 7 implementation — 2026-09-06

The full-conversation runner now validates every completed supervisor state
before accepting its result. It verifies that the context and typed route are
unchanged, routing confidence is sufficient, every recorded call names a
registered route-applicable tool, tool-call and `ToolMessage` identities match,
counts remain within their independent bounds, and no more than one declared
profile mutation occurred. Non-combined routes reject multiple tool results;
combined routes require at least two distinct capabilities. Multiple read-only
results must agree on profile, understood preferences, and readiness, while a
mutation cannot be mixed with another tool result.

Profile validation rejects newly introduced school IDs outside the
repository-resolved context and restricts mutating results to the three
preference-state tools. The validator reconstructs the supervisor candidate
from recorded typed tool results and requires exact equality for all
server-owned fields. Generated wording is bounded and extractively checked
against deterministic answer candidates, grounding facts, and citation
metadata so unsupported factual terms cannot be introduced.

Citation validation resolves every selected ID exactly against tool-returned
citations, rejects conflicting duplicate IDs, requires citation coverage for
each evidence-producing result, and enforces tool, route, and selected-school
scope. Cross-school, general/school mixed-scope, and model-invented citations
therefore fail closed.

Graph, model, tool, timeout, routing, argument, output, consistency, citation,
and execution-limit failures are reduced to the existing fixed non-sensitive
reason vocabulary. Every failure invokes one caller-supplied legacy controller
callback under a context-local guard that forces both conversation and
selected-school agent mode lookups to deterministic. This avoids process-wide
environment mutation and prevents recursive or duplicate graph entry. Service
mode dispatch remains Step 8 work.

Verification evidence:

- New conversation validation/fallback suite: **9 tests passed**, covering
  valid acceptance, malformed output, unknown tools, forged school IDs and
  facts, cross-school and mixed-scope citations, conflicting results, multiple
  mutations, invalid arguments, tool/model failures, timeouts, both execution
  limits, fixed failure reasons, and exactly-once guarded fallback.
- Focused supervisor, configuration, contract, tool, graph, integration, and
  validation suites: **58 tests passed**.
- Complete backend suite attempted: **stalled after 39 passes** at the known
  first `TestClient.post` boundary; stopped by the 70-second guard.
- Backend isolation run excluding the same three known `TestClient` tests:
  **261 tests passed in 52.896 seconds**.
- OpenAPI preference request/response references and required fields:
  **unchanged**.
- Python compilation and `git diff --check`: **passed**.

## Step 8 implementation — 2026-09-06

`PreferenceService.handle` is now the single rollout-mode dispatcher after it
has classified the legacy intent and built one authoritative turn context.
Deterministic mode calls the extracted legacy handler directly and does not
construct capability tools or import the full-conversation runner. The legacy
handler preserves the existing what-if, exclusion, Stage 1 controller,
selected-school evidence, and decision-state enrichment paths.

Shadow mode computes and serves one deterministic result, then runs the full-
conversation supervisor only for comparison. Its fallback callback returns a
deep copy of that already-computed response, so a failed shadow execution does
not invoke the legacy controller twice. Supervisor setup or execution errors
cannot alter or fail the served response. All context-bound preference,
decision, calculation, structured-fact, selected-school evidence, and general-
knowledge tools are registered only in shadow or agent mode and perform no
persistence.

Agent mode serves the response only after `run_conversation_supervisor` has
validated it. Successful agent profiles receive the same bounded decision-state
enrichment as legacy responses. Validation failures use the runner's exactly-
once deterministic fallback; failures while constructing the registry also
return one deterministic result with fixed non-sensitive fallback metadata.
The existing selected-school graph is context-locally disabled for every
legacy response used by shadow or agent mode, preventing nested or duplicate
graph execution. Conversation-memory and answer-feedback writes remain in the
HTTP endpoint after `PreferenceService.handle` selects the served response and
therefore still occur exactly once.

Endpoint-level tests invoke the unchanged `/api/preferences` handler contract
in all three modes and validate every result through the existing
`PreferenceResponse`. They confirm identical public key shapes and verify that
memory receives the selected profile and answer feedback records the selected
response after dispatch.

Verification evidence:

- New conversation mode and endpoint integration suite: **5 tests passed**.
- Backend isolation run excluding the same three known `TestClient` transport-
  stall tests: **265 tests passed in 52.555 seconds**.
- Complete backend suite attempted: **stalled after 39 passes** at the known
  first `TestClient.post` boundary; stopped by the 70-second guard.
- OpenAPI preference request/response references and required fields:
  **unchanged**.
- Python compilation and `git diff --check`: **passed**.

## Step 9 implementation — 2026-09-06

A versioned, ordered evaluation set now covers all 15 legacy `IntentName`
values plus pending importance, contradiction, relaxation, reset, missing-
context, and ambiguity transitions. Its factual routing cases explicitly cover
Singapore subsidy guidance, selected-school food, vacancy, an unavailable
structured field, school-published evidence, and a combined school/general
question. Inputs are synthetic and validated by a strict backend-only schema.

The offline evaluator accepts an injected turn runner, compares legacy intent
selection with agent route and tool choice, and checks exact profile/readiness/
understood state parity, grounding acceptance, citation validity and scope, and
bounded response usefulness. Reports contain only reviewed case IDs, booleans,
aggregate rates, tool names, bounded execution counts, latency, termination,
validation outcome, and normalized fallback reason. Messages, answers,
profiles, family values, evidence text, URLs, provider errors, and prompts are
never included.

Runtime shadow and agent attempts now emit the same privacy-minimised execution
surface through a strict observation contract. Shadow observations add only
three comparison booleans for profile, citations, and readiness; agent setup
failures emit a normalized `validation_error`. Telemetry construction can read
the served and candidate results only to calculate equality and never
serializes their content.

The staged evaluator deliberately requires an explicit acknowledgement because
it uses the configured provider and real authoritative repositories. From the
repository root, its reserved command is:

```bash
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python -m SystemCode.src.backend.scripts.evaluate_conversation_supervisor \
  --staged --output SystemCode/src/backend/output/conversation_agent_evaluation.json
```

This live staged run was not executed in the automated session and is not a
rollout decision; that gate belongs to Step 10.

Verification evidence:

- New evaluation and observability coverage: **4 tests passed**.
- Focused conversation supervisor, validation, mode, evaluation, and
  observability suites: **25 tests passed**.
- All legacy `test_*agent*.py` regressions: **38 tests passed**.
- Backend isolation run excluding the same three known `TestClient` transport-
  stall tests: **270 tests passed in 53.281 seconds**.
- OpenAPI preference request/response references and required fields:
  **unchanged**.
- Python compilation, staged-command help/import validation, and
  `git diff --check`: **passed**.

## Step 10 compatibility decision — 2026-09-06

The rollout decision is **no-go**. `CONVERSATION_AGENT_MODE` remains
`deterministic`; agent mode remains an explicit backend opt-in and was not made
the default.

The compatibility gates produced the following evidence:

- Complete backend suite: **not passing**. With the documented `PYTHONPATH`,
  the run reached
  `test_api_startup.ApiStartupTests.test_nearest_chat_uses_postal_code_and_full_grounded_catalogue`
  and stalled at the known Starlette/HTTPX `TestClient.post` boundary. The
  80-second guarded run timed out there.
- Backend isolation run excluding the three previously identified
  `TestClient.post` tests: **270 tests passed in 52.592 seconds**.
- Frontend production build: **passed** with Next.js 14.2.31. There are no
  tracked frontend changes and no frontend agent contract was added.
- OpenAPI compatibility: **passed**. `/api/preferences` still references
  `PreferenceRequest` and `PreferenceResponse`; their required fields remain
  `message`, and `profile`/`understood`/`ready_to_search`/`question`,
  respectively.
- Staged evaluation: **incomplete**. The first attempt exposed malformed
  synthetic pending-contradiction and pending-relaxation fixtures; those were
  corrected to the controller's server-created profile shapes and the focused
  evaluation tests passed. The rerun invoked the configured provider but
  stopped at the grounded closest-school case because the environment lacks
  `ONEMAP_EMAIL` and `ONEMAP_PASSWORD`. No staged report or aggregate metrics
  were produced, so the structural, citation, discrepancy, tool-selection,
  and fallback thresholds are unevaluated and therefore cannot authorize
  rollout.

No production default was changed. A future rollout review must first resolve
the `TestClient` transport stall, provide the required staged OneMap
configuration, rerun the full staged set to completion, and satisfy every
threshold in the Step 10 definition.

## Migration checklist

| Step | Status | Owner | Completion date | Files changed | Tests run |
|---|---|---|---|---|---|
| 1. Record the full-conversation baseline | complete | Architecture and progress owner | 2026-08-31 | `backend/doc/agents.md` | Full backend suite attempted: stalled after 33 passes in TestClient; 219 non-TestClient tests passed; frontend `npm run build` passed; OpenAPI snapshot generated. |
| 2. Define supervisor configuration, contracts, and authoritative context | complete | Graph and configuration owner | 2026-08-31 | `backend/agents/config.py`, `backend/agents/contracts.py`, `backend/agents/model_factory.py`, `backend/services/preference_service.py`, four scoped test modules, `backend/doc/agents.md` | 22 scoped tests and 227 non-TestClient backend tests passed; full suite reproduced the known TestClient stall after 38 passes; OpenAPI compatibility and `git diff --check` passed. |
| 3. Extract preference-state tools | complete | Conversation-state tool owner | 2026-09-06 | `backend/agents/contracts.py`, `backend/agents/tools.py`, `backend/agents/__init__.py`, `backend/tests/test_preference_state_tools.py`, `backend/doc/agents.md` | 6 new scoped tests, 17 agent contract/tool tests, 91 dialogue/Stage 1 regressions, and 233 non-TestClient backend tests passed; OpenAPI compatibility and `git diff --check` passed. |
| 4. Extract decision and calculation tools | complete | Decision-tool owner | 2026-09-06 | `backend/agents/__init__.py`, `backend/agents/contracts.py`, `backend/agents/tools.py`, `backend/repositories/school_repository.py`, `backend/services/conversation_calculations.py`, `backend/services/preference_service.py`, `backend/tests/test_decision_tools.py`, `backend/doc/agents.md` | 7 new scoped tests, 124 agent/decision/policy regressions, and 240 non-TestClient backend tests passed; full suite reproduced the known TestClient stall after 39 passes; OpenAPI compatibility and `git diff --check` passed. |
| 5. Complete the evidence toolset | complete | Evidence-tool owner | 2026-09-06 | `backend/agents/__init__.py`, `backend/agents/contracts.py`, `backend/agents/tools.py`, `backend/tests/test_evidence_tools.py`, `backend/doc/agents.md` | 5 new scoped tests, 31 evidence/agent regressions, and 245 non-TestClient backend tests passed; full suite reproduced the known TestClient stall after 39 passes; OpenAPI compatibility, Python compilation, and `git diff --check` passed. |
| 6. Build the bounded conversation supervisor | complete | Graph and configuration owner | 2026-09-06 | `backend/agents/__init__.py`, `backend/agents/contracts.py`, `backend/agents/supervisor.py`, `backend/tests/test_conversation_supervisor.py`, `backend/doc/agents.md` | 7 new supervisor tests, 47 focused agent regressions, and 252 non-TestClient backend tests passed; full suite reproduced the known TestClient stall after 39 passes; OpenAPI compatibility, Python compilation, and `git diff --check` passed. |
| 7. Add result validation and legacy fallback | complete | Validation and safety-test owner | 2026-09-06 | `backend/agents/__init__.py`, `backend/agents/config.py`, `backend/agents/supervisor.py`, `backend/agents/validation.py`, `backend/tests/test_conversation_validation.py`, `backend/doc/agents.md` | 9 new validation/fallback tests, 58 focused agent regressions, and 261 non-TestClient backend tests passed; full suite reproduced the known TestClient stall after 39 passes; OpenAPI compatibility, Python compilation, and `git diff --check` passed. |
| 8. Integrate deterministic, shadow, and agent modes | complete | Service integration owner | 2026-09-06 | `backend/services/preference_service.py`, `backend/tests/test_conversation_modes.py`, `backend/doc/agents.md` | 5 new mode/endpoint tests and 265 non-TestClient backend tests passed; full suite reproduced the known TestClient stall after 39 passes; OpenAPI compatibility, Python compilation, and `git diff --check` passed. |
| 9. Add full-conversation evaluation and observability | complete | Evaluation and observability owner | 2026-09-06 | `backend/agents/evaluation.py`, `backend/agents/observability.py`, `backend/agents/__init__.py`, `backend/services/preference_service.py`, `backend/resources/conversation_agent_evaluation.json`, `backend/scripts/evaluate_conversation_supervisor.py`, `backend/tests/test_conversation_evaluation.py`, `backend/tests/test_conversation_modes.py`, `backend/doc/agents.md`, resource/script guides | 4 new evaluation/observability tests, 25 focused supervisor/mode regressions, 38 legacy agent regressions, and 270 non-TestClient backend tests passed; OpenAPI compatibility, staged command import/help, Python compilation, and `git diff --check` passed. |
| 10. Run compatibility gates and decide rollout | complete | Architecture and progress owner | 2026-09-06 | `backend/resources/conversation_agent_evaluation.json`, `backend/doc/agents.md` | No-go: frontend build and OpenAPI checks passed; 270 non-TestClient tests passed; complete backend suite timed out at the known TestClient stall; staged evaluation could not complete without OneMap credentials; deterministic remains the default. |

## Step definitions

### Step 1 — Record the full-conversation baseline

- Inventory every current intent and every pre-intent state transition in
  `PreferenceService` and the Stage 1 conversation controller. Record the
  authoritative inputs, output fields, missing-context response, side effects,
  and existing test coverage for each capability in the table above.
- For every factual intent, record its actual runtime source separately:
  generated school catalogue, live Neo4j query, policy repository,
  selected-school webpage index, or curated general-knowledge index. Explicitly
  identify structured fields that exist in Neo4j but are not yet reachable from
  `/api/preferences`, including food and vacancy-related data.
- Snapshot the `POST /api/preferences` OpenAPI request and response references
  and all currently required fields so later steps can prove compatibility.
- Run the complete backend suite and frontend production build without changing
  executable code. Investigate and record the known TestClient startup stall;
  do not treat a partial run as a passing baseline.

### Step 2 — Define supervisor configuration, contracts, and context

- Add strict framework-independent contracts for a server-built conversation
  request context, routing decision, capability-tool result, generated answer,
  public citations, execution limits, and privacy-safe metadata. The routing
  decision distinguishes application-workflow, structured-KinderCompass,
  general-knowledge, combined, and clarification scopes. Extra fields are
  forbidden and all text and collections are bounded.
- Add `CONVERSATION_AGENT_MODE=deterministic|shadow|agent`, defaulting safely to
  `deterministic`, and reuse the lazy shared model factory without constructing
  a client in deterministic mode.
- Build one authoritative context in `PreferenceService` from the request's
  stable IDs, repository data, evaluated schools, family details, postal-code
  distances, current profile, and server-loaded evidence indexes. No agent
  contract is added to the HTTP models.

### Step 3 — Extract preference-state tools

- Register typed tools for updating preferences, resetting preferences, and
  continuing pending clarification, contradiction, and relaxation flows.
- Refactor existing deterministic functions rather than duplicating their
  rules. Each tool operates on a copy and returns the complete proposed profile
  plus its deterministic answer candidate; it performs no persistence.
- Mark these tools as state-mutating so graph validation can enforce the
  one-mutation-per-turn rule and preserve existing mixed-message precedence.

### Step 4 — Extract decision and calculation tools

- Register typed read-only tools for closest-school lookup, top-ranking
  explanation, selected-school comparison, trade-offs, provenance,
  recommendation, suitability, what-if scenarios, and exclusion explanations.
- Inject selected, eligible, and excluded schools plus family and distance
  context server-side. Tools must delegate to existing ranking, evaluation,
  policy, and location logic and return deterministic answer candidates.
- Cover missing selections, family details, postal codes, eligible results, and
  excluded results with the current actionable responses rather than allowing
  the model to infer absent facts.
- Add a typed structured-school-facts tool behind a repository interface. It
  accepts an allowlisted operation and server-resolved stable school IDs, then
  returns only authoritative fields and provenance from the catalogue or
  Neo4j. It must cover food and vacancy questions when those fields are present,
  report unavailable or stale data explicitly, and never accept model-authored
  Cypher.

### Step 5 — Complete the evidence toolset

- Reuse `search_selected_school_evidence` and add a typed general-knowledge
  retrieval interface. Its first adapter may use the current curated index; a
  later vector-store adapter must preserve the same bounded query, result,
  provenance, and citation contracts. Both retrieval tools accept the user's
  bounded question but use server-owned indexes and authoritative scope.
- Support combined evidence by calling both read-only tools. Preserve school
  and general citation metadata, reject cross-school evidence, and distinguish
  unavailable information from negative evidence.
- Retain deterministic answer candidates for selected, general, and combined
  evidence so validation or model failure always has a grounded fallback.

### Step 6 — Build the bounded conversation supervisor

- Compile a supervisor graph that receives the authoritative context, produces
  a typed routing decision, requires a registered capability tool, and lets the
  model choose the next applicable tool based on the newest message and bounded
  profile context. General questions route to general retrieval; school facts
  route to structured data or school-published evidence according to the field;
  combined questions may call both.
- Enforce three total tool calls, one state mutation, and a separately bounded
  model-iteration count. Ignore or reject model arguments that conflict with
  authoritative context.
- After tool execution, require structured output containing only bounded
  answer wording and citation IDs. Assemble all other response fields from the
  accepted tool result.

### Step 7 — Add result validation and legacy fallback

- Validate tool identity, call counts, mutation counts, profile invariants,
  authoritative result consistency, answer bounds, and exact citation
  resolution before accepting an agent result.
- Reduce failures to a fixed non-sensitive reason vocabulary. On every failure,
  invoke the existing controller once with both agent entry points disabled and
  return its complete deterministic result.
- Test malformed output, unknown tools, forged IDs or facts, cross-school and
  mixed-scope citations, multiple mutations, tool/model exceptions, timeouts,
  and both execution limits.

### Step 8 — Integrate deterministic, shadow, and agent modes

- Make `PreferenceService.handle` the single mode dispatcher for every
  `/api/preferences` message. Deterministic mode retains the existing path;
  shadow mode serves that exact result while evaluating the agent without
  writes; agent mode serves only a validated graph result or legacy fallback.
- Ensure the existing selected-school answer mode cannot cause nested graph or
  duplicate model execution. Keep conversation memory and answer-feedback
  writes after served-result selection.
- Validate results through the unchanged `PreferenceResponse` and add endpoint-
  level tests proving identical frontend-visible shapes in every mode.

### Step 9 — Add evaluation and observability

- Create an ordered, curated evaluation set covering every intent, combined
  evidence, missing context, ambiguous requests, and multi-turn pending,
  contradiction, relaxation, and reset transitions.
- Include explicit routing cases for Singapore subsidy guidance, selected-school
  food, vacancy availability, missing structured fields, school-published
  claims, and questions that combine a school fact with general guidance.
- Compare deterministic and agent tool choice, profile/state output, grounding,
  citations, and response usefulness. Tests use injected models; a documented
  staged command is reserved for real grounded executions.
- Emit only allowlisted aggregate and per-case booleans, tool names, bounded
  counts, latency, termination reason, validation outcome, and normalized
  fallback reason. Do not emit request or response content or private context.

### Step 10 — Run compatibility gates and decide rollout

- Require a complete backend suite, frontend production build, unchanged
  OpenAPI request/response schemas, and confirmation that no frontend files or
  frontend agent contracts changed.
- Require staged results with 100% structural and citation validity, zero
  authoritative profile/calculation discrepancies, at least 95% accepted tool
  selection, and at most 5% agent fallback across the curated suite.
- Record a go/no-go decision. Keep `CONVERSATION_AGENT_MODE=deterministic` on
  any failed or unevaluated gate; if every gate passes, make agent mode an
  explicit backend opt-in rather than the default.

## Decision log

- 2026-08-29 — Define “all conversation” as every natural-language turn sent
  to `POST /api/preferences`. Preserve the browser-controlled search,
  evaluation, map, route, memory, and feedback flows because changing those
  flows would require a new frontend contract.
- 2026-08-29 — Use the model as a bounded supervisor and response composer,
  not as an authority for profile state, ranking, eligibility, fees, distance,
  school facts, or evidence provenance.
- 2026-08-29 — Preserve the current deterministic conversation controller as
  the universal fallback and introduce the supervisor through deterministic,
  shadow, and explicit opt-in agent modes.
- 2026-08-29 — Split the migration into ten independently testable steps and
  retain the one-step-per-session gate.
- 2026-08-31 — Separate the closed Implementation 1 record from this active
  Implementation 2 plan so historical constraints cannot be mistaken for the
  current supervisor scope.
- 2026-08-31 — Define the supervisor around explicit intent and data-source
  routing: application workflow, structured KinderCompass catalogue/knowledge-
  graph facts, general retrieval, and combined turns. Keep general retrieval
  replaceable so the curated index can later move to a vector store without
  changing the supervisor or HTTP contracts.
- 2026-08-31 — Record the Implementation 2 baseline without changing executable
  code. `/api/preferences` currently reloads factual school context from the
  generated catalogue and does not query Neo4j; structured school questions
  lack a catalogue/graph fact route. Keep the full backend gate failing until
  the Starlette/HTTPX TestClient stall is resolved, despite all 219 unaffected
  tests and the frontend production build passing.
- 2026-08-31 — Keep full-conversation rollout configuration independent from
  the selected-school answer switch while reusing one lazy provider factory.
  Build a strict authoritative context before deterministic handling so later
  supervisors cannot obtain school, family, distance, or retrieval facts from
  model-authored arguments. Preserve the HTTP models unchanged. The known
  TestClient transport stall remains open; all 227 unaffected tests pass.
- 2026-09-06 — Bind preference-state tools to the server-built turn context and
  expose no model-authored message or profile arguments. Reuse the deterministic
  conversation controller on a fresh profile copy for every invocation, mark
  all three tools as mutations for the future one-mutation guard, and reject a
  pending-flow call when the authoritative profile has no pending state.
- 2026-09-06 — Bind all decision and calculation tools to authoritative turn
  context and reuse the existing deterministic controller and shared scenario
  helpers. Treat them as read-only capabilities even when their returned
  response carries deterministic conversational metadata. Restrict structured
  school queries to allowlisted repository projections and context-approved
  stable IDs, with explicit catalogue provenance, availability, and freshness;
  do not expose Cypher or arbitrary field selection.
- 2026-09-06 — Keep the original selected-school retrieval contract for its
  existing graph and wrap it with a context-bound conversation capability that
  supplies the authoritative school scope. Define general retrieval behind a
  typed interface, initially adapted to the curated index. Combined evidence is
  two bounded read-only calls rather than a third tool, so school and general
  citations remain independently scoped and unavailable evidence remains
  distinct from a negative fact.
- 2026-09-06 — Compile the full-conversation supervisor for exactly one
  authoritative turn context and an explicit context-bound tool registry.
  Separate typed routing from tool selection, restrict each route to applicable
  capabilities, replace model-authored context arguments with server-owned
  values, and require at least one tool result before structured answer
  composition. Enforce tool-call, mutation, and model-iteration limits in the
  graph; defer universal result validation and deterministic fallback to Step
  7 so rollout modes remain unintegrated.
- 2026-09-06 — Accept a conversation-agent result only after reconstructing it
  from the exact registered tool-call transcript and enforcing route, count,
  mutation, profile, grounding, and citation invariants. Normalize every
  failure to the fixed backend reason vocabulary and invoke one deterministic
  fallback callback inside a context-local guard that disables both graph entry
  points. Keep this runner independent of `PreferenceService` mode dispatch
  until Step 8.
- 2026-09-06 — Make `PreferenceService.handle` the single rollout dispatcher.
  Keep deterministic mode lazy, serve one unchanged deterministic result in
  shadow mode while discarding the agent candidate, and serve agent mode only
  through the validated runner or its one legacy fallback. Reuse the computed
  shadow response as the runner fallback and disable the selected-school graph
  in shadow and agent fallback contexts so one request cannot duplicate graph
  or controller execution. Keep memory and feedback persistence after served-
  result selection in the unchanged HTTP endpoint.
- 2026-09-06 — Evaluate the full-conversation supervisor from one ordered,
  versioned set of synthetic turns that covers every legacy intent, required
  state transition, source route, and missing-context condition. Keep raw turn
  content entirely out of reports and runtime telemetry: expose only reviewed
  case IDs, booleans, tool names, bounded counts and latency, termination and
  validation status, and normalized fallback reasons. Require an explicit
  `--staged` acknowledgement for configured-provider runs and defer all rollout
  thresholds and the go/no-go decision to Step 10.
- 2026-09-06 — Record a no-go rollout decision. The frontend build, unchanged
  OpenAPI boundary, and 270-test backend isolation suite pass, but the complete
  backend suite still stalls at the deprecated Starlette/HTTPX TestClient
  boundary and the staged evaluation cannot complete without configured
  OneMap credentials. Correct the reviewed pending-state fixtures discovered by
  the staged run, keep `CONVERSATION_AGENT_MODE=deterministic`, and require a
  new compatibility review after both blocking gates can run to completion.

## Next step

None — Implementation 2 is closed with a no-go rollout decision. Begin a new
review only after the TestClient transport and staged OneMap configuration
blockers are resolved.
