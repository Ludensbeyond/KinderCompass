# [ Practice Module ] KinderCompass — Preschool Recommender System

**[ Naming Convention ]** `IRS-PM-YYYY-MM-DD-STKxx-GRP-TeamName-KinderCompass.zip`

**GitHub:** https://github.com/Ludensbeyond/KinderCompass

---

## SECTION 1 : PROJECT TITLE

## KinderCompass: A Preschool Recommender System

An intelligent multi-stage decision support system that helps parents in Singapore find, compare, and plan preschool enrollment using hybrid recommendation, business rules, genetic algorithm routing, and a Neo4j knowledge graph.

---

## SECTION 2 : EXECUTIVE SUMMARY / PAPER ABSTRACT

Choosing a preschool in Singapore involves reconciling distance, fees, ECDA subsidies, curriculum preferences, vacancies, and multi-child drop-off logistics. Existing tools such as LifeSG provide static proximity search but lack natural language understanding, explainable matching, subsidy calculation, and route optimization.

KinderCompass integrates four IRS technique groups:

| Technique group | Engine |
|---|---|
| Knowledge Discovery & Data Mining | Hybrid recommender (matrix factorization + content-based) |
| Decision Automation | Business rules engine (age eligibility, ECDA subsidies) |
| Business Resource Optimization | Genetic algorithm for multi-child morning routes |
| Cognitive Systems | NLP chatbot + Neo4j knowledge graph (MOE NEL framework) |

Data is sourced from [data.gov.sg](https://data.gov.sg) ECDA preschool registries. The system is delivered as a FastAPI backend and Next.js frontend.

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

## SECTION 5 : USER GUIDE

`Refer to User Guide PDF in Github Folder: ProjectReport`

### [ 1 ] Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend)
- Neo4j (for knowledge graph engine)

### [ 2 ] To run locally (future)

```bash
# Backend
cd SystemCode/src/backend
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend
cd SystemCode/src/frontend
npm install
npm run dev
```

### [ 3 ] Data pipeline (offline scripts)

```bash
cd SystemCode/src/scripts
python clean.py
python build_graph.py
```

Raw datasets are in `SystemCode/data/raw/`. Processed outputs go to `SystemCode/data/processed/`.

---

## SECTION 6 : PROJECT REPORT / PAPER

`Refer to project report at Github Folder: ProjectReport`

**Report contents (required for final submission):**

- Executive Summary / Paper Abstract
- Business Problem Background / Market Research
- Project Objectives & Success Measurements
- Project Solution (domain modelling & system design)
- Project Implementation (development & testing)
- Project Performance & Validation (experiments)
- Project Conclusions: Findings & Recommendation

**Appendices:**

- Project Proposal
- Mapped System Functionalities vs MR, RS, CGS modules
- Installation and User Guide
- Individual reflection (1 page per member)
- References

Working drafts: `docs/KinderCompass_Proposal Draft1.docx`

---

## SECTION 7 : MISCELLANEOUS

`Refer to Github Folder: Miscellaneous`

| Item | Location |
|---|---|
| data.gov.sg source links | `Miscellaneous/data-sources.txt` |
| Raw ECDA datasets | `SystemCode/data/raw/` |
| Exploration notebooks | `SystemCode/notebooks/` |

---

## Repository structure

```
KinderCompass/
├── README.md                 # This file (IRS Sections 1–7)
├── member-github.txt         # Group info for Canvas submission
├── SystemCode/               # Runnable system
│   ├── src/
│   │   ├── scripts/          # Offline data pipeline
│   │   ├── backend/          # FastAPI — four engines
│   │   └── frontend/         # Next.js website
│   ├── data/
│   │   ├── raw/              # Original datasets
│   │   └── processed/        # Cleaned data & graph exports
│   └── notebooks/            # Exploration & demos
├── ProjectReport/            # Final group report + user guide PDFs
├── Video/                    # Promotion + system design videos
├── Miscellaneous/            # Supporting files
└── docs/                     # Working drafts (proposal, slides)
```

---

**This project is part of the NUS-ISS Graduate Certificate in [Intelligent Reasoning Systems (IRS)](https://www.iss.nus.edu.sg/stackable-certificate-programmes/intelligent-systems).**
