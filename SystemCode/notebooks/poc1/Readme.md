# KinderCompass Proof of Concept 1

PoC 1 turns a parent's preschool preferences into an eligible, costed shortlist and then compares selected preschools with home.

```text
Raw preschool data
        |
        v
Data preparation -> Neo4j knowledge graph
                         |
Parent preferences ------+-> Stage 1 shortlist
                                  |
Child and household details ------+-> Stage 2 eligible/costed results
                                             |
Selected centres + home postal code -----------+-> Stage 3 distance comparisons
```

The notebooks demonstrate data preparation and the first two stages interactively. The Python modules under `src/` provide reusable and command-line implementations of the three-stage flow. JSON files under `output/` are the handoff artifacts between stages.

## How the proof of concept operates

### Data preparation and knowledge graph creation

- `data_prep.ipynb` cleans and combines the source preschool records into a master dataset for downstream use.
- `knowledge_graph_gen.ipynb` converts the prepared data into the Neo4j knowledge graph queried by Stage 1.

These preparation notebooks are normally run when the underlying source data changes, rather than for every parent search.

### Stage 1: preference search

Stage 1 accepts free text such as `Montessori nursery with Chinese and SPARK` or `a school within 2 km`. `src/stage1/nlp_mapper.py` extracts hard constraints and weighted preferences. Care levels, explicitly required languages, and maximum home distance constrain the candidate set; pedagogy, language, SPARK certification, operator scheme, transport, food, and full-day service contribute to explainable compatibility scores. Distance uses the home postal code entered in Family Details. Unrecognized requests return a clarification error instead of every school.

The web chat sends its current structured preference profile with each new message. New preferences are merged with earlier turns, and parents can correct them—for example, `Chinese is preferred, not required` changes a language requirement into a soft preference. `clear preferences`, `reset preferences`, or `start over` clears the accumulated profile. The chat UI displays the currently understood preferences above the conversation.

Conversation updates use `POST /api/preferences` and do not query Neo4j. Ambiguous language and pedagogy statements trigger required-versus-preferred follow-up questions. Once the profile has no unresolved clarification, the UI enables **Show recommendations**; only that explicit action calls `POST /api/search`.

Conversational operations use a closed intent catalogue. Clear phrases such as `nearest preschool`, `selected preschool`, and `is this school suitable` are routed by deterministic rules. Set `OPENAI_INTENT_CLASSIFICATION_ENABLED=true` to use a structured LLM classifier only for less explicit wording; low-confidence classifications ask for clarification, and deterministic rules retain priority. For closest-school questions, the API recalculates straight-line distances from the saved postal code to every currently eligible result and selects the minimum distance in code.

Recommendation regressions can be checked without Neo4j or real family data by running `scripts/evaluate_recommendations.py`. The synthetic golden evaluator emits Markdown or JSON and returns a failing exit code if a required constraint, missing-evidence rule, importance ordering, or confidence tie-break changes unexpectedly. API search responses also include aggregate, privacy-safe stage-count traces; see `PHASE7_RECOMMENDATION_EVALUATION.md`.

Evidence provenance is defined centrally in `src/stage1/evidence.py` and shown in each result's score breakdown. Run `scripts/audit_evidence_quality.py` to inspect source coverage, confirmed negative versus unknown values, derived evidence, and freshness. See `PHASE8_EVIDENCE_PROVENANCE.md`.
The live `Last updated` label comes from the catalogue's `last_updated` field imported by `knowledge_graph_gen.ipynb`; rerun that notebook after catalogue refreshes so existing Neo4j nodes receive the new dates.

Phase 9 begins with the offline `scripts/build_website_inventory.py` audit. It normalises the existing website fields and creates an unverified candidate review queue without fetching pages. See `PHASE9_WEBPAGE_RAG.md` before approving any page for ingestion or school-specific RAG evidence.

Postal-code searches are geocoded through OneMap. Without a distance preference, the coordinates are mapped to their URA planning area and Stage 1 returns matching schools in that town. With any positive distance preference, including decimals such as 1.5 km, Stage 1 ignores town boundaries and filters the full candidate set by straight-line distance before ranking it. Configure `ONEMAP_EMAIL` and `ONEMAP_PASSWORD` in the PoC `.env` file. The backend caches the returned token, refreshes it five minutes before expiry, and retries once with a new token if OneMap reports that the token is invalid or expired. A manually managed `ONEMAP_TOKEN` remains supported as a fallback.

`src/stage1/query_builder.py` builds a parameterized candidate query, `src/stage1/kg_client.py` executes it against Neo4j, and `src/stage1/scorer.py` ranks candidates by match score and evidence confidence. Stage 1 returns at most 20 recommendations with strengths, trade-offs, and a per-attribute breakdown. The shortlist can be saved as `output/stage1_shortlist.json`.

The shortlist includes fields used by later stages, notably `school_id`, `centre_code`, `name`, `base_fee`, `operator_scheme`, `care_levels`, `pedagogy`, `match_score`, `profile_confidence`, `strengths`, `tradeoffs`, and `match_breakdown`. `stage1_kg_query.ipynb` demonstrates the earlier query process interactively.

### Stage 2: eligibility and estimated cost

Stage 2 combines the public Stage 1 shortlist with private family inputs:

- child's date of birth;
- intended admission date;
- gross household income; and
- basic monthly subsidy.

`src/stage2/engine.py` calculates the child's calendar age at admission and maps ages 2 through 6 to the corresponding care level. It rejects a centre if that required level is not offered. For an eligible centre, the current prototype calculates an additional income-tier subsidy and estimates:

```text
net monthly fee = max(0, base fee - basic subsidy - additional subsidy)
```

Ineligible centres are omitted by default, but can be retained with their rejection reasons. Results can be saved as `output/stage2_results.json`. `stage2_eval_presch_eligibility.ipynb` demonstrates and smoke-tests this logic.

The subsidy tiers are proof-of-concept rules, not production policy. They must be checked against current official ECDA rules before real-world use.

### Stage 3: home-to-preschool distance

The user selects one or more eligible preschools from the Stage 2 results and supplies a six-digit home postal code. For each selected preschool, Stage 3 independently:

1. validates that the selected centre is eligible;
2. resolves home through OneMap and joins its centre code to coordinates in `SystemCode/data/raw/PreSchoolsLocation.geojson`;
3. calculates the Haversine distance from home to the preschool; and
4. writes the two-point result to `output/stage3_route.json`.

Each preschool is compared directly with the same home location; selected schools are not treated as stops in a combined journey. Haversine distance is straight-line distance; the prototype does not account for roads, traffic, travel time, or turn-by-turn directions.

## Setup

Run commands from the repository root. Activate the existing virtual environment and expose the PoC source directory:

```powershell
.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "SystemCode/notebooks/poc1/src"
python -m pip install -r requirements.txt
```

The repository-level requirements file installs the backend, reusable Stage
1-3 modules, audit scripts, and notebook dependencies. The narrower
`SystemCode/src/backend/poc1/requirements.txt` remains available when only the
API runtime is required.

Stage 1 also requires access to Neo4j Aura and OneMap. Create a file named
`.env` in `SystemCode/notebooks/poc1/`, then add the following variables and
replace the blank values with your own credentials and instance details:

```dotenv
NEO4J_URI=
NEO4J_USERNAME=
NEO4J_PASSWORD=
NEO4J_DATABASE=
AURA_INSTANCEID=
AURA_INSTANCENAME=
ONEMAP_EMAIL=
ONEMAP_PASSWORD=

# Optional Phase 3 LLM extraction
OPENAI_PREFERENCE_EXTRACTION_ENABLED=false
OPENAI_API_KEY=
OPENAI_PREFERENCE_MODEL=gpt-4o-mini
OPENAI_PREFERENCE_TIMEOUT_SECONDS=8
OPENAI_GROUNDED_EXPLANATIONS_ENABLED=false
OPENAI_EXPLANATION_MODEL=gpt-4o-mini
OPENAI_EXPLANATION_TIMEOUT_SECONDS=8
```

Do not commit this `.env` file because it contains private credentials.
LLM extraction remains disabled unless `OPENAI_PREFERENCE_EXTRACTION_ENABLED`
is set to `true`. When it is disabled or an OpenAI request fails, Stage 1 uses
the deterministic keyword extractor.
Grounded selected-school explanations are controlled independently by
`OPENAI_GROUNDED_EXPLANATIONS_ENABLED` and use deterministic recommendation
and suitability decisions as their fixed basis.

## Launch the UI and backend together

On Windows, `run_poc1.ps1` checks the configuration and starts the FastAPI
backend and Next.js frontend in separate PowerShell windows:

```powershell
.\SystemCode\notebooks\poc1\run_poc1.ps1
```

For a first-time setup, allow the launcher to install both Python and Node.js
project dependencies:

```powershell
.\SystemCode\notebooks\poc1\run_poc1.ps1 -InstallDependencies
```

Node.js itself and the repository `.venv` must already exist. The launcher uses
the Neo4j credentials stored in `SystemCode/notebooks/poc1/.env`, creates the
frontend `.env.local` when needed, and reports the frontend and API addresses.

The launcher starts the frontend server but does **not** open a web browser.
Wait until the frontend PowerShell window reports that Next.js is ready, then
manually open this address in your browser:

```text
http://localhost:3000
```

Keep both the frontend and backend PowerShell windows running while using the
application.

For a complete set of demonstration inputs covering all three stages, see
`UI_EXAMPLE.md` in this folder.

### Shut down PoC 1

The launcher opens the backend and frontend in separate PowerShell windows. To
stop the complete application:

1. Open the FastAPI backend window and press `Ctrl+C`.
2. Open the Next.js frontend window and press `Ctrl+C`.
3. Close both windows after their server processes have stopped.

Closing only one window stops only that part of the application. For example,
the page may remain visible when the backend is stopped, but searches and
calculations will fail.

### Restart PoC 1

After both servers have been shut down, return to a PowerShell window at the
repository root and run:

```powershell
.\SystemCode\notebooks\poc1\run_poc1.ps1
```

Dependencies do not need to be installed again during a normal restart. Use
`-InstallDependencies` only for the first setup or after the dependency files
have changed:

```powershell
.\SystemCode\notebooks\poc1\run_poc1.ps1 -InstallDependencies
```

If only one server has stopped, first press `Ctrl+C` in the remaining server
window and then run the launcher again. This avoids accidentally starting a
second process on port `8000` or `3000`.

## Run the complete flow

From the repository root in PowerShell:

```powershell
# Stage 1: query Neo4j and create a shortlist
python -m stage1.runner `
  --text "play-based learning" `
  --town "560123" `
  --output "SystemCode/notebooks/poc1/output/stage1_shortlist.json"

# Stage 2: check care-level eligibility and estimate monthly fees
python -m stage2.runner `
  --input "SystemCode/notebooks/poc1/output/stage1_shortlist.json" `
  --dob "2023-06-10" `
  --admission-date "2026-01-01" `
  --ghi 4500 `
  --basic-subsidy 600 `
  --output "SystemCode/notebooks/poc1/output/stage2_results.json"

# Stage 3: select one eligible preschool and calculate its distance from home
python -m stage3.runner `
  --input "SystemCode/notebooks/poc1/output/stage2_results.json" `
  --select "CENTRE:PT8718" `
  --home-postal-code "540231" `
  --output "SystemCode/notebooks/poc1/output/stage3_route.json"
```

Replace the example identifier with one eligible `school_id` present in your Stage 2 output. Use `--include-ineligible` in Stage 2 when rejection details are needed.

For an in-memory Stage 1-to-Stage 2 call, `src/pipeline.py` exposes `search_and_evaluate(...)`. Stage 3 currently uses the JSON handoff and its own runner.

## Project layout

| Path | Role |
|---|---|
| `data_prep.ipynb` | Builds the cleaned master preschool dataset. |
| `knowledge_graph_gen.ipynb` | Generates the Neo4j knowledge graph. |
| `stage1_kg_query.ipynb` | Interactive Stage 1 query demonstration. |
| `stage2_eval_presch_eligibility.ipynb` | Interactive Stage 2 eligibility/cost demonstration. |
| `src/stage1/` | Text mapping, Cypher generation, Neo4j access, and Stage 1 CLI. |
| `src/stage2/` | Eligibility/cost engine and Stage 2 CLI. |
| `src/stage3/` | Coordinate lookup, route optimizer, and Stage 3 CLI. |
| `src/pipeline.py` | In-memory Stage 1-to-Stage 2 integration function. |
| `output/` | Example JSON artifacts passed between stages. |
| `tests/` | Unit and integration tests for the stage handoffs and optimizer. |

More detailed stage-specific notes are available in `src/stage1/Readme.md`, `src/stage2/Readme.md`, and `src/stage3/Readme.md`.

## Tests

The tests do not require a live Neo4j connection because the Stage 1 integration is mocked:

```powershell
$env:PYTHONPATH = "SystemCode/notebooks/poc1/src"
python -m unittest discover -s SystemCode/notebooks/poc1/tests -v
```

They cover Stage 2 eligibility and fee calculations, the Stage 1-to-Stage 2 contract, JSON handoffs, coordinate joining, Haversine distance, and the Stage 3 ordering constraint.

## Current proof-of-concept limitations

- Free-text interpretation is keyword-based, so unrecognised wording may produce no preference filter.
- Stage 1 depends on the Neo4j schema and expected preschool property names.
- Age is calculated by admission year minus birth year rather than exact age on the admission date.
- Subsidy calculations are simplified prototype tiers.
- Route optimization uses straight-line distance instead of a road network or live traffic.
- The sample pipeline is decision support only; outputs should be validated before operational use.
