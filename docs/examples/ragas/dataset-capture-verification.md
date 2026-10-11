# Starter dataset capture verification

Step 4 completed on 2026-10-08. The command in the [starter guide](README.md#capture-agent-runs)
automatically captures all 12 frozen version 1.0.0 inputs through the existing
staged service and validated conversation supervisor. No judge calls, scores,
behaviour verdicts or baseline are claimed.

## Observed execution

The initial sandbox run retained 12 controller fallback rows with explicit
`OpenAIConnectionError` records. It exited 2 and reported `incomplete`, attempted
12, failed 12. Artifacts remain at
`/tmp/kindercompass-ragas-step4-sandbox.jsonl` and its sibling `.manifest.json`.
No failed case was omitted or counted as a successful agent execution.

After approved network access, one command captured all 12 cases without manual
copying. Artifacts remain outside Git:

- `/tmp/kindercompass-ragas-step4-live.jsonl`
- `/tmp/kindercompass-ragas-step4-live.manifest.json`

| Item | Result |
|---|---|
| Started / finished UTC | 2026-10-08 06:42:29 / 06:43:41 |
| Source revision | `560dab5f1aba2fa3d757c06a28aab756577fed99` plus uncommitted collector |
| Collector SHA-256 at execution | `6124c2fce450c53eeef9bff7becf5f3b717f927b0328154c3ac9bbcc4fec57bf` |
| Capture SHA-256 | `f7bd6b27b9d5714ffc708abdfdf0de412a324acbde1332bfc8e74066ec38c1e0` |
| Dataset version | 1.0.0; frozen cases, input and general evidence hashes verified |
| Requested model / timeout | `gpt-4o-mini` / 8 seconds; provider default temperature |
| Python | 3.12.12 |
| LangChain Core / OpenAI | 1.6.0 / 1.6.0 |
| LangGraph / OpenAI SDK / Pydantic | 1.2.11 / 2.54.0 / 2.13.4 |
| Attempted / executed | 12 / 12 |
| Accepted agent / fallback / execution errors | 12 / 0 / 0 |
| Format validation | 10 RAGAS cases and two behaviour cases |

All input profiles remained unchanged. Evidence exports preserve composer order
and original chunk provenance; all observed passages have general scope.

| Case | Exported contexts | Actual tool |
|---|---:|---|
| montessori | 3 | search_general_knowledge |
| play_based | 3 | search_general_knowledge |
| nel_age | 3 | search_general_knowledge |
| eydf_age | 3 | search_general_knowledge |
| reggio | 3 | search_general_knowledge |
| spark_limits | 1 | search_general_knowledge |
| outdoor | 1 | search_general_knowledge |
| quality_teaching | 1 | search_general_knowledge |
| compare_frameworks | 0 | search_general_knowledge |
| compare_pedagogies | 0 | compare_selected_schools |
| no_selected_school | 0 | search_selected_school_evidence |
| request_invented_claim | 0 | search_general_knowledge |

Empty contexts were preserved. Accepted execution does not imply good routing
or complete answers. In particular the comparison tool choice and missing
comparison evidence need review in Step 5. The collector exports irrelevant
passages too: for example `reggio` received the Reggio passage followed by two
subsidy passages. Final citations are not used to filter model evidence.

After this live run, final metadata-only support was added for catalogue,
location, school-evidence and policy file hashes; those fields will appear on
subsequent captures. The recorded live collector hash identifies the exact
version used above. Duplicate observations of identical retrieved passages now
map to one provenance record without removing duplicate model-facing contexts.
These changes were verified with offline tests, without another paid run.

## Boundary and checks

The runner reads only label-free `inputs.jsonl` into execution. It strictly
rejects extra fields and unsupported history setup. It creates a fresh service,
model and deep-copied profile/selection for every case. The staged runner's
required evaluation expectation fields use unused placeholders, not labels;
that runner supplies only message, profile and setup to the agent. Labelled
cases are read after all executions for format validation.

The recording wrapper delegates model calls unchanged. Every original model
message, tool payload, response and provider error type remains in the private
capture. Ordered `grounding_facts` map to observed original passages with chunk
IDs and citations; an ambiguous or transformed passage fails export explicitly
and retains the partial execution. The capture does not substitute reference
passages or the entire index. School passage records retain school IDs and
citations. A fallback uses the separately observed deterministic composition
boundary, including comparison branches that select directly from the index;
unused controller evidence does not enter an accepted agent capture.

Seven focused tests cover irrelevant evidence/order, school provenance, rejected
labels and setup copying, observed fallback evidence/provider failure, fresh
case state and failure denominator retention, unobserved evidence rejection, and repeated retrieval without lost contexts:

```bash
PYTHONPATH=.:SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python -m unittest discover -s docs/examples/ragas -p 'test_*.py' -v

.venv/bin/python docs/examples/ragas/score.py \
  --runs /tmp/kindercompass-ragas-step4-live.jsonl --validate-only
```

All seven tests, standalone actual-capture validation, Python compilation and Git
whitespace checks pass. Production backend files are unchanged, so no backend
suite rerun was required for this step. The earlier configured-environment suite
failures remain documented in [Step 3 verification](capture-verification.md).

The manifest checkpoints after each flushed row, retains every attempted ID,
and reports incomplete runs with explicit failures. Raised execution exceptions
have a null answer; a genuine controller fallback answer remains its actual
answer and carries both fallback and execution-failure information when the
provider or tool failed. Exception text is not exported. Interrupted runs keep
`status: running` and their partial rows; reruns create a new capture bundle.
