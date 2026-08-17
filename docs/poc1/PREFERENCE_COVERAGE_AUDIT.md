# Phase 1: Preference coverage audit

## Scope

This audit compares parent-facing preferences with:

- the 1,867 records in `data/processed/kindercompass_master.json`;
- the properties imported into Neo4j by `knowledge_graph_gen.ipynb`; and
- the current Stage 1 extraction, filtering, and scoring code.

Coverage was measured on the current master JSON. Empty values and the literal value `na` were treated as unavailable evidence. A populated field does not automatically mean that its evidence is reliable enough for recommendation claims.

## Methodology

The audit was conducted in four steps.

### 1. Measure dataset coverage

The 1,867 records in `data/processed/kindercompass_master.json` were inspected for fields corresponding to parent-facing preferences. For each field, the audit counted records containing usable evidence and calculated the percentage of the complete catalogue covered.

The following were treated as unavailable evidence:

- null values;
- empty strings or collections; and
- placeholder values such as `na`.

Coverage was measured against all 1,867 unique `school_id` values. Examples of the resulting measurements include 100% for `spark_certified`, 96.5% for `weekday_full_day`, 95.9% for `second_languages_offered`, 81.4% for location geometry, and 57.8% for `operator_scheme`.

### 2. Review value distributions and evidence quality

Column completeness alone was not considered sufficient. The distribution and meaning of the populated values were also reviewed to determine whether they provided reliable recommendation evidence.

For example, all 1,867 records contain a `pedagogy` value, but the distribution is:

- General: 1,773 records;
- Montessori: 77 records;
- Play-based: 15 records;
- Bilingual: 2 records; and
- Reggio Emilia: 0 records.

This distribution prompted a data-lineage check rather than treating pedagogy as having 100% reliable coverage.

### 3. Trace data lineage and application usage

The audit inspected how each field was created, imported, interpreted, and used:

- `data_prep.ipynb` was reviewed to identify the source and derivation of processed fields;
- `knowledge_graph_gen.ipynb` was reviewed to verify which properties are imported into Neo4j;
- `../../SystemCode/src/backend/pipeline/stage1/nlp_mapper.py` was reviewed to identify the preferences recognised from chat messages;
- `../../SystemCode/src/backend/pipeline/stage1/query_builder.py` was reviewed to identify required database filters; and
- `../../SystemCode/src/backend/pipeline/stage1/scorer.py` was reviewed to identify weighted preferences and matching behaviour.

This revealed, for example, that pedagogy and philosophy are inferred only from keywords in the centre name. Consequently, `General` means that no supported keyword was detected; it is not verified evidence of a general teaching approach. The code review also found that the current food matcher treats both halal descriptions and no-pork descriptions as satisfying a halal preference, even though these claims are not equivalent.

### 4. Assign a support classification

Each preference was classified by combining coverage, provenance, evidence quality, and current application support:

- **Strong:** direct structured evidence with high coverage and a clear interpretation;
- **Partial:** evidence exists, but coverage, precision, provenance, or current handling limits its reliability;
- **Weak:** a field exists, but its value is derived from an unreliable proxy such as the school name;
- **Available but unused:** reliable-looking data exists but is not currently recognised or scored by Stage 1; or
- **Unsupported:** no corresponding school evidence exists in the current dataset.

The classification describes what the system can substantiate, not merely what the chatbot can recognise. A future LLM may understand unsupported requests, but it should not claim that a school satisfies them without an appropriate retrieved source.

## How to use the audit script

The reusable script is located at `SystemCode/src/backend/scripts/audit_preference_coverage.py`. It uses only the Python standard library, so no additional packages are required.

### Run the default audit

Open PowerShell in the KinderCompass repository root and run:

```powershell
python SystemCode/src/backend/scripts/audit_preference_coverage.py
```

Without options, the script reads `SystemCode/data/processed/kindercompass_master.json` and prints a Markdown report to the terminal.

### Save the report

Use `--output` to save the Markdown report instead of printing it:

```powershell
python SystemCode/src/backend/scripts/audit_preference_coverage.py --output preference_coverage.md
```

The output path is relative to the directory in which the command is run. Existing files at the specified path are replaced.

### Generate machine-readable JSON

Use JSON when the results will be consumed by another script, test, notebook, or CI process:

```powershell
python SystemCode/src/backend/scripts/audit_preference_coverage.py --format json --output preference_coverage.json
```

Omit `--output` to print the JSON to the terminal.

### Audit a different dataset

After regenerating or testing another master dataset, pass its path with `--input`:

```powershell
python SystemCode/src/backend/scripts/audit_preference_coverage.py --input path/to/kindercompass_master.json
```

The input must be a JSON array containing school objects.

### Control value-distribution detail

The report shows the eight most common informative values for each audited field by default. Change this with `--top-values`:

```powershell
python SystemCode/src/backend/scripts/audit_preference_coverage.py --top-values 5
```

Run the built-in help command to see all available options:

```powershell
python SystemCode/src/backend/scripts/audit_preference_coverage.py --help
```

### Interpret the output

The report contains:

- total records and unique school IDs;
- missing and duplicate school-ID checks;
- available, missing, and percentage coverage for each audited field;
- the most common informative values for each field; and
- the number of pedagogy records containing evidence more specific than `General`.

Null values, empty values, empty collections, and placeholders such as `na` are counted as missing. A high coverage percentage means that the field is populated; it does not by itself prove that the source or interpretation is reliable. Use the support ratings and evidence-quality analysis in this document when deciding whether a field can be used for filtering or recommendation scoring.

## Summary

| Preference | Dataset evidence | Coverage | Current Stage 1 | Support rating | Recommended treatment |
|---|---|---:|---|---|---|
| Child's care level | `care_levels` from service records | 1,794 / 1,867 (96.1%) | Required filter | Strong | Keep deterministic and required |
| Second language | `second_languages_offered` | 1,790 / 1,867 (95.9%) | Required filter or weighted preference | Strong | Support, but describe it as a language offered rather than teaching quality |
| SPARK certification | `spark_certified` | 1,867 / 1,867 (100%) | Weighted preference | Strong | Safe for filtering or scoring |
| Transport | `provision_of_transport` | 1,867 / 1,867 (100%) | Weighted preference | Strong | Safe for filtering or scoring |
| Full-day care | `weekday_full_day` | 1,802 / 1,867 (96.5%) | Weighted preference | Strong | Safe for filtering or scoring |
| Operator scheme | `operator_scheme` | 1,080 / 1,867 (57.8%) | Weighted preference | Partial | Use as a preference; distinguish no scheme from missing evidence before making it required |
| Food / halal requirement | `food_offered` | 1,751 / 1,867 (93.8%) | Weighted preference | Partial | Separate MUIS-certified halal, halal-source, no-pork/no-lard, vegetarian, and unknown |
| Pedagogy | `pedagogy`, inferred from centre name | 94 specific / 1,867 (5.0%) | Weighted preference | Weak | Do not present `General` as verified pedagogy; enrich from authoritative curriculum sources |
| Philosophy | `philosophy`, inferred from centre name | 94 specific / 1,867 (5.0%) | Not independently scored | Weak | Do not use as separate evidence until enriched |
| Monthly fee | `services_menu` and derived `base_fee` | 1,794 / 1,867 (96.1%) | Used by later stages | Partial | Use service-, level-, and citizenship-specific fees instead of the minimum fee where possible |
| Distance from home | location geometry | 1,519 / 1,867 (81.4%) | Calculated after postal-code geocoding | Partial | Show unavailable distance explicitly for the remaining 348 records |
| Vacancy | monthly vacancy columns | 1,867 / 1,867 flagged | Not recognised by chat or scored | Available but unused | Add only with admission-month mapping and freshness information |
| Hands-on learning | None | 0 / 1,867 | Some wording may map to play-based, but no direct evidence | Unsupported | Capture as unsupported until curriculum documents are added |
| Child-led / independent learning | None | 0 / 1,867 | Not recognised | Unsupported | Requires school curriculum evidence |
| Low worksheet use | None | 0 / 1,867 | Not recognised | Unsupported | Requires school curriculum evidence |
| Primary-school readiness | None | 0 / 1,867 | Not recognised | Unsupported | Requires programme-outcome or curriculum evidence |
| School atmosphere | None | 0 / 1,867 | Initial chat mentions it, but no matching field exists | Unsupported | Stop implying that it can currently be ranked |
| Class size / teacher ratio | None | 0 / 1,867 | Not recognised | Unsupported | Requires another authoritative source |
| Facilities / outdoor space | None | 0 / 1,867 | Not recognised | Unsupported | Requires structured facility data or sourced documents |
| Special-needs support | None | 0 / 1,867 | Not recognised | Unsupported | Requires verified programme and accessibility data |

## Evidence details

### Strong structured evidence

- Care level is derived from actual service rows and is appropriate as a hard eligibility constraint.
- Language coverage is high, but the field only establishes that a second language is offered. It does not prove bilingual immersion, teaching intensity, or instructional quality.
- SPARK and transport contain explicit `Yes`/`No` values for every school.
- Full-day operating hours are available for 96.5% of schools.

### Partial or potentially misleading evidence

- Operator scheme is populated for 698 Anchor Operator and 382 Partner Operator records. The remaining 787 records need an explicit distinction between “not in a scheme” and “unknown”.
- Food descriptions are nuanced. The current scorer treats both `halal` and `no pork` as satisfying a halal preference. “No pork/no lard” is not equivalent to MUIS halal certification, so this can produce misleading matches.
- `base_fee` is the minimum fee across a school's service menu. It may refer to a different care level, citizenship category, or service schedule from the user's actual case.
- Location evidence is absent for 348 records. Distance-based ranking therefore cannot provide complete coverage without location enrichment.

### Weak pedagogy evidence

Pedagogy and philosophy are inferred only from keywords in the centre name:

- Montessori: 77 records
- Play-based: 15 records
- Bilingual: 2 records
- Reggio Emilia: 0 records
- General: 1,773 records

`General` should be interpreted as “no specific pedagogy detected in the name”, not evidence of a general teaching approach. Consequently, absence of a Montessori or play-based label is not reliable negative evidence.

## Current product mismatches

1. The chat introduction says users can mention “atmosphere”, but Stage 1 has no atmosphere evidence.
2. Natural descriptions such as hands-on, child-led, few worksheets, and primary-school readiness cannot currently be verified against school data.
3. The recognizer accepts Reggio Emilia, but the current dataset contains no Reggio-labelled record.
4. `Bilingual` is treated as a pedagogy label while specific offered languages are stored separately. These concepts should not be conflated.
5. Missing pedagogy evidence receives partial scoring credit, which can make the match percentage look more certain than the evidence supports.
6. Halal matching currently conflates certification with no-pork/no-lard food policies.

## Phase 1 recommendation

Use three evidence classes in the future preference schema:

- `supported`: care level, offered language, SPARK, transport, and full-day care;
- `partially_supported`: operator scheme, food policy, fee, distance, vacancy, and name-inferred pedagogy; and
- `unsupported`: hands-on learning, child-led learning, worksheet intensity, primary-school readiness, atmosphere, class size, facilities, and special-needs support.

An LLM may understand all three classes, but it should only convert supported attributes into definitive filters. Partially supported attributes should carry an evidence warning, and unsupported attributes should be retained for conversation while explicitly excluded from ranking until new sources are added.

## Next implementation step

Phase 2 should define a validated preference schema containing:

- canonical attribute and value;
- importance (`required` or `preferred`);
- extraction confidence;
- evidence class (`supported`, `partially_supported`, or `unsupported`);
- school property used for matching; and
- any clarification or evidence warning shown to the user.
