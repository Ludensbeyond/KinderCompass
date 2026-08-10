# Phase 5: Recommendation transparency and comparisons

Phase 5 lets parents interrogate recommendation results without allowing a language model to recalculate scores or invent school evidence.

## Supported questions

- `Why is this preschool ranked first?`
- `Compare the selected preschools.`
- `What are the trade-offs of the selected schools?`

The first question uses the ordered eligible results. Comparison and trade-off questions use only schools explicitly selected in the Results panel.

## Grounding data

Answers may use only calculated or retrieved fields already present in application state:

- preference match score and evidence confidence;
- per-preference match breakdown;
- recorded strengths and trade-offs;
- eligible care level;
- estimated net monthly fee; and
- calculated distance from home.

Stage 1 ranking is explained as preference-match score followed by evidence confidence. Cost and distance are displayed for comparison but do not change the Stage 1 rank.

## Safety boundary

Deterministic code creates a complete fallback answer. When grounded explanations are enabled, the LLM may improve wording but cannot add schools outside the supplied context. Ranking explanations must reference the top-ranked school, and multi-school comparisons must reference every selected school. Invalid output and model failures return the deterministic answer.

## Manual tests

1. Generate recommendations and ask `Why is this preschool ranked first?`.
2. Select two or more results and ask `Compare the selected preschools.`.
3. Select one or more results and ask `What are their trade-offs?`.
4. Ask for a comparison with fewer than two selections and confirm that the chatbot requests at least two schools.

