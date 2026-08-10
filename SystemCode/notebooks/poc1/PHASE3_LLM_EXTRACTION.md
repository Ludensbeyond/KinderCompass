# Phase 3: Optional LLM preference extraction

## Purpose

Phase 3 uses an LLM to understand natural preschool-preference language and convert it into the validated Phase 2 schema. It does not allow the model to query Neo4j, rank schools, calculate eligibility or fees, or calculate distance.

The implementation uses the OpenAI Responses API with Structured Outputs and Pydantic parsing. The Phase 2 validator remains the final authority: unknown attributes, invalid values, or inconsistent evidence metadata are rejected before they reach the search pipeline.

## Runtime flow

```text
Chat preference message
        |
        v
Is LLM extraction enabled?
   | no             | yes
   v                v
Rule mapper     OpenAI structured extraction
   |                |
   |          Phase 2 validation fails?
   |                | yes
   |<---------------+
   v
Backward-compatible profile
        |
        v
Deterministic Neo4j filtering and scoring
```

The returned profile includes `extraction_method`:

- `llm`: structured LLM extraction succeeded;
- `rules`: LLM extraction was disabled or the user reset the profile; or
- `rules_fallback`: an API, timeout, SDK, parsing, or schema-validation failure caused deterministic fallback.

When fallback occurs, `llm_fallback_reason` contains only the exception type and never credentials or raw exception details.

## Configuration

Install the updated dependencies once:

```powershell
.\SystemCode\notebooks\poc1\run_poc1.ps1 -InstallDependencies
```

Add these values to `SystemCode/notebooks/poc1/.env`:

```dotenv
OPENAI_PREFERENCE_EXTRACTION_ENABLED=true
OPENAI_API_KEY=your-project-api-key
OPENAI_PREFERENCE_MODEL=gpt-4o-mini
OPENAI_PREFERENCE_TIMEOUT_SECONDS=8
```

Do not commit the `.env` file. Set the enabled flag to `false` to return to rules-only extraction without changing code.

## Data minimisation

The OpenAI request contains only:

- the newest preference-chat message; and
- existing canonical preference attributes, values, and importance.

The integration does not include the family form, date of birth, admission date, income, subsidy, postal code, selected-school results, or chat history. Requests set `store=False`.

## Safety boundaries

- Structured output is parsed into a closed Pydantic model.
- Canonical values are checked again by `preference_schema.py`.
- Unsupported preferences are retained but cannot independently enable search.
- Any exception causes deterministic fallback.
- Search, scoring, eligibility, fees, and distance remain deterministic.

## Testing

Automated tests mock the OpenAI extraction boundary, so they require neither network access nor an API key:

```powershell
cd SystemCode/notebooks/poc1
$env:PYTHONPATH = "src"
& "..\..\..\.venv\Scripts\python.exe" -m unittest discover -s tests
```

For a manual LLM test, enable the environment settings, restart the application, and enter a natural description that the keyword mapper does not directly cover. Inspect the `/api/preferences` response in browser developer tools and confirm that `profile.extraction_method` is `llm`.

## Reference

The integration follows the official OpenAI Structured Outputs guide:
https://developers.openai.com/api/docs/guides/structured-outputs

