# Phase 9: Official-webpage RAG enrichment

Phase 9 aims to retrieve cited, school-specific evidence for preferences that the structured catalogue cannot currently verify. Webpage evidence is explanation-only until coverage and retrieval accuracy are audited.

## Phase 9 scripts

| Script | Purpose |
|---|---|
| `build_website_inventory.py` | Reads website URLs from `kindercompass_master.json`, normalises them, and classifies them. |
| `automate_web_rag_pilot.py` | Runs inventory, school-page verification, shared-page handling, automatic approval, and ingestion as one workflow. |
| `run_web_rag_pilot.py` | Downloads and ingests approved pages from an existing allowlist. |
| `query_web_rag_pilot.py` | Searches the saved chunks for one specified school and returns cited evidence. |
| `evaluate_web_rag_pilot.py` | Tests school isolation, citation completeness, unavailable evidence, and the explanation-only contract. |
| `audit_web_rag_readiness.py` | Evaluates labelled identity and retrieval cases against explicit production acceptance gates. |
| `review_web_rag_audit.py` | Exports protected human-review CSV packets and imports completed rows into the audit labels. |

## Step 1: website candidate inventory

`../../SystemCode/src/backend/scripts/build_website_inventory.py` extracts `centre_website` and `website_lifesg` from the processed school catalogue. It runs offline and:

- adds a missing `https://` scheme;
- normalises host, path, fragments, and tracking parameters;
- deduplicates equivalent URLs;
- reports how many schools share a page;
- flags social-page candidates;
- distinguishes unavailable, shared-operator, and school-specific candidates; and
- leaves every candidate identity as `not_verified`.

The classification is a review queue, not proof that a unique URL belongs to a particular centre.

Current inventory:

| Candidate scope | Schools |
|---|---:|
| School-specific candidate | 520 |
| Shared operator-page candidate | 948 |
| Social-page candidate | 5 |
| Unavailable | 394 |

There are 659 normalised candidate URLs across 1,473 schools with at least one candidate.

### Inventory limitations

The inventory is a candidate-discovery audit, not webpage verification. In particular:

- it does not visit a URL, resolve redirects, inspect canonical links, or detect an outdated or unavailable page;
- `school_specific_candidate` means only that the exact normalised URL occurs for one school, not that the page is a verified branch page;
- a unique URL can still lead to an operator homepage or a page containing several branches;
- classification uses the first distinct candidate, with `centre_website` considered before `website_lifesg`;
- sharing is detected from exact normalised URLs rather than final destinations or page content;
- explicit `http` and `https`, `www` and non-`www`, and paths such as `/` and `/index.html` may remain separate;
- only common tracking parameters are removed, while other query parameters remain;
- social-page detection uses a small fixed domain list and may not recognise every social, directory, or third-party page; and
- the results reflect the current catalogue snapshot and become stale when catalogue fields or websites change.

Consequently, inventory classifications must pass the identity-verification gate before ingestion.

## Run the inventory

From the repository root:

```powershell
.\.venv\Scripts\python.exe SystemCode\src\backend\scripts\build_website_inventory.py
```

Save the detailed JSON inventory:

```powershell
.\.venv\Scripts\python.exe SystemCode\src\backend\scripts\build_website_inventory.py --format json --output SystemCode\notebooks\output\website_inventory.json
```

Create a reviewable CSV:

```powershell
.\.venv\Scripts\python.exe SystemCode\src\backend\scripts\build_website_inventory.py --format csv --output SystemCode\notebooks\output\website_inventory.csv
```

## Identity-verification gate

Before fetching or indexing a page, verify at least two centre identifiers, such as centre name, address, postal code, centre code, and official operator domain. Shared operator pages may support operator-level claims only and must not be attributed to every branch as school-specific evidence.

## Shared operator pages

The automated workflow groups `shared_operator_page_candidate` records by normalised URL and downloads each unique page once. An accessible shared page is stored separately with:

- an `OPERATOR_PAGE:` identifier;
- `evidence_scope: operator`;
- every catalogue school linked to that shared URL;
- final URL, title, retrieval time, content hash, and chunks; and
- an explicit warning that its claims are not verified for a particular branch.

Shared-page decisions are written to `../../SystemCode/src/backend/resources/web_rag/operator_page_allowlist.json`. Their chunks are stored under `operator_pages` in the pilot index, separate from the school-specific `pages` collection.

Ordinary retrieval searches only school-specific chunks. Operator evidence must be requested explicitly:

```powershell
.\.venv\Scripts\python.exe SystemCode/src/backend/scripts/query_web_rag_pilot.py `
  --school-id "CENTRE:PT9148" `
  --query "bilingual curriculum" `
  --include-operator
```

Operator results are labelled `OPERATOR LEVEL` and state that the information is not verified for the selected branch. They remain explanation-only and cannot fill a branch evidence field or affect ranking.

## Pilot implementation

The pilot uses an automatically generated review gate at `../../SystemCode/src/backend/resources/web_rag/pilot_allowlist.json`. An entry is fetchable only when:

- `review_status` is `approved`;
- the URL is absolute HTTPS; and
- at least two distinct identifiers are recorded as matched.

The deterministic verifier compares centre code, postal code, address, school/branch name, and operator domain with the fetched page. It automatically approves a centre-code match plus another identifier, a postal-code match plus an address or name match, or a strong name-and-address match on the official domain. Scheme-less catalogue domains are normalised before comparison. A root-level official brand homepage with a moderate name match but no branch location evidence is reclassified as operator-level rather than rejected as an incorrect school page. Name and domain alone on a non-root candidate remain pending; insufficient evidence is rejected. Pending, rejected, and failed entries are never ingested as school evidence.

The fetcher checks `robots.txt`, rejects non-public network addresses, accepts HTML only, limits responses to 2 MB, records redirects and hashes, and spaces repeated requests to the same host.

For policy-allowed pages whose ordinary HTML contains no readable text, `--browser-fallback` optionally renders the page with Playwright Chromium. The fallback is never invoked for a robots denial or another ordinary fetch failure. It validates the final HTTPS destination, removes navigation and interface elements from the rendered DOM, and extracts visible body text. Install the optional runtime with `pip install playwright` followed by `playwright install chromium`.

### Content extraction cleanup

The extractor prefers semantic `<main>` and `<article>` regions when they contain enough content, with a whole-page fallback for older sites. It suppresses scripts, styles, navigation, headers, footers, sidebars, forms, dialogs, cookie and consent banners, menus, social widgets, related-content carousels, testimonials, and reviews. It also removes exact repeated text blocks, common interface labels, and decorative symbol-only blocks before chunking.

The live Star Learners validation decreased from 13 noisy chunks to 4 content-focused chunks (675 words including overlap), with no detected cookie/consent or parent-review text. The Small Wonder operator page produced one 80-word cleaned chunk. Extraction remains deterministic and should still be audited across different website designs before full use.

Run the complete workflow for all inventoried `school_specific_candidate` records from the repository root:

```powershell
$env:PYTHONPATH = "SystemCode/src/backend/pipeline;SystemCode/src/backend"
.\.venv\Scripts\python.exe SystemCode/src/backend/scripts/automate_web_rag_pilot.py
```

That command rebuilds the inventory in memory, verifies all school-specific candidates, processes every unique shared operator page once, writes both decision files, and creates separate school and operator indexes without downloading approved pages twice. Social pages and unavailable records remain in the inventory but are not fetched.

### Incremental processing and resume

The workflow resumes by default from `pilot_allowlist.json`, `operator_page_allowlist.json`, and `web_rag_pilot_index.json`. It:

- skips completed decisions whose candidate URL is unchanged and whose approved page is already indexed;
- retries `fetch_failed` entries on the next run;
- reprocesses a school when its candidate URL changes;
- saves the relevant decision file and index after every attempted page;
- replaces an older page for the same school or operator rather than duplicating it; and
- writes through a temporary file followed by an atomic replacement to protect checkpoints from interruption.

`--limit` and `--shared-limit` count new attempts in the current run, not already completed pages. This makes repeated batches advance through the inventory. Progress is printed for every attempt, followed by attempted, skipped, and indexed totals.

Use `--limit` when a smaller audit batch is desired:

```powershell
.\.venv\Scripts\python.exe SystemCode/src/backend/scripts/automate_web_rag_pilot.py --limit 20
```

`--limit` controls school-specific candidates. Use `--shared-limit` to bound unique shared pages as well:

```powershell
.\.venv\Scripts\python.exe SystemCode/src/backend/scripts/automate_web_rag_pilot.py `
  --limit 20 `
  --shared-limit 10
```

Reprocess one or more specific school decisions without pruning any other checkpoints:

```powershell
.\.venv\Scripts\python.exe SystemCode/src/backend/scripts/automate_web_rag_pilot.py `
  --school-id "CENTRE:PT3460" `
  --school-id "CENTRE:PT8736" `
  --shared-limit 0
```

To intentionally discard checkpoints and rebuild from the beginning, use:

```powershell
.\.venv\Scripts\python.exe SystemCode/src/backend/scripts/automate_web_rag_pilot.py `
  --fresh `
  --limit 20 `
  --shared-limit 10
```

Because `--fresh` replaces the existing decision and index files, use it only when a deliberate rebuild is required.

### Page changes and freshness-based refresh

Approved indexed pages become eligible for refresh after 30 days by default. Change the interval with `--refresh-after-days`, or use `0` to force a check of completed pages within the selected batch:

```powershell
.\.venv\Scripts\python.exe SystemCode/src/backend/scripts/automate_web_rag_pilot.py `
  --limit 20 `
  --shared-limit 10 `
  --refresh-after-days 30
```

On refresh, the workflow re-verifies school identity and compares the final URL and SHA-256 content hash with the indexed version. It records:

| Change status | Meaning |
|---|---|
| `new` | First successful retrieval. |
| `unchanged` | Final URL and content hash are unchanged. |
| `changed` | Page content changed and the new verified chunks replaced the old chunks. |
| `redirected` | The final URL changed; verified content was indexed under the new destination. |
| `identity_changed` | Refreshed content no longer verifies the school; old school evidence was removed. |
| `unavailable` | Refresh failed; last-known evidence was preserved with the error and original retrieval time. |

Indexed pages receive a freshness label based on their last successful retrieval: `current` through 30 days, `aging` from 31 through 90 days, `stale` after 90 days, or `unknown` when no valid timestamp exists. Freshness describes retrieval age, not a guarantee that a claim remains correct.

The command summary reports change and freshness counts. A temporary refresh failure is retried on the next run. It does not silently delete previously verified evidence, but the preserved page carries `change_status: unavailable`, `last_refresh_error`, and its aging or stale label.

### Failure classification and retry policy

Fetch failures carry `failure_code`, `retryable`, `retry_after_seconds`, `attempt_count`, and `next_retry_at`. Temporary failures use exponential backoff up to 30 days, while a server-provided numeric `Retry-After` value supplies the initial delay. A page is retried only after `next_retry_at`; permanent failures are checkpointed and skipped on later runs.

| Failure code | Default policy |
|---|---|
| `robots_disallowed` | Permanent; do not retry automatically. |
| `robots_unavailable` | Retry for temporary policy-file/network/server failures; permanent for non-retryable HTTP responses. |
| `rate_limited` | Retry after `Retry-After`, or after one hour when absent. |
| `timeout` | Retry with backoff. |
| `dns_failure` / `network_error` | Retry with backoff. |
| `server_error` | Retry with backoff. |
| `not_found` | Retry after 30 days in case the page is restored. |
| `access_denied` | Permanent. |
| `invalid_url` / `unsafe_host` / `unsafe_redirect` | Permanent safety failure. |
| `unsupported_content` / `response_too_large` | Permanent for the current ingestion method. |
| `javascript_required` | Permanent for the ordinary HTML fetcher; eligible for a future browser-rendered path. |

Legacy unclassified `fetch_failed` entries default to retryable so existing checkpoints migrate naturally on their next attempt. The command summary groups current failures by code.

The lower-level ingestion command remains available when using an existing allowlist:

```powershell
$env:PYTHONPATH = "SystemCode/src/backend/pipeline;SystemCode/src/backend"
.\.venv\Scripts\python.exe SystemCode/src/backend/scripts/run_web_rag_pilot.py
```

Query evidence for exactly one school:

```powershell
.\.venv\Scripts\python.exe SystemCode/src/backend/scripts/query_web_rag_pilot.py `
  --school-id "CENTRE:PT9148" `
  --query "outdoor learning literature curriculum"
```

Every result includes the final source URL, title, retrieval time, content hash, and school-scoped chunk ID. A query with no evidence returns an explicit empty result; it does not fall back to another school's page.

### Retrieval quality

Retrieval uses deterministic BM25-style scoring within the requested school or explicitly linked operator pages. Before scoring it:

- removes common question and stop words;
- normalises simple singular/plural forms;
- recognises compound terms such as `hands-on` and `activity-based`;
- expands a small controlled synonym catalogue for concepts such as outdoor/garden/playground, curriculum/programme/framework, hands-on/experiential, fees/cost, and bilingual/dual-language;
- gives an additional boost to exact multi-word phrases; and
- rejects results below a minimum relevance threshold instead of returning any token overlap.

High-precision intent gates additionally require concrete evidence for language, outdoor, fee, curriculum, enrichment, and facility questions. For example, an outdoor query does not accept an indoor-only playground, a language query requires a named language or explicit language evidence, and a curriculum query does not accept a generic use of `programme`. Curriculum ranking boosts named methods such as literature-based, activity-based, Montessori, Reggio, inquiry, and play-based approaches over generic certification text. Conversational words such as `kind` and `much` are ignored, and common compounds and fee plurals are normalised.

Results expose BM25 score, relevance, matched query terms, and phrase-match status. The command-line default minimum relevance is `0.25` and can be adjusted for evaluation:

```powershell
.\.venv\Scripts\python.exe SystemCode/src/backend/scripts/query_web_rag_pilot.py `
  --school-id "CENTRE:PT9148" `
  --query "outdoor learning curriculum" `
  --min-relevance 0.35
```

The offline evaluator includes golden checks for exact-phrase ranking, synonym retrieval, and weak-match rejection in addition to isolation and citation checks.

Run the offline isolation and citation evaluation:

```powershell
.\.venv\Scripts\python.exe SystemCode/src/backend/scripts/evaluate_web_rag_pilot.py
```

## Production-readiness audit

Human-reviewed labels live in `../../SystemCode/src/backend/resources/web_rag/production_audit_labels.json`. Identity cases state the expected school/operator decision, while retrieval cases state the school, question, expected evidence scope, expected terms, source domain, and whether evidence should exist.

Run the audit and save a Markdown report:

```powershell
.\.venv\Scripts\python.exe SystemCode/src/backend/scripts/audit_web_rag_readiness.py `
  --output SystemCode/src/backend/output/web_rag_readiness.md
```

The command exits non-zero until every gate passes. Default production gates are:

- at least 50 manually reviewed identity cases;
- at least 30 labelled retrieval cases;
- identity accuracy of at least 95%;
- retrieval accuracy of at least 90%;
- 100% citation completeness;
- 100% evidence-scope accuracy;
- 100% school isolation; and
- at least 95% clean indexed pages under the audit's noise check.

The completed audit contains 57 identity cases and 61 retrieval cases. The cumulative index contains 20 school pages and 7 operator pages. Current failure records include policy refusal, invalid URLs, an unsafe redirect, a server error, and one temporarily unavailable policy file. Every acceptance gate passes: identity accuracy is 100%, retrieval accuracy is 90.16%, and citation completeness, evidence-scope accuracy, and school isolation are all 100%. The generated report therefore records `Production ready: YES` for the audited explanation-only workflow. This status does not authorize webpage evidence to affect deterministic ranking or suitability decisions.

### Human-review CSV workflow

Export the current review packet:

```powershell
.\.venv\Scripts\python.exe SystemCode/src/backend/scripts/review_web_rag_audit.py export
```

This creates:

- `../../SystemCode/src/backend/output/web_rag_review/identity_review.csv`, containing automated decisions, confidence, matched identifiers, failure codes, and blank human decision fields; and
- `../../SystemCode/src/backend/output/web_rag_review/retrieval_review.csv`, containing topic-based candidate questions, retrieved passages, sources, relevance, and blank human expectation fields.

The exporter refuses to overwrite existing CSVs unless `--overwrite` is supplied. Do not use `--overwrite` after review has started.

In `identity_review.csv`, set `include_in_audit` to `yes` and independently classify `human_expected_identity` as `school`, `operator`, `incorrect`, `ambiguous`, or `unverified`. The legacy `human_expected_status` column remains importable for existing packets, but `fetch_failed` maps to `unverified` rather than counting as an identity decision. In `retrieval_review.csv`, mark included rows and complete the human query, scope, evidence-expected decision, expected terms, and source domain. Suggested questions and passages are review aids, not labels; reviewers must verify them against the official page.

Identity accuracy is calculated only for cases where both the reviewer supplied an identity label and the automated workflow reached an identity decision. Fetch failures are reported separately through identity-assessment coverage, fetch-success rate, and failure-code counts. This prevents a correct page blocked by robots policy or JavaScript requirements from being counted as an identity-classification error.

Fetch success is calculated across policy-eligible cases. Explicit `robots_disallowed` cases are reported as `policy_excluded_cases` and omitted from that denominator, since production readiness must not reward bypassing a publisher's policy. All other permanent and temporary failures remain in the fetch-success denominator.

Import completed rows:

```powershell
.\.venv\Scripts\python.exe SystemCode/src/backend/scripts/review_web_rag_audit.py import
```

Import validates statuses, scopes, boolean fields, required school IDs, and positive-case expected terms, then merges cases by stable `case_id` into `production_audit_labels.json`. Rows without `include_in_audit: yes` are ignored.

Positive retrieval cases may list alternative acceptable evidence phrases separated by `|` or commas; a returned passage must contain at least one. Negative cases pass when no evidence is returned and do not require a source URL or expected term.

The current generated packet contains 54 identity rows and 58 retrieval suggestions, enough candidates to meet the 50/30 sample-size gates after independent review. It covers 13 indexed school pages, 7 operator pages, rejections, pending review, permanent failures, and temporary failures.

### Initial automated live pilot

The first automated run checked three candidates. Two Star Learners branch pages were approved from matching postal code, centre name, address, and operator domain, then ingested. A generic Sunshine Kids homepage was rejected because it matched the school name but lacked school-specific location evidence.

The generated index is explanation-only. It is not connected to the scorer, hard constraints, Neo4j query, recommendation ordering, or suitability verdict.

## Chat answer integration

The `/api/preferences` chat endpoint loads `../../SystemCode/src/backend/output/web_rag_pilot_index.json` and recognises factual questions about exactly one selected preschool, for example, “What curriculum does this school use?” It retrieves only chunks belonging to that school and returns:

- a concise set of matching official-page passages;
- structured citations with source URL, title, retrieval date, and chunk ID;
- `evidence_scope: school`; and
- `ranking_affected: false`.

The frontend renders each citation as a source link with its retrieval date. If no index, school page, or relevant passage is available, the answer says the evidence is unavailable; absence is not presented as proof that a feature is absent. Selecting zero or multiple schools prevents retrieval so evidence cannot be mixed across schools.

When `OPENAI_WEB_RAG_ANSWERS_ENABLED=true`, the retrieved school-isolated passages are passed to an LLM for a short parent-friendly answer. Structured output requires `answer`, `evidence_available`, and exact retrieved `citation_ids`. The backend rejects invented or missing citations and falls back to deterministic extraction on validation, timeout, or API failure. The model never receives authority to alter filters, scores, ranking, or suitability.

Evaluate the deterministic answer formatter without API calls:

```powershell
.\.venv\Scripts\python.exe SystemCode/src/backend/scripts/evaluate_web_rag_answers.py `
  --output SystemCode/src/backend/output/web_rag_answer_quality.json
```

Run the same labelled cases through the configured LLM:

```powershell
.\.venv\Scripts\python.exe SystemCode/src/backend/scripts/evaluate_web_rag_answers.py `
  --use-llm `
  --output SystemCode/src/backend/output/web_rag_answer_quality_llm.json
```

The focused four-case smoke labels live in `../../SystemCode/src/backend/resources/web_rag/answer_quality_labels.json`. By default, the evaluator consumes the independently reviewed school-scoped cases in `production_audit_labels.json`; 41 currently apply to indexed school pages. It reports answer accuracy, citation validity, unsupported-claim-free rate, conciseness, school isolation, LLM-grounded rate, and fallback rate.

Production gates require at least 30 cases, answer accuracy of at least 90%, 100% citation validity, 100% school isolation, 100% unsupported-claim-free answers, at least 95% concise answers, and at most 10% LLM fallback. On the expanded 41-case set, the intent-aware deterministic formatter achieves 70.73% answer accuracy. The combined LLM and validated deterministic fallback achieves 90.24% answer accuracy, 100% evidence-availability accuracy, citation validity, isolation, unsupported-claim-free answers, and conciseness, with a 7.32% fallback rate. Every answer-quality gate therefore passes. Three reviewed cases still expose upstream indexed-evidence gaps, so passing the aggregate gates does not remove the need to refresh and improve individual page extraction.

Set `WEB_RAG_INDEX_PATH` to use an index outside the default output location. The index is a generated runtime artifact and must be built or provisioned wherever the backend runs.

## Remaining Phase 9 work

After the initial pilot:

1. review medium-confidence cases and audit a larger batch of automatic decisions;
2. audit extraction quality across different site designs, including JavaScript-rendered pages;
3. add scheduled execution around the implemented freshness-based refresh command;
4. expand retrieval evaluation beyond the initial golden cases to a larger labelled question set;
5. compare LLM-synthesised answer quality against the deterministic formatter on a labelled answer set; and
6. add monitoring for synthesis fallback rate and invalid citation attempts.

No webpage evidence should affect ranking until this evaluation passes.
