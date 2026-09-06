# `scripts/`

`scripts/` contains offline operational tools, not request-time application
code. These commands inspect Neo4j, audit evidence and preference coverage,
evaluate recommendations and RAG answers, build webpage inventories and
indexes, and prepare human-review packets.

Scripts may read curated `resources/` and write generated `output/`. Keep them
safe to run deliberately from the repository root, document required
environment variables, and avoid importing script modules into the online API.
Commands that inspect systems should remain read-only unless their purpose and
write effects are explicit.

`evaluate_conversation_supervisor.py` compares deterministic and agent behavior
over the curated full-conversation set. Run it as a module with the backend
`PYTHONPATH`; it requires `--staged` before it will use the configured model and
writes a privacy-safe report only when `--output` is supplied.
