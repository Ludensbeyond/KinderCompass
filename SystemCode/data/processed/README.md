# Processed data

Reproducible output from the offline data pipeline, ready for Neo4j loading and
backend audits.

## Current output

| File | Description |
|---|---|
| `kindercompass_master.json` | Enriched preschool catalogue with stable IDs, location, service, fee, evidence, and coverage fields. |

Regenerate it from the repository root:

```powershell
.venv\Scripts\python.exe -m SystemCode.src.scripts.prepare_data
```

Then update Neo4j without clearing existing data:

```powershell
.venv\Scripts\python.exe -m SystemCode.src.scripts.build_knowledge_graph
```

Do not edit generated data manually. Replace the raw source files and rerun the
pipeline instead. See [the offline pipeline guide](../../src/scripts/README.md)
for validation, path overrides, tests, and the explicit destructive rebuild
option.
