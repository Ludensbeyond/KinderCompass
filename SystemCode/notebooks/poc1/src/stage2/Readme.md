# Stage 2 — Compliance and Cost

Stage 2 reads the preschool shortlist produced by Stage 1, checks whether each
preschool offers the care level required for the child's age, and calculates the
estimated net monthly fee.

## Files in this folder

| File | Purpose |
|---|---|
| `__init__.py` | Exposes the reusable Stage 2 functions as package imports. |
| `engine.py` | Contains age eligibility, subsidy, fee, and shortlist evaluation logic. |
| `runner.py` | Command-line interface that reads Stage 1 JSON and optionally writes Stage 2 JSON. |

## Inputs

Stage 2 combines two types of input:

1. Preschool information produced by Stage 1:
   - centre code and name
   - base fee
   - operator scheme
   - care levels
   - pedagogy
2. Private family information supplied when Stage 2 is run:
   - child's date of birth
   - intended admission date
   - gross household income
   - basic monthly subsidy

Family information is not part of Stage 1 because Stage 1 searches public
preschool data, while Stage 2 performs private eligibility and cost evaluation.

## Stage 1 input template

Stage 1 normally creates this file using its `--output` option. The expected JSON
format is an array of preschool objects:

```json
[
  {
    "centre_code": "ST0001",
    "name": "Example Preschool",
    "base_fee": 1200.0,
    "operator_scheme": "Anchor Operator Scheme",
    "care_levels": [
      "Pre-Nursery (3 yrs old)",
      "Nursery (4 yrs old)"
    ],
    "pedagogy": "Play-based"
  }
]
```

The `base_fee` field is required. Stage 2 uses `care_levels` to determine whether
the preschool offers the level required for the child.

## Setup

Run commands from the repository root in PowerShell:

```powershell
.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "SystemCode/notebooks/poc1/src"
```

On Linux or macOS, use Bash:

```bash
source .venv/bin/activate
export PYTHONPATH="SystemCode/notebooks/poc1/src"
```

## Run Stage 2

Stage 2 reads a shortlist JSON file previously produced by Stage 1.

### Read the shortlist and calculate costs

```powershell
python -m stage2.runner `
  --input "SystemCode/notebooks/poc1/output/stage1_shortlist.json" `
  --dob "2023-06-10" `
  --admission-date "2026-01-01" `
  --ghi 4500 `
  --basic-subsidy 600 `
  --output "SystemCode/notebooks/poc1/output/stage2_results.json"
```

Dates must use `YYYY-MM-DD`. Monetary values are monthly amounts in Singapore
dollars.

Bash:

```bash
python -m stage2.runner \
  --input "SystemCode/notebooks/poc1/output/stage1_shortlist.json" \
  --dob "2023-06-10" \
  --admission-date "2026-01-01" \
  --ghi 4500 \
  --basic-subsidy 600 \
  --output "SystemCode/notebooks/poc1/output/stage2_results.json"
```

### Keep ineligible preschools in the output

By default, Stage 2 writes only eligible preschools. Add
`--include-ineligible` to retain rejected preschools and their rejection reason:

```powershell
python -m stage2.runner `
  --input "./../output/stage1_shortlist.json" `
  --dob "2023-06-10" `
  --admission-date "2026-01-01" `
  --ghi 4500 `
  --basic-subsidy 600 `
  --include-ineligible `
  --output "./../output/stage2_results.json"
```

The `--output` option is optional. Without it, Stage 2 prints a summary but does
not save the result to a file.

Bash:

```bash
python -m stage2.runner \
  --input "./../output/stage1_shortlist.json" \
  --dob "2023-06-10" \
  --admission-date "2026-01-01" \
  --ghi 4500 \
  --basic-subsidy 600 \
  --include-ineligible \
  --output "./../output/stage2_results.json"
```

## Stage 2 output template

An eligible preschool is enriched with the Stage 2 fields:

```json
[
  {
    "centre_code": "ST0001",
    "name": "Example Preschool",
    "base_fee": 1200.0,
    "operator_scheme": "Anchor Operator Scheme",
    "care_levels": ["Pre-Nursery (3 yrs old)"],
    "pedagogy": "Play-based",
    "eligible": true,
    "eligible_level": "Pre-Nursery (3 yrs old)",
    "additional_subsidy": 250.0,
    "net_monthly_fee": 350.0
  }
]
```

When `--include-ineligible` is used, an ineligible result resembles:

```json
{
  "centre_code": "ST0002",
  "name": "Another Preschool",
  "base_fee": 1000.0,
  "care_levels": ["Kindergarten 1 (5 yrs old)"],
  "eligible": false,
  "eligible_level": "Pre-Nursery (3 yrs old)",
  "reason": "Preschool does not offer the required care level"
}
```

## Current calculation rules

The child's required care level is based on admission year minus birth year:

| Calendar age | Required care level |
|---:|---|
| 2 | Playgroup |
| 3 | Pre-Nursery |
| 4 | Nursery |
| 5 | Kindergarten 1 |
| 6 | Kindergarten 2 |

The current proof-of-concept additional subsidy tiers are:

| Gross household income | Additional subsidy |
|---:|---:|
| Up to $3,000 | $400 |
| $3,000.01–$6,000 | $250 |
| $6,000.01–$12,000 | $100 |
| Above $12,000 | $0 |

The estimated fee is calculated as:

```text
net monthly fee = max(0, base fee - basic subsidy - additional subsidy)
```

These are prototype rules and should be checked against current official ECDA
eligibility and subsidy rules before production use. A future version should
derive the basic subsidy from citizenship, care type, and parental working
status instead of requiring `--basic-subsidy` manually.

## Use Stage 2 from Python

```python
import datetime as dt
from stage2.runner import run_from_file

results = run_from_file(
    "SystemCode/notebooks/poc1/output/stage1_shortlist.json",
    dob=dt.date(2023, 6, 10),
    admission_date=dt.date(2026, 1, 1),
    ghi=4500,
    basic_subsidy=600,
    output_path="SystemCode/notebooks/poc1/output/stage2_results.json",
)
```

For an already loaded Stage 1 list, call
`stage2.engine.evaluate_shortlist(...)` directly.

## Run the tests

```powershell
python -m unittest discover -s SystemCode/notebooks/poc1/tests -v
```

Bash:

```bash
python -m unittest discover -s SystemCode/notebooks/poc1/tests -v
```
