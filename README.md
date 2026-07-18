# KinderCompass

NUS-ISS Intelligent Reasoning Systems (IRS) Practice Module project.

KinderCompass helps parents explore and compare preschool options in Singapore using data from [data.gov.sg](https://data.gov.sg), a knowledge graph, and reasoning engines exposed through a web application.

## Project structure

```
KinderCompass/
├── data/
│   ├── raw/           # Original datasets (CSV, GeoJSON)
│   └── processed/     # Cleaned data and graph exports
├── src/
│   ├── scripts/       # Offline pipeline: scrape, clean, build graph
│   ├── backend/       # FastAPI — reasoning engines as API
│   └── frontend/      # Next.js/React website
├── notebooks/         # Exploration and demos
├── docs/              # Project documentation
└── presentation/      # Proposal and final presentation
```

## Data flow

```
scripts/  →  data/processed/  →  backend/  →  frontend/
```

Each folder contains a README describing its planned contents.
