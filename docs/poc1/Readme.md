# KinderCompass Proof of Concept 1

KinderCompass PoC 1 turns a family's preschool preferences into an eligible,
costed shortlist and helps compare selected centres by suitability and distance
from home.

```text
Preschool data -> preparation -> Neo4j knowledge graph
                                      |
Family preferences -------------------+-> Stage 1: ranked shortlist
Family and child details ----------------> Stage 2: eligibility and cost
Selected centres and home postal code ---> Stage 3: distance comparison
```

The web application exposes the complete flow. The offline modules in
`SystemCode/src/scripts/` prepare the catalogue and update Neo4j. Notebooks call
those shared modules for interactive demonstrations, while reusable application
code lives in `SystemCode/src/backend/`.

## How the stages work

### Stage 1: preference search and ranking

Stage 1 converts free text into a validated preference profile. Hard
requirements constrain candidates; supported preferences contribute to an
explainable compatibility score. A deterministic extractor is always available,
while optional structured LLM extraction can interpret less explicit wording.
Unsupported preferences are retained in conversation but do not affect ranking.

Postal codes are resolved through OneMap. Without a distance limit, search uses
the corresponding planning area. With a positive limit, including decimals such
as 1.5 km, search crosses planning-area boundaries and filters by straight-line
distance.

The chat updates preferences through `POST /api/preferences` without querying
Neo4j. After ambiguities are resolved, **Show recommendations** calls
`POST /api/search`. Results include strengths, trade-offs, evidence provenance,
freshness, and a per-preference score calculation.

Official-webpage retrieval can answer questions about selected schools using
school-isolated evidence and citations. General guidance uses a separate curated
knowledge index. Web evidence explains results but does not alter ranking.

### Stage 2: eligibility and estimated cost

Stage 2 combines the shortlist with the child's date of birth, admission date,
gross household income, and basic monthly subsidy. It checks the required care
level and calculates the prototype estimate:

```text
net monthly fee = max(0, base fee - basic subsidy - additional subsidy)
```

The subsidy tiers are demonstration rules, not production policy. Verify them
against current official ECDA policy before real-world use.

### Stage 3: home-to-preschool distance

Stage 3 validates selected centres, resolves home through OneMap, joins centre
coordinates from the ECDA location dataset, and calculates Haversine distance.
Each centre is compared independently with the same home. This is straight-line
distance, not road distance or travel time.

## Project layout

| Path | Purpose |
|---|---|
| `SystemCode/src/scripts/` | Offline catalogue preparation and Neo4j loading. |
| `SystemCode/src/backend/main.py` | FastAPI application and endpoints. |
| `SystemCode/src/backend/pipeline/` | Reusable Stage 1–3 modules. |
| `SystemCode/src/backend/scripts/` | Audits and evaluation utilities. |
| `SystemCode/src/backend/resources/` | Curated RAG resources and labels. |
| `SystemCode/src/backend/tests/` | Backend tests. |
| `SystemCode/src/backend/output/` | Generated handoff and audit files. |
| `SystemCode/src/frontend/` | Next.js application. |
| `SystemCode/notebooks/` | Interactive demonstrations of shared pipeline logic. |
| `SystemCode/data/` | Raw and processed preschool datasets. |
| `docs/poc1/` | Design, evaluation, and demonstration documentation. |
| `run_poc1.ps1` | Windows launcher for both services. |

## Setup and launch

Run commands from the repository root. The launcher expects `.venv`, Node.js,
and `npm`. Create `.env` in the repository root:

```dotenv
NEO4J_URI=
NEO4J_USERNAME=
NEO4J_PASSWORD=
NEO4J_DATABASE=
ONEMAP_EMAIL=
ONEMAP_PASSWORD=

# Optional LLM features
OPENAI_API_KEY=
OPENAI_PREFERENCE_EXTRACTION_ENABLED=false
OPENAI_INTENT_CLASSIFICATION_ENABLED=false
OPENAI_GROUNDED_EXPLANATIONS_ENABLED=false
OPENAI_WEB_RAG_ANSWERS_ENABLED=false
```

Do not commit `.env`. If an optional LLM feature is disabled or its request
fails, deterministic behavior remains available.

With `OPENAI_INTENT_CLASSIFICATION_ENABLED=true`, the LLM is the primary
interpreter for explanatory, ambiguous, and mixed-topic questions. It returns a
validated closed intent, topic categories, and relationships before curated
evidence retrieval. Explicit operational commands and all recommendation,
eligibility, cost, and distance decisions remain deterministic.

Install dependencies and launch both services:

```powershell
.\run_poc1.ps1 -InstallDependencies
```

For subsequent launches, use `.\run_poc1.ps1`. The launcher starts FastAPI at
`http://127.0.0.1:8000` and Next.js at `http://localhost:3000` in separate
PowerShell windows. Open the frontend URL manually. Press `Ctrl+C` in each
window to stop the application.

## Command-line flow

```powershell
$env:PYTHONPATH = "SystemCode/src/backend;SystemCode/src/backend/pipeline"

python -m stage1.runner `
  --text "play-based learning within 2 km" `
  --town "560123" `
  --output "SystemCode/src/backend/output/stage1_shortlist.json"

python -m stage2.runner `
  --input "SystemCode/src/backend/output/stage1_shortlist.json" `
  --dob "2023-06-10" `
  --admission-date "2026-01-01" `
  --ghi 4500 `
  --basic-subsidy 600 `
  --output "SystemCode/src/backend/output/stage2_results.json"

python -m stage3.runner `
  --input "SystemCode/src/backend/output/stage2_results.json" `
  --select "CENTRE:PT8718" `
  --home-postal-code "540231" `
  --output "SystemCode/src/backend/output/stage3_route.json"
```

Replace the Stage 3 identifier with an eligible `school_id` from Stage 2.

## Tests

```powershell
$env:PYTHONPATH = "SystemCode/src/backend;SystemCode/src/backend/pipeline"
python -m unittest discover -s SystemCode/src/backend/tests -v
npm --prefix SystemCode/src/frontend run build
```

## Supporting documentation

- [Demonstration inputs](UI_EXAMPLE.md)
- [Implemented upgrades](upgrades.md)
- [Preference schema](PREFERENCE_SCHEMA.md)
- [Recommendation evaluation](PHASE7_RECOMMENDATION_EVALUATION.md)
- [Evidence provenance](PHASE8_EVIDENCE_PROVENANCE.md)
- [Official-webpage RAG](PHASE9_WEBPAGE_RAG.md)

## Project materials

The final report and installation/user-guide PDFs belong in `ProjectReport/`.
The expected report coverage includes:

- executive summary and business-problem background;
- objectives and success measurements;
- domain modelling and system design;
- implementation and testing;
- performance evaluation and validation;
- findings, recommendations, and conclusions;
- project proposal, module-to-functionality mapping, individual reflections,
  installation guide, and references.

Supporting submission material is organized as follows:

| Path | Purpose |
|---|---|
| `ProjectReport/` | Final group report and user-guide documents. |
| `Video/` | Promotion and system-design demonstration videos. |
| `Miscellaneous/` | Supporting files, including source-data references. |
| `SystemCode/data/raw/` | Original ECDA and planning-area datasets. |
| `SystemCode/notebooks/` | Interactive pipeline and reasoning demonstrations. |

## Repository structure

```text
KinderCompass/
|-- README.md                  # Submission overview and concise user guide
|-- requirements.txt           # Complete Python environment
|-- run_poc1.ps1               # Backend and frontend launcher
|-- SystemCode/
|   |-- src/
|   |   |-- scripts/           # Offline data and Neo4j pipeline
|   |   |-- backend/           # FastAPI and reasoning implementation
|   |   `-- frontend/          # Next.js interface
|   |-- data/
|   |   |-- raw/               # Original datasets
|   |   `-- processed/         # Generated master catalogue
|   `-- notebooks/             # Interactive demonstrations
|-- docs/poc1/                 # Detailed PoC design and evaluation notes
|-- ProjectReport/             # Report and user guide
|-- Video/                     # Submission videos
`-- Miscellaneous/             # Supporting material
```

KinderCompass is part of the NUS-ISS Graduate Certificate in
[Intelligent Reasoning Systems](https://www.iss.nus.edu.sg/stackable-certificate-programmes/intelligent-systems).

## Limitations

- Stage 1 depends on the expected Neo4j schema and catalogue fields.
- Optional LLM interpretation is bounded by the preference schema and falls back
  to deterministic extraction.
- Eligibility and subsidy calculations are simplified proof-of-concept rules.
- Distance ignores roads, traffic, and public-transport travel time.
- Web retrieval is limited to curated sources and is not ranking evidence.
- Results require policy and data validation before operational use.
