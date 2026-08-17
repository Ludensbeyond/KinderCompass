# Stage 1 — Knowledge Graph Search & Match (Local module)

This folder contains a minimal, modular Stage‑1 implementation used to map parent free‑text preferences into Neo4j queries and return a shortlist of preschools with baseline attributes.

Files
- `kg_client.py`: Neo4j helper functions — `get_driver()`, `verify_connectivity(driver)`, and `run_query(driver, query, params)`.
- `query_builder.py`: Builds parameterized Cypher for Stage‑1 from a `filters` dict. Also contains `sample_preschool_keys()` to inspect node property keys.
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
- `query_builder` assumes the `Preschool` nodes have properties named `base_fee`, `operator_scheme`, and `care_levels`. Use `sample_preschool_keys(driver)` to verify property names before running.

Quick test checklist
1. Ensure your Neo4j instance is running and accessible (resume Aura instance if paused).
2. Create `.env` with `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` at the repo root or current working directory.
3. Run the runner as shown above. The script will print the generated Cypher, params, and up to 50 results.

Extending
- Replace `nlp_mapper.map_text_to_filters` with a semantic text-to-filter mapper (sentence embeddings + nearest-neighbour lookup against KG concept labels).
- Add `tests/` and CI steps to validate mapping and query building.

