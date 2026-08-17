# Notebooks

Interactive data preparation and reasoning demonstrations for KinderCompass.

| Notebook | Purpose |
|---|---|
| `data_prep.ipynb` | Demonstrate and inspect the shared catalogue-preparation module. |
| `knowledge_graph_gen.ipynb` | Demonstrate the shared, non-destructive-by-default Neo4j loader. |
| `example_stage1_kg_query.ipynb` | Historical Stage 1 graph-query example. |
| `example_stage2_eval_presch_eligibility.ipynb` | Historical Stage 2 eligibility example. |

All notebooks are interactive aids rather than application entry points. The two
operational demonstrations import their implementation from
`SystemCode/src/scripts/`; backend reasoning remains under
`SystemCode/src/backend/`.

See [the PoC 1 guide](../../docs/poc1/Readme.md) for setup and the complete flow.
