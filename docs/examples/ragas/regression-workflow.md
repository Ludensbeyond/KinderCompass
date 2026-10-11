# Repeatable evaluation regression workflow

Run from the repository root. Offline checks need the configured backend `.venv`
and no credentials. Capture uses the configured agent provider; scoring sends
answers/evidence to the OpenAI judge and incurs separate judge charges. Neither
provider operation is part of routine automated tests.

## Routine checks

```bash
make eval-check
```

This runs capture-boundary, failure reporting, frozen-label/snapshot, conversation
state/fee/provenance, bundle integrity and regression comparison tests, followed
by a synthetic format-only smoke check. No real captures or synthetic scores are
committed. If production backend code changes, also run its required suite:

```bash
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python -m unittest discover -s SystemCode/src/backend/tests -v
```

## Explicit provider run

The following example selects **20 tuning cases** from dataset 2.0.0 (13 evidence,
seven behaviour). Use a fresh private output directory per run. For held-out
reporting after tuning, change `tuning` to `held_out` in both selection commands:
that split contains **four cases** (three evidence, one behaviour). Capture reads
label-free inputs directly; the exported labels are only for scoring and review.

Install the isolated judge environment once using the lock file:

```bash
python3.12 -m venv /tmp/kindercompass-ragas-venv
/tmp/kindercompass-ragas-venv/bin/python -m pip install -r docs/examples/ragas/requirements.lock.txt
/tmp/kindercompass-ragas-venv/bin/python -m pip check
```

Capture and validate, using backend provider credentials from the root `.env`:

```bash
mkdir -p /tmp/kindercompass-ragas-candidate
.venv/bin/python docs/examples/ragas/select_cases.py \
  --dataset-dir docs/examples/ragas/expanded --split tuning \
  --output /tmp/kindercompass-ragas-candidate/cases.jsonl
PYTHONPATH=.:SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python docs/examples/ragas/capture_dataset.py --staged \
  --dataset-dir docs/examples/ragas/expanded --split tuning \
  --output /tmp/kindercompass-ragas-candidate/runs.jsonl
.venv/bin/python docs/examples/ragas/score.py \
  --cases /tmp/kindercompass-ragas-candidate/cases.jsonl \
  --runs /tmp/kindercompass-ragas-candidate/runs.jsonl --validate-only
```

Inspect `runs.manifest.json`: expected IDs and attempted count must both be 20.
Exit 2 from capture/validation means incomplete execution. Retain all rows and
continue with failure-aware scoring/reporting rather than dropping failed cases.
A manifest still marked `running` means an interrupted capture; rerun in a new
directory to obtain a complete denominator before bundling.

Read each actual answer, original evidence/provenance and `coverage_checks`.
Write `/tmp/kindercompass-ragas-candidate/reviews.json` with the explicit
case-keyed format in the [starter guide](README.md#run-scoring): completeness
pass/fail with a reason for each valid evidence answer; every frozen check in
order with pass/fail and a reason for each valid behaviour answer. Leave failed
executions unreviewed. Record reviewer/date and failure classification/next
action in `/tmp/kindercompass-ragas-candidate/notes.md`. Do not copy previous
verdicts without reviewing the new answer. Exact state/fee/ownership checks do
not replace semantic review.

Score with the pinned judge setting **OpenAI `gpt-4o-mini`, temperature 0**:

```bash
/tmp/kindercompass-ragas-venv/bin/python docs/examples/ragas/score.py \
  --cases /tmp/kindercompass-ragas-candidate/cases.jsonl \
  --runs /tmp/kindercompass-ragas-candidate/runs.jsonl \
  --reviews /tmp/kindercompass-ragas-candidate/reviews.json \
  --judge-model gpt-4o-mini --env-file .env \
  --output /tmp/kindercompass-ragas-candidate/scores.csv
```

Judge credentials are read separately from agent configuration. Exit 2 retains
all exports and means failed, unscorable or undefined cases need investigation.
The report records judge configuration, scoring dependency versions and scorer
hash. Capture records agent settings, Git revision, evidence and supporting
snapshot hashes. Empty evidence stays empty; undefined scores stay null.

Freeze the reviewed candidate (including explicit failed execution rows):

```bash
.venv/bin/python docs/examples/ragas/baseline.py \
  --cases /tmp/kindercompass-ragas-candidate/cases.jsonl \
  --dataset-manifest docs/examples/ragas/expanded/manifest.json \
  --runs /tmp/kindercompass-ragas-candidate/runs.jsonl \
  --run-manifest /tmp/kindercompass-ragas-candidate/runs.manifest.json \
  --scores /tmp/kindercompass-ragas-candidate/scores.csv \
  --score-report /tmp/kindercompass-ragas-candidate/scores.report.json \
  --reviews /tmp/kindercompass-ragas-candidate/reviews.json \
  --notes /tmp/kindercompass-ragas-candidate/notes.md \
  --output /tmp/kindercompass-ragas-candidate/candidate.tar.gz
```

For the first run, retain this as the new baseline outside Git. For subsequent
runs, compare with the previous reviewed bundle:

```bash
.venv/bin/python docs/examples/ragas/compare.py \
  --baseline /tmp/kindercompass-ragas-baseline/baseline.tar.gz \
  --candidate /tmp/kindercompass-ragas-candidate/candidate.tar.gz \
  --output /tmp/kindercompass-ragas-candidate/comparison.json
```

Read `comparison.md` for per-ID metric deltas, pass-to-fail or pending review
regressions, fallback changes and unresolved failures; JSON retains before/after
metric outcomes, review reasons, counts, agent settings and Git revisions.
Negative deltas need interpretation and repeats when borderline. Deltas are null
when a metric is missing/nonfinite or answer origin changes, so fallback scores
cannot conceal agent failures. Review both old and new failure outcomes in JSON.
A successful comparison command means compatible inputs and a generated report,
not a release pass. Flags below 0.90 faithfulness or 0.80 precision/recall remain
provisional; human calibration is pending.

## Compatibility and artifact policy

Comparison verifies archive hashes without extraction. It requires matching
frozen dataset identity/version/file hashes, case ID set, split, execution
schema, general and supporting evidence snapshot hashes, judge settings,
scoring package versions and scorer hash. Snapshot paths can differ between
checkouts; basename and hash must agree. Agent model settings and Git revision
may differ and are reported as the change being evaluated.

Changed labels, setup, evidence, judge or scoring implementation require a new
reviewed baseline; incompatible comparison exits 2 and writes no comparison.
Unknown metadata also requires a new baseline. The original Step 6 starter
bundle predates supporting-snapshot recording, so it remains a historical result
and cannot establish compatibility for a new regression run. Recapture the
starter with current tooling if it is needed: omit the split, use the starter
dataset directory and its existing cases file (12 cases: ten evidence, two
behaviour). The expanded dataset has no measured provider baseline yet.

Keep raw captures, behaviour exports, reviews and bundles under `/tmp`, or
reviewed private bundles in the ignored `.local/evaluation-baselines/` directory.
Capture rejects output paths inside the repository. Deliberately shareable
fixtures must be individually reviewed before committing. The committed tests
create fictional answers/scores in temporary directories and make no provider
calls. Preserve the 20/4 tuning/held-out boundary; do not tune on held-out results.
