# [ Practice Module ] KinderCompass — Preschool Recommender System

**[ Naming Convention ]** `IRS-PM-YYYY-MM-DD-STKxx-GRP-TeamName-KinderCompass.zip`

**GitHub:** https://github.com/Ludensbeyond/KinderCompass

---

## SECTION 1 : PROJECT TITLE

## KinderCompass: A Preschool Recommender System

An intelligent multi-stage decision-support system that helps parents in
Singapore find, compare, and plan preschool enrolment using explainable
preference ranking, eligibility and cost rules, distance calculations, a Neo4j
knowledge graph, and grounded guidance.

---

## SECTION 2 : EXECUTIVE SUMMARY / PAPER ABSTRACT

Choosing a preschool in Singapore involves reconciling distance, fees,
eligibility, curriculum preferences, service availability, and the quality of
supporting evidence. Existing search tools provide useful catalogue information
but offer limited conversational preference handling, explainable matching, and
integrated comparison support.

KinderCompass implements a three-stage workflow:

| Stage | Capability |
|---|---|
| Stage 1 | Convert conversational preferences into validated constraints and explainably ranked Neo4j results. |
| Stage 2 | Evaluate care-level eligibility and estimate monthly cost using proof-of-concept subsidy rules. |
| Stage 3 | Compare selected eligible centres with home using OneMap geocoding and straight-line distance. |

The system also provides evidence provenance, recommendation explanations, and
school-isolated official-webpage retrieval. Data is sourced from
[data.gov.sg](https://data.gov.sg) ECDA preschool registries. The application is
delivered through a FastAPI backend and Next.js frontend.

---

## SECTION 3 : CREDITS / PROJECT CONTRIBUTION

| Official Full Name | Student ID | Work Items (Who Did What) | Email (Optional) |
|---|---|---|---|
| Eunice Goh | [TBD] | [TBD] | [TBD] |
| Henry Foo Yong Jie | [TBD] | [TBD] | [TBD] |
| Jarebb | [TBD] | [TBD] | [TBD] |
| Jawad Bin Joha | [TBD] | [TBD] | [TBD] |

---

## SECTION 4 : VIDEO OF SYSTEM MODELLING & USE CASE DEMO

| Video | File | Status |
|---|---|---|
| Promotion (5 min) | `Video/KinderCompass-promotion.mp4` | Pending |
| System design (5 min) | `Video/KinderCompass-system.mp4` | Pending |

> Upload both videos to the `Video/` folder before final submission.  
> Note: AI-generated presentation speech is **not allowed**.

---

## SECTION 5 : Project Setup

See the detailed [KinderCompass PoC 1 guide](docs/poc1/Readme.md) and the user
guide PDF in `ProjectReport/`.

### [ 1 ] Prerequisites

- Python 3.11+
- Node.js 18+ with npm
- Neo4j database for Stage 1 knowledge-graph search
- OneMap credentials for postal-code and distance features
- optional OpenAI API credentials for enabled LLM features

Create a `.env` file in the repository root and add your environment-specific
credentials:

```dotenv
# Required for Stage 1 graph search
NEO4J_URI=
NEO4J_USERNAME=
NEO4J_PASSWORD=
NEO4J_DATABASE=neo4j

# Required for postal-code and distance features
ONEMAP_EMAIL=
ONEMAP_PASSWORD=

# Optional LLM features
OPENAI_API_KEY=
OPENAI_PREFERENCE_EXTRACTION_ENABLED=false
OPENAI_INTENT_CLASSIFICATION_ENABLED=false
OPENAI_GROUNDED_EXPLANATIONS_ENABLED=false
OPENAI_WEB_RAG_ANSWERS_ENABLED=false
```

Replace the blank values with your credentials. Keep any unused OpenAI features
set to `false`, and do not commit `.env` or place backend credentials in the
frontend `.env.local` file.

### [ 2 ] Python dependencies

Create the repository virtual environment if it does not already exist, then
install the complete Python environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

This installs the FastAPI backend, reusable Stage 1–3 packages, offline data
pipeline, evaluation utilities, and notebook dependencies.

### [ 3 ] Initialize or refresh the data pipeline when required

You do **not** run this step for every application launch. Run it only when:

- setting up an empty Neo4j database for the first time;
- replacing or refreshing files under `SystemCode/data/raw/`; or
- changing catalogue preparation or graph-loading logic.

Prepare the catalogue first, then update Neo4j:

```powershell
.\.venv\Scripts\python.exe -m SystemCode.src.scripts.prepare_data
.\.venv\Scripts\python.exe -m SystemCode.src.scripts.build_knowledge_graph
```

If `SystemCode/data/processed/kindercompass_master.json` is current and the
configured Neo4j database is already populated, skip this step. The application
launcher does not rebuild the catalogue or graph.

Raw datasets are stored in `SystemCode/data/raw/`; the generated catalogue is
written to `SystemCode/data/processed/kindercompass_master.json`. Graph updates
are non-destructive by default. See the
[offline pipeline guide](SystemCode/src/scripts/README.md) before using the
explicit destructive rebuild option. The
[knowledge graph schema](SystemCode/src/scripts/KNOWLEDGE_GRAPH_SCHEMA.md)
documents which features are properties or nodes, their relationships, source
mapping, constraints, and current limitations.

### [ 4 ] Run locally

For the first application launch, install the frontend and backend runtime
dependencies and start both services:

```powershell
.\run_poc1.ps1 -InstallDependencies
```

For normal subsequent launches:

```powershell
.\run_poc1.ps1
```

In short: initialize the data only when Neo4j or the source catalogue needs it;
otherwise start directly with `run_poc1.ps1`.

## SECTION 6 : User Guide

- User enter FORM
- User start chatting with CompassChat to gain preferential Preschools Information \
  For Example:
  - CompassChat: I want a school that is within 2km from my house and teaches Chinese
  - Click "Show Recommendations"
  - Select schools of interest from results
  - CompassChat: Compare the selected schools

## SECTION 7 : Repository structure

```text
KinderCompass/
├── README.md                 # This file (IRS Sections 1–5)
├── member-github.txt         # Group info for Canvas submission
├── SystemCode/               # Runnable system
│   ├── src/
│   │   ├── scripts/          # Offline data pipeline
│   │   ├── backend/          # FastAPI three-stage workflow
│   │   └── frontend/         # Next.js website
│   ├── data/
│   │   ├── raw/              # Original datasets
│   │   └── processed/        # Cleaned data and graph inputs
│   └── notebooks/            # Exploration and demonstrations
├── ProjectReport/            # Final group report and user guide PDFs
├── Video/                    # Promotion and system design videos
├── Miscellaneous/            # Supporting files
└── docs/                     # PoC documentation and working drafts
```
