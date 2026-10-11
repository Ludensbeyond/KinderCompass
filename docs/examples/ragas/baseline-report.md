# First starter baseline

Baseline `starter-v1.0.0-2026-10-09` is a **12-case smoke check**, not a
comprehensive reliability estimate. It preserves Step 4's real agent execution
and Step 5's actual scores and Codex reviews. A completed evaluation exposes
failures; it does not establish a passing release gate.

## Bundle and provenance

The private archive is stored at
`.local/evaluation-baselines/starter-v1.0.0-2026-10-09.tar.gz`, ignored by Git.
It contains the original run manifest and all 12 captures, exact per-case score
CSV and JSON, case-keyed review decisions, this interpretation, frozen cases and
dataset manifest, and unchanged inputs/results for two judge repeats. Its
`bundle.manifest.json` records every member's SHA-256 and size, per-case review
flags, category summaries and separate agent/fallback metric aggregates.
Archive verification reads members without extracting them.

The capture hash remains
`f7bd6b27b9d5714ffc708abdfdf0de412a324acbde1332bfc8e74066ec38c1e0`.
Dataset version is 1.0.0; the frozen general evidence hash is
`9abf0de536ca0dc11e11455b0a5258a7e848a0ffed7132ab18a7e4ffd5afb6f6`.
The [capture record](dataset-capture-verification.md) preserves the dirty source
revision and exact collector hash used during execution; the later committed
collector has metadata additions. Historical supporting catalogue hashes were
not captured, although these cases use general evidence and no selected schools.
Do not claim that checking out a Git revision alone reproduces that historical
execution or that the private archive is remotely backed up.

Agent: requested `gpt-4o-mini`, observed `gpt-4o-mini-2024-07-18`, timeout
8 seconds and provider-default temperature. Judge: OpenAI `gpt-4o-mini`,
temperature 0, RAGAS 0.2.15 / LangChain OpenAI 0.3.35 / Core 0.3.86.
The model alias does not pin future provider revisions. Agent and judge settings
are distinct and preserved in their respective manifests.

Human review and fresh external-source verification have not been performed.
Codex reviewed frozen references and actual answers; these are interim review
judgments, not calibrated human labels.

## Results by case

Attempted/executed **12/12**; accepted agent **12**; controller fallback **0**;
execution errors **0**. Eight evidence cases have all three finite scores; two
are unscorable because retrieval is empty. Scoring errors **0**, undefined cases
**0**. All ten evidence answers and both behaviour cases have completed reviews.

Require every explicit behaviour check to pass: only `no_selected_school` does.
`request_invented_claim` passes two of three checks, so the behaviour requirement
is **not met**. Eight of ten evidence answers cover all necessary reference facts.
Acceptance is supervisor contract acceptance, not successful routing or a correct,
complete answer. No fallback contribution can conceal these agent failures.

Use provisional flags for faithfulness **<0.90** and precision/recall **<0.80**.
These are local review prompts, not release gates; calibrate them against human
review before adopting gates. Missing/undefined scores and failed explicit
checks always require review. Scores below are the original Step 5 values,
rounded to four decimals; repeats do not replace them.

| Case | Origin | Faithfulness | Precision | Recall | Completeness / behaviour | Review |
|---|---|---:|---:|---:|---|---|
| montessori | Agent | 1.0000 | 1.0000 | 1.0000 | Complete | Unrelated EYDF answer detail |
| play_based | Agent | 1.0000 | 0.8333 | 1.0000 | Complete | Borderline precision; repeated |
| nel_age | Agent | 1.0000 | 1.0000 | 1.0000 | Complete | Unnecessary teaching-tool detail |
| eydf_age | Agent | 1.0000 | 1.0000 | 1.0000 | Complete | Unnecessary NEL detail |
| reggio | Agent | 1.0000 | 1.0000 | 1.0000 | Complete | Unrelated, truncated subsidy answer |
| spark_limits | Agent | 1.0000 | 1.0000 | 0.6667 | Complete | Recall flag; contradicts evidence review |
| outdoor | Agent | 1.0000 | 1.0000 | 1.0000 | Complete | No observed failure |
| quality_teaching | Agent | 1.0000 | 1.0000 | 1.0000 | Complete | No observed failure |
| compare_frameworks | Agent | — | — | — | Incomplete | Correct general tool; empty retrieval |
| compare_pedagogies | Agent | — | — | — | Incomplete | School-comparison tool for general pedagogy |
| no_selected_school | Agent | — | — | — | 3/3 checks pass | Correct clarification; behaviour only |
| request_invented_claim | Agent | — | — | — | 2/3 checks pass | Fails to explain the evidence limit |

## Results by category

Metric means include finite values only. The scored/total column retains
unscorable cases, which never become zeros or disappear from the denominator.
All rows below represent accepted-agent results. The controller-fallback group
has zero cases and no metric means; the bundle maintains its own separate group
for later runs containing fallbacks.

| Category | Cases | Scored | Mean faithfulness | Mean precision | Mean recall | Review result |
|---|---:|---:|---:|---:|---:|---|
| pedagogy | 2 | 2/2 | 1.0000 | 1.0000 | 1.0000 | 2 complete; unrelated answer content |
| learning_benefits | 2 | 2/2 | 1.0000 | 0.9167 | 1.0000 | 2 complete; one borderline precision |
| framework_age | 2 | 2/2 | 1.0000 | 1.0000 | 1.0000 | 2 complete; unnecessary answer detail |
| quality_framework_limits | 1 | 1/1 | 1.0000 | 1.0000 | 0.6667 | Complete; recall review flag |
| quality_teaching | 1 | 1/1 | 1.0000 | 1.0000 | 1.0000 | Complete |
| framework_comparison | 1 | 0/1 | — | — | — | Incomplete; empty retrieval |
| pedagogy_comparison | 1 | 0/1 | — | — | — | Incomplete; wrong tool |
| missing_school_selection | 1 | Behaviour only | — | — | — | All checks pass |
| unsupported_claim | 1 | Behaviour only | — | — | — | Evidence-limit check fails |

Do not interpret high precision as a clean context set. Its ranking calculation
can stay near 1.0 when a useful passage comes first and irrelevant passages
follow. Montessori, Reggio and age answers therefore need composition/relevance
review despite high scores. Faithfulness can be high for irrelevant but supported
claims and does not measure answer completeness.

## Failure interpretation and next improvement

| Affected cases | Classification | Evidence and interpretation | Next action |
|---|---|---|---|
| compare_pedagogies | Routing | Recorded model calls `compare_selected_schools` although the question compares Montessori/Reggio concepts and no school is selected. The tool's school-selection answer is copied. Current offline rule routing recognizes the question as general knowledge, so blaming the rule matcher alone would be unsupported. | Fix the staged/supervisor route or allowed-tool boundary for general concept comparisons; confirm general tool selection with deterministic coverage and the unchanged starter question. |
| compare_frameworks | Retrieval | Recorded general-tool query is the actual EYDF/NEL age question; both retrievals and composer facts are empty despite both framework passages existing in the frozen index. Offline retrieval with the same query and snapshot also returns empty. | Separately improve acronym/topic matching so both passages are returned; rerun the same cases and evidence after that change. |
| request_invented_claim | Retrieval; answer composition | General tool queries whether Montessori guarantees top exam results and gets nothing. Composer repeats the unknown-guidance candidate rather than explaining that available descriptions cannot establish a guarantee. It invents neither a guarantee nor a citation. Offline replay of the tool query also retrieves nothing. | After routing, address topical retrieval and then the evidence-limit response contract as separate changes; require all three checks to pass. |
| montessori, play_based, nel_age, eydf_age, reggio | Answer composition; retrieval distractors | Tool candidate concatenates the first two retrieved passages and composer retains unrelated facts. Reggio appends subsidy text and truncates it. Necessary reference facts are still complete. | Review candidate composition and relevance filtering independently; preserve all model-facing evidence in evaluation captures. |
| spark_limits | Execution/scoring discrepancy; reference-label quality reviewed | Original recall is 2/3, but the captured passage explicitly covers quality-improvement practices and the lack of superiority proof. The reference's opening “No” restates that limit. Codex finds no unsupported reference fact and no missing evidence; the label is retained. Judge decomposition/reasoning was not exported, so the cause of 2/3 is unconfirmed. | Repeat judge scoring; request human review before revising labels or gating on this score. |

There are no provider/tool execution failures, scoring exceptions or undefined
scores in the original baseline or the reviewed repeat results. There is
therefore no undefined case to dismiss or average; future undefined outcomes
must receive explicit review, not be treated as passes. No frozen reference or
production code is changed during baseline establishment.

The **next concrete improvement is routing for general pedagogy comparisons**.
Handle that category first. Rerun the unchanged 12-case dataset with the same
frozen general evidence, agent settings and judge settings, record the new
capture provenance, and compare `compare_pedagogies` tool selection, evidence,
completeness and fallback status. Revisit retrieval only after routing is
verified. Dataset expansion (Step 7) and a reusable comparison workflow (Step 8)
remain pending; no production fix or improved run is claimed by this baseline.

## Judge variation

Treat precision within 0.05 of the provisional 0.80 flag as borderline for this
local review; this definition does not create another release threshold.
`play_based` at 0.8333 is the only borderline original metric. Also repeat the
SPARK recall discrepancy. Two additional paid scoring runs reuse the exact
original answers, ordered contexts and frozen references; they make no new
agent calls. The repeat input/label/review files and all output files are included
in the private archive. Judge/provider, temperature and dependency versions
match the original scorer, verified before bundling.

| Case / metric | Original | Repeat 1 | Repeat 2 | Range / interpretation |
|---|---:|---:|---:|---|
| play_based precision | 0.8333 | 0.8333 | 0.8333 | Stable in these three observations; still near the local flag |
| spark_limits recall | 0.6667 | 1.0000 | 0.6667 | Range 0.3333; crosses 0.80 without any evidence change |

All other metrics for these two cases remained unchanged. Repeat 1 completed
2026-10-09 03:59:54 UTC; repeat 2 completed 04:01:21 UTC. Both scored two of two
cases with no execution errors, scoring errors or undefined results. Twelve
additional metric evaluations returned finite values. The initial sandbox
attempt was interrupted after an independent `ConnectError` connectivity check;
provider-backed repeats succeeded with approved network access.

Three observations do not estimate judge variance reliably. SPARK's score
variation and manual-review disagreement prevent adopting its recall flag as a
release gate. Do not silently replace the original score with the best repeat,
average away an unresolved discrepancy or edit a supported label to improve a
metric. Preserve all observations and obtain human calibration.

## Recreate and verify this bundle

Using the retained local Step 4/5 artifacts and repeat outputs:

```bash
.venv/bin/python docs/examples/ragas/baseline.py \
  --runs /tmp/kindercompass-ragas-step4-live.jsonl \
  --run-manifest /tmp/kindercompass-ragas-step4-live.manifest.json \
  --scores /tmp/kindercompass-ragas-step5-live.csv \
  --score-report /tmp/kindercompass-ragas-step5-live.report.json \
  --reviews /tmp/kindercompass-ragas-step5-reviews.json \
  --notes docs/examples/ragas/baseline-report.md \
  --repeat-dir /tmp/kindercompass-ragas-step6-repeats \
  --output .local/evaluation-baselines/starter-v1.0.0-2026-10-09.tar.gz

.venv/bin/python docs/examples/ragas/baseline.py \
  --verify .local/evaluation-baselines/starter-v1.0.0-2026-10-09.tar.gz
```

Creation refuses to overwrite an existing bundle. This preserves one completed
baseline and verifies its inventory and hashes; it is not Step 8's regression
comparison workflow. The creation command validates frozen case/capture/review
hashes, execution results, score/report agreement, complete reviews and repeated
input/judge consistency before archiving. Synthetic fixtures remain separate.

## Completion verification

The local bundle contains every original capture, manifest, per-case score and
review plus both repeat runs. Its verified category summaries retain all nine
categories, all 12 accepted executions and zero fallback results. One original
metric receives a provisional flag; both empty-evidence cases and the failed
behaviour case remain unresolved and explained. Human calibration is pending.
Seventeen focused offline tests pass, including archive tamper detection, input
mismatch rejection, denominator retention and separate fallback/agent metrics.
Python compilation, original-capture validation and Git whitespace checks pass.
Production backend files and dataset labels are unchanged.

Step 6's completion criteria are met: the first baseline is preserved, every
observed failure is explained with its limits, and the next concrete improvement
is identified. This smoke check cannot estimate broader product reliability.
