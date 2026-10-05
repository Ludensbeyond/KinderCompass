# `pipeline/`

`pipeline/` contains reusable recommendation logic that is not tied to FastAPI.
`pipeline.py` provides an in-memory Stage 1-to-Stage 2 integration entry point.

## Subfolders

- `stage1/` interprets preferences, routes intents, queries Neo4j, applies
  proximity and scoring, builds explanations, and retrieves grounded webpage
  evidence. Its `runner.py` also supports command-line execution.
- `stage2/` evaluates age/programme eligibility and estimates fees and subsidies
  from authoritative school and dated policy data.
- `stage3/` loads coordinates and calculates home-to-preschool distances and
  route output.

Each stage has its own `Readme.md` with stage-specific usage. Pipeline functions
should remain callable by services and tests without starting an HTTP server.
Keep credentials in server-side configuration, isolate external calls in their
existing clients, and preserve deterministic fallbacks for optional LLM
features.
