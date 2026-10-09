# File-based preschool knowledge retrieval plan

Status: Steps 1–5 complete; backend agent and deterministic retrieval are wired. Step 6 evaluation remains pending.

## Objective and first-version scope

Build a local, persistent vector index from
`SystemCode/data/vectors/Singapore_Preschool_Parent_Guide.md` and let the existing
conversation supervisor select `search_general_knowledge` when a question needs
preschool guidance. No additional database service is required.

The first version covers general guidance from this document: service types,
curriculum, budgeting, subsidy explanations, enrolment, safety, developmental
support, and primary-school transition. School-specific evidence continues to
use its existing isolated retrieval path. Exact school facts and personalised
fee, eligibility, distance, and ranking calculations stay with their existing
repositories and deterministic functions.

This is a separate retrieval extension, not a reopening of the completed
LangGraph migration in `SystemCode/src/backend/doc/agents.md`. Implementation should follow this plan's
steps and update its progress record.

## Recommended design

- Use NumPy for a normalised float32 embedding matrix and cosine similarity.
  Start with exhaustive search; this single guide does not justify FAISS or a
  separate vector database.
- Store chunk text and metadata in JSON and persist model/build information in
  a manifest. Load a validated index once per backend worker rather than once
  per message.
- Keep embedding generation behind an injectable provider interface. Start
  with the project's configured hosted provider if it supports embeddings;
  confirm the model/deployment in step 1. Store credentials in the existing
  backend configuration. A local model is an alternative if an offline demo
  is required, but requires its own dependency and model download.
- Embed document chunks during an explicit offline build. At query time,
  embed only the question with the exact same model and dimensions. Local
  storage does not eliminate that query-time provider requirement.
- Implement the existing `GeneralKnowledgeRetriever.search(question, limit)`
  boundary and inject the adapter into `create_evidence_tools`. Preserve its
  typed evidence and citation results.
- Retain the current curated BM25 retriever for provider/index failures. Also
  provide lexical search over the new guide chunks so its content can remain
  useful when query embeddings are unavailable.

## Data layout

```text
SystemCode/data/vectors/
├── Singapore_Preschool_Parent_Guide.md  # Maintained source
└── parent_guide/
    ├── sources.json                    # Reviewed chunk/section provenance
    ├── CURRENT                         # Active completed build identifier
    └── builds/<build_id>/
        ├── chunks.json                 # Generated text and metadata
        ├── embeddings.npy              # Generated normalised float32 matrix
        └── manifest.json               # Generated integrity/model metadata
```

Keep code in backend modules and scripts. Build into a new directory, validate
all artifacts, then atomically replace `CURRENT`; never publish a partially
written index. Preserve the prior build for rollback. A small completed build
may be checked into the school-project repository for reproducible setup after
reviewing its size and source permissions. Do not store secrets or chat data
with these artifacts.

Chunk metadata should include a stable content-derived ID, matrix row,
document-relative path, section/subsection heading, text, content hash, topic,
`evidence_scope=general`, source links, primary citation mapping, review status,
and relevant policy dates. Keep `document_checked_on`, `source_verified_at`,
and `indexed_at` separate. The guide's claim that information was checked on
9 October 2026 is not a source-fetch timestamp.

The manifest records schema version, source and provenance hashes, chunking
settings, embedding provider/model identifier and version where available,
dimensions, dtype, normalisation method, chunk count, artifact hashes, and
build time. Changed model, dimensions, or chunking settings require a rebuild.

## Step 1 — Review the source and fix the configuration

- Inventory all 11 sections, Markdown tables, source links, and dated claims.
- Define the embedding provider/model, vector path, retrieval mode, timeout,
  and maximum query length. Keep vector retrieval opt-in initially.
- Record primary source mappings in `sources.json`. Review fees, subsidy
  conditions, registration dates, and announced 2027 changes against the
  linked sources before presenting them as authoritative current guidance.
- The public citation contract currently requires an HTTPS URL and a
  retrieval timestamp, and general evidence carries one citation per chunk.
  Map a chunk to one reviewed primary source that supports its claims; split
  mixed-source claims when necessary. Preserve other links as internal
  metadata. Do not invent a public URL for the local Markdown file or claim
  that a cited webpage was fetched when only the guide was read.
- Distinguish the guide's editorial advice from verified official facts. The
  existing general tool labels results `authoritative_fact`; adjust that
  classification if the indexed passage does not warrant it. Restrict the
  first runtime corpus to passages that fit the existing citation contract,
  and report any omitted material.

Acceptance: reviewed source mapping and explicit model configuration exist;
unverified/date-sensitive passages are identified rather than silently
labelled authoritative.

## Step 2 — Parse and chunk the Markdown

- Split by section and subsection before applying a size limit. Start around
  250–450 tokens and tune against actual query results, respecting the
  existing 5,000-character passage contract.
- Prefix embedding text with the document and heading context.
- Preserve lists and table headers. Keep a table whole when it fits; otherwise
  repeat its headers for each row group and attach its explanatory notes.
- Keep exceptions and qualifications with the claims they modify. For
  example, childcare employment exceptions must not lose the infant-care
  qualification, and subsidy maximums must retain co-payment notes.
- Do not overlap across distinct topics or policy periods. Preserve explicit
  distinctions between current 2026 arrangements and announced 2027 changes;
  manually review effective-date metadata instead of inferring that every
  statement expires at year end.

Acceptance: every eligible source block is represented, tables remain
interpretable, IDs are reproducible, and dated guidance retains its context.

## Step 3 — Build and validate the persistent index

- Add an offline build command under `backend/scripts/`, using parsing and
  embedding helpers under `pipeline/` and artifact loading under
  `repositories/`.
- Batch document embeddings with bounded retries and provider timeouts.
  Reuse unchanged vectors only when content and model settings match.
- Reject missing/duplicate IDs, inconsistent row counts, non-finite values,
  zero vectors, dimension mismatches, and artifact hash mismatches. Load NumPy
  arrays with pickle disabled.
- Write the generated artifacts and build summary, validate the completed
  build, and publish it atomically. Do not rebuild on backend startup.

Acceptance: a reproducible build can be loaded in a fresh process without
re-embedding documents, and a failed build leaves the active index usable.

## Step 4 — Implement retrieval and fallback

- Load the active validated build once per worker and embed each bounded query.
- Rank normalised vectors by cosine similarity and return at most three
  passages, matching the current tool limit. Treat scores as rankings, not
  probabilities or universal confidence values.
- Apply reviewed topic/date constraints before ranking when the question
  specifies them. For ambiguous questions affected by a policy change, retain
  clearly labelled periods or ask for the intended year.
- Use a relevance threshold calibrated on labelled questions. Do not return
  an unrelated nearest neighbour just because it ranks first.
- Evaluate lexical and vector retrieval independently. Add hybrid ranking
  only if results show a benefit, particularly for acronyms and exact amounts.
- On missing/corrupt artifacts, incompatible models, or embedding timeouts,
  use guide lexical retrieval and then the existing curated retriever. If no
  relevant evidence is available, return the existing unavailable-evidence
  response. A low-relevance result may also trigger lexical retrieval.

Acceptance: a standalone query command returns relevant cited passages,
rejects unrelated questions, and demonstrates each fallback without a server.

## Step 5 — Connect the existing agent and deterministic paths

- Construct the configured retriever in the preference service and inject it
  into `create_evidence_tools` through `GeneralKnowledgeRetriever`.
- Review intent routing for the guide's broader topics: existing Montessori
  questions are covered, but enrolment, CCTV, CDA, and 2027 policy questions
  must also reach general knowledge when appropriate.
- Keep the current supervisor policy: deterministic intents can constrain
  tool selection and a registered capability is required before answering.
  Vector search runs only when the general knowledge tool is invoked;
  preference updates and structured calculations use their own capabilities.
- Ensure combined questions can request general and school-scoped evidence
  while preserving the distinction between them.
- Wire the same knowledge retrieval boundary into deterministic general
  answers and combined evidence, so agent failures do not silently lose the
  new corpus. This needs explicit service/controller wiring because the
  existing deterministic path takes a JSON index directly.
- Preserve citation validation, bounded execution, and existing HTTP shapes.
  Keep operational logs limited to build ID, retrieval mode, timing, result
  count, and failure category rather than questions or family information.

Acceptance: relevant guidance turns invoke the tool and retrieve vectors;
preference/calculation turns make zero vector calls; deterministic and agent
fallbacks provide grounded guidance without changing user state.

## Step 6 — Evaluate and document the demo

Create a small human-labelled set covering all 11 sections, with expected
section/chunk matches, acceptable answers, and expected tool selection. Include:

| Question | Expected behaviour |
|---|---|
| What is Montessori? | Retrieve learning-approach guidance |
| Does a waitlist guarantee a place? | Retrieve enrolment qualifications |
| Can parents watch the CCTV livestream? | Retrieve access limitations |
| How do subsidy thresholds change in 2027? | Retrieve dated 2027 guidance |
| Does the childcare work exception also apply to infant care? | Preserve the exception's qualification |
| What is the fee for this selected centre? | Query structured school facts |
| Change my budget to $800 | Update preferences; zero vector calls |
| Does this centre use Montessori? | Use centre-specific evidence |
| What is the weather tomorrow? | No relevant guidance; no fabricated answer |

Compare BM25 and vectors on the same labelled set. Proposed first-version
gates: at least 90% of answerable questions retrieve an expected passage in
the top three; all reviewed date/exception cases preserve their qualifications;
all returned citations resolve to approved metadata; and no unrelated test
question receives a supported factual answer. Report corpus exclusions and
failures alongside results.

Use deterministic embedding doubles for unit tests and a separate real-provider
smoke evaluation. Cover persistence/reload, table chunking, mismatch/corruption,
timeout fallback, tool routing, combined scope, and state preservation. Run the
focused suites followed by the complete backend suite required by `AGENTS.md`.

Document build, query, backend opt-in, and rollback commands; whether a demo
requires network/API access; and how to update the source and rebuild. Check
startup memory and retrieval latency on the intended demo machine.

Acceptance: evaluation gates and backend checks pass, and a teammate can run
the documented demo with local artifacts and no vector database provisioning.

## Progress and next step

- Plan created from the supplied guide and current backend interfaces.
- Step 1 completed on 9 October 2026: all 11 sections, 9 tables and 49 unique
  source URLs inventoried in `SystemCode/data/vectors/parent_guide/sources.json`.
  23 source mappings approved with actual fetch timestamps, response hashes,
  selection rules and policy dates. All other material is explicitly excluded
  pending verification or citation-compatible splitting.
- Verified the 2026 fees, 2026/2027 infant and childcare subsidy tables,
  childcare employment exception, CDA/package transitions and MK registration
  dates against fetched primary sources. Blocked sources, unverified KiFAS
  amounts/future thresholds and the incorrect MK/P1 source mapping are recorded.
- Added validated opt-in configuration: OpenAI `text-embedding-3-small`, 1536
  dimensions, repository-relative vector path, 8-second timeout and maximum
  2000-character query. Default mode remains curated; configuration is not yet
  wired to a retriever. Non-authoritative typed general passages retain `unknown`
  classification through the existing evidence tool.
- Details and exclusions: [backend source review](../SystemCode/src/backend/doc/file-vector-source-review.md).
- No dependencies, source Markdown, embeddings, index publication, parsing or
  runtime retriever wiring were changed. Source and plan are included as inputs.
- Verification: all 11 focused configuration/provenance/evidence-tool tests
  passed. Full backend discovery ran 310 tests: 307 passed, two failures and
  one error. An untouched `HEAD` checkout under identical environment settings
  ran 305 tests with the same three failures (combined evidence routing, invalid
  LLM-value fallback and incremental ingestion checkpointing). No new regression
  was observed. Optional live LLM features were disabled for both full runs;
  in-process API tests required execution outside the filesystem sandbox.
- After Step 1, the next implementation step was Step 2, parse and chunk the Markdown.
- Step 1 reverified on 9 October 2026 against implementation commit `16f8ef2`:
  all 11 focused tests passed again. Full backend discovery outside the sandbox
  ran 310 tests in 69.762 seconds: 307 passed, with the same two failures and
  one error listed above. Optional live LLM features were disabled. No further
  implementation was needed, and Step 2 remains unstarted.
- Step 2 completed on 9 October 2026: added pure offline Markdown parsing and
  reviewed sentence/column selection under `pipeline/parent_guide_chunking.py`.
  All 23 eligible mappings produce reproducible chunks covering sections 1–10;
  all existing corpus exclusions remain recorded. Section 11 remains excluded.
- Tables reconstruct their original headers, split mixed primary sources, and
  repeat explanatory notes with each size-limited row group. Atomic reviewed
  prose preserves exceptions and qualifications; oversized atomic selections
  fail for further review instead of being truncated. The soft target is 1,800
  characters and the hard cap is 5,000 including embedding heading context.
- Added hashed, sentence-specific context selections for the already-reviewed
  citizen-child fee-cap and MK/KCare holiday-payment conditions. Source text is
  unchanged; no sources were fetched. Policy dates and citation fetch timestamps
  are copied from reviewed metadata without inferred expiry dates.
- Details: [backend chunking guide](../SystemCode/src/backend/doc/file-vector-chunking.md).
  No embeddings, build artifacts, publication command or runtime wiring were added.
- Verification: all 22 focused chunking/configuration/evidence-tool tests passed.
  Required backend discovery outside the sandbox ran 321 tests in 71.974 seconds:
  317 passed, three failures and one error. A matched untouched `HEAD` archive
  with the same repository `.env` ran 310 tests in 68.938 seconds and reproduced
  the previously recorded combined-routing, invalid-value fallback and ingestion
  issues. The implementation run also had a variable Montessori/SPARK routing
  failure. Backend startup loads `.env` with `override=True`, so shell flags did
  not reliably disable optional providers. A controlled offline run disabled
  dotenv loading and all four optional LLM flags: 320 of 321 tests passed in
  14.987 seconds, with only the existing ingestion checkpoint failure. The
  untouched archive without `.env` likewise had only that ingestion failure
  (309 of 310 passed). No deterministic regression was observed.
- Next implementation step: Step 3, build and validate the persistent index.
  Stop here for this implementation request.
- Step 3 completed on 9 October 2026: added an explicit offline build CLI,
  injectable batched OpenAI embeddings with bounded transient retries/timeouts,
  and validated NumPy/JSON artifact loading. Compatible unchanged vectors are
  reused; missing, corrupt or incompatible builds cannot supply reused vectors.
- Completed builds are validated before atomically replacing `CURRENT`; failed
  embedding, write, validation or publication leaves the prior index active.
  The loader rejects invalid IDs/rows/counts, model/dimension mismatches,
  non-finite/zero/non-unit vectors, pickle arrays and artifact hash mismatches.
  Empty NumPy artifacts become validation errors so rebuilds recover.
- Reviewed both pre-existing uncommitted 23-chunk, 1536-dimensional builds and
  validated them in fresh processes against the configured model and original
  reviewed metadata. One build records 23 embeddings; its successor records
  complete reuse. Both small builds are retained for reproducible loading and
  rollback. This verification made no new provider embedding requests.
- Added NumPy to backend requirements and documented build, validation, reuse,
  network requirements and rollback in the
  [index construction guide](../SystemCode/src/backend/doc/file-vector-index.md).
  Runtime retrieval, fallback, routing and service injection remain deferred.
- Verification: all 39 focused persistence/chunking/configuration/evidence-tool
  tests passed. Required full backend discovery outside the sandbox, with dotenv
  loading and all four optional LLM flags disabled, ran 338 tests in 15.644
  seconds: 337 passed and the existing incremental ingestion checkpoint test
  failed. An untouched `b5204ea` archive with identical settings ran 321 tests
  in 15.453 seconds: 320 passed, with that same failure. No deterministic
  regression was observed. Sandboxed full runs stalled in API tests; completed
  verification uses the outside-sandbox runs above.
- Next implementation step: Step 4, implement retrieval and fallback.
  Stop here for this implementation request.

- Step 4 completed on 9 October 2026: added a standalone typed parent-guide
  retriever and read-only query CLI. A constructed instance validates/loads the
  active build once and embeds bounded questions only, with one timed provider
  attempt, matching model/dimensions and exhaustive cosine ranking (maximum three).
- Reviewed topic/year constraints apply before vector and lexical ranking;
  dated passages retain explicit policy-period labels and original qualifications.
  Undated background remains eligible. Explicit constraints cannot be undone by
  curated fallback whose metadata cannot enforce them.
- Missing/corrupt/incompatible builds recover through freshly hash-validated
  reviewed Markdown. Provider/model/invalid-vector/timeout failures and low
  similarity try guide lexical search, then the injected curated retriever.
  Empty evidence retains the existing unavailable-response boundary.
- Calibrated provisional cosine cutoff 0.40 and lexical coverage cutoff 0.45
  on eight labelled positives and six unsupported questions. Real OpenAI query
  embeddings retrieved expected top-three passages for all eight positives;
  all six unsupported cases returned empty evidence. Independent lexical search
  also passed all fourteen cases; no hybrid ranking was added. Four negatives
  are unrelated and two (CCTV/waitlist) are excluded by existing source review.
  This small standalone set does not replace the comprehensive Step 6 evaluation.
- Added deterministic tests for load-once behavior, query bounds, typed citations,
  period/topic constraints, cosine rejection and every fallback category/order.
  No source, provenance, build artifacts, service injection or routing changed.
  Commands and limitations: [standalone retrieval guide](../SystemCode/src/backend/doc/file-vector-retrieval.md).
- Verification: all 50 focused retrieval/persistence/chunking/configuration/tool
  tests passed. Full backend discovery outside the sandbox with dotenv loading
  and four optional LLM flags disabled ran 349 tests in 16.105 seconds: 348 passed
  and the existing incremental ingestion checkpoint test failed. An untouched
  HEAD archive under identical settings ran 338 tests in 16.299 seconds: 337
  passed, with the same failure. No new deterministic regression was observed.
- Next implementation step: Step 5, connect the existing agent and deterministic
  paths. Stop here for this implementation request.

- Step 5 completed on 9 October 2026: `PreferenceService` constructs and caches
  the configured general retriever under a construction lock, then injects it
  into the registered evidence tool and deterministic general/combined answers.
  Vector/lexical modes retain guide-to-curated fallbacks; invalid configuration
  falls back to curated. Default retrieval mode remains curated.
- Broader question routing covers enrolment, registration, waitlists, CCTV, CDA,
  EIPIC, fee caps and dated policy changes. Centre/center references preserve
  school scope. Existing deterministic tool restrictions keep preferences,
  structured school facts and family calculations away from vector search.
- Deterministic answers validate typed passages/citations and retain full text,
  policy labels and evidence classification. Agent setup failure retrieves the
  same guide corpus through the deterministic service boundary. Combined answers
  keep school and general citations separate; family preferences remain intact.
- Added nine integration tests using deterministic embedding/model doubles for
  service load-once behavior, supervisor vector calls, grounded agent fallback,
  timeout/lexical recovery, corpus exclusions, combined scope, safe configuration
  fallback, evidence classification, routing and zero non-guidance vector calls.
  No provider calls, source changes or generated build changes were required.
- Runtime configuration and restart requirements are documented in the
  [backend integration guide](../SystemCode/src/backend/doc/file-vector-service.md).
  No new operational question/family logging or HTTP shapes were introduced.
- Verification: all 75 focused retrieval, persistence, chunking, configuration,
  evidence, routing and supervisor tests passed. Required full backend discovery
  outside the sandbox, with dotenv and four optional LLM flags disabled, ran
  358 tests in 16.927 seconds: 357 passed and the existing incremental ingestion
  checkpoint test failed. An untouched `a9090cf` archive under identical settings
  ran 349 tests with the same sole failure. No new deterministic regression was
  observed. Sandboxed API tests stalled; completed verification used the runs
  outside the sandbox. The nine integration tests also passed after final cleanup.
- Next implementation step: Step 6, evaluate and document the demo.
  Stop here for this implementation request.
