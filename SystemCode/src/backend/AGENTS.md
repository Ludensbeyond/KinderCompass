# Backend contributor guidance

This file supplements [`README.md`](README.md).

## Architecture boundaries

- Keep `main.py` a thin FastAPI layer for routing, dependency wiring, CORS, and
  translating service failures into HTTP responses.
- Put shared request, response, catalogue, and family contracts in `domain/`;
  domain models must not depend on FastAPI or infrastructure clients.
- Keep authoritative catalogue and dated policy access in `repositories/`.
- Use `services/` for use-case orchestration across repositories and pipeline
  functions, and keep reusable ranking, eligibility, cost, distance, and
  evidence logic in `pipeline/`.
- Preserve deterministic fallbacks and keep external integrations isolated at
  their existing boundaries.

The backend is authoritative for school facts. Accept stable school IDs and
user choices from the frontend, then reload names, fees, programmes,
coordinates, and other facts server-side before evaluating or returning them.
Never trust browser-supplied school records.

## Safety and verification

- Keep Neo4j, OneMap, and OpenAI secrets in the repository-level `.env`. Never
  commit, log, return, or expose them through frontend or `NEXT_PUBLIC_*`
  variables.
- Treat `output/` as generated. Regenerate artifacts with their owning pipeline
  or audit command instead of casually editing them; review changes carefully
  because the application reads `output/web_rag_pilot_index.json` by default.
- From the Git repository root, run:

  ```bash
  PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline .venv/bin/python -m unittest discover -s SystemCode/src/backend/tests -v
  ```

Put substantial, durable backend design documentation in this project's `doc/` and
link it from this project's [`README.md`](README.md). Do not use `doc/` for
temporary notes or to duplicate README content.
