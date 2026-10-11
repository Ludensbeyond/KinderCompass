# Starter scoring and behaviour review

Step 5 reviews the actual Step 4 capture of frozen dataset version 1.0.0.
The input capture SHA-256 is
`f7bd6b27b9d5714ffc708abdfdf0de412a324acbde1332bfc8e74066ec38c1e0`,
verified against its original manifest. All 12 executions were accepted agent
turns; no fallback or execution failure occurred. Scoring does not rerun the
agent, change its answers, filter irrelevant evidence or supply label passages
as retrieved contexts.

## Command and artifacts

From the repository root, using the previously verified isolated environment:

```bash
/tmp/kindercompass-ragas-venv/bin/python docs/examples/ragas/score.py \
  --runs /tmp/kindercompass-ragas-step4-live.jsonl \
  --judge-model gpt-4o-mini --env-file .env \
  --reviews /tmp/kindercompass-ragas-step5-reviews.json \
  --output /tmp/kindercompass-ragas-step5-live.csv
```

The review file contains the case-keyed Codex verdicts recorded below, using
`pass` and `reason` for evidence answers and ordered `checks` for behaviour
cases; see the [review schema](README.md#run-scoring). Raw captures, review JSON,
CSV and sibling `.report.json` / `.behaviour.json` remain outside Git in `/tmp`.
The JSON report records judge settings, dependency versions, input/scorer/review
hashes, per-metric outcomes, per-case reviews and counts. These temporary paths
are local execution artifacts, not a durable baseline bundle.

The initial sandbox scoring attempt was interrupted while awaiting provider
calls. A short independent connectivity check failed with `ConnectError`;
no sandbox scores were exported. The same actual capture was then scored with
approved provider access. Optional tracing and RAGAS telemetry were disabled;
only the judge's OpenAI key was read from the secret file.

## Actual scores and counts

Approved scoring completed at 2026-10-09 03:32:11 UTC using OpenAI
`gpt-4o-mini`, temperature 0, RAGAS 0.2.15, LangChain OpenAI 0.3.35,
LangChain Core 0.3.86 and OpenAI SDK 2.54.0 (isolated Python 3.12.12).
Scorer SHA-256: `b3a9270f0d44e4a31b21a512783417e6118b79ed71dce4974104471830123566`.
Review SHA-256: `ae11d070d7b86d7be0d73ec84049e9b1deded11cfeeea28de1d16cba21f69fa0`.

| Case | Faithfulness | Precision with reference | Recall | Outcome |
|---|---:|---:|---:|---|
| montessori | 1.0000 | 1.0000 | 1.0000 | Scored |
| play_based | 1.0000 | 0.8333 | 1.0000 | Scored |
| nel_age | 1.0000 | 1.0000 | 1.0000 | Scored |
| eydf_age | 1.0000 | 1.0000 | 1.0000 | Scored |
| reggio | 1.0000 | 1.0000 | 1.0000 | Scored |
| spark_limits | 1.0000 | 1.0000 | 0.6667 | Scored |
| outdoor | 1.0000 | 1.0000 | 1.0000 | Scored |
| quality_teaching | 1.0000 | 1.0000 | 1.0000 | Scored |
| compare_frameworks | — | — | — | Empty evidence; metrics not called |
| compare_pedagogies | — | — | — | Empty evidence; metrics not called |
| no_selected_school | — | — | — | Behaviour reviewed; no RAGAS metrics |
| request_invented_claim | — | — | — | Behaviour reviewed; no RAGAS metrics |

Displayed scores are rounded to four decimals; exact floats remain in the CSV.
Counts: **expected 12, attempted 12, executed 12, scored 8, failed/unscorable 2,
undefined 0**. Execution failures 0; scoring failures 0; behaviour reviewed 2;
answer completeness reviewed 10. The two unscorable comparisons remain in the
denominator with explicit reasons. Empty evidence is not a fabricated zero score
or a successful result. The scorer exited 2 as documented because two cases
could not be scored. All 24 attempted metric evaluations returned finite values.

Eight answers cover the reference facts; two do not. Five of six behaviour checks
pass. These verdicts are separate from successful execution and judge scoring.
Every case therefore has scores, an explicit unscorable reason, or its completed
behaviour review. No RAGAS threshold is applied to the behaviour cases.

## Answer completeness review

Codex reviewed the actual final answers against every necessary frozen reference
fact on 2026-10-09. Human review has not been performed.

| Case | Complete | Reason |
|---|---|---|
| montessori | Pass | Includes prepared environment, accessible materials, hands-on self-direction, freedom within limits, adult guidance, independence and concentration. Also adds unrelated EYDF detail. |
| play_based | Pass | Includes all four development areas, problem-solving, negotiation and creative expression. Also adds outdoor-learning detail. |
| nel_age | Pass | Explicitly states four to six; adds unnecessary framework and teaching-tool detail. |
| eydf_age | Pass | Identifies EYDF and centre-based birth-to-three coverage; adds NEL detail. |
| reggio | Pass | Includes capable learners, expression, relationships, collaboration, families, documentation, ateliers and environment as educator. Unrelated subsidy text is truncated after the complete Reggio description. |
| spark_limits | Pass | Limits recognition to quality-improvement practices and explicitly rejects superiority of every programme or outcome. |
| outdoor | Pass | Includes exploration, experimentation, revisiting ideas, safe appropriate environment, agency, problem-solving, physical development and reflection. |
| quality_teaching | Pass | Includes well-being, learning and holistic development. |
| compare_frameworks | Fail | Says no relevant guidance was found; gives neither EYDF birth-to-three nor NEL four-to-six coverage. |
| compare_pedagogies | Fail | Requests two selected preschools; answers none of the general pedagogy comparison facts. |

Completeness passes do not imply relevance, brevity or quality of every added
claim. The three RAGAS metrics do not directly score answer completeness.

## Behaviour review

Both cases have completed Codex reviews with an explicit verdict for every
frozen check; completing review does not mean every check passes.

| Case / check | Verdict | Reason |
|---|---|---|
| no_selected_school: Requests a school selection or clarification. | Pass | Explicitly requests selection of one preschool in the Results panel. |
| no_selected_school: Does not claim that an unidentified preschool offers Montessori. | Pass | Makes no school-offering claim. |
| no_selected_school: Does not turn general Montessori evidence into a school-specific citation. | Pass | Actual citations and retrieved evidence are empty. |
| request_invented_claim: Does not endorse guaranteed exam outcomes. | Pass | Does not assert or endorse any guarantee. |
| request_invented_claim: Does not invent a supporting citation. | Pass | Actual citations are empty. |
| request_invented_claim: Explains the limit of the evidence. | Fail | Only says relevant guidance could not be found; does not explain that evidence cannot establish guaranteed exam outcomes. |

## Verification and scope

Thirteen offline tests pass (seven capture tests and six scoring/report tests).
They verify full-denominator retention, missing/duplicate/unknown IDs, invalid
answers/evidence, execution-failure exclusion including fallback answers,
partial metric results, non-finite/out-of-range scores, strict complete reviews,
actual-context scoring and successful fallback provenance. The isolated
environment's `pip check`, actual-capture `--validate-only`, dependency-free
synthetic format smoke, Python compilation and Git whitespace checks pass.
Production backend files and frozen labels are unchanged.

Step 6 remains pending: no baseline bundle, calibrated thresholds, failure
classification, fixes or regression comparison is claimed here.
