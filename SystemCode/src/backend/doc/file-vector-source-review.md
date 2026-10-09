# Parent-guide source review and configuration (step 1)

The review in `SystemCode/data/vectors/parent_guide/sources.json` inventories
all 11 guide sections, 9 Markdown tables and 49 unique HTTPS sources. It records
actual fetch timestamps and response hashes separately from the guide's
editorial `document_checked_on` date. No index has been built; `indexed_at` is
null. The source guide is preserved as supplied.

There are 23 approved source mappings. They are review selections, not generated
chunks: line ranges and hashes pin the reviewed content, while sentence and
table-column selections remove unsupported or editorial claims. Step 2 must
apply those selections, retain qualifications and table headers, and split
mixed-source passages. Only `verified` and `runtime_eligible` mappings belong
in the first corpus. The other source links remain internal metadata.

## Review findings

ECDA's AOP/POP pages confirm the listed fee caps; MOE confirms the 2026 MK and
KCare charges. The official subsidy PDF, updated 6 October 2026, confirms all
seven full-day HHI rows for both childcare and infant care in both policy
periods. ECDA confirms the working-applicant rule and the childcare-only
employment exception; the infant-care qualification must stay with it.
LifeSG confirms the CDA grants and announced SG Child Support Package,
including April 2027 payouts and the September/October co-matching transition.
MOE directly confirms the 23–31 March 2026 exercise for 2027 K1 admission.

The following remain excluded pending verification or a suitable citation:

- Age/cohort and staffing ratio tables, CCTV access claims, childminding and
  vaccination law: linked sources returned 403.
- KiFAS Start-Up Grant amounts/income conditions and the exact announced 2027
  KiFAS income ceiling: SupportGoWhere returned a JavaScript shell. The
  childcare/infant-care PDF does not establish KiFAS policy.
- MK/P1 Phase 2A priority: the linked short URL resolves to an MK online
  registration PDF, not evidence for P1 priority. The P1 overview does not
  establish the claimed 2027 exercise changes for 2028 entry.
- IB descriptions, unverified Reggio details, and general Waldorf claims
  backed only by a single school's practice example.
- Mixed programme descriptions requiring separate primary citations,
  editorial visit/settling/shortlist advice, and derived budgeting examples.
  Numeric estimates remain with deterministic calculations.

Every section has explicit exclusion notes, including section 11, which has no
approved passage initially. A successful HTTP response is recorded as a fetch,
not proof that a claim was verified. Future chunks must use their primary
source's actual `source_verified_at` for public `retrieved_at`; never use the
guide date or invent a URL for the local Markdown.

`GeneralKnowledgeEvidence.evidence_category` now permits `unknown`. The general
tool returns `unknown` if any passage is non-authoritative. Existing curated
passages retain their prior authoritative default. Editorial content is still
excluded from this first corpus.

## Fixed first-version configuration

The project already uses the OpenAI SDK and `OPENAI_API_KEY`. Select the OpenAI
embeddings endpoint with `text-embedding-3-small`, explicitly 1536 dimensions.
Official documentation confirms the model supports embeddings and its default
1536-dimensional output:

- https://developers.openai.com/api/docs/models/text-embedding-3-small
- https://developers.openai.com/api/docs/guides/embeddings

No independently versioned snapshot is established by the model page. Record
the exact returned model identifier in the future build manifest; never assume
that the chat model can supply compatible embeddings. Account access has not
been tested, and no paid embedding request was made.

Add these non-secret settings to the repository-level `.env` when the later
runtime steps are implemented:

```dotenv
GENERAL_KNOWLEDGE_RETRIEVAL_MODE=curated
GENERAL_KNOWLEDGE_VECTOR_PATH=SystemCode/data/vectors/parent_guide
GENERAL_KNOWLEDGE_EMBEDDING_PROVIDER=openai
GENERAL_KNOWLEDGE_EMBEDDING_MODEL=text-embedding-3-small
GENERAL_KNOWLEDGE_EMBEDDING_DIMENSIONS=1536
GENERAL_KNOWLEDGE_TIMEOUT_SECONDS=8
GENERAL_KNOWLEDGE_MAX_QUERY_CHARACTERS=2000
```

`pipeline/general_knowledge_config.py` parses these settings without loading an
index, reading credentials or constructing a provider. Missing/blank/invalid
modes resolve to `curated`. `lexical` and `vector` are reserved explicit opt-ins;
they do not activate any runtime path in step 1. Relative paths resolve against
the repository regardless of worker working directory. Timeout must be finite
and between 1 and 30 seconds; query bounds are 1–2000 characters. Provider,
model and dimensions are fixed for the first version; changing them requires
an intentional configuration change and index rebuild. Error messages omit
configured values. Existing general retrieval remains active until step 5.

The planned vector mode needs provider network/API access for query embeddings
as well as offline document builds. The future lexical/curated fallback needs
no embedding provider. No dependency changes are needed for step 1.

## Verification

All 11 focused configuration, provenance and evidence-tool tests passed.
Required backend discovery ran 310 tests with 307 passing. The two failures
and one error also reproduce in full discovery on an untouched `HEAD` checkout
(305 tests) with the same repository environment and optional LLM feature flags
disabled: combined-evidence routing, invalid LLM-value fallback and incremental
ingestion checkpointing. These existing failures are outside step 1. Both full
runs used the AGENTS.md command with optional live LLM flags disabled and ran
outside the sandbox to allow the in-process FastAPI tests to complete.
