# RAGAS evaluation implementation plan

Build a repeatable evaluation that runs KinderCompass on reviewed questions,
captures its actual answers and evidence, and reports RAGAS scores alongside
explicit agent behaviour checks. Implement one step at a time and meet its
completion criteria before moving on.

## Current starting point

The [starter guide](examples/ragas/README.md) and these files already exist:

- [cases.jsonl](examples/ragas/cases.jsonl): 10 evidence questions and two
  behaviour cases, with snapshot-reviewed reference answers (version 1.0.0).
- [manifest.json](examples/ragas/manifest.json) and [review.md](examples/ragas/review.md):
  frozen dataset hashes, reviewer information and per-case review decisions.
- [inputs.jsonl](examples/ragas/inputs.jsonl): label-free execution inputs.
- [runs.template.jsonl](examples/ragas/runs.template.jsonl): empty capture rows.
- [score.py](examples/ragas/score.py): capture validation and a RAGAS scoring CLI.
- [requirements.txt](examples/ragas/requirements.txt): isolated evaluation
  dependencies using the RAGAS 0.2 API.

Dataset structure, capture validation, isolated dependency installation and
OpenAI judge compatibility have been verified. One synthetic fixture completed
live RAGAS scoring and CSV export. One real `nel_age` capture now verifies the
agent and evidence boundary; full-dataset capture and actual scoring remain
pending. Step 1's Codex review is against the repository
snapshot; human review and fresh external website verification have not been
performed.

The existing [conversation evaluator](../SystemCode/src/backend/scripts/evaluate_conversation_supervisor.py)
already covers routing, tools, citations and state. Its normal reports omit raw
answers and evidence. Add evaluation-only capture separately; retain its
existing checks and privacy-safe reporting.

## Implementation checklist

- [x] Step 1: Review and freeze the starter cases.
- [x] Step 2: Verify the isolated scoring environment.
- [x] Step 3: Capture one real agent turn and its evidence.
- [ ] Step 4: Automate capture for the starter dataset.
- [ ] Step 5: Score the starter set and review behaviour.
- [ ] Step 6: Establish and interpret the first baseline.
- [ ] Step 7: Extend coverage to selected schools and conversations.
- [ ] Step 8: Add a repeatable regression workflow.

## Step 1 — Review and freeze the starter cases

**Work:** Read each question, reference answer and reference passage in
`cases.jsonl`. Confirm the answer is supported by the cited repository snapshot
and contains only facts needed for the question. Fix ambiguous questions and
unnecessary reference details. Review external sources where needed and record
the date of that review. Add dataset version and reviewer information in a
small manifest beside the cases.

For each case, record its category, required setup and intended evidence scope.
The first ten are independent general-knowledge questions with a fresh profile
and no selected schools. The two behaviour cases have explicit checks rather
than RAGAS pass thresholds.

**Complete when:** All 12 cases have reviewed labels, unique IDs and clear
expected behaviour. References remain unavailable to the answering agent.

## Step 2 — Verify the isolated scoring environment

**Work:** Follow the starter guide to install evaluation dependencies in a
separate virtual environment. Check that the pinned RAGAS imports work and run
`pip check`. Select an evaluation judge model available in your account. If
using Azure, adapt the judge client and credential handling to that provider.
Keep judge settings separate from agent settings.

Run `score.py --validate-only` against a clearly labelled temporary format
fixture. Then use one clearly labelled fixture to verify a paid scoring call
and CSV export. The current script expects all cases in its selected dataset;
use a temporary one-case dataset for this smoke test.

**Complete when:** Imports, capture validation and one judge call succeed.
Record Python, RAGAS, LangChain and judge model versions. Fixture scores are
kept separate from actual agent results.

## Step 3 — Capture one real agent turn and its evidence

**Work:** Start with `nel_age`. Run the configured conversation agent using the
existing service and supervisor path. Map the final
`agent_response["question"]` value to the capture's `response` field.

Inspect the tool and answer-composition boundary to capture the ordered evidence
actually supplied to the answering model. The current capability contract has
`grounding_facts`, `answer_candidate` and citations; determine which fields the
composer consumes. Preserve original retrieved passage text and provenance
where available. Record transformed grounding facts separately when they differ
from the original passages, so it is clear what each metric evaluates.

Use an evaluation-only collector or wrapper. Keep raw captures out of public API
responses and ordinary telemetry. Capture all supplied evidence, including
irrelevant material, rather than only cited chunks. Do not use the entire index
or the labelled `reference_contexts` as a substitute for actual retrieval.

Record case ID, actual answer, contexts, chunk IDs/scopes, tool calls and
agent/fallback status. If a fallback produces the final answer, capture the
evidence used by that path and label the result as a fallback. An empty retrieval
must remain empty.

**Complete when:** A manually inspected capture matches one real execution,
including its context order and provenance. Evaluation capture does not change
the returned answer or profile state.

## Step 4 — Automate capture for the starter dataset

**Work:** Add an offline runner that reads the cases, applies setup and writes
one JSONL capture per case. Reuse the existing conversation evaluator's service
wiring where appropriate. Run each independent case with fresh state. Pass only
the question and setup into execution; join reference labels during scoring.

Save run metadata in a manifest: dataset version, Git revision, evidence snapshot
or hashes, model settings, timestamp and dependency versions. Record execution
errors explicitly and retain partial captures. Do not manufacture an answer for
failed runs or silently omit them from the denominator.

Verify the capture boundary with focused tests: irrelevant evidence survives
export, school provenance is preserved, labels do not enter the agent input,
fallbacks are identified and case state does not leak into the next case. Run
the relevant backend checks if backend code changes, following its contributor
guidance.

**Complete when:** One command captures all 12 cases, with failures identifiable
and no manual copying. Successful captures pass `--validate-only`; execution
failures produce a clear incomplete-run report.

## Step 5 — Score the starter set and review behaviour

**Work:** Run the scorer on actual captures using:

- Faithfulness: support for factual claims in the answer.
- Context precision with reference: useful evidence versus irrelevant evidence
  in retrieval order.
- Context recall: support for reference facts in the retrieved evidence.

Handle execution failures, empty answers, empty evidence and undefined scores
explicitly. The starter currently rejects blank answers and writes behaviour
checks for review; extend reporting so invalid runs are visible without treating
them as successful scores. Distinguish scoring failures from agent failures.

For the two behaviour cases, record each check's pass/fail result and a short
reason. Also review whether each evidence answer covers the necessary reference
facts, since these three RAGAS metrics do not directly measure final-answer
completeness.

**Complete when:** Every case has either scores or an explicit reason it could
not be scored, and both behaviour cases have completed reviews. Report counts
for attempted, executed, scored, failed and undefined cases.

## Step 6 — Establish and interpret the first baseline

**Work:** Save the run manifest, captures, per-case scores and review notes as
one baseline bundle. Report results by case and category, alongside agent
acceptance and fallback counts. Label controller fallback results separately
so they cannot conceal agent failures.

Use provisional review flags of faithfulness below 0.90 and precision or recall
below 0.80. Calibrate these against human review before adopting release gates;
they are local starting points. Require explicit behaviour checks to pass and
review every undefined score.

Classify failures as routing, retrieval, answer composition, reference-label
quality or execution/scoring errors. Fix one category at a time and rerun the
same cases with the same evidence and judge settings. Repeat borderline scores
to assess judge variation.

**Complete when:** A baseline report explains each failure and identifies the
next concrete improvement. The small starter set is described as a smoke check,
not a comprehensive reliability estimate.

## Step 7 — Extend coverage to selected schools and conversations

**Work:** Grow to roughly 20–30 reviewed cases using real stable school IDs and
fixed catalogue/evidence snapshots. Add:

| Category | Example | Additional check |
|---|---|---|
| Selected-school evidence | Ask about a centre's published curriculum. | School-specific citations belong to that centre. |
| Unavailable evidence | Ask about transport when evidence is absent. | Missing evidence is not reported as “no transport.” |
| Wrong-school distractor | Supply another centre's relevant-looking passage in a controlled test. | Its claim is not attributed to the selected centre. |
| Combined evidence | Ask what a centre says about play and what play-based learning means. | General and school claims retain distinct provenance. |
| Multi-turn preference | Require Chinese, then explicitly change that preference. | Final structured state reflects the confirmed change. |
| Calculation explanation | Ask why an indicative fee changed. | Numeric result matches deterministic calculation. |

Use existing deterministic checks for exact age, fees, ranking and profile
state. For conversations, replay all setup turns and carry the returned profile
forward; specify which answer turns receive RAGAS scoring. Keep separate dataset
schemas or an explicit adapter for conversation cases.

**Complete when:** The expanded set has reviewed references, reproducible setup
and checks appropriate to each category. Reserve a held-out subset for reporting
after tuning.

## Step 8 — Add a repeatable regression workflow

**Work:** Document a short sequence of commands for capture, validation, scoring
and reporting. Keep format and focused backend checks in routine automated
testing; make provider-backed evaluations an explicit workflow with recorded
judge settings and a known case count.

Add baseline comparison by case ID. Show score changes, behaviour regressions,
fallback changes and unresolved failures. Compare only runs with compatible
dataset, evidence and judge versions; establish a new baseline when those
inputs change. Store generated raw captures outside committed source files
unless they have been deliberately reviewed as shareable fixtures.

**Complete when:** Another contributor can reproduce a run from the documented
commands and judge a change from the comparison report.

## Progress record

Update this table after each completed step. Record failed attempts and their
next action without marking the step complete.

| Step | Status | Evidence / result | Next action |
|---|---|---|---|
| 1 | Complete (2026-10-07) | Version 1.0.0: Codex reviewed all 12 labels against the repository snapshot; unique IDs, explicit setup/category/scope/behaviour, provenance and hashes verified. [Review decisions](examples/ragas/review.md); [manifest](examples/ragas/manifest.json); label-free inputs added. No fresh external or human review claimed. | Proceed to isolated scoring environment verification in step 2. |
| 2 | Complete (2026-10-07) | Isolated Python 3.12.12 / RAGAS 0.2.15 environment: imports and `pip check` pass; one synthetic fixture validated and scored with OpenAI `gpt-4o-mini`, temperature 0; three finite scores and CSV export verified. Initial sandbox network failures resolved with approved access. [Versions and results](examples/ragas/environment-verification.md); dependency lock and smoke command added. No agent capture or baseline claimed. | Proceed to one real `nel_age` capture in step 3. |
| 3 | Complete (2026-10-08) | Real `nel_age` accepted by configured supervisor; three ordered original passages and complete composer tool input captured outside Git. Initial model-error fallback retained with empty evidence; approved live retry succeeded. Replay with/without instrumentation preserves full answer and profile state; one-case format validation passes. [Boundary, provenance and verification](examples/ragas/capture-verification.md); single-turn offline collector added. No scoring or baseline claimed. | Proceed to dataset capture automation in step 4. |
| 4 | Pending | Empty capture template exists. | Build runner after one capture is verified. |
| 5 | Pending | Scoring CLI exists; behaviour review is manual. | Score actual captures and report missing results. |
| 6 | Pending | No measured baseline. | Save and review the first complete run. |
| 7 | Pending | Starter covers general guidance and two behaviours. | Add school and multi-turn cases after baseline. |
| 8 | Pending | No automated regression comparison. | Document workflow and compare compatible runs. |
