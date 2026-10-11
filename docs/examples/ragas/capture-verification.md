# One real agent capture

Step 3 completed on 2026-10-08 for the unchanged, label-free `nel_age` input:
“Which ages does the Nurturing Early Learners framework cover?” Fresh empty
profile, no selected schools and no history were supplied. No reference labels
were loaded by the collector.

Reproduce from the repository root (uses the configured provider and incurs
agent charges; no judge call):

```bash
PYTHONPATH=.:SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python docs/examples/ragas/capture_one.py --staged \
  --output /tmp/kindercompass-ragas-nel-age-live.jsonl
```

The offline wrapper reuses `staged_runner`, the real `PreferenceService`,
repository wiring, tools and validated supervisor. It delegates model calls
unchanged, records messages before invocation and observes retrieval return
values. It does not modify production contracts, public responses or ordinary
evaluation reports. Optional LangSmith export is disabled in this process.
Only this one case is supported; dataset automation belongs to step 4.

## Inspected execution

The initial sandbox attempt failed at the model boundary (`model_error`). Its
controller fallback asked for a preference and supplied no evidence. That
capture remains `/tmp/kindercompass-ragas-nel-age.jsonl`; its empty contexts were
preserved. After approved network access, the live retry succeeded:

| Item | Observed result |
|---|---|
| Capture time (UTC) | 2026-10-08T06:00:51.186976+00:00 |
| Source revision | `a0265f71f36e105fe89faed8b54d08e1fd9e0cb3` plus uncommitted offline collector |
| Requested / resolved agent | `gpt-4o-mini` / `gpt-4o-mini-2024-07-18` |
| Timeout | 8 seconds; provider temperature left at existing default |
| Python | 3.12.12 |
| LangChain Core / OpenAI | 1.6.0 / 1.6.0 |
| LangGraph / OpenAI SDK | 1.2.11 / 2.54.0 |
| Route / tool | `general_knowledge` / `search_general_knowledge` |
| Supervisor | Accepted; one capability call, three graph iterations, zero profile mutations, no fallback |
| Model boundary | Two invocations: tool selection then answer composition |
| Evidence snapshot SHA-256 | `9abf0de536ca0dc11e11455b0a5258a7e848a0ffed7132ab18a7e4ffd5afb6f6` |
| Live capture SHA-256 | `35791311a63bb297bd668a4dc0f869522944099135c457adec3dd54c820e6423` |

Raw model inputs, responses, retrieved texts and returned state remain outside
Git in `/tmp/kindercompass-ragas-nel-age-live.jsonl`. These temporary files are
local verification artifacts, not a durable baseline bundle.

Manual inspection confirmed the composer received these passages in order:

| Position | Chunk ID | Provenance |
|---|---|---|
| 1 | `GENERAL:nel-framework:0` | Singapore Ministry of Education, Nurturing Early Learners 2022 PDF |
| 2 | `GENERAL:quality-teaching:0` | ECDA, Quality Teaching Tool |
| 3 | `GENERAL:eydf:0` | ECDA, Early Years Development Framework 2023 |

All have general scope and snapshot retrieval date 2026-08-14. Full source URLs,
titles, authority and timestamps are retained in `passages[].citation`.
The final `agent_response.question` becomes `response`. It starts “Singapore's
Nurturing Early Learners framework guides preschool education for children
aged four to six.” It also includes the Quality Teaching Tool passage. This
extra content is an observation for later quality review, not corrected here.

## Evidence boundary and verification

`CuratedGeneralKnowledgeRetriever.search` returns up to three typed passages.
`create_evidence_tools.search_general` joins the first two into
`answer_candidate`, retains all three texts as `grounding_facts`, and includes
all three citations. The supervisor sends the complete serialized capability
result in a `ToolMessage` to the answering model, including profile, understood
items and status fields. The raw message and `composer_tool_payloads` preserve
that complete input, not just the cited excerpts.

`retrieved_contexts` contains all three ordered grounding texts, which were
verified to equal the original retrieved passage texts byte for byte. The
concatenated answer candidate remains separate in `composer_tool_payloads`;
it is derived from those passages, not another independently retrieved context.
`composer_grounding_facts` records the model-facing facts separately so future
transformations can be identified. The exporter fails if accepted-path facts
and observed passages differ, requiring inspection before scoring. RAGAS will
evaluate these passage contexts; it will not evaluate profile/status metadata
or count the duplicate answer candidate as a separate chunk.

The composer uses candidates and facts; its grounding guard additionally uses
citation title and authority. Server composition can replace unsupported
wording with bounded candidates. Full pre-composition responses are retained,
so the final public wording can be compared with provider output. A rejected
supervisor is explicitly labelled `fallback`, and this collector separately
observes the controller's actual retrieval. For this single non-comparison
question the controller uses its first match; it can also return no evidence.
This fallback mapping is intentionally specific to `nel_age`.

Replaying the observed provider responses through the same service with and
without instrumentation produced identical complete agent and controller
responses, including returned profile state. The replay fixed the observed
server intent (`ask_general_knowledge`, method `llm`) to avoid another paid
classification call. The caller's empty input profile remained unchanged;
returned agent state matched controller state. This verifies wrapper
transparency without expecting two stochastic live calls to match.

The real capture passed `score.py --validate-only` against a temporary
one-case subset of the frozen dataset:

```bash
.venv/bin/python docs/examples/ragas/score.py \
  --cases /tmp/kindercompass-ragas-nel-age-cases.jsonl \
  --runs /tmp/kindercompass-ragas-nel-age-live.jsonl --validate-only
```

Result: one RAGAS case validated. No scores or baseline are claimed. Step 4
remains pending.

The required backend discovery command was also attempted. The sandbox run
stalled in a FastAPI TestClient test and was interrupted. The approved retry
completed all 305 tests: 302 passed, two failed and one errored. The failures
were `test_combined_answer_keeps_school_and_general_sources_distinct`
(`general_knowledge` instead of `combined_evidence`) and
`test_incremental_run_checkpoints_and_skips_completed_pages` (one attempt
instead of zero); the error was
`test_stage1_rejects_invalid_llm_value_and_falls_back` (missing
`extraction_method`). None imports this collector; backend implementation and
fixtures were unchanged. The suite therefore does not pass in this configured
environment, and these unrelated checks remain unresolved. Collector syntax,
Git whitespace checks, actual capture validation and replay transparency pass.
