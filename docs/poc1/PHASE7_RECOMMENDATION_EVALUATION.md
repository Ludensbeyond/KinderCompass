# Phase 7: Recommendation evaluation and observability

Phase 7 adds repeatable evidence that ranking changes preserve the intended recommendation behavior.

## Golden scenarios

`../../SystemCode/src/backend/scripts/evaluate_recommendations.py` runs five synthetic scenarios:

1. proven mismatches on required supported preferences are excluded;
2. unknown evidence receives no compatibility credit;
3. changing importance can change recommendation order;
4. evidence confidence breaks a tied verified match score; and
5. hard-constraint-only searches correctly report a full requirements match without a weighted breakdown.

The fixtures contain no real postal codes, income, dates, family details, or chat history.

## Run the evaluation

From the repository root:

```powershell
.\.venv\Scripts\python.exe SystemCode\src\backend\scripts\evaluate_recommendations.py
```

The default report is Markdown printed to the terminal. A failed scenario makes the command exit with status 1.

Save a Markdown report:

```powershell
.\.venv\Scripts\python.exe SystemCode\src\backend\scripts\evaluate_recommendations.py --output SystemCode\src\backend\output\recommendation_evaluation.md
```

Generate machine-readable JSON:

```powershell
.\.venv\Scripts\python.exe SystemCode\src\backend\scripts\evaluate_recommendations.py --format json --output SystemCode\src\backend\output\recommendation_evaluation.json
```

## Runtime search traces

`POST /api/search` now returns a privacy-safe trace containing:

- a random trace ID;
- ranking method;
- database candidates after hard constraints;
- candidates after distance filtering;
- candidates after required-preference enforcement;
- required-preference exclusion count;
- Stage 1 shortlist size; and
- mean shortlist evidence confidence.

`POST /api/evaluate` accepts the trace ID and returns Stage 2 input, eligible, and excluded counts. Traces contain aggregate counts only. They do not persist or return the postal code, family details, income, dates, or chat text.

## Automated verification

The normal unit-test suite also invokes the golden evaluator:

```powershell
# Run from the repository root
$env:PYTHONPATH = "SystemCode/src/backend/pipeline;SystemCode/src/backend"
.\.venv\Scripts\python.exe -m unittest discover -s SystemCode/src/backend/tests -v
```

