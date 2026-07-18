# SystemCode

All runnable code and project data for KinderCompass.

## Structure

```
SystemCode/
├── src/
│   ├── scripts/       # Offline pipeline: scrape, clean, build graph
│   ├── backend/       # FastAPI — four reasoning engines
│   └── frontend/      # Next.js/React website
├── data/
│   ├── raw/           # Original datasets from data.gov.sg
│   └── processed/     # Cleaned tables and graph exports
└── notebooks/         # Jupyter exploration before moving logic to src/
```

## Data flow

```
data/raw/  →  src/scripts/  →  data/processed/  →  src/backend/  →  src/frontend/
```

Each subfolder contains a README describing planned contents.
