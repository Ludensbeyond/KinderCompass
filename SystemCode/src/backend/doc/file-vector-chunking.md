# Parent-guide Markdown chunking (step 2)

`pipeline/parent_guide_chunking.py` exposes `parse_markdown`,
`chunk_parent_guide`, and the filesystem convenience reader
`load_parent_guide_chunks`. These functions create in-memory metadata only.
No embedding provider, index publication, backend wiring or dependencies are
introduced. Step 3 owns the offline build command and generated artifacts.

The parser inventories all 11 sections and nine tables and splits section and
subsection boundaries before applying size limits. Reviewed mappings are kept
separate even when adjacent: each resulting chunk has one primary citation.
All 23 eligible mappings are represented by 23 default chunks covering sections
1–10. Section 11 and the other exclusions from the source review remain omitted.
Most reviewed selections are shorter than the initial 250–450-token target;
merging them would cross citation or topic boundaries. The largest passage is
932 characters, or 1,046 with document/heading context. Token lengths are not
claimed as exact model-tokenizer measurements.

The default soft target is 1,800 characters (roughly 450 tokens); the hard
limit is 5,000 characters including embedding context. Lists and reviewed
prose remain atomic so claims cannot lose exceptions. Tables stay whole when
they fit. Larger tables split into complete row groups, with headers and all
approved explanatory prose repeated in every group. If a single row and its
qualifications, or atomic prose, cannot fit the hard limit, parsing fails and
requires a smaller reviewed selection. It never truncates qualifications.

Document and locator hashes must match before sentence or column selections
are applied. Table selections reconstruct headers and separator rows from the
original table even when a mapping's locator starts on its separator or data
row. Unsupported visit-question and parent-action columns are removed. Fees
are split by AOP, POP and MOE source. Three explicit hashed `context_selections`
in `sources.json` attach the existing citizen-child cap condition or MK/KCare
holiday-payment condition from line 102. These conditions were already verified
in step 1; no additional source fetch is represented.

Chunk IDs derive from the reviewed mapping ID and SHA-256 of the exact
embedding text, including document and headings. Reordering mappings changes
matrix rows but preserves IDs. Metadata carries the source-relative path,
topic/headings, selected text, qualifications, internal source links, citation,
review status and manually reviewed policy dates. The public citation uses the
primary source's resolved HTTPS URL and actual `source_verified_at`. The
editorial `document_checked_on` stays separate and `indexed_at` remains null.
No effective dates are inferred: 2026 and announced 2027 guidance stay in
separate chunks with the reviewed dates unchanged.

Inspect the corpus without a server, network access or filesystem writes:

```bash
.venv/bin/python - <<'PY'
from SystemCode.src.backend.pipeline.parent_guide_chunking import load_parent_guide_chunks
for chunk in load_parent_guide_chunks():
    print(chunk.mapping_id, len(chunk.text), chunk.citation)
PY
```

Focused coverage checks reproducibility, complete eligible mapping coverage,
source drift, sentence/column exclusions, citation timestamps, mixed-source
fees, whole tables and forced row groups, atomic infant-care qualifications,
and the 2027 birth-cohort/PayNow/co-matching transition.

All 22 focused tests pass. Required full discovery ran 321 tests, with 317
passing and four failures/errors; a matched untouched baseline reproduces
three known issues. The extra Montessori/SPARK routing failure varied with
optional provider execution. Backend startup overrides shell flags from `.env`.
Controlled offline discovery (dotenv loading disabled, all optional LLM flags
false) passes 320 of 321 tests, leaving the existing ingestion checkpoint failure,
which also occurs in the untouched offline baseline. See the plan progress
record for timings and comparison details.
