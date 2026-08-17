# Offline data pipeline

These modules turn the raw preschool datasets into the processed catalogue and
load that catalogue into Neo4j. They run manually or from a scheduler; FastAPI
does not execute them during web requests.

## Modules

| Path | Purpose |
|---|---|
| `prepare_data.py` | Validate, join, enrich, and atomically write the master preschool catalogue. |
| `build_knowledge_graph.py` | Validate the processed catalogue and idempotently update Neo4j nodes and relationships. |
| `KNOWLEDGE_GRAPH_SCHEMA.md` | Authoritative nodes, properties, relationships, constraints, sources, and modelling decisions. |
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
that school's current knowledge relationships, and merges the corresponding
concept nodes. It also creates uniqueness constraints for stable identifiers and
concept names, plus an index on preschool names.

See the [knowledge graph schema](KNOWLEDGE_GRAPH_SCHEMA.md) for the complete
property-versus-node design and source mapping.

```text
(Preschool)-[:LOCATED_IN]->(Town)
(Preschool)-[:SERVES_LEVEL]->(CareLevel)
(Preschool)-[:TEACHES_IN]->(Language)
(Preschool)-[:USES_PEDAGOGY]->(Pedagogy)
(Preschool)-[:PARTICIPATES_IN]->(OperatorScheme)
(Preschool)-[:HAS_CERTIFICATION]->(Certification)
```

Longitude and latitude parsed from the official location GeoJSON are retained
on each `Preschool` node. Existing scalar properties remain available for
backward compatibility with Stage 1 ranking. Concept relationships that no
longer apply are replaced during refresh, and unused concept nodes are removed.

After updating the graph, inspect the enriched model in Neo4j Browser:

```cypher
MATCH (p:Preschool)-[r]->(concept)
RETURN p, r, concept
LIMIT 500;
```

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
