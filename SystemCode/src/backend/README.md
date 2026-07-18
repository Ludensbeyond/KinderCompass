# Backend

FastAPI service exposing KinderCompass reasoning engines as HTTP endpoints.

## Planned contents

| Component | Purpose |
|-----------|---------|
| `main.py` | FastAPI app entry point |
| `engines/` | Four reasoning engines (search, compare, recommend, explain) |
| `models/` | Pydantic request/response schemas |
| `services/` | Graph queries and business logic |
| `api/` | Route definitions |

## Planned API (example)

```
GET  /centres              — search and filter preschools
GET  /centres/{id}         — centre detail
POST /compare              — side-by-side comparison
POST /recommend            — personalised recommendations
GET  /explain/{id}         — reasoning trace for a result
```

## Runs against

`data/processed/` — graph and lookup files built by `src/scripts/`.

## Dev (future)

```bash
uvicorn src.backend.main:app --reload
```
