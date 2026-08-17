# Offline data pipeline

These modules turn the raw preschool datasets into the processed catalogue and
load that catalogue into Neo4j. They run manually or from a scheduler; FastAPI
does not execute them during web requests.

## Modules

| Path | Purpose |
|---|---|
| `prepare_data.py` | Validate, join, enrich, and atomically write the master preschool catalogue. |
| `build_knowledge_graph.py` | Validate the processed catalogue and idempotently update Neo4j nodes and relationships. |
| `tests/` | Offline-pipeline tests, including catalogue invariants and destructive-operation safeguards. |

The notebooks in `SystemCode/notebooks/` import these modules for interactive
inspection. The notebooks are demonstrations, not separate implementations.

## Prepare the catalogue

Run from the repository root:

```powershell
.venv\Scripts\python.exe -m SystemCode.src.scripts.prepare_data
```

Default inputs:

```text
SystemCode/data/raw/ListingofCentres.csv
SystemCode/data/raw/ListingofCentresLicenceHistory.csv
SystemCode/data/raw/ListingofCentreServices.csv
SystemCode/data/raw/PreSchoolsLocation.geojson
SystemCode/data/raw/MasterPlan2025PlanningArea.geojson
```

Default output:

```text
SystemCode/data/processed/kindercompass_master.json
```

Override paths when needed:

```powershell
.venv\Scripts\python.exe -m SystemCode.src.scripts.prepare_data `
  --raw-dir SystemCode/data/raw `
  --output SystemCode/data/processed/kindercompass_master.json
```

The output is written atomically. Missing inputs, absent identifiers, duplicate
school IDs, or invalid many-to-one joins fail before replacing the master file.

## Update Neo4j

Configure the repository-level `.env`, then run:

```powershell
.venv\Scripts\python.exe -m SystemCode.src.scripts.build_knowledge_graph
```

The default operation is non-destructive. It upserts each `Preschool`, replaces
that school's current `LOCATED_IN` and `SERVES_LEVEL` relationships, and merges
the corresponding `Town` and `CareLevel` nodes.

To intentionally delete every Neo4j node before rebuilding, supply the explicit
flag:

```powershell
.venv\Scripts\python.exe -m SystemCode.src.scripts.build_knowledge_graph --clear-existing
```

`--clear-existing` is destructive and cannot be enabled through notebook state
or an environment variable. Omit it for normal catalogue refreshes.

## Tests

```powershell
.venv\Scripts\python.exe -m unittest discover -s SystemCode/src/scripts/tests -v
```

The tests do not connect to Neo4j. A fake driver verifies generated operations
and confirms that graph clearing occurs only after explicit opt-in.

## Data flow

```text
data/raw
   -> prepare_data.py
   -> data/processed/kindercompass_master.json
   -> build_knowledge_graph.py
   -> Neo4j
   -> backend Stage 1 search
```
