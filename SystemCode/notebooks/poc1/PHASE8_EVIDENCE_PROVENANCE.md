# Phase 8: Evidence provenance, quality, and freshness

Phase 8 shows where recommendation evidence came from and prevents missing, derived, and confirmed-negative values from being conflated.

## Evidence metadata

Each weighted preference breakdown now includes:

- evidence state: `verified`, `derived`, `calculated`, or `unknown`;
- value state: `confirmed_yes`, `confirmed_no`, `confirmed_value`, or `unknown`;
- source and source method;
- source reliability;
- source date when available; and
- freshness: `current`, `stale`, `future_dated`, or `unknown`.

A source date is current for up to 365 days. Missing or invalid dates are unknown rather than assumed current. Engineering code and audits retain the standard `freshness` and `value_state` fields, while the parent-facing UI keeps the evidence summary concise with **Source**, **Evidence**, and **Last updated**.

Pedagogy is explicitly labelled as a limited KinderCompass derivation from the centre name. The processed value `General` means no specific pedagogy keyword was detected; Phase 8 treats it as unknown evidence, not as verified general pedagogy or a proven mismatch.

## User interface and chat

Expand **How this score was calculated** below a result to inspect its source, evidence state, value state, and freshness.

After selecting a school, the chatbot can answer:

- `Where did this school information come from?`
- `How reliable is its pedagogy information?`
- `Which evidence is missing for this school?`

Deterministic responses remain available, and optional LLM wording is restricted to the supplied school breakdown.

## Run the evidence audit

From the repository root:

```powershell
.\.venv\Scripts\python.exe SystemCode\notebooks\poc1\scripts\audit_evidence_quality.py
```

Generate JSON:

```powershell
.\.venv\Scripts\python.exe SystemCode\notebooks\poc1\scripts\audit_evidence_quality.py --format json
```

Save a report:

```powershell
.\.venv\Scripts\python.exe SystemCode\notebooks\poc1\scripts\audit_evidence_quality.py --output SystemCode\notebooks\poc1\output\evidence_quality.md
```

The audit reports coverage, unknown values, confirmed `No` values, derived evidence, freshness, and invalid provenance definitions. It uses school catalogue data only and does not read family details or chat history.

## Refreshing live update dates

`last_updated` is imported from `kindercompass_master.json` into each Neo4j `Preschool` node and returned by the Stage 1 query. After introducing this field or refreshing the processed catalogue, rerun `knowledge_graph_gen.ipynb` so existing graph nodes receive the latest source date. Restart the backend and generate new recommendations afterward; previously returned browser results are not updated in place.
