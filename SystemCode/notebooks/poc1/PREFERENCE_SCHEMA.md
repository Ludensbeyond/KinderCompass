# Phase 2: Evidence-aware preference schema

## Purpose

Stage 1 now attaches validated evidence metadata to every recognised preference. This creates a safe contract for future LLM extraction without allowing an LLM to invent attributes or values that the search pipeline cannot handle.

The schema is implemented in `src/stage1/preference_schema.py`. Schema version 2 is backward-compatible: `hard_constraints` and `preferences` remain available to the existing Neo4j query builder and deterministic scorer, while `preference_items` provides the new canonical representation.

## Preference item

Each item contains:

| Field | Meaning |
|---|---|
| `attribute` | Canonical attribute from the controlled catalogue |
| `value` | Validated value allowed for that attribute |
| `importance` | `required` or `preferred` |
| `confidence` | Extraction confidence from 0 to 1 |
| `evidence_class` | `supported`, `partially_supported`, or `unsupported` |
| `school_property` | Dataset/Neo4j property used for matching, or `null` |
| `warning` | Evidence limitation that must accompany interpretation |

Example:

```json
{
  "attribute": "pedagogy",
  "value": "Montessori",
  "importance": "preferred",
  "confidence": 1.0,
  "evidence_class": "partially_supported",
  "school_property": "pedagogy",
  "warning": "Pedagogy is inferred from the centre name and is specific for only about 5% of records."
}
```

## Profile structure

```json
{
  "schema_version": 2,
  "hard_constraints": {
    "language": "Chinese"
  },
  "preferences": {
    "pedagogy": {
      "value": "Montessori",
      "weight": 5,
      "desired": true
    }
  },
  "preference_items": [
    {
      "attribute": "language",
      "value": "Chinese",
      "importance": "required",
      "confidence": 1.0,
      "evidence_class": "supported",
      "school_property": "second_languages_offered",
      "warning": "Evidence confirms that the language is offered, not its teaching intensity or quality."
    },
    {
      "attribute": "pedagogy",
      "value": "Montessori",
      "importance": "preferred",
      "confidence": 1.0,
      "evidence_class": "partially_supported",
      "school_property": "pedagogy",
      "warning": "Pedagogy is inferred from the centre name and is specific for only about 5% of records."
    }
  ],
  "unsupported_preferences": [],
  "recognized": [],
  "source_text": ""
}
```

`preference_items` is synchronised from the backward-compatible fields during Phase 2. Future phases can make it the primary representation after the query builder and scorer have been migrated.

## Evidence treatment

- **Supported:** care level, offered language, SPARK, transport, and full-day care.
- **Partially supported:** pedagogy, operator scheme, food policy, and maximum home distance. Distance is computed from the saved home postal code; schools without location data cannot be verified. These items include an evidence warning.
- **Unsupported:** hands-on learning, child-led learning, low worksheet use, primary-school readiness, and atmosphere.

Unsupported needs are retained in `unsupported_preferences` and shown to the user as not used for ranking. They cannot enable recommendation search on their own.

## Validation rules

- Unknown attributes are rejected.
- Each attribute accepts only controlled canonical values.
- Importance must be `required` or `preferred`.
- Confidence must be numeric and between 0 and 1.
- Evidence class, school property, and warning must match the central attribute catalogue.
- Unsupported items cannot appear in `preference_items`.
- Supported or partially supported items cannot appear in `unsupported_preferences`.

These rules allow future LLM output to be validated before it reaches Neo4j or the scorer.
