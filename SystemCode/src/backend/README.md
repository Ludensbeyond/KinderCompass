# Backend

FastAPI services and reusable reasoning modules for KinderCompass PoC 1.

| Path | Purpose |
|---|---|
| `main.py` | HTTP API application. |
| `pipeline/` | Stage 1 search, Stage 2 eligibility, and Stage 3 distance logic. |
| `scripts/` | Evaluation, evidence-audit, and webpage-RAG utilities. |
| `resources/` | Curated RAG resources and review labels. |
| `tests/` | Unit and integration tests. |
| `output/` | Generated handoff and evaluation artifacts. |

From the repository root:

```powershell
.venv\Scripts\python.exe -m uvicorn SystemCode.src.backend.main:app --reload
$env:PYTHONPATH = "SystemCode/src/backend;SystemCode/src/backend/pipeline"
.venv\Scripts\python.exe -m unittest discover -s SystemCode/src/backend/tests -v
```

See [the PoC 1 guide](../../../docs/poc1/Readme.md) for complete setup and usage.
