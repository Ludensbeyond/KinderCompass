# Offline recommendation evaluation

## Ranking score semantics

Stage 1 keeps its weighted match calculation, importance multipliers, and
geometric-mean combined score. See the [recommendation evidence contract](../doc/recommendation-evidence-contract.md)
for the distinction between direct, inferred, partial, stale, and unknown
evidence. Confirmed required mismatches are excluded; inferred, partial, stale,
and unknown values do not count as confirmed matches or mismatches. Score
calculations and sorting use full precision; returned score fields are rounded
for display. Exact ties use ascending stable school ID.

`profile_confidence` remains in the API for compatibility and is displayed as
evidence completeness. It is not a calibrated probability or factual reliability
measure. The combined score is
`sqrt(match_score * (100 * profile_confidence))`.

Unsupported preferences are stored outside the scored preference map and do
not enter either denominator. Zero-weight preferences also do not enter the
denominators. If there are no applicable positive-weight supported
preferences, match score and completeness are both defined as 100, giving a
neutral combined score of 100. Empty or ambiguous attribute values are unknown;
known false values are mismatches only when the evidence supports the comparison.

Run from the repository root:

```sh
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline python -m SystemCode.src.backend.evaluation.run_recommendation_evaluation
```

Pass `--dataset PATH` to evaluate a different labelled JSON file or `--output
PATH` to write a JSON report. The bundled `synthetic_fixtures.json` contains
invented IDs and labels for reproducibility and metric smoke checks only. It is
not preschool data and provides no evidence about product performance. Keep
real evaluations in a separate, documented dataset with independent labels;
never append human judgements or real school outcomes to the synthetic fixture.

The dataset may provide `hard_constraints` (`candidate_ids`, predicted
`excluded_ids`, and `outcomes` with `pass`, `fail`, or `unknown`), `ranking_cases`
(stable `case_id` and matching `reference_case_id`, a profile, candidate school
records, `reference_ids`, completeness declaration, and graded relevance),
`eligibility_fee_claims` (atomic claim records with `claim_type` set to
`eligibility` or `fee`, plus `verified`, `predicted`, and `expected`),
`explanation_claims`, paired `human` and `llm_judge` ratings, and
`confidence_cases` containing `known_weight`, `total_weight`, and reported
0–1 completeness. Missing hard-constraint labels are unknown. Unknown ground
truth is omitted from precision/recall/F1 and reported separately, including
the proportion retained. Claim accuracy counts only verified claims with usable
values; fee amounts are compared numerically and status labels case-insensitively.
Missing or malformed values are reported as unverified. Grounded-claim rate counts atomic
factual claims only when evidence is available; unavailable evidence is
unverified, not grounded or unsupported. Claims without an explicit support
label are also unverified.

### Ranking metrics and comparison policy

Ranking relevance labels are integers on a four-point scale: **0** not
relevant, **1** marginally relevant, **2** relevant, **3** highly relevant.
Binary metrics use relevance >= 2. Every ranking case must provide a non-empty
`case_id` and an explicit, non-empty `reference_case_id`; the IDs must match.
The runner never substitutes a missing reference ID. Repeated school IDs in a
returned order are deduplicated, preserving the first occurrence; duplicate or
empty reference IDs are invalid.

To establish Recall@3's denominator, declare `reference_ids` as the complete
reference pool, or omit that pool and set `labels_complete: true` to explicitly
declare that the relevance map contains the complete pool. With a declared
pool, Recall@3 is calculated only when every pool ID has a relevance label and
`labels_complete` is not explicitly false. `labels_complete: true` with missing
pool labels, or with a known relevant label outside the declared pool, is
rejected as contradictory. If neither a pool nor a completeness declaration is
provided, Recall@3 is `null` with reason
`reference_completeness_not_declared`; it is not inferred from the supplied
labels. An explicitly empty `reference_ids: []` is reported as an empty
reference pool, distinct from missing reference data. An empty pool has no
Recall@3 score. A non-empty, fully labelled pool with no relevant schools is
also excluded from Recall@3, with a separate reason.

The evaluator computes NDCG@3 with exponential gain `(2^relevance - 1)` and
discount `log2(rank + 1)`. IDCG uses all available graded labels for that same
case. If there are no positive graded labels, IDCG is zero and NDCG is `null`,
with `idcg_zero_no_positive_relevance` and an excluded-case count. Empty or
missing reference labels are separately identified. An unlabelled school in the returned top three makes
NDCG and binary top-three metrics undefined for that case; it is never silently
treated as irrelevant. For fewer than three returned schools, Precision@3's
denominator is the number actually returned. Recall@3 uses all labelled
relevant IDs in the declared reference pool and is excluded when that pool is
incompletely labelled or contains no relevant school. MRR and Hit Rate@3 are
zero for a fully labelled case with no relevant schools. MRR searches the full
returned order (rather than stopping at rank three); an unlabelled result
before the first relevant school makes MRR undefined. Every metric reports its
defined-case denominator and excluded-case count; aggregate values are macro
means of defined per-case scores.

Eligibility violation rate counts recommendations of explicitly ineligible
schools divided by recommendations with known eligibility; unknown and
unlabelled recommendations are counted separately. Hard-constraint violation
rate is the share of confirmed failing candidates that remain in the generated
result; over-exclusion (confirmed pass excluded) is reported separately.
Unknown outcomes have separate counts and are omitted from confirmed rates.

The old order is generated by the frozen `legacy_match_first.py` scorer copied
from `main` at `c86d269`; the new order uses production `rank_schools()`. Both
receive the same profile and school records, then use the same reference labels
for evaluation. The fixture is synthetic and only checks evaluation plumbing;
its scores do not support claims of recommendation quality or improvement.

NDCG uses exponential graded gain. Kendall tau-b compares shared candidates;
the metric helper accepts rank/score mappings when ties need to be represented
and returns `null` when fewer than two comparable items or no untied pairs are
available. Human–LLM agreement uses quadratic weighted Cohen's kappa for
ordinal 1–5 ratings; it is not accuracy, and a constant-rating sample returns
`null` because chance agreement cannot be estimated. Confidence error checks
only whether the reported value matches weighted evidence completeness. It is
not factual correctness or probability calibration.

The quantitative runner and LLM judge remain separate: quantitative ranking
metrics measure ordering against reference labels, while judge scores assess
explanations and other rubric dimensions. They are never combined into a single
quality score. To place an already completed judge report beside the
quantitative results without making model calls, pass `--judge-report PATH` to
the quantitative runner. Judge data is included in its own report section.

A useful quality comparison still needs a sufficiently sized,
independently labelled dataset; the generated comparison on the bundled
synthetic fixture is not performance evidence.

## Opt-in LLM-as-a-Judge evaluation

`llm_judge.py` evaluates supplied recommendation examples and explanations. It
does not participate in production ranking or Stage 2 eligibility. The judge
uses only the case's anonymized preference statement (when supplied),
normalized preference summary, school evidence, ranking, and response. Fixture
descriptions, expected per-case safety behaviors, and human ratings are withheld
from the judge. The case schema has no child identity, dates, income, or postal
code fields. Keep custom evidence and response text free of identifying details
before running a live evaluation.

Each applicable rubric dimension is rated 1–5: **1** means a serious failure,
**2** a major concern, **3** mixed or incomplete, **4** good with minor gaps, and
**5** strong and fully supported. The seven dimensions are preference
alignment, evidence grounding, eligibility safety, explanation quality,
ranking justification, uncertainty handling, and overall usefulness. Ranking
justification may be marked not applicable when no comparison is requested.
Every rating requires a concise evidence-based rationale. Unsupported claims,
critical failure codes, overall assessment, and human-review requirement are
separate structured fields. Critical failures cover required-preference
violations, misrepresented eligibility, unsupported material claims, and
misrepresented unknown evidence; they always require human review.

`judge_cases.json` is schema version 1, dataset version 1.0.0. Its stable case
IDs cover confirmed eligibility, explicit ineligibility, unknown eligibility,
missing family details, unknown school evidence, importance distinctions,
ranking explanations, unsupported claims, and appropriate uncertainty. Every
case is synthetic and unreviewed. There are currently **no human-reviewed
recommendation labels**. The dataset is a workflow and rubric fixture, not
quality ground truth or product-performance evidence. Human labels may be
added only in a separately reviewed dataset with `dataset_kind` set to
`human_reviewed`; the judge never receives those labels. Agreement is reported
as per-dimension quadratic weighted kappa only for actual paired labels, and
repeated model runs count once per case for that comparison.

The evaluator repeats each case twice by default and reports individual
structured results, per-dimension means, repeat rating/critical-failure
agreement, critical failure counts, invalid or failed calls, and human-review
counts. Invalid schemas, missing scores, out-of-range scores, provider errors,
and mismatched case IDs are recorded as invalid runs, never as passing scores.
An incomplete run requires human review. The report labels valid ratings as
preliminary judge evaluation; a judge is not ground truth.

Live model calls are disabled unless both the command-line `--live` flag and
`OPENAI_RECOMMENDATION_JUDGE_ENABLED=true` are supplied. The API key is read
from the existing `OPENAI_API_KEY` environment configuration. The model uses
`OPENAI_RECOMMENDATION_JUDGE_MODEL` when set, otherwise the existing
`OPENAI_EXPLANATION_MODEL` / `gpt-4o-mini`; timeout uses
`OPENAI_RECOMMENDATION_JUDGE_TIMEOUT_SECONDS` (1–30 seconds, defaulting to the
existing explanation timeout or 8 seconds). The provider request uses
structured output and `store=false`.

From the repository root, a live run can be explicitly enabled with:

```sh
OPENAI_RECOMMENDATION_JUDGE_ENABLED=true \
  PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python -m SystemCode.src.backend.scripts.evaluate_recommendation_judge \
  --live --repeats 2 --output /tmp/recommendation-judge-report.json
```

Unit tests inject deterministic mock judges and make no live calls. The
evaluation function accepts the same injectable judge callable for repeatable
offline tests and marks those reports as `judge_mode: injected`. Do not treat an
injected/mock report as model-quality evidence. Safety decisions remain
deterministic in production, regardless of judge ratings or provider
availability.
