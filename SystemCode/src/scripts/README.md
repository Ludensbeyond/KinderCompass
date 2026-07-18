# Scripts

Offline pipeline — runs locally or on a schedule, not on every web request.

## Planned contents

| Script / module | Purpose |
|-----------------|---------|
| `download.py` | Fetch or refresh datasets from data.gov.sg |
| `clean.py` | Normalise columns, handle missing values, deduplicate |
| `build_graph.py` | Construct the knowledge graph from cleaned tables |
| `export.py` | Write outputs to `data/processed/` |

## Usage (future)

```bash
python -m src.scripts.clean
python -m src.scripts.build_graph
```

## Flow

```
data/raw/  →  scripts/  →  data/processed/
```
