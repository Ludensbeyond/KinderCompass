# PoC 1 backend

FastAPI endpoints wrapping the three-stage PoC 1 reasoning pipeline.

## Run

From the repository root:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r SystemCode/src/backend/poc1/requirements.txt
uvicorn SystemCode.src.backend.poc1.main:app --reload
```

Stage 1 loads Neo4j credentials from
`SystemCode/notebooks/poc1/.env`. The API is served at
`http://localhost:8000`; interactive documentation is at `/docs`.

| Endpoint | Pipeline stage |
|---|---|
| `GET /api/health` | Service health check |
| `POST /api/search` | Stage 1 preference search through Neo4j |
| `POST /api/evaluate` | Stage 2 age eligibility and fee estimate |
| `POST /api/route` | Stage 3 coordinate join and route optimization |

Requests are processed in memory. The API does not write sensitive form values to the PoC JSON output files.
