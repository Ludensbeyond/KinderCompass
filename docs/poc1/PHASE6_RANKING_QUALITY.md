# Phase 6: Ranking quality and personalisation

Phase 6 improves how Stage 1 scores and explains recommendation order.

## Before

- Missing school evidence received half of a preference's points.
- Preference weights were internal and could not be adjusted in the UI.
- A required scored preference could remain as a lower-ranked mismatch.
- Results exposed strengths and trade-offs but not the underlying calculation.

## After

- Unknown evidence earns no compatibility points and is excluded from the verified match denominator.
- Evidence coverage remains a separate confidence percentage.
- Parents can set adjustable preferences to Required, High priority, Preferred, or Nice to have.
- A school is excluded when available evidence proves that it fails a required supported preference. Unknown evidence is retained and clearly marked rather than treated as a failure.
- Every result has an expandable score breakdown showing matched, not matched, and unknown evidence, importance, and verified point contribution.

Hard constraints such as required care level, required language, and maximum distance continue to filter before scoring. Searches containing only hard constraints receive a 100% match after passing those constraints.

## Ranking order

The remaining results are ordered by:

1. verified preference-match percentage;
2. evidence confidence; and
3. school name as a deterministic tie-breaker.

## Manual tests

1. Add two or more adjustable preferences and expand **Understood preferences**.
2. Change one preference to **High priority** and another to **Nice to have**.
3. Show recommendations and confirm the ranked results update.
4. Expand **How this score was calculated** on several schools.
5. Confirm missing evidence appears as **unknown**, not as a partial match.
6. Mark a supported preference **Required** and confirm schools with a proven mismatch disappear.

