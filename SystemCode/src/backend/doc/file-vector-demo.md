# Parent-guide evaluation and demo (step 6)

The evaluation is implemented, but demo acceptance **fails** on the broader set.
Keep retrieval opt-in. The checked-in report is
[`output/parent_guide_evaluation.json`](../output/parent_guide_evaluation.json).
This step changes evaluation and documentation; it does not tune retrieval,
change routing, expand provenance, or rebuild document vectors.

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
overriding shell settings. Exit status is 0 for all acceptance gates passing,
1 for failed/incomplete gates (including offline-only evaluation), and 2 for a
setup/report failure. Provider failures remain failed cases with categories;
lexical recovery is never credited as vector success.

Both modes rank the same persisted 23-chunk corpus with the existing topic/year
constraints and top-three thresholds. Lexical uses the existing BM25/coverage
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
| Expected passage in top three | 22/24 (91.7%) | 22/24 (91.7%) |
| Unsupported/excluded rejection | 7/7 | 6/7 |
| Reviewed qualifications | Fail | Fail |
| Returned citations match approved URL/timestamp/scope | Pass | Pass |
| Provider failures | 0 | 0 |
| Query latency p50 / p95 | 2.46 / 4.29 ms | 229.44 / 411.29 ms |

The 90% retrieval gate passes independently, but the mandatory qualification and
unsupported-evidence gates fail. No hybrid is introduced on these results.
Actual routing/tool expectations pass 24/34 cases. Five answerable questions
(ECDA services, Anchor Operators, EYC partnership, SPARK and DS-LS), the excluded
Primary 1 question and four unrelated questions route to preferences. The
structured-fee, budget-update and school-Montessori cases select the expected
capabilities; combined routing correctly permits both evidence tools.

Lexical misses KiFAS eligibility (returns KCare guidance) and the full combined
question (returns nothing). Its KiFAS deterministic answer consequently loses
the private-kindergarten/co-payment qualification. Vectors miss Anchor Operators
and MK submission-order priority; the latter returns registration dates without
the admission qualification. Vectors also return MK admissions/partnership
passages for the excluded Primary 1 guarantee question. These related passages
must not be treated as support for a Primary 1 admission guarantee. All four
unrelated questions are rejected by standalone retrieval in both modes. The
report lists individual failures and all section exclusions.

A warm-process validated index load took 8.63 ms, with 1,057,707 peak traced bytes
and 141,312 matrix bytes (141,440 bytes including the `.npy` header on disk).
These are incremental index-load allocations, not total backend RSS. Query p95
excludes neither initial API setup nor outliers; the first vector query took
0.92 seconds. Measurements are from this workspace, not a promise for another
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
demo; disclose the failures above. CCTV, waitlist and Primary 1 advice remain
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

Final backend discovery ran 363 tests: 362 passed, with the existing incremental
ingestion checkpoint failure. An untouched `51271e3` archive reproduced the same
sole failure in 358 tests. All 84 focused checks passed; fresh-process artifact
validation passed.

Step 6 acceptance remains open: fix the recorded routing, qualification and
unsupported-evidence failures in a separately scoped implementation; obtain
independent human answer review and repeat the same gates. The current report
must not be presented as passing comprehensive end-to-end demo acceptance.
