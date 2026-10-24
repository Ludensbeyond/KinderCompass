# SystemCode

Runnable application code, offline pipelines, and project data for
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
[the implementation guide](../docs/impl.md) for application setup and
operation.
