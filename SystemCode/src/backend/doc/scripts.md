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
