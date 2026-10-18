# Recommendation evidence and ranking contract

This note defines how Stage 1 treats evidence before the scoring implementation
is adjusted.

## Evidence semantics

- `school_value` is the catalogue value, when one exists. Its presence alone does
  not make the value verified.
- `evidence_state` describes support: `verified` is reserved for supported
  structured records, `derived` identifies name-derived pedagogy, and
  `unknown` means the catalogue cannot answer the question. A populated derived
  value is not a verified fact.
- `status` describes the preference comparison: `matched` and `not_matched` are
  reserved for usable evidence; `inferred` describes a comparison based only on
  a derived value; `unknown` means no comparison can safely be made.
- `source_reliability` is a qualitative provenance label, not a probability.
  The existing pedagogy support factor `0.65` is retained as a bounded evidence
  coverage factor only; it is not a 65% probability that a claim is true and is
  not used to award match points. No new numeric reliability factors are
  introduced.
- Freshness is reported separately. A source older than the existing 365-day
  threshold is stale; stale, inferred, and ambiguous evidence does not establish
  a match or mismatch for ranking or required-preference enforcement.
- Explicitly supported values may establish either a match or a mismatch.
  Missing or ambiguous values establish neither.

## Ranking semantics

The preference-match percentage is the importance-weighted share of scorable
preferences that match, with known mismatches in the denominator and unknown,
inferred, stale, and unsupported evidence excluded. Evidence completeness is
the importance-weighted usable evidence coverage divided by all scored
preferences; the existing availability factor is used only in this component.
The existing combined ranking score remains the geometric mean of preference
match and evidence completeness percentages. The calculation and ordering use
unrounded values; response fields remain rounded for display. Exact ties use
ascending stable school ID. Stage 2 removes ineligible results without
reordering the survivors.

Required supported preferences exclude a school only on an explicit usable
mismatch. Unknown, stale, or inferred evidence is retained as an uncertain
candidate, surfaced as requiring confirmation, and never presented as satisfying
the requirement. Explicit hard filters are applied before scoring and cannot be
overridden by a score.

These rules do not certify catalogue truth or policy eligibility. Sources and
freshness remain visible so families can confirm facts with preschools and ECDA.
