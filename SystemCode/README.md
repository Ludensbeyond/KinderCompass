# SystemCode

Runnable application code, offline pipelines, notebooks, and project data for
KinderCompass.

## Structure

```text
SystemCode/
|-- src/
|   |-- scripts/       # Offline catalogue preparation and Neo4j loading
|   |-- backend/       # FastAPI, reasoning pipeline, audits, and RAG tools
|   `-- frontend/      # Next.js user interface
|-- data/
|   |-- raw/           # Source CSV and GeoJSON datasets
|   `-- processed/     # Reproducible processed catalogue
`-- notebooks/         # Interactive demonstrations using shared modules
```

## Data and application flow

```text
data/raw
   -> src/scripts/prepare_data.py
   -> data/processed/kindercompass_master.json
   -> src/scripts/build_knowledge_graph.py
   -> Neo4j
   -> src/backend
   -> src/frontend
```

Use [src/scripts/README.md](src/scripts/README.md) for the offline pipeline and
[the PoC 1 guide](../docs/poc1/Readme.md) for application setup and operation.
