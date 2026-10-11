# Offline recommendation evaluation

## Ranking score semantics

Stage 1 keeps its existing weighted match calculation and importance
multipliers. For each supported preference with positive effective weight,
verified matches and mismatches are known evidence. Unknown values earn no
match credit and are omitted from the match-score denominator, matching the
original Stage 1 definition. They remain in the total preference weight used
for completeness. Thus an unknown
required preference is retained where existing policy allows it, but lowers
completeness; a verified required mismatch is excluded before sorting.

`profile_confidence` remains a 0–1 fraction for compatibility and means only
`known effective preference weight / total effective preference weight`.
It does not use source reliability, freshness, or probability calibration.
`combined_score` is the percentage-scale geometric mean
`sqrt(match_score * (100 * profile_confidence))`. Schools sort by combined
score, then match score, completeness, and ascending stable school ID.

Unsupported preferences are stored outside the scored preference map and do
not enter either denominator. Zero-weight preferences also do not enter the
denominators. If there are no applicable positive-weight supported
preferences, match score and completeness are both defined as 100, giving a
neutral combined score of 100. Empty or missing attribute values are unknown;
known false values are mismatches. Pedagogy values remain usable evidence when
present even though the provenance metadata marks that attribute as derived;
source quality is not used as confidence.

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
(old and new orders, a human reference order, and graded relevance),
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

NDCG uses exponential graded gain. Kendall tau-b compares shared candidates;
the metric helper accepts rank/score mappings when ties need to be represented
and returns `null` when fewer than two comparable items or no untied pairs are
available. Human–LLM agreement uses quadratic weighted Cohen's kappa for
ordinal 1–5 ratings; it is not accuracy, and a constant-rating sample returns
`null` because chance agreement cannot be estimated. Confidence error checks
only whether the reported value matches weighted evidence completeness. It is
not factual correctness or probability calibration.

## Ranking-algorithm comparison status

**Unfinished.** The runner compares supplied old/new order fields; it does not
execute either the original match-first scorer or the current combined-score
scorer on shared raw cases. The bundled orders and labels are synthetic and
exist only to test metric arithmetic. Their output is not ranking-performance
evidence, and no conclusion that one ranking is better is supported. A valid
comparison still needs a sufficiently sized, independently labelled dataset
and a runner that executes both algorithms against the same cases and labels.
