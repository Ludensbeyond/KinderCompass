# KinderCompass contributor guidance

KinderCompass's Next.js frontend sends family inputs and stable school IDs to
the FastAPI backend. The backend owns validation and orchestration, resolves
authoritative school and policy data, and integrates with Neo4j, OneMap,
optional OpenAI features, and curated webpage evidence. Keep credentials and
external-service access out of browser code.

## Directory map

- [`backend/`](backend/AGENTS.md) contains the API, domain contracts,
  repositories, services, recommendation pipeline, tests, resources, and
  generated outputs. Follow its nested instructions for backend work.
- [`frontend/`](frontend/AGENTS.md) contains the Next.js App Router interface.
  Follow its nested instructions for frontend work.
- `scripts/` is the separate offline catalogue and Neo4j-loading pipeline; its
  workflow and safeguards are documented in `scripts/README.md`.

Keep changes within the responsible project and preserve the boundary that the
browser talks to FastAPI rather than directly to external data providers.
