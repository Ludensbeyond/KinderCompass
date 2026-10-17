# Stage 1 — Knowledge Graph Search & Match (Local module)

This folder contains a minimal, modular Stage‑1 implementation used to map parent free‑text preferences into Neo4j queries and return a shortlist of preschools with baseline attributes.

Files
- `kg_client.py`: Neo4j helper functions — `get_driver()`, `verify_connectivity(driver)`, and `run_query(driver, query, params)`.
- `query_builder.py`: Builds parameterized Cypher for Stage 1. Hard town, care-level, and required-language filters traverse `LOCATED_IN`, `SERVES_LEVEL`, and `TEACHES_IN`. Postal code stays a property filter. Results include `retrieval_path`. Also contains `sample_preschool_keys()` to inspect node property keys.
- `graph_evaluation.py`: Competency-question coverage and labelled retrieval metrics for Workstream 2. Gold sets are independent Cypher, not `query_builder`.
- `nlp_mapper.py`: Lightweight rule-based text → KG filter mapper (`map_text_to_filters(text)`). Replaceable with a richer NLP/embedding approach later.
- `runner.py`: CLI runner that maps free-text to filters, queries Neo4j, prints results, and returns the shortlist for Stage 2.
- `__init__.py`: Package marker (empty).

Requirements
- Python 3.8+ (use your workspace venv).
- Packages: `python-dotenv`, `neo4j`.

Install (in your venv):

```bash
python -m pip install python-dotenv neo4j
```

Usage (recommended):

- Unix / macOS (from repo root):

```bash
# expose the pipeline packages
PYTHONPATH=SystemCode/src/backend/pipeline python -m stage1.runner --text "montessori" --town 54 --output "SystemCode/src/backend/output/stage1_shortlist.json"
```

- Windows PowerShell:

```powershell
$env:PYTHONPATH = "SystemCode/src/backend/pipeline"
python -m stage1.runner --text "montessori" --town 54 --output "SystemCode/src/backend/output/stage1_shortlist.json"
```

Write the Stage 1 shortlist to a JSON handoff file:

```powershell
python -m stage1.runner --text "play-based learning" --town "560123" --output "SystemCode/src/backend/output/stage1_shortlist.json"
```

Notes
- The runner requires `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD` to be set in a `.env` file (the code uses `python-dotenv` to load them).
- The `nlp_mapper` is intentionally simple (keyword lookup). For production or better matching, replace it with an embeddings-based semantic mapper.
- `query_builder` still returns Preschool properties (`base_fee`, `operator_scheme`, `care_levels`, and the rest) so ranking can read them. Hard filters use graph relationships. Preferred SPARK and pedagogy are scored after retrieval, not in Cypher. Use `sample_preschool_keys(driver)` to inspect stored property names.

Graph retrieval evaluation (from the repository root):

```powershell
$env:PYTHONPATH = "SystemCode/src/backend;SystemCode/src/backend/pipeline"
.venv\Scripts\python.exe SystemCode/src/backend/scripts/evaluate_stage1_graph.py
```

`--offline` runs competency-question and Cypher-shape checks without Neo4j.
The live run writes `SystemCode/src/backend/output/stage1_graph_evaluation.json`.

Quick test checklist
1. Ensure your Neo4j instance is running and accessible (resume Aura instance if paused).
2. Create `.env` with `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` at the repo root or current working directory.
3. Run the runner as shown above. The script will print the generated Cypher, params, and up to 50 results.

To inspect Neo4j connectivity, preschool counts, stored property keys, and a
random sample without running a recommendation search, use the read-only
maintenance utility from the repository root:

```powershell
$env:PYTHONPATH = "SystemCode/src/backend;SystemCode/src/backend/pipeline"
.venv\Scripts\python.exe SystemCode/src/backend/scripts/check_kg.py
```

Extending
- Replace `nlp_mapper.map_text_to_filters` with a semantic text-to-filter mapper (sentence embeddings + nearest-neighbour lookup against KG concept labels).
- Add `tests/` and CI steps to validate mapping and query building.

