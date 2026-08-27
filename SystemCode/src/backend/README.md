# KinderCompass backend

This folder contains the FastAPI service and reusable reasoning pipeline for
KinderCompass PoC 1. The backend interprets family preferences, queries and
ranks preschool data from Neo4j, evaluates eligibility and estimated cost,
calculates home-to-preschool distances, and provides grounded guidance from
curated web evidence.

## Quick start

The recommended Windows workflow starts the backend and frontend together. From
the repository root:

```powershell
.\run_poc1.ps1
```

For the first setup, install both projects' dependencies:

```powershell
.\run_poc1.ps1 -InstallDependencies
```

The launcher starts FastAPI at `http://127.0.0.1:8000`, exposes interactive API
documentation at `http://127.0.0.1:8000/docs`, and starts the frontend at
`http://localhost:3000`.

## Manual setup

Prerequisites:

- Python virtual environment at `.venv`;
- an accessible Neo4j database containing the KinderCompass graph;
- OneMap credentials for postal-code geocoding and distance features;
- optional OpenAI credentials for enabled LLM features.

Install backend dependencies from the repository root:

```powershell
.venv\Scripts\python.exe -m pip install -r SystemCode/src/backend/requirements.txt
```

Create `.env` in the repository root. Do not place backend credentials in the
frontend `.env.local` file.

```dotenv
# Required for Stage 1 graph search
NEO4J_URI=
NEO4J_USERNAME=
NEO4J_PASSWORD=
NEO4J_DATABASE=neo4j

# Required for postal-code and distance features
ONEMAP_EMAIL=
ONEMAP_PASSWORD=

# Optional static OneMap fallback
ONEMAP_TOKEN=

# Optional LLM features
OPENAI_API_KEY=
OPENAI_PREFERENCE_EXTRACTION_ENABLED=false
OPENAI_PREFERENCE_MODEL=gpt-4o-mini
OPENAI_PREFERENCE_TIMEOUT_SECONDS=8
OPENAI_INTENT_CLASSIFICATION_ENABLED=false
OPENAI_INTENT_MODEL=gpt-4o-mini
OPENAI_INTENT_TIMEOUT_SECONDS=8
OPENAI_GROUNDED_EXPLANATIONS_ENABLED=false
OPENAI_EXPLANATION_MODEL=gpt-4o-mini
OPENAI_EXPLANATION_TIMEOUT_SECONDS=8
OPENAI_WEB_RAG_ANSWERS_ENABLED=false
OPENAI_WEB_RAG_MODEL=gpt-4o-mini
OPENAI_WEB_RAG_TIMEOUT_SECONDS=8

# Selected-school webpage answer implementation (deterministic or agent)
WEB_RAG_ANSWER_MODE=deterministic

# Optional override for the generated school-webpage index
WEB_RAG_INDEX_PATH=
```

The LLM features are independently disabled by default. Deterministic
preference extraction, intent routing, recommendation explanations, and RAG
answer formatting remain available when their LLM feature is disabled or its
request fails.

`WEB_RAG_ANSWER_MODE` accepts `deterministic` or `agent`. Missing, empty, and
invalid values resolve to `deterministic`; agent execution is introduced only
in a later migration step.

When `OPENAI_INTENT_CLASSIFICATION_ENABLED=true`, structured LLM interpretation
takes priority for explanatory, ambiguous, mixed-topic, and nearest-school chat.
It returns a closed intent plus validated topic names, semantic categories, and
their relationship. If the LLM is unavailable, deterministic intent rules are
the fallback. Other explicit operations, such as resetting preferences or acting
on selected schools, retain deterministic precedence. Retrieval, ranking,
eligibility, fees, and distance remain grounded or deterministic regardless of
the routing method.

A nearest-school chat request does not require an existing recommendation list.
With the saved postal code, the backend loads the full grounded Neo4j school
catalogue, geocodes the home through OneMap, calculates distances against ECDA
school coordinates, and returns the closest school. That school becomes the
active conversational subject, so pronoun follow-ups such as “what curriculum
does it use?” retrieve evidence for the same school without requiring a Results
panel selection.

Start the API from the repository root:

```powershell
.venv\Scripts\python.exe -m uvicorn SystemCode.src.backend.main:app --reload
```

Check that it is ready:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

Expected response:

```json
{"status":"ok"}
```

Stop the development server with `Ctrl+C`.

## API endpoints

| Method and path | Purpose |
|---|---|
| `GET /api/health` | Confirm that FastAPI is running. |
| `POST /api/preferences` | Merge preferences and route chat questions. A nearest-school request queries the grounded catalogue for a location answer, but does not create a ranked recommendation shortlist. |
| `POST /api/search` | Run confirmed Stage 1 constraints and preference ranking against Neo4j. |
| `POST /api/evaluate` | Run Stage 2 exact-age eligibility and an explainable programme-specific fee/subsidy estimate. |
| `POST /api/schools/{school_id}/programme-estimate` | Recalculate one authoritative school's fee and subsidy for an exact programme option shown by the GUI. |
| `POST /api/feedback` | Record explicit, consented anonymous feedback against an immutable recommendation snapshot. |
| `POST /api/geocode` | Resolve one six-digit postal code through OneMap for map feedback. |
| `POST /api/distances` | Calculate independent home distances for a collection of centres. |
| `POST /api/route` | Run Stage 3 for one selected authoritative preschool ID and return its two-point map schedule. |

Request schemas, validation rules, and live examples are available through the
OpenAPI interface at `/docs` while the server is running.

All post-search endpoints accept stable `school_id` values rather than complete
school objects from the browser. For example, Stage 2 accepts `school_ids`, the
confirmed preference profile, and family inputs; distance accepts `school_ids`
and a postal code; route accepts one `school_id`. The backend resolves names,
fees, programmes, identifiers, and coordinates from its authoritative catalogue
before applying domain logic. Unknown IDs return `404`.

The development CORS policy accepts the frontend origins
`http://localhost:3000` and `http://127.0.0.1:3000`. Update the policy in
`main.py` before serving a frontend from another origin.

## Folder contents

See the [`doc/` directory guide](doc/README.md) for ownership boundaries and
more detail about each backend folder.

| Path | Description |
|---|---|
| `main.py` | Thin FastAPI routing layer, CORS policy, service wiring, and HTTP error translation. |
| `agents/` | Backend-only configuration and, in later migration steps, bounded selected-school evidence orchestration. |
| `domain/` | Typed Pydantic request, response, and family contracts used by FastAPI and services. |
| `repositories/` | Authoritative school lookup and admission-date-aware subsidy policy selection. |
| `services/` | Preference, evaluation, and location orchestration separated from HTTP endpoints. |
| `requirements.txt` | Backend runtime dependency constraints for FastAPI, Uvicorn, Pydantic, dotenv, Neo4j, OpenAI, LangGraph, and LangChain OpenAI. |
| `.gitignore` | Excludes Python bytecode and cache directories. |
| `pipeline/pipeline.py` | Reusable in-memory Stage 1-to-Stage 2 integration function. |
| `pipeline/stage1/` | Preference extraction, schema validation, intent routing, Neo4j queries, scoring, evidence metadata, proximity filtering, explanations, and webpage retrieval. |
| `pipeline/stage2/` | Care-level eligibility and prototype subsidy/cost calculations. |
| `pipeline/stage3/` | Preschool coordinate loading and Haversine home-distance calculations. |
| `scripts/` | Offline audits, evaluations, RAG ingestion, review, and query utilities. |
| `resources/web_rag/` | Curated general guidance, school/operator decisions, evaluation labels, and audit inputs. |
| `tests/` | Unit and integration tests for all stages, preference conversation, ranking, provenance, and webpage RAG. |
| `output/` | Generated shortlist, eligibility, distance, inventory, RAG index, review, and evaluation artifacts. |

The authoritative catalogue is validated into typed `SchoolRecord` and
`SchoolService` domain objects when the repository starts or reloads. Invalid
records stop loading with the record index, school ID, and failing field rather
than reaching ranking or fee evaluation. Stage 2 returns typed
`ProgrammeOption` and `EvaluatedSchool` objects, and the FastAPI evaluation
response uses the same domain contract. These models remain mapping-compatible
while the older Stage 1 scoring functions are migrated incrementally.

### Stage 1 modules

| File | Responsibility |
|---|---|
| `conversation.py` | Maintains accumulated preferences and handles recommendation or evidence questions. |
| `preference_schema.py` | Defines validated supported preferences, importance levels, and evidence awareness. |
| `nlp_mapper.py` | Deterministic natural-language preference extraction and profile merging. |
| `llm_extractor.py` | Optional structured OpenAI extraction with validation and deterministic fallback. |
| `intent_router.py` | Hybrid routing with deterministic operational safeguards and optional structured LLM topic/relationship interpretation. |
| `query_builder.py` | Builds parameterized Cypher candidate queries. |
| `kg_client.py` | Connects to Neo4j using Bolt with the supported HTTPS query fallback. |
| `scorer.py` | Produces explainable compatibility scores, strengths, trade-offs, and confidence ordering. |
| `evidence.py` | Describes evidence source, method, reliability, value state, date, and freshness. |
| `proximity.py` | Authenticates with OneMap, geocodes postal codes, and applies radius filtering. |
| `grounded_explainer.py` | Produces deterministic or optional LLM-grounded explanations from fixed results and evidence. |
| `web_rag.py` | Verifies, ingests, retrieves, and cites school-isolated or operator webpage evidence. |
| `runner.py` | Stage 1 command-line and reusable execution entry points. |

### Maintenance scripts

| Script | Purpose |
|---|---|
| `check_kg.py` | Verify Neo4j connectivity and inspect preschool counts, property keys, and sample records. |
| `audit_preference_coverage.py` | Measure which parent-facing preferences are supported by catalogue fields. |
| `audit_evidence_quality.py` | Audit evidence coverage, value states, derivation, source dates, and freshness. |
| `evaluate_recommendations.py` | Run privacy-safe golden ranking scenarios and detect regressions. |
| `build_website_inventory.py` | Build offline JSON, CSV, or Markdown inventories of candidate school webpages. |
| `automate_web_rag_pilot.py` | Incrementally verify candidate pages and build the school-isolated RAG index. |
| `run_web_rag_pilot.py` | Ingest an already approved school-page allowlist. |
| `query_web_rag_pilot.py` | Query one school's indexed evidence from the command line. |
| `evaluate_web_rag_pilot.py` | Check school isolation and citation behavior against offline golden cases. |
| `evaluate_web_rag_answers.py` | Evaluate deterministic or optional LLM-synthesized chat answers. |
| `audit_web_rag_readiness.py` | Measure labelled identity, fetch, retrieval, and citation readiness gates. |
| `review_web_rag_audit.py` | Export human-review CSV packets and import validated labels. |

The Phase 9 commands, review workflow, and quality gates are documented in
[PHASE9_WEBPAGE_RAG.md](../../../docs/poc1/PHASE9_WEBPAGE_RAG.md).

Run the Neo4j diagnostic from the repository root with:

```powershell
$env:PYTHONPATH = "SystemCode/src/backend;SystemCode/src/backend/pipeline"
.venv\Scripts\python.exe SystemCode/src/backend/scripts/check_kg.py
```

This command connects to the configured database, reports the number of
`Preschool` nodes, displays one node's property keys, and prints a random sample.
It is read-only and does not rebuild or modify the graph.

## Tests

Tests import both backend scripts and the individual stage packages. On
PowerShell, expose both locations before running discovery:

```powershell
$env:PYTHONPATH = "SystemCode/src/backend;SystemCode/src/backend/pipeline"
.venv\Scripts\python.exe -m unittest discover -s SystemCode/src/backend/tests -v
```

The suite mocks external services where appropriate and does not require a live
Neo4j database for normal regression testing.

## Generated output and curated resources

Files under `output/` are generated artifacts. Re-running their corresponding
pipeline or audit may replace them. The web application reads
`output/web_rag_pilot_index.json` by default; `WEB_RAG_INDEX_PATH` can select a
different index.

Files under `resources/web_rag/` are curated inputs or human-reviewed labels.
Treat changes there as source changes requiring review. In particular:

- `general_knowledge_index.json` supplies general preschool guidance;
- `pilot_allowlist.json` and `operator_page_allowlist.json` record webpage
  identity decisions;
- `production_audit_labels.json` and `answer_quality_labels.json` support
  evaluation and readiness checks.

### Stage 2 policy estimates

Stage 2 selects the fee matching the child's completed age in months, reported
citizenship, and selected programme from the catalogue's detailed
`services_menu`. It derives potential Basic and Additional Subsidy amounts from
the dated ECDA policy resource under `resources/policy/`, including the relevant
minimum co-payment. Larger qualifying households are assessed using reported
per-capita income criteria.

The evaluation response also lists the exact programmes available for each
school and age level, such as Half Day AM and Half Day PM. If the preferred
programme is unavailable, the school remains visible with its lowest-fee
supported option and an explicit warning. Selecting another programme in the
GUI calls the programme-estimate endpoint, which resolves the school and fee
again from the authoritative catalogue rather than accepting a browser-supplied
fee.

The result is an estimate, not subsidy approval. Class C kindergarten, reported
Special Approval circumstances, missing programme fees, and unsupported
programme types are routed to review or an unavailable state instead of being
assigned an invented amount. GST treatment and additional centre charges may
vary.

Flexi-care 2 can be selected when a centre publishes a matching fee. Because
the configured ECDA policy source does not contain a separate Flexi-care 2
subsidy table, these results show the programme fee and require manual review;
the engine does not interpolate a subsidy from Flexi-care 1 or 3.

Policy files are selected by the requested admission date. The policy
repository rejects overlapping effective periods and returns an unavailable
policy error when no single version applies, preventing an out-of-period table
from being silently used.

## Security and data boundaries

- Never commit the repository `.env` or expose its values through frontend
  variables.
- Neo4j, OneMap, and OpenAI credentials are backend-only.
- The browser communicates with FastAPI; it does not connect directly to those
  services.
- The browser submits school IDs and user choices only. School facts are
  reloaded server-side before scoring, fee estimation, comparison, distance, or
  route calculation.
- Family details and chat content are not written into the generated aggregate
  stage traces.
- Official-webpage evidence is explanation-only and does not change ranking.
- The subsidy and eligibility logic remains a proof of concept and must be
  checked against current ECDA policy before operational use.

## Troubleshooting

- **API starts but search fails:** verify Neo4j credentials, database name,
  network access, and graph contents.
- **Postal-code or distance requests fail:** verify `ONEMAP_EMAIL` and
  `ONEMAP_PASSWORD`, or configure the supported static token fallback.
- **LLM output is not used:** confirm the specific feature flag and
  `OPENAI_API_KEY`; each LLM capability has its own enable flag.
- **School webpage answers are unavailable:** confirm
  `output/web_rag_pilot_index.json` exists or set `WEB_RAG_INDEX_PATH`.
- **General guidance is unavailable:** confirm
  `resources/web_rag/general_knowledge_index.json` exists.
- **Imports fail in direct CLI or test commands:** set `PYTHONPATH` as shown in
  the test section and run commands from the repository root.
- **Port 8000 is already in use:** stop the existing backend process before
  launching another development server.

See the [PoC 1 guide](../../../docs/poc1/Readme.md) for the full application
workflow, frontend launch, demonstration inputs, and system limitations.
