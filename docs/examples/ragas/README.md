# A small RAGAS evaluation for KinderCompass

Start with a fixed, manually reviewed set of questions. Run the real agent,
capture the answers and evidence it actually received, then let RAGAS score
those captures. This makes failures easier to understand than starting with a
large automatically generated dataset.

The starter includes 10 evidence questions and two behaviour checks. References
come from the project's curated general-knowledge index, with source IDs and
snapshot dates preserved. Version 1.0.0 is frozen after a Codex review against
that snapshot on 7 October 2026; human review and fresh external website
verification have not been performed. See [manifest.json](manifest.json) for
reviewer information and file hashes, and [review.md](review.md) for per-case
decisions. No school-specific offerings or current fees are invented.

## What to measure

| Metric | What it tells you | Typical failure |
|---|---|---|
| Faithfulness | Are the answer's factual claims supported by retrieved passages? | Invents an outcome or school offering. |
| Context precision with reference | Are useful retrieved passages ranked ahead of irrelevant ones? | Retrieves mostly unrelated material. |
| Context recall | Do the retrieved passages support the facts in the reference answer? | Retrieves NEL but misses EYDF in a comparison. |

These three metrics need an LLM judge but no embedding model. They do not directly
measure how completely the final answer covers the reference. Initially review
that manually; add answer correctness or a suitable rubric later. Answer
relevancy is another option, but its standard implementation also needs
embeddings.

Keep existing deterministic evaluations for exact age, fees, ranking, tool
permissions, citation ownership and preference updates. RAGAS scores cannot
establish those properties. In particular, faithfulness can still be high when
an answer uses evidence from the wrong preschool.

## Capture agent runs

1. Use `inputs.jsonl` for execution. Forward only `user_input` and `setup` to
   the agent; retain `case_id` outside its prompt for capture correlation.
   `cases.jsonl` holds evaluation-only labels: never send references, reference
   contexts, source labels, expected behaviour or checks to the answering agent.
2. Run all 12 independent cases from the repository root with the configured
   agent provider (incurs agent charges; no judge calls):

   ```bash
   PYTHONPATH=.:SystemCode/src/backend:SystemCode/src/backend/pipeline \
     .venv/bin/python docs/examples/ragas/capture_dataset.py --staged \
     --output /tmp/kindercompass-ragas-runs.jsonl
   ```

3. Validate a complete capture without model calls:

   ```bash
   .venv/bin/python docs/examples/ragas/score.py \
     --runs /tmp/kindercompass-ragas-runs.jsonl --validate-only
   ```

The runner uses fresh profile, service and model state for each case, preserves
all ordered model-facing passage texts, and records original provenance and
complete tool payloads separately. It uses the existing staged service and
supervisor path without changing production contracts. References are loaded
only after execution for format validation. The sibling `.manifest.json`
records dataset and evidence hashes, supporting snapshots, source revision and
collector hashes, model settings, dependency versions, timestamps and counts.
Raw outputs must be outside the repository; optional LangSmith export is disabled.

Execution errors retain a JSONL row, partial answer/evidence when available and
an explicit error type. Provider/tool failures with a returned controller answer
remain labelled `fallback` and also count as failed execution. A completed run
with any execution failures exits 2 with `status: incomplete`; interrupted runs
retain flushed rows and a manifest with `status: running`. Inspect that manifest
before scoring. Successful subsets are format-validated automatically. Standalone `--validate-only`
rejects missing rows, null answers and execution-failure fallbacks. Scoring retains
missing, invalid and failed cases as explicit report rows without calling the judge
for them. Do not remove failed cases to claim full-dataset results.

[Dataset capture verification](dataset-capture-verification.md) records Step 4's
execution and focused tests. [capture_one.py](capture_one.py) retains the original
Step 3 `nel_age` wrapper and its [boundary verification](capture-verification.md).

Example capture shape (the response below illustrates the format and is not a
measured agent result):

```json
{
  "case_id": "nel_age",
  "response": "The NEL framework guides preschool education for children aged four to six.",
  "retrieved_contexts": [
    "Singapore's Nurturing Early Learners framework guides preschool education for children aged four to six. It emphasises holistic development, positive relationships, active construction of knowledge, meaningful and authentic learning, quality interactions, and integrated development across learning areas."
  ]
}
```

Write one JSON object per line in the actual capture file. `reference_contexts`
in the labelled dataset are the passages used to write the expected answer;
they must not be substituted for actual retrievals. Missing retrieved evidence
should remain `[]`. Empty or claim-free answers may yield undefined RAGAS
scores; review them separately instead of counting them as passes.

The labelled dataset records `category`, `evidence_scope`, `expected_behaviour`
and `review` for every case. The ten RAGAS cases use general evidence. The
missing-school behaviour case needs no evidence; the invented-claim behaviour
case permits general Montessori evidence. Behaviour cases use their explicit
checks, without RAGAS pass thresholds. Change the dataset version and refresh
manifest hashes when editing questions, setup, labels or the evidence snapshot.

## Run scoring

This example deliberately pins the RAGAS 0.2 API. Use a separate environment
because the production backend uses newer LangChain packages. When upgrading
RAGAS, check its migration documentation before changing the imports.

From the repository root:

```bash
python3.12 -m venv /tmp/kindercompass-ragas-venv
/tmp/kindercompass-ragas-venv/bin/python -m pip install -r docs/examples/ragas/requirements.lock.txt
/tmp/kindercompass-ragas-venv/bin/python -m pip check

# Check capture format without dependencies, credentials or model calls.
python docs/examples/ragas/score.py --runs /tmp/kindercompass-ragas-runs.jsonl --validate-only

# Set OPENAI_API_KEY through your usual secret-management mechanism first.
# Replace YOUR_JUDGE_MODEL with a model available in your evaluation account.
# This command sends captures to the judge and incurs API charges.
/tmp/kindercompass-ragas-venv/bin/python docs/examples/ragas/score.py \
  --runs /tmp/kindercompass-ragas-runs.jsonl \
  --judge-model YOUR_JUDGE_MODEL \
  --output /tmp/kindercompass-ragas.csv
```

The lock file records the verified Python 3.12 environment; `requirements.txt`
retains the intended dependency ranges for future upgrades. See the
[environment verification](environment-verification.md) for tested versions.

Before scoring real captures, verify the scorer with a single synthetic case:

```bash
# Dependency-free format check; writes a clearly labelled temporary fixture.
python docs/examples/ragas/smoke.py --validate-only

# Paid provider check using an explicit judge model and local credentials.
# --env-file is optional when OPENAI_API_KEY is already exported.
/tmp/kindercompass-ragas-venv/bin/python docs/examples/ragas/smoke.py \
  --judge-model gpt-4o-mini --env-file .env
```

The smoke runner reads only `OPENAI_API_KEY` from the optional secret file;
an exported key takes precedence. It creates its own one-case dataset and capture,
validates them, invokes the three scoring metrics and checks that the CSV contains
one fixture row with finite scores between zero and one. Generated files remain
under `/tmp/kindercompass-ragas-fixture/` by default. The fixture uses fictional
content and never calls the KinderCompass agent. Its scores are not a baseline.
Optional LangSmith tracing and RAGAS usage telemetry are disabled for this check.

The scoring example uses an OpenAI judge; configure the wrapper appropriately
if your evaluation account uses Azure or another provider. Judge configuration
is separate from the agent's model configuration.

The CSV includes every dataset case, its outcome/reason and any finite scores.
The sibling `.report.json` retains individual metric failures, undefined outcomes,
counts, judge settings, package versions and input hashes. `.behaviour.json`
contains the explicit behaviour checks and their review status. Empty evidence
is reported as `empty_evidence` without judge calls; empty or invalid answers,
missing captures and execution failures never receive successful scores.
A controller fallback without an execution error can be scored and retains its
`agent_status`; provider/tool failures are excluded even if a fallback answer exists.
Metric exceptions are `scoring_failed`, separately from `execution_failed`.
Non-finite scores become JSON null with `undefined` status, never zero or a pass.
Other metrics for that case still run and their results are retained. Exit 2
means failed/unscorable or undefined cases were reported; it does not discard exports.

Counts mean: `attempted` is captured IDs (including failed executions), `executed`
is nonempty returned answers without execution errors, `scored` is evidence cases
with all three finite scores, `failed` includes missing/invalid captures, execution
errors, empty evidence and judge errors, and `undefined` counts cases with at least
one non-finite metric. A case can be both failed and undefined if different metrics
have different outcomes. Behaviour cases are counted separately as reviewed;
review failure is a recorded verdict and is not a judge execution error.

Supply `--env-file .env` to read only the judge's `OPENAI_API_KEY` when it is not
already exported. Optional LangSmith tracing and RAGAS telemetry are disabled.
Supply `--reviews /tmp/reviews.json` to join explicit reviews by case ID:

```json
{
  "nel_age": {"pass": true, "reason": "States four to six."},
  "no_selected_school": {
    "checks": [
      {"check": "Requests a school selection or clarification.", "pass": true,
       "reason": "Requests one school in the Results panel."},
      {"check": "Does not claim that an unidentified preschool offers Montessori.",
       "pass": true, "reason": "Makes no school offering claim."},
      {"check": "Does not turn general Montessori evidence into a school-specific citation.",
       "pass": true, "reason": "No citations are returned."}
    ]
  }
}
```

Evidence-case reviews evaluate coverage of all necessary reference facts;
behaviour reviews must cover each frozen check in order with a boolean verdict
and a nonempty reason. Omitted reviews remain pending. Reviewer/date metadata
may also be recorded. These are Codex or human reviews, not metric-generated
verdicts. [Step 5 verification](scoring-verification.md) records actual scores,
answer completeness and both completed behaviour reviews. The [first baseline report](baseline-report.md) preserves the local bundle,
category results, provisional flags, failure interpretation and repeated judge
observations. The bundle CLI checks input integrity and separates controller
fallback metrics from accepted-agent metrics; private bundles remain ignored by Git.
Human calibration is pending; these 12 cases remain a smoke check.

## Expanded school and conversation coverage

Step 7 adds a separate [24-case dataset](expanded/manifest.json), preserving the
frozen starter and baseline. It covers selected-school evidence, missing
webpage evidence, a controlled wrong-school passage, combined evidence,
confirmed preference changes and a deterministic fee explanation. See the
[review and replay contract](expanded/review.md) and
[verification and capture command](coverage-verification.md). Twenty cases are
for tuning; four are held out for reporting after tuning. Only the final answer
turn is scored, and exact state, arithmetic and ownership checks remain separate
from RAGAS. No expanded provider-backed results are claimed.

## Repeatable regression workflow

Use the [regression workflow](regression-workflow.md) for the complete capture,
validation, review, scoring, bundle and comparison commands. `make eval-check`
runs offline format and focused regression checks without provider calls.
[Step 8 verification](regression-verification.md) records compatibility rules,
29 passing tests and the historical baseline's missing snapshot metadata.

## Make the small set effective

Use these 12 cases as a smoke check, then grow to around 20–30 reviewed cases:
add real selected-school questions, unavailable evidence, wrong-school
distractors, and short conversations that change an earlier preference.
Keep school IDs and context snapshots fixed. For multi-turn tests, preserve
the conversation setup and validate final structured state with the existing
conversation evaluator; an isolated last message loses the relevant context.

Start with provisional review flags such as faithfulness below 0.90 and context
precision or recall below 0.80. These are local starting points, not RAGAS
standards or validated release thresholds. Review every failure and every
undefined score; revise reference answers that require unnecessary details.
Require all explicit behaviour checks to pass. Compare changes using the same
cases, evidence snapshot, judge model and metric versions. Repeat borderline
scores because LLM judges can vary even at temperature zero.

After the manual set is reliable, generate additional questions from your
approved documents using RAGAS test-set generation and review them before
adding them to the regression set. Keep a separate held-out set for reporting
results after tuning.

References: [RAGAS 0.2 metric documentation](https://docs.ragas.io/en/v0.2.15/concepts/metrics/available_metrics/),
[evaluation datasets](https://docs.ragas.io/en/v0.2.15/concepts/components/eval_dataset/).
