# Notebooks

Interactive data preparation and reasoning demonstrations for KinderCompass.

| Notebook | Purpose |
|---|---|
| `data_prep.ipynb` | Clean and combine source preschool records. |
| `knowledge_graph_gen.ipynb` | Load the prepared dataset into Neo4j. |
| `example_stage1_kg_query.ipynb` | Historical Stage 1 graph-query example. |
| `example_stage2_eval_presch_eligibility.ipynb` | Historical Stage 2 eligibility example. |

The `example_` notebooks are learning aids rather than application entry points.
Generated notebook artifacts belong in `output/`. Stable application logic is
maintained under `SystemCode/src/backend/`.

See [the PoC 1 guide](../../docs/poc1/Readme.md) for setup and the complete flow.
