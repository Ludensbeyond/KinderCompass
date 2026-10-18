# KinderCompass recommendation benchmark datasets

The two populated files in this directory are **synthetic scenario fixtures**, not
manually labelled product-quality benchmarks. Every candidate, profile scenario,
relevance grade, and hard-constraint outcome is invented for deterministic smoke
testing. Their reports must remain `illustrative_only`; they are not evidence of
real preschool facts or recommendation quality. No sources, verification dates,
reviewer identities, human ratings, factual claim labels, or independent ranking
labels are asserted.

- `development.json`: 30 synthetic development scenarios.
- `held_out_test.json`: 20 distinct synthetic held-out scenarios.

Both are validated with the same structural validator as manual benchmark files,
but the synthetic mode requires conspicuous synthetic markers and forbids
provenance or factual/human labels. The two splits have unique case IDs and share
the benchmark ID. Use the held-out split only as a fixture split; it is not a
statistically meaningful product test set.

## Synthetic relevance rubric

The grades are explicit, illustrative labels assigned from each hand-authored
scenario matrix before running the production ranker:

- **0**: no meaningful fit to either preference dimension, or explicit conflict
  with the primary dimension.
- **1**: limited fit to one preference dimension.
- **2**: fit to the primary stated preference dimension.
- **3**: fit to both stated preference dimensions.

These grades are not human judgements and do not claim independent validation.
The benchmark intentionally contains no `reference_order`, because the system's
own order must not be presented as independent ground truth. Cases with unknown
relevance are left unlabeled and declare an incomplete pool instead of treating
unknown as grade zero.

`hard_constraint_outcomes` in these synthetic cases encode the intended
pass/fail/unknown result for required, directly supported Stage 1 preferences:
a confirmed mismatch is `fail`, a confirmed match is `pass`, and absent or stale
usable evidence is `unknown`. The production Stage 1 ranker's generated order is
then checked against those scenario outcomes. All such reports remain
illustrative, not evidence that independent reviewers verified the labels.

## Scenario coverage and evaluator limits

Case `scenario_tags` identify input themes: supported required preferences,
conflicting required language preferences, missing and simulated stale evidence,
no Stage 1 results, distance context, budget context, programme context, and
varied relevance grades. Stale `last_updated` values are simulation inputs only,
not factual verification dates.

The offline evaluator calls the legacy and current Stage 1 rankers on each case's
provided profile and candidates. It does **not** run Neo4j query hard filters,
postal-code geocoding or `filter_within_radius`, Stage 2 age/programme/budget
eligibility, or fee policy calculations. Distance, budget, and Stage 2 programme
fields are scenario context only and do not receive expected eligibility or fee
labels. Zero-results cases exercise Stage 1 required-preference enforcement; they
do not assert that Stage 2 found no eligible schools. A separately labelled,
source-verified benchmark and a Stage 2-capable evaluator are needed to measure
those behaviours.

## Preparing a separate manual benchmark

Do not convert these fixtures into real-world evaluation evidence. A future
manual benchmark must use independently collected cases and labels, with source
references, verification dates, and reviewer provenance for every factual
reference label. Keep development and held-out test cases separate. The strict
manual dataset kind remains `manual_label_benchmark`; its validation requirements
are described below. The validator checks structure and provenance presence only;
it cannot establish that a source is authoritative or that a reviewer actually
performed the stated verification.

## Generating a versioned scenario split from real school records

`SystemCode/src/backend/scripts/generate_recommendation_benchmark.py` is a
separate, opt-in scenario generator. It performs a read-only query against
Neo4j `Preschool` nodes using the existing `stage1.kg_client`, joins those
records by stable `school_id` to `data/processed/kindercompass_master.json` for
the detailed service menu used by Stage 2, and freezes the school records used
by each case. Neo4j-owned values take precedence, including explicit nulls.
Each artifact records the model, prompt version, seed, catalogue version, and a
SHA-256 snapshot fingerprint.

The LLM proposes synthetic family details, supported preference choices,
candidate IDs from the supplied snapshot, and a short scenario description.
Schema validation rejects unsupported preferences, malformed family values,
duplicate candidates, and IDs absent from the snapshot. The model is not asked
for recommendations, relevance judgements, or expected labels. The generator
uses production `EvaluationService.evaluate()` over frozen candidate records
to calculate ranking and Stage 2 eligibility/fee outputs. Direct required
care-level and language outcomes are labelled as code-derived; missing facts
remain `unknown`. Relevance remains empty for separate human review.
Family age, citizenship, household income, and programme inputs are validated
against `FamilyDetails`; distance is omitted because production distance search
also requires a six-digit home postal code and OneMap geocoding, which this
generator does not freeze or replay.

This workflow does not replay the per-case Stage 1 Neo4j retrieval query. The
LLM proposes candidate IDs from the frozen snapshot, and the report marks
`candidate_retrieval.status` as `not_executed`. It exercises production ranking
and Stage 2 calculations over that fixed subset; it cannot measure retrieval
recall or prove that live search would have returned those same candidates.

Generate the two splits in separate invocations. The held-out command requires
an extra confirmation switch, and outputs are created exclusively: an existing
path is never overwritten.

```sh
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  python -m SystemCode.src.backend.scripts.generate_recommendation_benchmark \
  --split development --seed 4107 \
  --output SystemCode/src/backend/evaluation/generated/20261018/development.json \
  --allow-live-neo4j --allow-llm-cost

PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  python -m SystemCode.src.backend.scripts.generate_recommendation_benchmark \
  --split held_out_test --seed 9921 \
  --output /secure/kindercompass-benchmark/20261018/held_out_test.json \
  --allow-live-neo4j --allow-llm-cost --confirm-held-out-generation
```

Replay either saved artifact without contacting Neo4j or an LLM:

```sh
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline \
  python -m SystemCode.src.backend.scripts.evaluate_generated_recommendation_benchmark \
  --dataset SystemCode/src/backend/evaluation/generated/20261018/development.json \
  --output /tmp/kindercompass-development-report.json
```

The command reads Neo4j credentials and `OPENAI_API_KEY` from the environment;
it does not print or store them. Review `generated_at` and
`source_snapshot.sha256` before refreshing deliberately. A checked-in held-out
file cannot be made inaccessible by code alone: restrict its access in the
repository process. The generator rejects a held-out output path inside this
development repository, and do not inspect the held-out artifact while tuning
development behavior.
Different case IDs do not establish independent samples. This generator does
not create human relevance labels or prove recommendation quality. Generated
files are a separate artifact kind and do not replace the existing synthetic
smoke fixtures.

## Case template

Copy a case into the file's `ranking_cases` list and replace every placeholder.
Use a real family profile in the normalized form described below and a frozen
snapshot of the candidate school records used for that evaluation. This is a
shape template only; it contains no example preschool, label, or reference.

```json
{
  "case_id": "<unique-case-id>",
  "reference_case_id": "<same-unique-case-id>",
  "profile": {
    "hard_constraints": {},
    "preferences": {
      "<normalized-attribute>": {
        "value": "<family-requested-value>",
        "weight": "<positive-or-zero-weight>",
        "desired": "<true-or-false>"
      }
    },
    "preference_items": [
      {
        "attribute": "<normalized-attribute>",
        "value": "<family-requested-value>",
        "importance": "<required|high_priority|preferred|nice_to_have>"
      }
    ]
  },
  "schools": [
    {
      "school_id": "<stable-school-id>",
      "name": "<recorded-school-name>",
      "<school-attribute-used-by-the-profile>": "<value-from-frozen-record>"
    }
  ],
  "reference_ids": ["<candidate-school-id>"],
  "labels_complete": "<true-or-false>",
  "relevance": {},
  "reference_order": null,
  "hard_constraint_outcomes": {},
  "eligibility": {},
  "hard_constraint_checks": []
}
```

The production scorer expects normalized `profile.preferences` entries with a
`value`, optional numeric `weight` (default 3), and optional `desired` boolean
(default true). `preference_items` supplies `attribute`, `value`, and
`importance`; allowed importance values are `required`, `high_priority`,
`preferred`, and `nice_to_have`. `hard_constraints` is a mapping, for example
the production keys `level` and `language`. School records use the production
`school_id` field and the catalogue attributes referenced by the preferences,
such as `pedagogy`, `spark_certified`, `provision_of_transport`,
`operator_scheme`, `food_offered`, `second_languages_offered`, and `care_levels`.
Include the actual record values needed to run the ranker; do not infer values
or fill unknown catalogue fields with guessed facts. The benchmark ranker is
Stage 1: `profile` and `schools` are passed to the legacy and current Stage 1
rankers. Stage 2 eligibility and factual fee claims are scored against your
labels; this offline runner does not call live eligibility/policy services.

The actual Stage 2 service accepts `FamilyDetails` (date of birth, admission
date, income, citizenship, programme, working hours, household size,
dependants, and special approval) and returns eligibility and fee fields. This
benchmark runner does not invoke that service: `eligibility` labels currently
check the Stage 1 generated recommendation order for known ineligible schools,
and fee/eligibility claim records compare values you enter. Do not interpret
these offline metrics as a fresh execution of Stage 2 or as a policy estimate.

## Fields, labels, and provenance

### Case inputs and ranking labels

- `case_id` is required and unique within a split. `reference_case_id` is
  required because the existing metric function checks that it equals
  `case_id`.
- `profile` and `schools` are required to generate both rankings. A school
  needs a unique stable `school_id` (the existing evaluator also accepts the
  legacy `id` key, but new records should use production `school_id`).
- `reference_ids` is the candidate pool considered for independent relevance
  labels. Every ID must be present in `schools`. To calculate recall correctly,
  label the complete pool and set `labels_complete` to `true`; the validator
  then requires every pool ID in `relevance`. If the pool is incomplete, use
  `false` and expect recall to be undefined. Missing reference IDs or labels
  are not interpreted as irrelevant.
- `relevance` maps school IDs to integer grades: `0` not relevant, `1` marginal,
  `2` relevant, `3` highly relevant. Enter these judgments manually. Grade zero
  is a deliberate “not relevant” label, not a missing or unknown value.
- `reference_order` is optional. Use an ordered array of school IDs or a mapping
  of school IDs to numeric ranks; equal ranks represent a tie. Only enter it
  when you have independently judged an order. NDCG, precision/recall, MRR and
  hit rate use relevance; Kendall tau-b uses this reference order.
- `hard_constraint_outcomes` maps school IDs to `pass`, `fail`, or `unknown`.
  Unknown means the constraint could not be established. Do not use `fail` for
  missing evidence. These labels support confirmed violation, precision/recall,
  F1, and unknown-retention measures.
- `eligibility` maps school IDs to `eligible`, `ineligible`, or `unknown` and
  supports the eligibility violation measure. Record `unknown` when eligibility
  is not established; omit a label if it has not been reviewed yet.
- `hard_constraint_checks` is optional and allows separate evaluation per
  named constraint. Each item has `constraint`, candidate school IDs,
  predicted `excluded_ids`, and reference `outcomes` (`pass`, `fail`, or
  `unknown`). Every supplied outcome needs its own provenance entry.

### Factual claims, explanation claims, and paired ratings

These arrays are at the dataset root; each record must include `case_id` for
the case it describes.

- `eligibility_fee_claims`: each item needs a stable `claim_id`, `case_id`,
  `school_id`, `claim_type`, `verified`, `predicted`, `expected`, and `reference` with
  `source` and a stable `reference` identifier or URL when verified. Numeric
  types include `fee`, `subsidy`, `age_months`, and `numeric`; they support
  optional `unit`, `expected_unit`, and non-negative `tolerance`. Dates use
  `date` or `admission_date`. `verified: false` is not scored as correct or
  incorrect; leave genuinely unknown expected values absent and do not guess.
  Every verified expected factual value needs provenance below.
- `explanation_claims`: manually split each factual statement into an atomic
  claim. Include `claim_id`, `case_id`, `claim`, `factual`,
  `evidence_available`, an `evidence` object with `source` and stable
  `reference`, and `status`: `supported`, `contradicted`, `unsupported`, or
  `unverifiable` (or `not_applicable` when the rubric dimension genuinely does
  not apply). The metric calculates grounding among supported,
  contradicted, and unsupported factual claims; unverifiable claims stay out
  of that denominator and are counted separately. Non-factual wording can be
  marked `factual: false` and is excluded.
- `human_judge_ratings`: include a record only after both a human and an LLM
  have rated that same case and rubric dimension. Each record requires
  `case_id`, `dimension`, and integer `human` and `llm_judge` ratings from 1
  through 5. A duplicate
  case/dimension pair is invalid. `judge_configuration` must record `model`,
  `prompt_version`, `rubric_version`, and `settings`. Agreement is not
  calculated from human-only or LLM-only ratings.
- `confidence_cases` is optional and checks reported evidence completeness
  against known/total evidence weight. This is not factual accuracy or
  probability calibration.
- `not_applicable_labels` is optional for labels outside the supported metric
  classes or dimensions that genuinely do not apply. Each record has
  `case_id`, `label_type`, `label_key`, `reason`, `reviewer`, and
  `decided_at` (`YYYY-MM-DD`). These records are reported separately and never
  converted to zero, pass, fail, or unknown. Omit an uncollected label instead;
  omissions are reported as missing or remain metric-specific exclusions.

The three record arrays below belong at the dataset root. These are copyable
shapes only; replace all placeholder strings and ratings with actual collected
data. Do not copy placeholder values as labels.

```json
{
  "eligibility_fee_claims": [
    {
      "case_id": "<case-id>",
      "claim_id": "<claim-id>",
      "school_id": "<candidate-school-id>",
      "claim_type": "<eligibility|fee|subsidy|age_months|numeric|date|admission_date>",
      "verified": "<true-or-false>",
      "predicted": "<value from evaluated system output>",
      "expected": "<manually checked reference value>",
      "unit": "<unit, if applicable>",
      "expected_unit": "<same unit, if applicable>",
      "tolerance": "<non-negative-number>",
      "reference": {"source": "<source name>", "reference": "<stable reference ID or URL>"}
    }
  ],
  "explanation_claims": [
    {
      "case_id": "<case-id>",
      "claim_id": "<claim-id>",
      "claim": "<one atomic statement from the evaluated explanation>",
      "factual": "<true-or-false>",
      "evidence_available": "<true-or-false>",
      "evidence": {"source": "<evidence source>", "reference": "<stable reference ID or URL>"},
      "status": "<supported|contradicted|unsupported|unverifiable|not_applicable>"
    }
  ],
  "human_judge_ratings": [
    {"case_id": "<case-id>", "dimension": "<rubric dimension>", "human": "<integer 1-to-5>", "llm_judge": "<integer 1-to-5>"}
  ]
}
```

If you enter paired ratings, also fill `judge_configuration` with the actual
`model`, `prompt_version`, `rubric_version`, and `settings`. For each populated
label, add a matching provenance item to `label_provenance`, such as:

```json
{
  "case_id": "<case-id>",
  "label_type": "<eligibility_fee_claims|explanation_claims|human_judge_ratings>",
  "label_key": "<claim_id, or dimension for a paired rating>",
  "source": "<source or review record>",
  "reference": "<stable source ID or URL>",
  "verified_at": "<YYYY-MM-DD>",
  "reviewer": "<reviewer identifier or role>"
}
```

For factual claims, `verified: true` requires both `predicted` and manually
checked `expected` values, plus a source/reference and provenance. Use
`verified: false` when the factual claim cannot be checked; it remains
unverified and is not scored as correct or incorrect. Do not invent an expected
value or citation. A paired-rating reference should identify the actual rubric
or collection record and the provenance date should be the date ratings were
collected.

### Provenance for every reference label

Every supplied reference judgment requires one entry in root-level
`label_provenance`. Its `case_id`, `label_type`, and `label_key` identify exactly
one label. `source` names the evidence source; `reference` is a stable record
identifier or URL; `verified_at` is the date you checked it, exactly
`YYYY-MM-DD`; `reviewer` identifies the person or reviewer role. The validator
requires a provenance entry for each populated relevance, reference-order,
hard-constraint, eligibility, constraint-check, claim, explanation, and paired
rating label. It rejects unused or duplicate provenance entries.

Use these `label_type` / `label_key` pairs:

| Label | `label_type` | `label_key` |
|---|---|---|
| Relevance for a school | `relevance` | school ID |
| Reference order for a school | `reference_order` | school ID |
| Hard constraint result | `hard_constraint_outcomes` | school ID |
| Eligibility result | `eligibility` | school ID |
| Individual constraint result | `hard_constraint_check` | `<constraint>:<school-id>` |
| Factual claim expected value | `eligibility_fee_claims` | `claim_id` |
| Explanation grounding status | `explanation_claims` | `claim_id` |
| Paired human/LLM rating | `human_judge_ratings` | dimension |

Each case can have one paired rating per dimension. Cite the rubric or review
record and the actual rating collection date. Do not claim an external factual
source for an opinion rating.

The provenance record describes your manual verification; entering a source,
date, and reviewer does not make the label independently audited by KinderCompass.
The report will not upgrade the benchmark to an independently verified result.

## Validate and evaluate

Run these commands from the repository root. Validation makes no model or
external-service calls:

```sh
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline .venv/bin/python -m SystemCode.src.backend.evaluation.run_recommendation_evaluation --dataset SystemCode/src/backend/evaluation/benchmark/development.json --validate-only
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline .venv/bin/python -m SystemCode.src.backend.evaluation.run_recommendation_evaluation --dataset SystemCode/src/backend/evaluation/benchmark/held_out_test.json --validate-only
```

After validation, evaluate each split separately:

```sh
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline .venv/bin/python -m SystemCode.src.backend.evaluation.run_recommendation_evaluation --dataset SystemCode/src/backend/evaluation/benchmark/development.json --output /tmp/kindercompass-development-report.json
PYTHONPATH=SystemCode/src/backend:SystemCode/src/backend/pipeline .venv/bin/python -m SystemCode.src.backend.evaluation.run_recommendation_evaluation --dataset SystemCode/src/backend/evaluation/benchmark/held_out_test.json --output /tmp/kindercompass-held-out-report.json
```

Reports identify benchmark ID, version, split, dataset kind, case and label
counts, and metric denominators/exclusions. `null` values mean the metric could
not be calculated; check its exclusion reason (for example, no positive
relevance, unknown/incomplete labels, or fewer than two comparable items).
These populated files exercise the existing evaluator with synthetic scenarios.
Some metrics remain `null` when required reference labels are intentionally
absent or incomplete. Neither split is performance evidence. The default
`synthetic_fixtures.json` remains separate and continues to test metric
arithmetic only.

## JSON editing tips

Use a text editor with JSON syntax highlighting. Keep double quotes around
field names and strings, put commas between sibling fields, and remove the
comma after the last item. JSON does not allow comments. Validate after each
batch of edits; errors name the case and field to fix.
