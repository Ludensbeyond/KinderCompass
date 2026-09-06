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
over the curated full-conversation set. Run its read-only dependency preflight
before staging; it initializes the configured model client without generating,
performs a live synthetic OneMap geocode, and validates the catalogue, current
policy, selected-school evidence, and general-knowledge evidence:

```bash
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python -m SystemCode.src.backend.scripts.evaluate_conversation_supervisor \
  --preflight
```

The live evaluation repeats that preflight before its first case, requires the
explicit `--staged` acknowledgement, and writes a privacy-safe report only when
`--output` is supplied. A failed preflight exits with status 2 and never writes
the report. Reports retain the raw `agent_fallback_rate`; rollout thresholds use
`unexpected_agent_fallback_rate`, which excludes only cases whose reviewed
fixture explicitly requires or permits safe deterministic fallback.

```bash
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python -m SystemCode.src.backend.scripts.evaluate_conversation_supervisor \
  --staged --output SystemCode/src/backend/output/conversation_agent_evaluation.json
```
