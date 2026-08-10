# Phase 4: Grounded selected-school explanations

## Purpose

Phase 4 improves answers to questions such as:

- “Which of the selected preschools will you recommend to me?”
- “Is the selected school suitable for me?”

The application retrieves the selected schools and their calculated facts from current application state. Deterministic code still chooses the recommended school and determines the suitability verdict. An optional LLM converts that fixed decision and retrieved evidence into a concise explanation.

This is structured RAG: retrieval uses structured application data rather than embeddings or a vector database.

## Retrieved context

Only these school fields may be sent to the explanation model:

- school ID and name;
- match score and evidence confidence;
- strengths and trade-offs;
- eligible care level;
- estimated net monthly fee; and
- calculated distance from home.

The model also receives canonical preferences with importance, evidence class, and evidence warnings. It does not receive date of birth, admission date, income, subsidy, postal code, raw coordinates, or chat history.

## Decision boundary

The LLM cannot:

- select a different winning school;
- change the deterministic suitability verdict;
- reference an unselected school;
- treat unsupported preferences as verified evidence; or
- recalculate match, eligibility, fee, or distance.

The parsed response must reference the deterministically decided school ID. Any API, timeout, parsing, or grounding-validation error returns the existing deterministic explanation.

## Configuration

Add the following to `SystemCode/notebooks/poc1/.env`:

```dotenv
OPENAI_GROUNDED_EXPLANATIONS_ENABLED=true
OPENAI_EXPLANATION_MODEL=gpt-4o-mini
OPENAI_EXPLANATION_TIMEOUT_SECONDS=8
```

Phase 4 uses the same `OPENAI_API_KEY` configured for Phase 3. Preference extraction and grounded explanations have independent enabled flags.

Restart the backend after changing these settings.

## Runtime status

The `/api/preferences` response profile contains `explanation_method`:

- `llm_grounded`: grounded LLM explanation succeeded;
- `deterministic`: the feature is disabled or the question does not have a valid school decision to explain; or
- `deterministic_fallback`: the LLM path failed validation or raised an exception.

For fallback, `explanation_fallback_reason` contains only the exception type.

## Manual test

1. Enable grounded explanations and restart the backend.
2. Complete Family details and obtain recommendations.
3. Select at least two preschools.
4. Ask: `Which of the selected preschool will you recommend to me?`
5. Inspect the `/api/preferences` response in browser Developer Tools.
6. Confirm `profile.explanation_method` is `llm_grounded`.
7. Verify that the answer mentions only selected schools and uses displayed match, cost, and distance evidence.

To test suitability, select exactly one school and ask: `Is the selected school suitable for me?`

## Automated tests

```powershell
cd SystemCode/notebooks/poc1
$env:PYTHONPATH = "src"
& "..\..\..\.venv\Scripts\python.exe" -m unittest discover -s tests
```

The Phase 4 tests mock the OpenAI boundary and cover successful grounding, rejection of an unselected-school reference, and timeout fallback without using an API key.

## Reference

The implementation follows official OpenAI guidance to specify required evidence and output structure, keep deterministic processing in code, and evaluate final-answer completeness:
https://developers.openai.com/api/docs/guides/latest-model

