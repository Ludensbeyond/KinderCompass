# `tests/`

`tests/` contains backend unit and integration regression coverage for API
startup, architecture boundaries, conversational state, preferences, feedback,
recommendation stages, policy evaluation, distances, and grounded webpage RAG.

Tests should mock external providers where practical and must not require live
Neo4j, OneMap, or OpenAI access for normal regression runs. Add tests alongside
behavior changes and preserve assertions that the backend reloads authoritative
school data rather than trusting browser-provided records.

Run the suite from the Git repository root using the command in
[`backend/AGENTS.md`](../AGENTS.md#safety-and-verification).
