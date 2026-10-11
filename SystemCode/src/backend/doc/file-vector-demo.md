# Parent-guide evaluation and demo (step 6)

Automated retrieval and routing gates now pass on the unchanged labels.
Demo acceptance **remains open** because the full backend suite has an existing
failure and independent human answer adjudication is outstanding.
Keep retrieval opt-in. The checked-in report is
[`output/parent_guide_evaluation.json`](../output/parent_guide_evaluation.json).
The Step 6 follow-up fixes runtime routing, subject constraints and query wording.
Source-review exclusions, labels, provenance and document vectors remain unchanged.

## Labels and evaluation

[`resources/parent_guide_evaluation.json`](../resources/parent_guide_evaluation.json)
contains 34 manually specified synthetic questions with expected mapping IDs,
acceptable answers, required qualifications, intents and capability names. All
23 approved mappings and all 11 sections are represented. Section 11 is an
excluded case, not an answerable passage. Labels were specified from the supplied
guide and reviewed provenance before running this evaluation. Eight formulations
reuse step 4 calibration questions, so this is not an independent holdout set.
These are reviewable manual labels authored during implementation; no independent
human adjudication of generated answers has been performed.

Run from the repository root:

```bash
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python -m SystemCode.src.backend.scripts.evaluate_parent_guide \
  --output /tmp/parent-guide-offline.json

PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python -m SystemCode.src.backend.scripts.evaluate_parent_guide \
  --real-provider --output /tmp/parent-guide-live.json
```

Offline runs make no provider calls. `--real-provider` makes 31 bounded synthetic
question-embedding calls using the configured OpenAI model/key, requiring network
access and incurring API usage. Neither command changes source, CURRENT or builds.
The script disables optional intent/answer providers and loads `.env` without
overriding shell settings. Exit status is 0 only for complete acceptance,
1 for failed/incomplete gates (including outstanding independent review), and 2 for a
setup/report failure. Provider failures remain failed cases with categories;
lexical recovery is never credited as vector success.

Both modes rank the same persisted 23-chunk corpus with shared subject/year
constraints, query normalization and unchanged top-three thresholds. Lexical uses the existing BM25/coverage
helpers without curated fallback. Vector evaluation applies cosine ranking
without lexical fallback. Runtime fallback is separately covered in retrieval
and service tests. The harness checks actual deterministic routing and the
supervisor capability restrictions; registered-tool execution, combined scope,
preference mutation, agent failure and zero non-guidance vector calls are covered
by `test_parent_guide_service.py` and `test_conversation_supervisor.py`.
Deterministic general answers are checked for state preservation, citations and
required qualifications. This is a retrieval and deterministic integration smoke,
not a real model-supervisor answer-quality evaluation.

Results on 9 October 2026, Linux x86_64 demo workspace, active build
`f7ef031d99fe4a12a4f08b9556ef1ed7`, OpenAI `text-embedding-3-small` (1536 dimensions):

| Gate/measurement | Guide lexical (BM25) | Independent vectors |
|---|---:|---:|
| Expected passage in top three | 24/24 (100%) | 24/24 (100%) |
| Unsupported/excluded rejection | 7/7 | 7/7 |
| Reviewed qualifications | Pass | Pass |
| Returned citations match approved URL/timestamp/scope | Pass | Pass |
| Provider failures | 0 | 0 |
| Query latency p50 / p95 | 2.41 / 4.67 ms | 203.05 / 279.76 ms |

All automated retrieval gates pass independently. Actual routing/tool expectations
pass 34/34 cases, and deterministic general-answer qualification, citation and
state checks pass. `automated_evaluation_passed` records this narrower result;
`acceptance_passed` remains false and `independent_answer_review_completed` false.
The evaluator cannot certify separately run backend checks or human review.

Broader ECDA/operator/EYC/SPARK/DS-LS and Primary 1 questions reach guidance;
unrecognized questions/requested content reach clarification without preference
mutation. Selected-centre and explicit preference scopes remain protected.
Primary 1, CCTV and waitlists cannot borrow adjacent guide or curated evidence.
KiFAS and MK submission-priority questions constrain reviewed subjects; query
wording expands eligibility and MOE Kindergarten terminology. Combined questions
retrieve the explicit general explanation separately from the school clause.
No hybrid ranking, threshold reduction, source expansion or rebuild was needed.

The fixed labels remain implementation-authored and overlap earlier calibration;
these gains are tuning results, not independent holdout validation. The report
retains all source-review exclusions. CCTV, waitlists and section 11 remain excluded.

A warm-process validated index load took 8.23 ms, with 1,057,707 peak traced bytes
and 141,312 matrix bytes (141,440 bytes including the `.npy` header on disk).
These are incremental index-load allocations, not total backend RSS. Query p95
excludes neither initial API setup nor outliers; the first vector query took
0.73 seconds. Measurements are from this workspace, not a promise for another
machine. Repeat the live command on the actual presentation machine.

## Run a limited demo

Install backend dependencies and validate the included artifacts in a fresh
process; no vector database provisioning or document embedding call is needed:

```bash
.venv/bin/python -m pip install -r SystemCode/src/backend/requirements.txt
.venv/bin/python -m SystemCode.src.backend.scripts.build_parent_guide_index --validate-only

PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python -m SystemCode.src.backend.scripts.query_parent_guide \
  'How do subsidy thresholds change in 2027?' --mode lexical
```

Use `--mode vector` for hosted question embeddings. Lexical queries use local
artifacts and require no API/network. Prefer passing examples such as Montessori,
2027 subsidy thresholds and the childcare/infant-care work exception for a limited
demo; disclose the incomplete acceptance gates above. CCTV, waitlist and Primary 1 advice remain
excluded. Exact selected-centre fees use structured data, not this corpus.

For backend opt-in, put `GENERAL_KNOWLEDGE_RETRIEVAL_MODE=lexical` or `vector`
in repository `.env`, then restart workers. For a deterministic guidance demo,
also set `CONVERSATION_AGENT_MODE=deterministic` and
`OPENAI_INTENT_CLASSIFICATION_ENABLED=false`. Start normally:

```bash
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/uvicorn SystemCode.src.backend.main:app --host 0.0.0.0 --port 8000
```

The API's other features retain their ordinary catalogue/service requirements.
Vector guidance needs `OPENAI_API_KEY`; the optional model supervisor separately
needs its model provider. `main.py` loads `.env` with `override=True`; edit that
file rather than assuming shell overrides apply. See
[backend integration](file-vector-service.md) for the full configuration.

## Update, build and rollback

Edit the maintained Markdown and review/update `sources.json` together, including
source-fetch timestamps, verified claims, selection hashes and policy dates.
The chunker rejects drift; unverified material stays excluded. Then run the
explicit builder (needs API/network for changed document vectors):

```bash
.venv/bin/python -m SystemCode.src.backend.scripts.build_parent_guide_index
.venv/bin/python -m SystemCode.src.backend.scripts.build_parent_guide_index --validate-only
```

Rerun the fixed evaluation labels and review failures before demonstrating a new
build. Publication is atomic and prior completed builds remain for rollback.
To activate a retained build, supply its actual directory ID below; validation
finishes before CURRENT changes:

```bash
.venv/bin/python - RETAINED_BUILD_ID <<'PY'
import os
from pathlib import Path
import sys
import tempfile
from SystemCode.src.backend.pipeline.general_knowledge_config import DEFAULT_VECTOR_PATH
from SystemCode.src.backend.pipeline.parent_guide_embeddings import EmbeddingSettings
from SystemCode.src.backend.pipeline.general_knowledge_config import get_general_knowledge_config
from SystemCode.src.backend.repositories.parent_guide_index import load_build

root = DEFAULT_VECTOR_PATH
build_id = sys.argv[1]
if Path(build_id).name != build_id or build_id in {'.', '..'}:
    raise ValueError('Supply a retained build directory ID')
load_build(root / 'builds' / build_id,
           expected_embedding=EmbeddingSettings.from_config(get_general_knowledge_config()))
with tempfile.NamedTemporaryFile(mode='w', dir=root, delete=False) as pointer:
    pointer.write(build_id + '\n')
    pointer.flush()
    os.fsync(pointer.fileno())
os.replace(pointer.name, root / 'CURRENT')
PY
```

Restart workers after rollback because each caches its loaded build. Set retrieval
mode back to `curated` in `.env` and restart to return to the original runtime
corpus. See [index construction](file-vector-index.md) for reuse and source review
requirements.

## Verification and remaining work

Deterministic embedding doubles exercise scorer failure handling; semantic recall
claims above come only from the real provider. Existing focused suites cover
persistence/fresh reload, table headers, model mismatches, corrupted artifacts,
timeout fallback, routing, combined evidence and state preservation. The new
suite verifies complete label coverage, independent vector failure accounting,
qualification/citation mutations, capability restrictions and honest failed gates.

Final backend discovery ran 366 tests: 365 passed, with the existing incremental
ingestion checkpoint failure (`second["school_attempts"]` is 1, expected 0).
An untouched `fb5d9bd` archive under identical offline settings reproduced that
sole failure in 363 tests. All 87 focused checks passed; fresh-process artifact
validation and `git diff --check` passed. Full suites ran outside the sandbox
with dotenv loading and the four optional LLM features disabled.

Step 6 acceptance remains open until the full backend gate passes and independent
human answer review is obtained. This follow-up resolves the recorded labelled
retrieval/routing/qualification failures but does not waive either remaining gate.
