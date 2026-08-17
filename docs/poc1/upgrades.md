# KinderCompass PoC 1 upgrades

## Purpose

This document records the main improvements made to PoC 1 and highlights the difference between the earlier behaviour and the current implementation. The overall direction has been to improve conversational flexibility without allowing an LLM to control filtering, ranking, eligibility, fees, or distance calculations.

## Upgrade summary

| Area | Before | After |
|---|---|---|
| Dataset coverage | Schools without complete enrichment could be omitted or difficult to distinguish | All 1,867 school records are retained with enrichment-coverage flags |
| Stage 1 chat | Individual messages were interpreted with keyword rules and could accidentally return every school | Preferences accumulate across turns, unrecognised input is clarified, and search requires explicit confirmation |
| Preference importance | Requirements and preferences were not consistently distinguished | Language and pedagogy can be clarified as required/essential or preferred |
| Preference evidence | Recognised wording could imply that matching school evidence existed | Preferences are classified as supported, partially supported, or unsupported |
| Natural-language understanding | Limited to predefined keywords and phrases | Optional LLM extraction maps natural language into a strictly validated schema |
| LLM failure handling | Not applicable because no LLM was used | Invalid output, timeout, or API failure automatically falls back to deterministic rules |
| Recommendation explanations | Selected schools were compared using a fixed Python response template | The deterministic decision can optionally be explained naturally by a grounded LLM |
| Suitability questions | Initially treated as ordinary preference messages | One selected school can be assessed deterministically, with an optional grounded explanation |
| User workflow | Chat came first and Family details were collected after search | Family details are completed first and unlock the chat; saved details are reused automatically |
| Results and map | Limited single-school interaction | Multiple schools can be selected, mapped, filtered by distance, and compared independently with home |
| Distance preference | Distance was only a manual Results-panel filter and was not understood by chat | Chat recognises any positive maximum distance, including decimals such as 1.5 km, displays it with the understood preferences, and applies it to the full candidate set using the saved home postal code; distance remains optional |
| Closest-school questions | “Which preschool is closest?” could be mistaken for an incomplete distance preference | A closed-set intent router distinguishes nearest-school questions from maximum-distance preferences; the backend calculates distances for every eligible result and returns the minimum-distance preschool |

## 1. Complete school coverage

### Before

The combined dataset depended heavily on `centre_code` enrichment. Records identified only by `tp_code`, or records missing a particular enrichment source, risked being excluded from downstream processing.

### After

The processed catalogue retains all 1,867 unique school records. Each record has a stable `school_id` and coverage indicators including:

- `has_location`;
- `has_fee_data`;
- `has_licence_data`; and
- `has_vacancy_data`.

Missing enrichment is represented as unavailable evidence instead of being treated as a reason to delete a school. Features that depend on missing evidence, such as distance or fees, can report that limitation explicitly.

## 2. Conversational Stage 1 preference collection

### Before

Each chat message was interpreted mainly through keyword matching. A broad or unrecognised request such as `montessori` could result in an overly broad search, including all schools. Preferences were not reliably accumulated or corrected across turns.

### After

The chat maintains a cumulative structured profile. Users can:

- add preferences over several messages;
- correct an earlier preference;
- change a language from required to preferred;
- clear or reset the profile;
- receive follow-up questions for ambiguous importance; and
- explicitly click **Show recommendations** before Neo4j is queried.

An unrecognised request no longer silently produces every school.

Relevant implementation:

- [`conversation.py`](../../SystemCode/src/backend/pipeline/stage1/conversation.py)
- [`nlp_mapper.py`](../../SystemCode/src/backend/pipeline/stage1/nlp_mapper.py)

## 3. Evidence-aware preference schema

### Before

Preferences were stored in loosely structured dictionaries. The system did not consistently communicate whether a preference could actually be verified against school data.

For example, the chatbot could understand requests about hands-on learning or atmosphere even though no corresponding school evidence existed.

### After

Schema version 2 gives each canonical preference:

- an attribute and controlled value;
- `required` or `preferred` importance;
- extraction confidence;
- an evidence classification;
- the school property used for matching; and
- an evidence warning where necessary.

Evidence classes are:

- `supported`;
- `partially_supported`; and
- `unsupported`.

Unsupported preferences are retained in the conversation but are not used for ranking. This lets the system acknowledge a parent's need without claiming that the current dataset can verify it.

Relevant documentation:

- [`PREFERENCE_COVERAGE_AUDIT.md`](PREFERENCE_COVERAGE_AUDIT.md)
- [`PREFERENCE_SCHEMA.md`](PREFERENCE_SCHEMA.md)

## 4. Optional LLM preference extraction

### Before

The chatbot could only recognise wording covered by deterministic rules. Natural descriptions such as the following could be missed:

> I need a centre that can look after my child from morning until evening.

The rules recognise `full day`, but not every natural paraphrase of that concept.

### After

Phase 3 optionally uses an LLM to extract preferences into the Phase 2 schema. The LLM is limited to language interpretation. It cannot search Neo4j or calculate school rankings.

Every model result is validated against controlled attributes and values. Runtime status is recorded as:

- `llm` when structured extraction succeeds;
- `rules` when LLM extraction is disabled; or
- `rules_fallback` when an API, timeout, parsing, or validation failure causes deterministic fallback.

Only the newest preference message and existing canonical preferences are sent to the model. Family form values, income, dates, postal code, selected-school results, and chat history are excluded.

Relevant implementation and documentation:

- [`llm_extractor.py`](../../SystemCode/src/backend/pipeline/stage1/llm_extractor.py)
- [`PHASE3_LLM_EXTRACTION.md`](PHASE3_LLM_EXTRACTION.md)

## 5. Selected-school recommendation

### Before

The chatbot did not initially understand questions such as:

> Which of the selected preschools would you recommend to me?

The question could be processed as another preference message.

### After

The chatbot recognises the question as a contextual comparison. Only schools selected in the Results panel are considered. Deterministic Python logic prioritises:

1. preference-match score;
2. estimated monthly cost as a tie-breaker; and
3. distance from home as a further tie-breaker.

If no school is selected, the user is prompted to make a selection first.

## 6. Selected-school suitability assessment

### Before

The question below was initially not recognised as a school assessment:

> Is the selected school suitable for me?

It fell through to the general preference flow and could receive a response such as “Would you like to add another preference or show recommendations?”

### After, before Phase 4

The system learned to recognise suitability intent. With exactly one school selected, deterministic Python logic produced a fixed-template assessment using:

- preference-match score;
- strengths;
- trade-offs;
- estimated monthly cost; and
- distance from home.

With no selection, the user was asked to select a school. With multiple selections, the user was asked to select only the school to assess.

### After Phase 4

The deterministic suitability verdict still remains authoritative. Phase 4 optionally supplies the selected-school facts and fixed verdict to an LLM, which writes a more natural, contextual explanation.

Therefore, Phase 4 did **not** introduce the ability to answer the suitability question. It upgraded the explanation:

```text
Before Phase 4
Question -> deterministic assessment -> fixed response template

After Phase 4
Question -> deterministic assessment -> retrieved selected-school facts
         -> grounded LLM explanation
         -> deterministic fallback if needed
```

## 7. Grounded explanations and structured RAG

### Before

Recommendation and suitability responses used deterministic templates. They were explainable but could sound rigid and did not adapt their wording well to the available evidence.

### After

Phase 4 provides optional structured RAG. Retrieval comes from current application state rather than a vector database. The grounding context is limited to:

- selected school ID and name;
- match score and evidence confidence;
- strengths and trade-offs;
- eligible care level;
- estimated net monthly fee;
- calculated home distance; and
- canonical preferences and evidence warnings.

The LLM cannot change the winning school or suitability verdict. Its response must reference the deterministically decided selected-school ID and cannot reference an unselected school.

Runtime status is recorded as:

- `llm_grounded`;
- `deterministic`; or
- `deterministic_fallback`.

Relevant implementation and documentation:

- [`grounded_explainer.py`](../../SystemCode/src/backend/pipeline/stage1/grounded_explainer.py)
- [`PHASE4_GROUNDED_EXPLANATIONS.md`](PHASE4_GROUNDED_EXPLANATIONS.md)

## 7.1 Phase 5 recommendation transparency

### Before

Parents could request a winner or suitability verdict, but could not directly ask why the first result ranked highest, compare several selected schools across the available metrics, or request their recorded trade-offs.

### After

The closed intent catalogue now includes ranking explanations, selected-school comparisons, and selected-school trade-off explanations. Deterministic answers use match score, evidence confidence, match breakdown, strengths, trade-offs, estimated cost, and calculated distance. Cost and distance are presented as comparison information and are not misrepresented as Stage 1 ranking inputs.

Optional grounded LLM wording must reference the top-ranked school for a ranking explanation and every selected school for a multi-school comparison. Otherwise, the system returns its deterministic fallback.

See [`PHASE5_RECOMMENDATION_TRANSPARENCY.md`](PHASE5_RECOMMENDATION_TRANSPARENCY.md).

## 7.2 Phase 6 ranking quality and personalisation

### Before

Unknown school evidence received half-credit, preference importance was controlled by fixed internal weights, required scored preferences could remain as mismatches, and parents could not inspect the point calculation.

### After

Unknown evidence earns no compatibility credit and is separated from the verified match percentage through evidence confidence. Parents can choose Required, High priority, Preferred, or Nice to have for adjustable preferences. Proven failures of required supported preferences are excluded, while genuinely unknown evidence remains visible rather than being assumed to match or fail.

Each result now includes an expandable calculation showing the evidence status, importance, and verified contribution for every scored preference.

See [`PHASE6_RANKING_QUALITY.md`](PHASE6_RANKING_QUALITY.md).

## 7.3 Phase 7 recommendation evaluation and observability

### Before

Ranking behavior was covered by individual unit tests, but there was no standalone golden-scenario audit, machine-readable evaluation report, or request-level view of how many candidates survived each recommendation stage.

### After

A privacy-safe evaluator runs synthetic golden scenarios and produces Markdown or JSON. It fails with a non-zero exit code when an expected constraint, score, or ordering changes. Search and evaluation responses also expose aggregate stage-count traces connected by a random trace ID. These traces exclude family details, postal codes, income, dates, and chat content.

See [`PHASE7_RECOMMENDATION_EVALUATION.md`](PHASE7_RECOMMENDATION_EVALUATION.md).

## 7.4 Phase 8 evidence provenance and freshness

### Before

The score breakdown reported match status and confidence but did not state where individual facts came from, whether a negative value was confirmed or merely missing, whether a field was derived, or whether its source date was stale.

### After

Every scored preference carries source, method, reliability, source date, freshness, evidence state, and value state. The parent-facing UI presents the concise fields **Source**, **Evidence**, and **Last updated**, while engineering audits retain detailed freshness and value-state terminology. The chatbot can explain sources and missing evidence for selected schools. A catalogue audit reports confirmed negatives, unknowns, derivations, coverage, and freshness.

`General` pedagogy is now correctly treated as unknown because it means no specific pedagogy keyword was detected in the centre name. It is not used as proof that a school has a general pedagogy or fails another pedagogy requirement.

See [`PHASE8_EVIDENCE_PROVENANCE.md`](PHASE8_EVIDENCE_PROVENANCE.md).

## 7.5 Phase 9 official-webpage RAG foundation

### Before

The application had no curated webpage source inventory for enriching unsupported preferences. Website fields existed in the processed catalogue, but shared operator pages, unique centre candidates, social pages, and missing URLs had not been separated.

### After

An offline inventory normalises both catalogue website fields, removes tracking parameters, detects shared URLs, and classifies scope. A deterministic verifier approves strong school matches, while shared URLs remain operator evidence. Processing is incremental, with atomic checkpoints and age-based refresh. Structured failure codes distinguish policy refusal, rate limits, timeouts, DNS/network/server errors, missing pages, unsafe targets, unsupported content, oversized responses, and JavaScript-only pages. Temporary failures use scheduled exponential-backoff retries; permanent failures are skipped. URLs and hashes distinguish webpage changes, while last-known evidence survives temporary refresh failures with an explicit error and freshness label. School-isolated BM25 retrieval remains explanation-only and disconnected from ranking.

See [`PHASE9_WEBPAGE_RAG.md`](PHASE9_WEBPAGE_RAG.md).

## 8. Family-first workflow

### Before

Users started in the chat. Family details were requested only after Stage 1 search, creating an interrupted workflow and requiring the application to wait before it could evaluate age eligibility and fees.

### After

Family details are Step 1. The chat input remains disabled until the form is saved. The saved details are then reused automatically when the user clicks **Show recommendations**:

```text
Family details -> preference chat -> explicit search confirmation
               -> Neo4j search -> eligibility and fee evaluation -> results
```

This avoids asking for the same data twice and ensures the results are already age- and fee-evaluated when displayed.

## 9. UI, results, and mapping

### Before

The interface did not consistently preserve space for chat history, and map comparison was oriented around a more complex journey model.

### After

The UI now provides:

- a left chat panel;
- a top-right form/results panel;
- a bottom-right live map;
- a collapsible **Understood preferences** panel;
- an always-visible **Show recommendations** action after preferences exist;
- a stable chat composer and scrollable message history;
- immediate home pinning from postal code;
- multiple preschool selection;
- school pins and independent home distances; and
- result filtering within 1, 2, 3, 4, or 5 km.

Stage 3 now compares home directly with each selected preschool. It no longer models workplace travel or a multi-stop route.

## 10. Safety and reliability boundaries

The current architecture deliberately separates language intelligence from decision logic:

| Capability | LLM | Deterministic code |
|---|---:|---:|
| Understand natural preference language | Optional | Rule fallback |
| Validate preference attributes and values | No | Yes |
| Query Neo4j | No | Yes |
| Enforce required filters | No | Yes |
| Rank schools | No | Yes |
| Determine age eligibility | No | Yes |
| Calculate fees | No | Yes |
| Calculate distance | No | Yes |
| Select recommendation winner | No | Yes |
| Determine suitability verdict | No | Yes |
| Write a grounded explanation | Optional | Fixed fallback |

## Verification

The current automated suite contains 61 tests covering the three-stage flow, cumulative preferences, schema validation, unsupported evidence, LLM extraction, deterministic fallback, contextual school questions, grounded explanations, recommendation transparency, ranking personalisation, missing-evidence scoring, required-preference enforcement, golden recommendation scenarios, evidence provenance, confirmed-negative handling, freshness classification, website URL normalisation and scope classification, multi-school comparison grounding, invalid-school grounding rejection, and timeout fallback.

The latest frontend production build also completes successfully.
