# KinderCompass development benchmark review

## Dataset summary

- **Split:** development
- **Dataset kind:** generated_synthetic_scenarios
- **Benchmark ID / version:** kindercompass-real-snapshot-template-scenarios / 20261018T134044Z
- **Cases:** 30
- **Generation method:** deterministic_templates; template version fictional-family-templates-v1
- **LLM use:** False (model field: —)
- **Frozen school snapshot:** 1867 joined schools
- **Snapshot SHA-256:** 037a6ab974c4c88780c152643a2aa7c2ca323d2001f6f56cd5022bb39d039cbe
- **Catalogue SHA-256:** 1017d16b7b293f0daf0d133e093ad35cb1213d132b7c27e4c823f1a5365a052e
- **Policy SHA-256:** e9f0c6ad063bbefa05438dc8a8865beba539a89412f8af2c551bfa0b70c55e3c

### Limitations and reading notes

Reviewer-supplied grades and provisional reference orders are now stored in the benchmark JSON. They are recorded as provided and have not been independently audited.

- Family scenarios are fictional, deterministic template inputs. Preschool names and records below are copied from each case’s frozen school records.
- Candidate selection came from the frozen snapshot; candidate retrieval status is not_executed, so the per-case Stage 1 retrieval query and retrieval recall were not tested.
- All 120 frozen-candidate pairs have reviewer-supplied relevance grades. Reference orders are provisional. The judgments are not independently audited and do not establish recommendation quality.
- Rankings and score fields are saved production evaluation outputs. This document does not recompute or reinterpret them.
- Rank numbers are the one-based position in the saved stage1_ranking array. Not returned means the candidate ID is absent from that array.
- The Stage 1 scorer defines match_score as the weighted match score over verifiable preferences (0–100); profile_confidence as evidence weight divided by requested weight (0–1); combined_score as the square root of match score times confidence expressed on a 0–100 scale. Hard-constraint labels are shown as saved: pass, fail, or unknown.
- Stage 2 fields are copied as recorded; they are production calculation outputs, not independent verification of school policy or fees.

## Cases

### 01. development-01-f930a3f1f8

**Scenario:** Deterministic fictional family template development 01: explores care_level and full_day preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2024-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 2500.0 |
| Citizenship category | SC |
| Requested programme | full_day |
| Working hours per month | 0.0 |
| Household size | 2 |
| Non-earning dependants | 0 |
| Special approval | false |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| level | Nursery (4 yrs old) |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| full_day | true | 4 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| care_level | Nursery (4 yrs old) | required | 1.0 | supported |
| full_day | true | high_priority | 1.0 | supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | IMAN CHILDCARE (SIMEI) PTE. LTD. (CENTRE:PT8501) | 100.0 | 1.0 | 100.0 | pass | {"eligible": true, "eligible_level": "Playgroup (18 mths to 2 yrs old)", "fee_before_subsidy": 1050.0, "net_monthly_fee": 900.0, "programme_id": "full_day", "status": "estimated"} |
| 2 | Little Learners Childcare Ltd (CENTRE:RC0810) | 100.0 | 1.0 | 100.0 | pass | {"eligible": true, "eligible_level": "Playgroup (18 mths to 2 yrs old)", "fee_before_subsidy": 790.0, "net_monthly_fee": 640.0, "programme_id": "full_day", "status": "estimated"} |
| 3 | IYAD PERDAUS CHILD DEVELOPMENT (CENTRE:RC1746) | 100.0 | 1.0 | 100.0 | pass | {"eligible": true, "eligible_level": "Playgroup (18 mths to 2 yrs old)", "fee_before_subsidy": 650.0, "net_monthly_fee": 500.0, "programme_id": "full_day", "status": "estimated"} |
| 4 | SUNFLOWER PRESCHOOL @ FRANKEL PTE LTD (CENTRE:PT9255) | 0.0 | 0.0 | 0.0 | pass | {"eligible": true, "eligible_level": "Playgroup (18 mths to 2 yrs old)", "fee_before_subsidy": 650.0, "net_monthly_fee": 500.0, "programme_id": "full_day", "status": "estimated"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:RC0810 | Little Learners Childcare Ltd | 0 | Same level mismatch; full-day matches. |
| CENTRE:PT9255 | SUNFLOWER PRESCHOOL @ FRANKEL PTE LTD | 0 | Same level mismatch; full-day matches, but no further evidence distinguishes it. |
| CENTRE:RC1746 | IYAD PERDAUS CHILD DEVELOPMENT | 0 | Same level mismatch; full-day matches. |
| CENTRE:PT8501 | IMAN CHILDCARE (SIMEI) PTE. LTD. | 0 | Playgroup conflicts with required Nursery. |

**Provisional reference order (ties preserved):** 1: IMAN CHILDCARE (SIMEI) PTE. LTD. (CENTRE:PT8501) = SUNFLOWER PRESCHOOL @ FRANKEL PTE LTD (CENTRE:PT9255) = Little Learners Childcare Ltd (CENTRE:RC0810) = IYAD PERDAUS CHILD DEVELOPMENT (CENTRE:RC1746)

**Reviewer rationale:** Tie all four: the evidence does not justify a meaningful distinction once the Nursery requirement is applied.

---
### 02. development-02-06fdd40598

**Scenario:** Deterministic fictional family template development 02: explores language and pedagogy preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2023-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 3500.0 |
| Citizenship category | SPR |
| Requested programme | half_day |
| Working hours per month | 56.0 |
| Household size | 3 |
| Non-earning dependants | 1 |
| Special approval | true |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| None recorded | — |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| language:Malay | Malay | 4 | true |
| pedagogy | Play-based | 3 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| language | Malay | high_priority | 1.0 | supported |
| pedagogy | Play-based | preferred | 1.0 | partially_supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | STAR LEARNERS @ BISHAN CENTRAL PTE. LTD. (CENTRE:PT8767) | 0.0 | 0.67 | 0.0 | unknown | {"eligible": true, "eligible_level": "Pre-Nursery (3 yrs old)", "fee_before_subsidy": 1330.0, "net_monthly_fee": 1330.0, "programme_id": "half_day_am", "status": "estimated"} |
| 2 | Little Footprints Preschool Pte Ltd (CENTRE:PT9158) | 0.0 | 0.67 | 0.0 | unknown | {"eligible": true, "eligible_level": "Pre-Nursery (3 yrs old)", "fee_before_subsidy": 1300.0, "net_monthly_fee": 1300.0, "programme_id": "full_day", "status": "estimated"} |
| 3 | MY WORLD PRESCHOOL LTD. (CENTRE:YM0164) | 0.0 | 0.67 | 0.0 | unknown | {"eligible": true, "eligible_level": "Pre-Nursery (3 yrs old)", "fee_before_subsidy": 630.0, "net_monthly_fee": 630.0, "programme_id": "half_day_am", "status": "estimated"} |
| 4 | TPBC KINDERGARTEN (CENTRE:RC1832) | 0.0 | 0.0 | 0.0 | unknown | {"eligible": false, "eligible_level": "Pre-Nursery (3 yrs old)", "fee_before_subsidy": null, "net_monthly_fee": null, "programme_id": null, "status": "fee_unavailable"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:RC1832 | TPBC KINDERGARTEN | 0 | Recorded as ineligible, with fees unavailable. |
| CENTRE:PT9158 | Little Footprints Preschool Pte Ltd | 1 | Full-day programme differs from the requested half-day. |
| CENTRE:PT8767 | STAR LEARNERS @ BISHAN CENTRAL PTE. LTD. | 1 | Half-day programme matches; Malay and pedagogy unverified. |
| CENTRE:YM0164 | MY WORLD PRESCHOOL LTD. | 1 | Half-day programme matches; Malay and pedagogy unverified. |

**Provisional reference order (ties preserved):** 1: STAR LEARNERS @ BISHAN CENTRAL PTE. LTD. (CENTRE:PT8767) = MY WORLD PRESCHOOL LTD. (CENTRE:YM0164) → 3: Little Footprints Preschool Pte Ltd (CENTRE:PT9158) → 4: TPBC KINDERGARTEN (CENTRE:RC1832)

**Reviewer rationale:** My World and Star Learners tied first; Little Footprints next; TPBC last. No evidence confirms Malay or play-based provision.

---
### 03. development-03-577bdb8e20

**Scenario:** Deterministic fictional family template development 03: explores spark_certified and transport preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2022-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 4500.0 |
| Citizenship category | Others |
| Requested programme | flexi_care_1 |
| Working hours per month | 120.0 |
| Household size | 4 |
| Non-earning dependants | 2 |
| Special approval | false |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| None recorded | — |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| spark_certified | true | 3 | true |
| transport | true | 1 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| spark_certified | true | preferred | 1.0 | supported |
| transport | true | nice_to_have | 1.0 | supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | MY FIRST SKOOL (CENTRE:NT0547) | 85.7 | 1.0 | 92.6 | unknown | {"eligible": true, "eligible_level": "Nursery (4 yrs old)", "fee_before_subsidy": 592.51, "net_monthly_fee": 592.51, "programme_id": "flexi_care_1", "status": "estimated"} |
| 2 | ORION PRESCHOOL (CENTRE:PT9145) | 14.3 | 1.0 | 37.8 | unknown | {"eligible": true, "eligible_level": "Nursery (4 yrs old)", "fee_before_subsidy": 1080.0, "net_monthly_fee": 1080.0, "programme_id": "half_day_am", "status": "estimated"} |
| 3 | SHEFFIELD KIDSWORLD (CCK) PTE. LTD. (CENTRE:PT6690) | 0.0 | 1.0 | 0.0 | unknown | {"eligible": true, "eligible_level": "Nursery (4 yrs old)", "fee_before_subsidy": 650.0, "net_monthly_fee": 650.0, "programme_id": "half_day_am", "status": "estimated"} |
| 4 | ESHKOL VALLEY @ SENGKANG PEARL PTE. LTD. (CENTRE:PT8834) | 0.0 | 1.0 | 0.0 | unknown | {"eligible": true, "eligible_level": "Nursery (4 yrs old)", "fee_before_subsidy": 960.0, "net_monthly_fee": 960.0, "programme_id": "half_day_am", "status": "estimated"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:NT0547 | MY FIRST SKOOL | 2 | Flexi-care programme matches; certification and transport remain unverified. |
| CENTRE:PT6690 | SHEFFIELD KIDSWORLD (CCK) PTE. LTD. | 1 | Half-day programme differs; no evidence distinguishes it from Orion. |
| CENTRE:PT8834 | ESHKOL VALLEY @ SENGKANG PEARL PTE. LTD. | 1 | Half-day programme differs; certification and transport unverified. |
| CENTRE:PT9145 | ORION PRESCHOOL | 1 | Half-day programme differs; certification and transport unverified. |

**Provisional reference order (ties preserved):** 1: MY FIRST SKOOL (CENTRE:NT0547) → 2: SHEFFIELD KIDSWORLD (CCK) PTE. LTD. (CENTRE:PT6690) = ESHKOL VALLEY @ SENGKANG PEARL PTE. LTD. (CENTRE:PT8834) = ORION PRESCHOOL (CENTRE:PT9145)

**Reviewer rationale:** My First Skool ranks first for the flexi-care match; the three half-day options are tied because evidence does not distinguish them.

---
### 04. development-04-eec8d83919

**Scenario:** Deterministic fictional family template development 04: explores transport and operator_scheme preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2021-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 5500.0 |
| Citizenship category | SC |
| Requested programme | flexi_care_2 |
| Working hours per month | 160.0 |
| Household size | 5 |
| Non-earning dependants | 3 |
| Special approval | true |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| None recorded | — |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| transport | false | 1 | true |
| operator_scheme | Anchor Operator Scheme | 5 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| transport | false | nice_to_have | 1.0 | supported |
| operator_scheme | Anchor Operator Scheme | required | 1.0 | partially_supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | AWWA LTD. (CENTRE:RC1776) | 100.0 | 0.05 | 21.8 | unknown | {"eligible": true, "eligible_level": "Kindergarten 1 (5 yrs old)", "fee_before_subsidy": 650.0, "net_monthly_fee": 650.0, "programme_id": "half_day_am", "status": "manual_review"} |
| 2 | MULBERRY LEARNING CENTRE ALEXANDRA PTE LTD (CENTRE:PT9196) | 0.0 | 0.05 | 0.0 | unknown | {"eligible": true, "eligible_level": "Kindergarten 1 (5 yrs old)", "fee_before_subsidy": 1800.0, "net_monthly_fee": 1800.0, "programme_id": "half_day_am", "status": "manual_review"} |
| 3 | BETHESDA CHAPEL KINDERGARTEN (CENTRE:RC1884) | 0.0 | 0.05 | 0.0 | unknown | {"eligible": false, "eligible_level": "Kindergarten 1 (5 yrs old)", "fee_before_subsidy": null, "net_monthly_fee": null, "programme_id": null, "status": "fee_unavailable"} |
| 4 | PCF SPARKLETOTS PRESCHOOL @ NANYANG BLK 825 (CC) (CENTRE:ST0155) | 0.0 | 0.0 | 0.0 | unknown | {"eligible": true, "eligible_level": "Kindergarten 1 (5 yrs old)", "fee_before_subsidy": 610.0, "net_monthly_fee": 610.0, "programme_id": "full_day", "status": "manual_review"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:ST0155 | PCF SPARKLETOTS PRESCHOOL @ NANYANG BLK 825 (CC) | 1 | Scheme requirement not confirmed; full-day differs from flexi-care. |
| CENTRE:RC1776 | AWWA LTD. | 1 | Scheme participation unverified; manual review required. |
| CENTRE:PT9196 | MULBERRY LEARNING CENTRE ALEXANDRA PTE LTD | 1 | Scheme participation unverified; expensive relative to the other listed fees. |
| CENTRE:RC1884 | BETHESDA CHAPEL KINDERGARTEN | 0 | Recorded as ineligible, with fees unavailable. |

**Provisional reference order (ties preserved):** 1: AWWA LTD. (CENTRE:RC1776) → 2: MULBERRY LEARNING CENTRE ALEXANDRA PTE LTD (CENTRE:PT9196) → 3: PCF SPARKLETOTS PRESCHOOL @ NANYANG BLK 825 (CC) (CENTRE:ST0155) → 4: BETHESDA CHAPEL KINDERGARTEN (CENTRE:RC1884)

**Reviewer rationale:** Provisional order only: the first three cannot be confidently distinguished on Anchor Operator Scheme eligibility.

---
### 05. development-05-af51d35799

**Scenario:** Deterministic fictional family template development 05: explores full_day and care_level preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2020-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 6500.0 |
| Citizenship category | SPR |
| Requested programme | flexi_care_3 |
| Working hours per month | 0.0 |
| Household size | 2 |
| Non-earning dependants | 1 |
| Special approval | false |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| level | Nursery (4 yrs old) |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| full_day | true | 5 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| care_level | Nursery (4 yrs old) | high_priority | 1.0 | supported |
| full_day | true | required | 1.0 | supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | MY FIRST SKOOL (CENTRE:NT0509) | 100.0 | 1.0 | 100.0 | pass | {"eligible": true, "eligible_level": "Kindergarten 2 (6 yrs old)", "fee_before_subsidy": 493.76, "net_monthly_fee": 493.76, "programme_id": "flexi_care_1", "status": "estimated"} |
| 2 | MY FIRST SKOOL (CENTRE:NT0545) | 100.0 | 1.0 | 100.0 | pass | {"eligible": true, "eligible_level": "Kindergarten 2 (6 yrs old)", "fee_before_subsidy": 493.76, "net_monthly_fee": 493.76, "programme_id": "flexi_care_1", "status": "estimated"} |
| 3 | SUNFLOWER PRESCHOOL @ WEST ROCK PTE LTD (CENTRE:PT9682) | 100.0 | 1.0 | 100.0 | pass | {"eligible": true, "eligible_level": "Kindergarten 2 (6 yrs old)", "fee_before_subsidy": 700.0, "net_monthly_fee": 700.0, "programme_id": "half_day_am", "status": "estimated"} |
| 4 | PCF Sparkletots Preschool @ Tampines West Blk 151 (EY) (CENTRE:ST0165) | 100.0 | 1.0 | 100.0 | pass | {"eligible": false, "eligible_level": "Kindergarten 2 (6 yrs old)", "fee_before_subsidy": null, "net_monthly_fee": null, "programme_id": null, "status": "ineligible"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:NT0545 | MY FIRST SKOOL | 0 | Same level mismatch; same provider does not establish suitability. |
| CENTRE:NT0509 | MY FIRST SKOOL | 0 | K2 conflicts with the required Nursery level. |
| CENTRE:ST0165 | PCF Sparkletots Preschool @ Tampines West Blk 151 (EY) | 0 | Recorded as ineligible; K2 also conflicts with Nursery. |
| CENTRE:PT9682 | SUNFLOWER PRESCHOOL @ WEST ROCK PTE LTD | 0 | K2 and half-day conflict with the stated requirements. |

**Provisional reference order (ties preserved):** 1: MY FIRST SKOOL (CENTRE:NT0509) = MY FIRST SKOOL (CENTRE:NT0545) = SUNFLOWER PRESCHOOL @ WEST ROCK PTE LTD (CENTRE:PT9682) → 4: PCF Sparkletots Preschool @ Tampines West Blk 151 (EY) (CENTRE:ST0165)

**Reviewer rationale:** The first three are tied as unsuitable for the required level; PCF is last because it is also recorded as ineligible.

---
### 06. development-06-81c7801472

**Scenario:** Deterministic fictional family template development 06: explores operator_scheme and transport preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2024-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 7500.0 |
| Citizenship category | Others |
| Requested programme | full_day |
| Working hours per month | 56.0 |
| Household size | 3 |
| Non-earning dependants | 1 |
| Special approval | true |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| None recorded | — |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| operator_scheme | Anchor Operator Scheme | 4 | true |
| transport | false | 3 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| operator_scheme | Anchor Operator Scheme | high_priority | 1.0 | partially_supported |
| transport | false | preferred | 1.0 | supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | MOE KINDERGARTEN @ WATERWAY (CENTRE:KM0018) | 100.0 | 0.33 | 57.7 | unknown | {"eligible": false, "eligible_level": "Playgroup (18 mths to 2 yrs old)", "fee_before_subsidy": null, "net_monthly_fee": null, "programme_id": null, "status": "ineligible"} |
| 2 | MAPLEBEAR WHIZ KIDS PTE. LTD. (CENTRE:PT9466) | 100.0 | 0.33 | 57.7 | unknown | {"eligible": true, "eligible_level": "Playgroup (18 mths to 2 yrs old)", "fee_before_subsidy": 1800.0, "net_monthly_fee": 1800.0, "programme_id": "full_day", "status": "estimated"} |
| 3 | Small Wonder Preschool Sengkang (CENTRE:PT9644) | 100.0 | 0.33 | 57.7 | unknown | {"eligible": true, "eligible_level": "Playgroup (18 mths to 2 yrs old)", "fee_before_subsidy": 1600.0, "net_monthly_fee": 1600.0, "programme_id": "full_day", "status": "estimated"} |
| 4 | PCF Sparkletots Preschool @ Nee Soon South Blk 879 (EY) (CENTRE:ST0133) | 100.0 | 0.33 | 57.7 | unknown | {"eligible": true, "eligible_level": "Playgroup (18 mths to 2 yrs old)", "fee_before_subsidy": 1172.0, "net_monthly_fee": 1172.0, "programme_id": "full_day", "status": "estimated"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:ST0133 | PCF Sparkletots Preschool @ Nee Soon South Blk 879 (EY) | 2 | Full-day matches; scheme status still needs verification. |
| CENTRE:KM0018 | MOE KINDERGARTEN @ WATERWAY | 0 | Recorded as ineligible. |
| CENTRE:PT9466 | MAPLEBEAR WHIZ KIDS PTE. LTD. | 1 | Full-day matches; scheme status unverified. |
| CENTRE:PT9644 | Small Wonder Preschool Sengkang | 1 | Full-day matches; scheme status unverified. |

**Provisional reference order (ties preserved):** 1: MAPLEBEAR WHIZ KIDS PTE. LTD. (CENTRE:PT9466) = Small Wonder Preschool Sengkang (CENTRE:PT9644) = PCF Sparkletots Preschool @ Nee Soon South Blk 879 (EY) (CENTRE:ST0133) → 4: MOE KINDERGARTEN @ WATERWAY (CENTRE:KM0018)

**Reviewer rationale:** PCF, MapleBear, and Small Wonder are tied provisionally; verify PCF scheme participation before treating its higher grade as final.

---
### 07. development-07-d64bff59ba

**Scenario:** Deterministic fictional family template development 07: explores food and pedagogy preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2023-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 2500.0 |
| Citizenship category | SC |
| Requested programme | half_day |
| Working hours per month | 120.0 |
| Household size | 4 |
| Non-earning dependants | 1 |
| Special approval | false |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| None recorded | — |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| food | no_pork | 3 | true |
| pedagogy | Reggio Emilia | 1 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| food | no_pork | preferred | 1.0 | partially_supported |
| pedagogy | Reggio Emilia | nice_to_have | 1.0 | partially_supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | SUNFLOWER KINDERHUB PTE LTD (CENTRE:PT8364) | 0.0 | 0.0 | 0.0 | unknown | {"eligible": true, "eligible_level": "Pre-Nursery (3 yrs old)", "fee_before_subsidy": 490.0, "net_monthly_fee": 105.0, "programme_id": "half_day_am", "status": "estimated"} |
| 2 | Small Wonder Preschool Punggol (CENTRE:PT9066) | 0.0 | 0.0 | 0.0 | unknown | {"eligible": true, "eligible_level": "Pre-Nursery (3 yrs old)", "fee_before_subsidy": 650.0, "net_monthly_fee": 3.0, "programme_id": "full_day", "status": "estimated"} |
| 3 | Skool4kidz Preschool (CENTRE:SK0009) | 0.0 | 0.0 | 0.0 | unknown | {"eligible": true, "eligible_level": "Pre-Nursery (3 yrs old)", "fee_before_subsidy": 460.0, "net_monthly_fee": 75.0, "programme_id": "half_day_am", "status": "estimated"} |
| 4 | MY WORLD PRESCHOOL LTD. (CENTRE:YM0169) | 0.0 | 0.0 | 0.0 | unknown | {"eligible": true, "eligible_level": "Pre-Nursery (3 yrs old)", "fee_before_subsidy": 460.0, "net_monthly_fee": 75.0, "programme_id": "half_day_am", "status": "estimated"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:PT9066 | Small Wonder Preschool Punggol | 1 | Full-day differs; no evidence confirms food or pedagogy. |
| CENTRE:YM0169 | MY WORLD PRESCHOOL LTD. | 1 | Half-day matches; food and pedagogy are unverified. |
| CENTRE:PT8364 | SUNFLOWER KINDERHUB PTE LTD | 1 | Half-day matches; food and pedagogy are unverified. |
| CENTRE:SK0009 | Skool4kidz Preschool | 1 | Half-day matches; food and pedagogy are unverified. |

**Provisional reference order (ties preserved):** 1: SUNFLOWER KINDERHUB PTE LTD (CENTRE:PT8364) = Skool4kidz Preschool (CENTRE:SK0009) = MY WORLD PRESCHOOL LTD. (CENTRE:YM0169) → 4: Small Wonder Preschool Punggol (CENTRE:PT9066)

**Reviewer rationale:** The three half-day options are tied; Small Wonder is below them due to the programme mismatch.

---
### 08. development-08-d825c8b042

**Scenario:** Deterministic fictional family template development 08: explores pedagogy and language preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2022-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 3500.0 |
| Citizenship category | SPR |
| Requested programme | flexi_care_1 |
| Working hours per month | 160.0 |
| Household size | 5 |
| Non-earning dependants | 1 |
| Special approval | true |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| language | Chinese |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| pedagogy | Play-based | 1 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| language | Chinese | required | 1.0 | supported |
| pedagogy | Play-based | nice_to_have | 1.0 | partially_supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | MONTESSORI @ GRACELAND PTE LTD (CENTRE:PT4910) | 0.0 | 0.0 | 0.0 | pass | {"eligible": true, "eligible_level": "Nursery (4 yrs old)", "fee_before_subsidy": 920.0, "net_monthly_fee": 920.0, "programme_id": "flexi_care_1", "status": "estimated"} |
| 2 | Small Wonder Preschool Khatib (CENTRE:PT9160) | 0.0 | 0.0 | 0.0 | pass | {"eligible": true, "eligible_level": "Nursery (4 yrs old)", "fee_before_subsidy": 0.0, "net_monthly_fee": 0.0, "programme_id": "half_day_am", "status": "estimated"} |
| 3 | MAPLEBEAR SMARTCUBS PTE. LTD. (CENTRE:PT9297) | 0.0 | 0.0 | 0.0 | pass | {"eligible": true, "eligible_level": "Nursery (4 yrs old)", "fee_before_subsidy": 1380.0, "net_monthly_fee": 1380.0, "programme_id": "half_day_am", "status": "estimated"} |
| 4 | Cambridge @ Midwood Pte. Ltd (CENTRE:PT9896) | 0.0 | 0.0 | 0.0 | pass | {"eligible": true, "eligible_level": "Nursery (4 yrs old)", "fee_before_subsidy": 1650.0, "net_monthly_fee": 1650.0, "programme_id": "half_day_am", "status": "estimated"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:PT9297 | MAPLEBEAR SMARTCUBS PTE. LTD. | 1 | Half-day differs; Chinese provision is unverified. |
| CENTRE:PT4910 | MONTESSORI @ GRACELAND PTE LTD | 1 | Flexi-care matches; Chinese provision is unverified. |
| CENTRE:PT9896 | Cambridge @ Midwood Pte. Ltd | 1 | Half-day differs; Chinese provision is unverified. |
| CENTRE:PT9160 | Small Wonder Preschool Khatib | 1 | Half-day differs; Chinese provision is unverified. |

**Provisional reference order (ties preserved):** 1: MONTESSORI @ GRACELAND PTE LTD (CENTRE:PT4910) → 2: Small Wonder Preschool Khatib (CENTRE:PT9160) = MAPLEBEAR SMARTCUBS PTE. LTD. (CENTRE:PT9297) = Cambridge @ Midwood Pte. Ltd (CENTRE:PT9896)

**Reviewer rationale:** Montessori @ Graceland ranks first for the flexi-care match; the remaining three half-day candidates are tied.

---
### 09. development-09-46f9def2eb

**Scenario:** Deterministic fictional family template development 09: explores care_level and full_day preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2021-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 4500.0 |
| Citizenship category | Others |
| Requested programme | flexi_care_2 |
| Working hours per month | 0.0 |
| Household size | 2 |
| Non-earning dependants | 2 |
| Special approval | false |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| level | Pre-Nursery (3 yrs old) |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| full_day | true | 4 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| care_level | Pre-Nursery (3 yrs old) | required | 1.0 | supported |
| full_day | true | high_priority | 1.0 | supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | MY FIRST SKOOL (CENTRE:NT0390) | 100.0 | 1.0 | 100.0 | pass | {"eligible": true, "eligible_level": "Kindergarten 1 (5 yrs old)", "fee_before_subsidy": 592.51, "net_monthly_fee": 592.51, "programme_id": "flexi_care_1", "status": "estimated"} |
| 2 | Sunflower Preschool @ Chevrons (CENTRE:PT9455) | 100.0 | 1.0 | 100.0 | pass | {"eligible": true, "eligible_level": "Kindergarten 1 (5 yrs old)", "fee_before_subsidy": 700.0, "net_monthly_fee": 700.0, "programme_id": "half_day_am", "status": "estimated"} |
| 3 | THE ORANGE ACADEMY (YISHUN) PTE LTD (CENTRE:PT9470) | 100.0 | 1.0 | 100.0 | pass | {"eligible": true, "eligible_level": "Kindergarten 1 (5 yrs old)", "fee_before_subsidy": 1100.0, "net_monthly_fee": 1100.0, "programme_id": "half_day_am", "status": "estimated"} |
| 4 | SUNFLOWER PRESCHOOL @ HOUGANG CC (PRIVATE LIMITED) (CENTRE:PT9535) | 0.0 | 0.0 | 0.0 | pass | {"eligible": true, "eligible_level": "Kindergarten 1 (5 yrs old)", "fee_before_subsidy": 772.02, "net_monthly_fee": 772.02, "programme_id": "half_day_am", "status": "estimated"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:NT0390 | MY FIRST SKOOL | 0 | K1 conflicts with Pre-Nursery; flexi-care variant also differs. |
| CENTRE:PT9470 | THE ORANGE ACADEMY (YISHUN) PTE LTD | 0 | K1 and half-day conflict with the requirements. |
| CENTRE:PT9535 | SUNFLOWER PRESCHOOL @ HOUGANG CC (PRIVATE LIMITED) | 0 | K1 and half-day conflict; saved score does not resolve the mismatch. |
| CENTRE:PT9455 | Sunflower Preschool @ Chevrons | 0 | K1 and half-day conflict with the requirements. |

**Provisional reference order (ties preserved):** 1: MY FIRST SKOOL (CENTRE:NT0390) = Sunflower Preschool @ Chevrons (CENTRE:PT9455) = THE ORANGE ACADEMY (YISHUN) PTE LTD (CENTRE:PT9470) = SUNFLOWER PRESCHOOL @ HOUGANG CC (PRIVATE LIMITED) (CENTRE:PT9535)

**Reviewer rationale:** Tie all four as unsuitable for the required Pre-Nursery level.

---
### 10. development-10-3a5ae7153e

**Scenario:** Deterministic fictional family template development 10: explores language and pedagogy preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2020-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 5500.0 |
| Citizenship category | SC |
| Requested programme | flexi_care_3 |
| Working hours per month | 56.0 |
| Household size | 3 |
| Non-earning dependants | 1 |
| Special approval | true |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| None recorded | — |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| language:Chinese | Chinese | 4 | true |
| pedagogy | Play-based | 3 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| language | Chinese | high_priority | 1.0 | supported |
| pedagogy | Play-based | preferred | 1.0 | partially_supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | MY FIRST SKOOL (CENTRE:NT0340) | 100.0 | 0.67 | 81.6 | unknown | {"eligible": true, "eligible_level": "Kindergarten 2 (6 yrs old)", "fee_before_subsidy": 430.92, "net_monthly_fee": 430.92, "programme_id": "flexi_care_1", "status": "manual_review"} |
| 2 | CARPE DIEM YOUNG MINDS PTE. LTD. (CENTRE:PT8461) | 100.0 | 0.67 | 81.6 | unknown | {"eligible": true, "eligible_level": "Kindergarten 2 (6 yrs old)", "fee_before_subsidy": 490.0, "net_monthly_fee": 490.0, "programme_id": "half_day_am", "status": "manual_review"} |
| 3 | SUNFLOWER PRESCHOOL @ BALESTIER PTE. LTD. (CENTRE:PT8922) | 100.0 | 0.67 | 81.6 | unknown | {"eligible": true, "eligible_level": "Kindergarten 2 (6 yrs old)", "fee_before_subsidy": 490.0, "net_monthly_fee": 490.0, "programme_id": "half_day_am", "status": "manual_review"} |
| 4 | CITIKIDS EDVENTURE PTE. LTD. (CENTRE:PT8494) | 0.0 | 0.0 | 0.0 | unknown | {"eligible": true, "eligible_level": "Kindergarten 2 (6 yrs old)", "fee_before_subsidy": 750.0, "net_monthly_fee": 750.0, "programme_id": "half_day_am", "status": "manual_review"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:PT8461 | CARPE DIEM YOUNG MINDS PTE. LTD. | 1 | Half-day differs; language and pedagogy unverified. |
| CENTRE:PT8922 | SUNFLOWER PRESCHOOL @ BALESTIER PTE. LTD. | 1 | Half-day differs; language and pedagogy unverified. |
| CENTRE:PT8494 | CITIKIDS EDVENTURE PTE. LTD. | 1 | Half-day differs; no evidence distinguishes it from the other half-day candidates. |
| CENTRE:NT0340 | MY FIRST SKOOL | 1 | Flexi-care matches better than half-day; language and pedagogy remain unverified. |

**Provisional reference order (ties preserved):** 1: MY FIRST SKOOL (CENTRE:NT0340) → 2: CARPE DIEM YOUNG MINDS PTE. LTD. (CENTRE:PT8461) = CITIKIDS EDVENTURE PTE. LTD. (CENTRE:PT8494) = SUNFLOWER PRESCHOOL @ BALESTIER PTE. LTD. (CENTRE:PT8922)

**Reviewer rationale:** My First Skool ranks first for the flexi-care match; the three half-day candidates are tied.

---
### 11. development-11-278bcec5e0

**Scenario:** Deterministic fictional family template development 11: explores spark_certified and transport preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2024-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 6500.0 |
| Citizenship category | SPR |
| Requested programme | full_day |
| Working hours per month | 120.0 |
| Household size | 4 |
| Non-earning dependants | 0 |
| Special approval | false |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| None recorded | — |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| spark_certified | true | 3 | true |
| transport | true | 1 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| spark_certified | true | preferred | 1.0 | supported |
| transport | true | nice_to_have | 1.0 | supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | MY FIRST SKOOL (CENTRE:NT0550) | 85.7 | 1.0 | 92.6 | unknown | {"eligible": true, "eligible_level": "Playgroup (18 mths to 2 yrs old)", "fee_before_subsidy": 835.0, "net_monthly_fee": 835.0, "programme_id": "full_day", "status": "estimated"} |
| 2 | Little Footprints Preschool @ Boon Keng Pte Ltd (CENTRE:PT9421) | 85.7 | 1.0 | 92.6 | unknown | {"eligible": true, "eligible_level": "Playgroup (18 mths to 2 yrs old)", "fee_before_subsidy": 1300.0, "net_monthly_fee": 1300.0, "programme_id": "full_day", "status": "estimated"} |
| 3 | PCF Sparkletots Preschool @ Bukit Batok Blk 446 (EY) (CENTRE:ST0374) | 85.7 | 1.0 | 92.6 | unknown | {"eligible": true, "eligible_level": "Playgroup (18 mths to 2 yrs old)", "fee_before_subsidy": 835.0, "net_monthly_fee": 835.0, "programme_id": "full_day", "status": "estimated"} |
| 4 | LITTLE DOLPHINS PLAYSKOOL (CENTRE:RC1745) | 0.0 | 1.0 | 0.0 | unknown | {"eligible": true, "eligible_level": "Playgroup (18 mths to 2 yrs old)", "fee_before_subsidy": 800.0, "net_monthly_fee": 800.0, "programme_id": "full_day", "status": "estimated"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:PT9421 | Little Footprints Preschool @ Boon Keng Pte Ltd | 1 | Programme matches; certification and transport need evidence. |
| CENTRE:RC1745 | LITTLE DOLPHINS PLAYSKOOL | 1 | Programme matches; no evidence distinguishes it from the other candidates. |
| CENTRE:ST0374 | PCF Sparkletots Preschool @ Bukit Batok Blk 446 (EY) | 1 | Programme matches; certification and transport need evidence. |
| CENTRE:NT0550 | MY FIRST SKOOL | 1 | Programme matches; certification and transport need evidence. |

**Provisional reference order (ties preserved):** 1: MY FIRST SKOOL (CENTRE:NT0550) = Little Footprints Preschool @ Boon Keng Pte Ltd (CENTRE:PT9421) = LITTLE DOLPHINS PLAYSKOOL (CENTRE:RC1745) = PCF Sparkletots Preschool @ Bukit Batok Blk 446 (EY) (CENTRE:ST0374)

**Reviewer rationale:** Tie all four: provider names alone do not establish SPARK certification or transport.

---
### 12. development-12-b6624f5248

**Scenario:** Deterministic fictional family template development 12: explores transport and operator_scheme preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2023-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 7500.0 |
| Citizenship category | Others |
| Requested programme | half_day |
| Working hours per month | 160.0 |
| Household size | 5 |
| Non-earning dependants | 5 |
| Special approval | true |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| None recorded | — |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| transport | false | 1 | true |
| operator_scheme | Anchor Operator Scheme | 5 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| transport | false | nice_to_have | 1.0 | supported |
| operator_scheme | Anchor Operator Scheme | required | 1.0 | partially_supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | E-Bridge Pre-School Pte Ltd (CENTRE:EB0021) | 100.0 | 0.05 | 21.8 | unknown | {"eligible": true, "eligible_level": "Pre-Nursery (3 yrs old)", "fee_before_subsidy": 1125.0, "net_monthly_fee": 1125.0, "programme_id": "full_day", "status": "estimated"} |
| 2 | PCF Sparkletots Preschool @ Fengshan Blk 126 (DS) (CENTRE:ST0242) | 100.0 | 0.05 | 21.8 | unknown | {"eligible": true, "eligible_level": "Pre-Nursery (3 yrs old)", "fee_before_subsidy": 1172.0, "net_monthly_fee": 1172.0, "programme_id": "full_day", "status": "estimated"} |
| 3 | The Grange International Preschool (CENTRE:PT9787) | 0.0 | 0.05 | 0.0 | unknown | {"eligible": false, "eligible_level": "Pre-Nursery (3 yrs old)", "fee_before_subsidy": null, "net_monthly_fee": null, "programme_id": null, "status": "ineligible"} |
| 4 | PCF Sparkletots Preschool @ Kampong Chai Chee Blk 32 (CC) (CENTRE:ST0104) | 0.0 | 0.0 | 0.0 | unknown | {"eligible": true, "eligible_level": "Pre-Nursery (3 yrs old)", "fee_before_subsidy": 1172.0, "net_monthly_fee": 1172.0, "programme_id": "full_day", "status": "estimated"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:ST0104 | PCF Sparkletots Preschool @ Kampong Chai Chee Blk 32 (CC) | 1 | Full-day differs; scheme status still needs confirmation. |
| CENTRE:EB0021 | E-Bridge Pre-School Pte Ltd | 1 | Full-day differs; scheme status unverified. |
| CENTRE:PT9787 | The Grange International Preschool | 0 | Recorded as ineligible; fees unavailable. |
| CENTRE:ST0242 | PCF Sparkletots Preschool @ Fengshan Blk 126 (DS) | 1 | Full-day differs; scheme status still needs confirmation. |

**Provisional reference order (ties preserved):** 1: E-Bridge Pre-School Pte Ltd (CENTRE:EB0021) = PCF Sparkletots Preschool @ Kampong Chai Chee Blk 32 (CC) (CENTRE:ST0104) = PCF Sparkletots Preschool @ Fengshan Blk 126 (DS) (CENTRE:ST0242) → 4: The Grange International Preschool (CENTRE:PT9787)

**Reviewer rationale:** E-Bridge and the two PCF options are tied; The Grange is last because it is recorded as ineligible.

---
### 13. development-13-b166fdbd4f

**Scenario:** Deterministic fictional family template development 13: explores full_day and care_level preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2022-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 2500.0 |
| Citizenship category | SC |
| Requested programme | flexi_care_1 |
| Working hours per month | 0.0 |
| Household size | 2 |
| Non-earning dependants | 0 |
| Special approval | false |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| level | Pre-Nursery (3 yrs old) |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| full_day | true | 5 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| care_level | Pre-Nursery (3 yrs old) | high_priority | 1.0 | supported |
| full_day | true | required | 1.0 | supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | CHERIE HEARTS KIDZ CAMPUS PTE. LTD. (CENTRE:PT8617) | 100.0 | 1.0 | 100.0 | pass | {"eligible": true, "eligible_level": "Nursery (4 yrs old)", "fee_before_subsidy": 820.0, "net_monthly_fee": 765.0, "programme_id": "flexi_care_1", "status": "estimated"} |
| 2 | JUDE CHILD CARE AND CHILD DEVELOPMENT CENTRE (CENTRE:PT8831) | 100.0 | 1.0 | 100.0 | pass | {"eligible": true, "eligible_level": "Nursery (4 yrs old)", "fee_before_subsidy": 400.0, "net_monthly_fee": 345.0, "programme_id": "flexi_care_1", "status": "estimated"} |
| 3 | Little Olive Tree (CENTRE:PW0040) | 100.0 | 1.0 | 100.0 | pass | {"eligible": true, "eligible_level": "Nursery (4 yrs old)", "fee_before_subsidy": 490.0, "net_monthly_fee": 340.0, "programme_id": "half_day_am", "status": "estimated"} |
| 4 | PCF Sparkletots Preschool @ Jurong Central Blk 465 (KN) (CENTRE:ST0304) | 100.0 | 1.0 | 100.0 | pass | {"eligible": false, "eligible_level": "Nursery (4 yrs old)", "fee_before_subsidy": null, "net_monthly_fee": null, "programme_id": null, "status": "fee_unavailable"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:PT8617 | CHERIE HEARTS KIDZ CAMPUS PTE. LTD. | 0 | Nursery conflicts with required Pre-Nursery, although flexi-care matches. |
| CENTRE:PT8831 | JUDE CHILD CARE AND CHILD DEVELOPMENT CENTRE | 0 | Same level mismatch; flexi-care matches. |
| CENTRE:ST0304 | PCF Sparkletots Preschool @ Jurong Central Blk 465 (KN) | 0 | Same level mismatch and recorded as ineligible. |
| CENTRE:PW0040 | Little Olive Tree | 0 | Same level mismatch; half-day also differs. |

**Provisional reference order (ties preserved):** 1: CHERIE HEARTS KIDZ CAMPUS PTE. LTD. (CENTRE:PT8617) = JUDE CHILD CARE AND CHILD DEVELOPMENT CENTRE (CENTRE:PT8831) → 3: Little Olive Tree (CENTRE:PW0040) → 4: PCF Sparkletots Preschool @ Jurong Central Blk 465 (KN) (CENTRE:ST0304)

**Reviewer rationale:** Cherie Hearts and Jude are tied; Little Olive Tree and PCF follow due to additional mismatch/ineligibility.

---
### 14. development-14-834e5b5425

**Scenario:** Deterministic fictional family template development 14: explores operator_scheme and transport preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2021-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 3500.0 |
| Citizenship category | SPR |
| Requested programme | flexi_care_2 |
| Working hours per month | 56.0 |
| Household size | 3 |
| Non-earning dependants | 1 |
| Special approval | true |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| None recorded | — |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| operator_scheme | Anchor Operator Scheme | 4 | true |
| transport | false | 3 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| operator_scheme | Anchor Operator Scheme | high_priority | 1.0 | partially_supported |
| transport | false | preferred | 1.0 | supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | E-Bridge Pre-School Pte Ltd (CENTRE:EB0018) | 100.0 | 0.33 | 57.7 | unknown | {"eligible": true, "eligible_level": "Kindergarten 1 (5 yrs old)", "fee_before_subsidy": 835.0, "net_monthly_fee": 835.0, "programme_id": "full_day", "status": "estimated"} |
| 2 | Star Learners @ Woodlands 888 Pte Ltd (CENTRE:PT8512) | 100.0 | 0.33 | 57.7 | unknown | {"eligible": true, "eligible_level": "Kindergarten 1 (5 yrs old)", "fee_before_subsidy": 1330.0, "net_monthly_fee": 1330.0, "programme_id": "half_day_am", "status": "estimated"} |
| 3 | Silk Education Pte. Ltd. (CENTRE:PT9766) | 100.0 | 0.33 | 57.7 | unknown | {"eligible": true, "eligible_level": "Kindergarten 1 (5 yrs old)", "fee_before_subsidy": 1080.0, "net_monthly_fee": 1080.0, "programme_id": "half_day_am", "status": "estimated"} |
| 4 | MINDCHAMPS PRESCHOOL @ ZHONGSHAN PARK PTE. LTD. (CENTRE:PT8958) | 0.0 | 0.0 | 0.0 | unknown | {"eligible": true, "eligible_level": "Kindergarten 1 (5 yrs old)", "fee_before_subsidy": 2270.0, "net_monthly_fee": 2270.0, "programme_id": "half_day_am", "status": "estimated"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:EB0018 | E-Bridge Pre-School Pte Ltd | 1 | Full-day may be more compatible than half-day, but scheme participation is unverified. |
| CENTRE:PT8958 | MINDCHAMPS PRESCHOOL @ ZHONGSHAN PARK PTE. LTD. | 1 | Half-day differs and the listed fee is highest; scheme status unverified. |
| CENTRE:PT9766 | Silk Education Pte. Ltd. | 1 | Half-day differs; scheme status unverified. |
| CENTRE:PT8512 | Star Learners @ Woodlands 888 Pte Ltd | 1 | Half-day differs; scheme status unverified. |

**Provisional reference order (ties preserved):** 1: E-Bridge Pre-School Pte Ltd (CENTRE:EB0018) → 2: Star Learners @ Woodlands 888 Pte Ltd (CENTRE:PT8512) = Silk Education Pte. Ltd. (CENTRE:PT9766) → 4: MINDCHAMPS PRESCHOOL @ ZHONGSHAN PARK PTE. LTD. (CENTRE:PT8958)

**Reviewer rationale:** E-Bridge ranks first provisionally; Silk and Star Learners are tied; MindChamps is last due to programme and fee concerns.

---
### 15. development-15-33846e8db7

**Scenario:** Deterministic fictional family template development 15: explores food and pedagogy preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2020-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 4500.0 |
| Citizenship category | Others |
| Requested programme | flexi_care_3 |
| Working hours per month | 120.0 |
| Household size | 4 |
| Non-earning dependants | 4 |
| Special approval | false |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| None recorded | — |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| food | no_pork | 3 | true |
| pedagogy | Reggio Emilia | 1 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| food | no_pork | preferred | 1.0 | partially_supported |
| pedagogy | Reggio Emilia | nice_to_have | 1.0 | partially_supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Children's Cove Preschool Pasir Ris Pte Ltd (CENTRE:PT8965) | 0.0 | 0.0 | 0.0 | unknown | {"eligible": true, "eligible_level": "Kindergarten 2 (6 yrs old)", "fee_before_subsidy": 1050.0, "net_monthly_fee": 1050.0, "programme_id": "half_day_am", "status": "estimated"} |
| 2 | ARTEMIS PRESKOOL @ WISTERIA MALL (CENTRE:PT9903) | 0.0 | 0.0 | 0.0 | unknown | {"eligible": true, "eligible_level": "Kindergarten 2 (6 yrs old)", "fee_before_subsidy": 850.0, "net_monthly_fee": 850.0, "programme_id": "half_day_am", "status": "estimated"} |
| 3 | PCF SPARKLETOTS PRESCHOOL @ CASHEW BLK 183 (CC) (CENTRE:ST0006) | 0.0 | 0.0 | 0.0 | unknown | {"eligible": true, "eligible_level": "Kindergarten 2 (6 yrs old)", "fee_before_subsidy": 1172.0, "net_monthly_fee": 1172.0, "programme_id": "full_day", "status": "estimated"} |
| 4 | PCF Sparkletots Preschool @ Punggol Coast Blk 303A (DS) (CENTRE:ST0114) | 0.0 | 0.0 | 0.0 | unknown | {"eligible": true, "eligible_level": "Kindergarten 2 (6 yrs old)", "fee_before_subsidy": 1172.0, "net_monthly_fee": 1172.0, "programme_id": "full_day", "status": "estimated"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:PT8965 | Children's Cove Preschool Pasir Ris Pte Ltd | 1 | No evidence confirms that it provides no-pork meals or Reggio Emilia pedagogy, and the requested programme differs from the recorded programme. |
| CENTRE:ST0006 | PCF SPARKLETOTS PRESCHOOL @ CASHEW BLK 183 (CC) | 1 | Its food and pedagogy offerings are unverified, and the recorded full-day programme differs from the requested flexi-care programme. |
| CENTRE:PT9903 | ARTEMIS PRESKOOL @ WISTERIA MALL | 1 | There is insufficient evidence to confirm either preferred offering, and its recorded programme does not match the request. |
| CENTRE:ST0114 | PCF Sparkletots Preschool @ Punggol Coast Blk 303A (DS) | 1 | Its no-pork meals and Reggio Emilia approach are unverified, and the recorded programme differs from the requested one. |

**Provisional reference order (ties preserved):** 1: Children's Cove Preschool Pasir Ris Pte Ltd (CENTRE:PT8965) → 2: PCF SPARKLETOTS PRESCHOOL @ CASHEW BLK 183 (CC) (CENTRE:ST0006) → 3: ARTEMIS PRESKOOL @ WISTERIA MALL (CENTRE:PT9903) → 4: PCF Sparkletots Preschool @ Punggol Coast Blk 303A (DS) (CENTRE:ST0114)

**Reviewer rationale:** No-pork meals and Reggio Emilia approach are unverified for all four; meaningful distinctions are unavailable.

---
### 16. development-16-bf376b58a8

**Scenario:** Deterministic fictional family template development 16: explores pedagogy and language preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2024-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 5500.0 |
| Citizenship category | SC |
| Requested programme | full_day |
| Working hours per month | 160.0 |
| Household size | 5 |
| Non-earning dependants | 3 |
| Special approval | true |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| language | Tamil |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| pedagogy | Play-based | 1 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| language | Tamil | required | 1.0 | supported |
| pedagogy | Play-based | nice_to_have | 1.0 | partially_supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | MOE KINDERGARTEN @ WESTWOOD (CENTRE:KM0015) | 0.0 | 0.0 | 0.0 | pass | {"eligible": false, "eligible_level": "Playgroup (18 mths to 2 yrs old)", "fee_before_subsidy": null, "net_monthly_fee": null, "programme_id": null, "status": "ineligible"} |
| Not returned | MY FIRST SKOOL (CENTRE:NT0504) | — | — | — | fail | — |
| Not returned | CHILDREN'S COVE PRESCHOOL PTE.LTD. (CENTRE:PT9390) | — | — | — | fail | — |
| Not returned | MY WORLD PRESCHOOL LTD (CENTRE:YM0191) | — | — | — | fail | — |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:YM0191 | MY WORLD PRESCHOOL LTD | 0 | The system marks it as failing the required Tamil-language constraint, making it unsuitable based on the available evaluation. |
| CENTRE:NT0504 | MY FIRST SKOOL | 0 | The system marks it as failing the required Tamil-language constraint, so it does not meet the family's stated requirement. |
| CENTRE:KM0015 | MOE KINDERGARTEN @ WESTWOOD | 0 | The system records a pass for Tamil but identifies the child as ineligible for the programme, creating a major suitability issue. |
| CENTRE:PT9390 | CHILDREN'S COVE PRESCHOOL PTE.LTD. | 0 | The system marks it as failing the required Tamil-language constraint, so it cannot be considered a suitable match without contrary evidence. |

**Provisional reference order (ties preserved):** 1: MOE KINDERGARTEN @ WESTWOOD (CENTRE:KM0015) → 2: MY WORLD PRESCHOOL LTD (CENTRE:YM0191) → 3: MY FIRST SKOOL (CENTRE:NT0504) → 4: CHILDREN'S COVE PRESCHOOL PTE.LTD. (CENTRE:PT9390)

**Reviewer rationale:** The recorded Tamil outcome favours Westwood, but the programme-level eligibility conflict prevents a confident recommendation.

---
### 17. development-17-1560d669fd

**Scenario:** Deterministic fictional family template development 17: explores care_level and full_day preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2023-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 6500.0 |
| Citizenship category | SPR |
| Requested programme | half_day |
| Working hours per month | 0.0 |
| Household size | 2 |
| Non-earning dependants | 1 |
| Special approval | false |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| level | Kindergarten 1 (5 yrs old) |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| full_day | true | 4 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| care_level | Kindergarten 1 (5 yrs old) | required | 1.0 | supported |
| full_day | true | high_priority | 1.0 | supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | BAMBINI CHILDCARE LLP (CENTRE:PT8359) | 100.0 | 1.0 | 100.0 | pass | {"eligible": true, "eligible_level": "Pre-Nursery (3 yrs old)", "fee_before_subsidy": 1000.0, "net_monthly_fee": 1000.0, "programme_id": "half_day_am", "status": "estimated"} |
| 2 | PERIDOT SCHOOLHOUSE PTE LTD (CENTRE:PT8687) | 100.0 | 1.0 | 100.0 | pass | {"eligible": true, "eligible_level": "Pre-Nursery (3 yrs old)", "fee_before_subsidy": 1180.0, "net_monthly_fee": 1180.0, "programme_id": "half_day_am", "status": "estimated"} |
| 3 | Little Footprints Preschool Group Pte Ltd (CENTRE:PT9023) | 100.0 | 1.0 | 100.0 | pass | {"eligible": true, "eligible_level": "Pre-Nursery (3 yrs old)", "fee_before_subsidy": 1000.0, "net_monthly_fee": 1000.0, "programme_id": "half_day_am", "status": "estimated"} |
| 4 | PCF Sparkletots Preschool @ Changi Blk 216 (KN) (CENTRE:ST0252) | 100.0 | 1.0 | 100.0 | pass | {"eligible": false, "eligible_level": "Pre-Nursery (3 yrs old)", "fee_before_subsidy": null, "net_monthly_fee": null, "programme_id": null, "status": "fee_unavailable"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:PT8359 | BAMBINI CHILDCARE LLP | 1 | The recorded Pre-Nursery level conflicts with the family's required Kindergarten 1 level, and the programme is listed as half-day rather than full-day. |
| CENTRE:PT9023 | Little Footprints Preschool Group Pte Ltd | 1 | The recorded level does not match the required Kindergarten 1 level, and the saved programme is half-day. |
| CENTRE:ST0252 | PCF Sparkletots Preschool @ Changi Blk 216 (KN) | 1 | The recorded Pre-Nursery level conflicts with the required Kindergarten 1 level, and eligibility or fee availability is unresolved. |
| CENTRE:PT8687 | PERIDOT SCHOOLHOUSE PTE LTD | 1 | It is recorded at Pre-Nursery rather than the required Kindergarten 1 level and offers a half-day programme in the saved results. |

**Provisional reference order (ties preserved):** 1: BAMBINI CHILDCARE LLP (CENTRE:PT8359) → 2: PERIDOT SCHOOLHOUSE PTE LTD (CENTRE:PT8687) → 3: Little Footprints Preschool Group Pte Ltd (CENTRE:PT9023) → 4: PCF Sparkletots Preschool @ Changi Blk 216 (KN) (CENTRE:ST0252)

**Reviewer rationale:** All have recorded programme-level mismatches; evidence does not reliably distinguish them.

---
### 18. development-18-a35d531cb7

**Scenario:** Deterministic fictional family template development 18: explores language and pedagogy preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2022-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 7500.0 |
| Citizenship category | Others |
| Requested programme | flexi_care_1 |
| Working hours per month | 56.0 |
| Household size | 3 |
| Non-earning dependants | 1 |
| Special approval | true |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| None recorded | — |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| language:Tamil | Tamil | 4 | true |
| pedagogy | Play-based | 3 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| language | Tamil | high_priority | 1.0 | supported |
| pedagogy | Play-based | preferred | 1.0 | partially_supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | PCF Sparkletots Preschool @ Yio Chu Kang Blk 611 (CC) (CENTRE:ST0167) | 100.0 | 0.67 | 81.6 | unknown | {"eligible": true, "eligible_level": "Nursery (4 yrs old)", "fee_before_subsidy": 849.93, "net_monthly_fee": 849.93, "programme_id": "half_day_am", "status": "estimated"} |
| 2 | PCF Sparkletots Preschool @ Queenstown Blk 3 (KN) (CENTRE:ST0216) | 100.0 | 0.67 | 81.6 | unknown | {"eligible": false, "eligible_level": "Nursery (4 yrs old)", "fee_before_subsidy": null, "net_monthly_fee": null, "programme_id": null, "status": "fee_unavailable"} |
| 3 | Little Seeds Preschool (CENTRE:RC1900) | 0.0 | 0.67 | 0.0 | unknown | {"eligible": true, "eligible_level": "Nursery (4 yrs old)", "fee_before_subsidy": 1500.0, "net_monthly_fee": 1500.0, "programme_id": "full_day", "status": "estimated"} |
| 4 | PCF Sparkletots Preschool @ Tampines Changkat Blk 112 (CC) (CENTRE:ST0032) | 0.0 | 0.67 | 0.0 | unknown | {"eligible": true, "eligible_level": "Nursery (4 yrs old)", "fee_before_subsidy": 1139.19, "net_monthly_fee": 1139.19, "programme_id": "full_day", "status": "estimated"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:ST0167 | PCF Sparkletots Preschool @ Yio Chu Kang Blk 611 (CC) | 2 | It is a possible candidate, but Tamil-language provision is unverified and the recorded half-day programme differs from the requested flexi-care programme. |
| CENTRE:RC1900 | Little Seeds Preschool | 1 | The saved score is zero and there is no evidence confirming Tamil provision or play-based pedagogy. |
| CENTRE:ST0032 | PCF Sparkletots Preschool @ Tampines Changkat Blk 112 (CC) | 1 | Its Tamil-language offering and play-based approach are unverified, and the saved programme is full-day rather than the requested flexi-care option. |
| CENTRE:ST0216 | PCF Sparkletots Preschool @ Queenstown Blk 3 (KN) | 1 | Its language and pedagogy fit are unverified, and the saved record indicates unresolved fee eligibility. |

**Provisional reference order (ties preserved):** 1: PCF Sparkletots Preschool @ Yio Chu Kang Blk 611 (CC) (CENTRE:ST0167) → 2: Little Seeds Preschool (CENTRE:RC1900) → 3: PCF Sparkletots Preschool @ Tampines Changkat Blk 112 (CC) (CENTRE:ST0032) → 4: PCF Sparkletots Preschool @ Queenstown Blk 3 (KN) (CENTRE:ST0216)

**Reviewer rationale:** Some candidates have programme or language uncertainties; evidence is insufficient for a confident ordering.

---
### 19. development-19-d69253583f

**Scenario:** Deterministic fictional family template development 19: explores spark_certified and transport preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2021-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 2500.0 |
| Citizenship category | SC |
| Requested programme | flexi_care_2 |
| Working hours per month | 120.0 |
| Household size | 4 |
| Non-earning dependants | 3 |
| Special approval | false |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| None recorded | — |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| spark_certified | true | 3 | true |
| transport | true | 1 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| spark_certified | true | preferred | 1.0 | supported |
| transport | true | nice_to_have | 1.0 | supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | MY FIRST SKOOL (CENTRE:NT0478) | 85.7 | 1.0 | 92.6 | unknown | {"eligible": true, "eligible_level": "Kindergarten 1 (5 yrs old)", "fee_before_subsidy": 430.92, "net_monthly_fee": 145.92, "programme_id": "flexi_care_1", "status": "estimated"} |
| 2 | Little Shepherds' Schoolhouse@Church of St Anthony (CENTRE:RC1220) | 85.7 | 1.0 | 92.6 | unknown | {"eligible": true, "eligible_level": "Kindergarten 1 (5 yrs old)", "fee_before_subsidy": 402.15, "net_monthly_fee": 17.15, "programme_id": "half_day_am", "status": "estimated"} |
| 3 | HEARTYLAND INFANT CARE PTE LTD (CENTRE:PT9416) | 0.0 | 1.0 | 0.0 | unknown | {"eligible": false, "eligible_level": "Kindergarten 1 (5 yrs old)", "fee_before_subsidy": null, "net_monthly_fee": null, "programme_id": null, "status": "ineligible"} |
| 4 | QUAYSIDE ISLE PREPARATORY SCHOOL (CENTRE:PT9583) | 0.0 | 1.0 | 0.0 | unknown | {"eligible": false, "eligible_level": "Kindergarten 1 (5 yrs old)", "fee_before_subsidy": null, "net_monthly_fee": null, "programme_id": null, "status": "fee_unavailable"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:PT9416 | HEARTYLAND INFANT CARE PTE LTD | 0 | The saved Stage 2 result marks it ineligible for the child's recorded Kindergarten 1 level. |
| CENTRE:PT9583 | QUAYSIDE ISLE PREPARATORY SCHOOL | 0 | The saved result marks it ineligible or unresolved for fee availability, and its certification and transport fit are unverified. |
| CENTRE:NT0478 | MY FIRST SKOOL | 3 | Strong saved match; verify SPARK certification and transport requirement. |
| CENTRE:RC1220 | Little Shepherds' Schoolhouse@Church of St Anthony | 2 | Its high saved match score suggests a possible fit, but transport and the programme mismatch need further checking. |

**Provisional reference order (ties preserved):** 1: MY FIRST SKOOL (CENTRE:NT0478) → 2: Little Shepherds' Schoolhouse@Church of St Anthony (CENTRE:RC1220) → 3: QUAYSIDE ISLE PREPARATORY SCHOOL (CENTRE:PT9583) → 4: HEARTYLAND INFANT CARE PTE LTD (CENTRE:PT9416)

**Reviewer rationale:** Heartyland has a recorded K1 eligibility issue; other candidates have unresolved requirements.

---
### 20. development-20-1322395d06

**Scenario:** Deterministic fictional family template development 20: explores transport and operator_scheme preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2020-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 3500.0 |
| Citizenship category | SPR |
| Requested programme | flexi_care_3 |
| Working hours per month | 160.0 |
| Household size | 5 |
| Non-earning dependants | 1 |
| Special approval | true |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| None recorded | — |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| transport | false | 1 | true |
| operator_scheme | Anchor Operator Scheme | 5 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| transport | false | nice_to_have | 1.0 | supported |
| operator_scheme | Anchor Operator Scheme | required | 1.0 | partially_supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | KIDDIE EXPLORERS PRESCHOOL (CENTRE:PT7040) | 0.0 | 0.05 | 0.0 | unknown | {"eligible": true, "eligible_level": "Kindergarten 2 (6 yrs old)", "fee_before_subsidy": 967.0, "net_monthly_fee": 967.0, "programme_id": "half_day_am", "status": "estimated"} |
| 2 | YASMINE @ FRANKEL EARLY LEARNING CENTRE (CENTRE:PT8072) | 0.0 | 0.05 | 0.0 | unknown | {"eligible": true, "eligible_level": "Kindergarten 2 (6 yrs old)", "fee_before_subsidy": 720.0, "net_monthly_fee": 720.0, "programme_id": "half_day_am", "status": "estimated"} |
| 3 | RH Positive Montessori Kindergarten (Bukit Timah) (CENTRE:PT9715) | 0.0 | 0.05 | 0.0 | unknown | {"eligible": true, "eligible_level": "Kindergarten 2 (6 yrs old)", "fee_before_subsidy": 2224.77, "net_monthly_fee": 2224.77, "programme_id": "full_day", "status": "estimated"} |
| 4 | CARPE DIEM @ ITE PTE. LTD. (CENTRE:PT8911) | 0.0 | 0.0 | 0.0 | unknown | {"eligible": true, "eligible_level": "Kindergarten 2 (6 yrs old)", "fee_before_subsidy": 780.0, "net_monthly_fee": 780.0, "programme_id": "half_day_am", "status": "estimated"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:PT9715 | RH Positive Montessori Kindergarten (Bukit Timah) | 2 | Its Montessori identity does not establish the required Anchor Operator Scheme status, and transport information is unavailable. |
| CENTRE:PT8911 | CARPE DIEM @ ITE PTE. LTD. | 2 | It may be relevant, but the required scheme participation is unverified and transport information is unavailable. |
| CENTRE:PT7040 | KIDDIE EXPLORERS PRESCHOOL | 2 | Its scheme status and transport arrangements are unverified, so its fit remains uncertain. |
| CENTRE:PT8072 | YASMINE @ FRANKEL EARLY LEARNING CENTRE | 2 | It may be a candidate, but the required operator-scheme participation and transport details are not confirmed. |

**Provisional reference order (ties preserved):** 1: RH Positive Montessori Kindergarten (Bukit Timah) (CENTRE:PT9715) → 2: CARPE DIEM @ ITE PTE. LTD. (CENTRE:PT8911) → 3: KIDDIE EXPLORERS PRESCHOOL (CENTRE:PT7040) → 4: YASMINE @ FRANKEL EARLY LEARNING CENTRE (CENTRE:PT8072)

**Reviewer rationale:** Anchor Operator Scheme and transport evidence is missing for all four.

---
### 21. development-21-6e7372b74e

**Scenario:** Deterministic fictional family template development 21: explores full_day and care_level preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2024-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 4500.0 |
| Citizenship category | Others |
| Requested programme | full_day |
| Working hours per month | 0.0 |
| Household size | 2 |
| Non-earning dependants | 2 |
| Special approval | false |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| level | Kindergarten 1 (5 yrs old) |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| full_day | true | 5 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| care_level | Kindergarten 1 (5 yrs old) | high_priority | 1.0 | supported |
| full_day | true | required | 1.0 | supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | MY FIRST SKOOL (CENTRE:NT0400) | 100.0 | 1.0 | 100.0 | pass | {"eligible": true, "eligible_level": "Playgroup (18 mths to 2 yrs old)", "fee_before_subsidy": 1188.0, "net_monthly_fee": 1188.0, "programme_id": "full_day", "status": "estimated"} |
| 2 | Shooting Star Preschool Pte Ltd (CENTRE:PT8762) | 100.0 | 1.0 | 100.0 | pass | {"eligible": true, "eligible_level": "Playgroup (18 mths to 2 yrs old)", "fee_before_subsidy": 1350.0, "net_monthly_fee": 1350.0, "programme_id": "full_day", "status": "estimated"} |
| 3 | Sengkang Methodist Preschool (CENTRE:PT9774) | 100.0 | 1.0 | 100.0 | pass | {"eligible": false, "eligible_level": "Playgroup (18 mths to 2 yrs old)", "fee_before_subsidy": null, "net_monthly_fee": null, "programme_id": null, "status": "fee_unavailable"} |
| 4 | BUMBLE BEE CHILD CARE CENTRE (CENTRE:PT3150) | 0.0 | 0.0 | 0.0 | unknown | {"eligible": true, "eligible_level": "Playgroup (18 mths to 2 yrs old)", "fee_before_subsidy": 990.0, "net_monthly_fee": 990.0, "programme_id": "full_day", "status": "estimated"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:PT9774 | Sengkang Methodist Preschool | 0 | The recorded child age conflicts with the required Kindergarten 1 level, and the saved result indicates fee or eligibility uncertainty. |
| CENTRE:NT0400 | MY FIRST SKOOL | 0 | The system identifies the child as Playgroup age rather than the required Kindergarten 1 level, despite the saved pass. |
| CENTRE:PT8762 | Shooting Star Preschool Pte Ltd | 0 | The recorded Playgroup level conflicts with the required Kindergarten 1 level, so the family’s hard constraint appears unmet. |
| CENTRE:PT3150 | BUMBLE BEE CHILD CARE CENTRE | 0 | The recorded Playgroup level does not match the required Kindergarten 1 level, and the saved evaluation has no supporting match evidence. |

**Provisional reference order (ties preserved):** 1: Sengkang Methodist Preschool (CENTRE:PT9774) → 2: MY FIRST SKOOL (CENTRE:NT0400) → 3: Shooting Star Preschool Pte Ltd (CENTRE:PT8762) → 4: BUMBLE BEE CHILD CARE CENTRE (CENTRE:PT3150)

**Reviewer rationale:** Recorded age, programme, and K1 mismatches undermine suitability; further eligibility checks are needed.

---
### 22. development-22-4c8dafa524

**Scenario:** Deterministic fictional family template development 22: explores operator_scheme and transport preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2023-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 5500.0 |
| Citizenship category | SC |
| Requested programme | half_day |
| Working hours per month | 56.0 |
| Household size | 3 |
| Non-earning dependants | 1 |
| Special approval | true |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| None recorded | — |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| operator_scheme | Anchor Operator Scheme | 4 | true |
| transport | false | 3 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| operator_scheme | Anchor Operator Scheme | high_priority | 1.0 | partially_supported |
| transport | false | preferred | 1.0 | supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | MY FIRST SKOOL (CENTRE:NT0561) | 100.0 | 0.33 | 57.7 | unknown | {"eligible": true, "eligible_level": "Pre-Nursery (3 yrs old)", "fee_before_subsidy": 460.0, "net_monthly_fee": 460.0, "programme_id": "half_day_am", "status": "manual_review"} |
| 2 | SUPER TALENT CHILDCARE LTD (CENTRE:RC1786) | 100.0 | 0.33 | 57.7 | unknown | {"eligible": true, "eligible_level": "Pre-Nursery (3 yrs old)", "fee_before_subsidy": 490.0, "net_monthly_fee": 490.0, "programme_id": "half_day_am", "status": "manual_review"} |
| 3 | Ang Mo Kio Methodist Preschool (CENTRE:PT9863) | 0.0 | 0.33 | 0.0 | unknown | {"eligible": true, "eligible_level": "Pre-Nursery (3 yrs old)", "fee_before_subsidy": 1250.0, "net_monthly_fee": 1250.0, "programme_id": "half_day_am", "status": "manual_review"} |
| 4 | KIDZ MEADOW CHILDCARE & DEVELOPMENT CENTRE (BUANGKOK CRESCENT) (CENTRE:RC1719) | 0.0 | 0.0 | 0.0 | unknown | {"eligible": true, "eligible_level": "Pre-Nursery (3 yrs old)", "fee_before_subsidy": 490.0, "net_monthly_fee": 490.0, "programme_id": "half_day_am", "status": "manual_review"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:PT9863 | Ang Mo Kio Methodist Preschool | 2 | It is a possible candidate, but Anchor Operator Scheme participation and transport arrangements are not verified. |
| CENTRE:NT0561 | MY FIRST SKOOL | 2 | It may fit the scheme preference, but the saved confidence is low and transport availability remains unconfirmed. |
| CENTRE:RC1786 | SUPER TALENT CHILDCARE LTD | 2 | It is worth considering, although scheme status and transport provision need verification. |
| CENTRE:RC1719 | KIDZ MEADOW CHILDCARE & DEVELOPMENT CENTRE (BUANGKOK CRESCENT) | 2 | Its fit is uncertain because neither the required operator-scheme participation nor transport arrangements are confirmed. |

**Provisional reference order (ties preserved):** 1: Ang Mo Kio Methodist Preschool (CENTRE:PT9863) → 2: MY FIRST SKOOL (CENTRE:NT0561) → 3: SUPER TALENT CHILDCARE LTD (CENTRE:RC1786) → 4: KIDZ MEADOW CHILDCARE & DEVELOPMENT CENTRE (BUANGKOK CRESCENT) (CENTRE:RC1719)

**Reviewer rationale:** Scheme participation and transport remain unverified, so the distinctions are weak.

---
### 23. development-23-16c4837e94

**Scenario:** Deterministic fictional family template development 23: explores food and pedagogy preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2022-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 6500.0 |
| Citizenship category | SPR |
| Requested programme | flexi_care_1 |
| Working hours per month | 120.0 |
| Household size | 4 |
| Non-earning dependants | 2 |
| Special approval | false |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| None recorded | — |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| food | no_pork | 3 | true |
| pedagogy | Reggio Emilia | 1 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| food | no_pork | preferred | 1.0 | partially_supported |
| pedagogy | Reggio Emilia | nice_to_have | 1.0 | partially_supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | KIDDIWINKIE SCHOOLHOUSE PTE LTD (CENTRE:PT5280) | 0.0 | 0.0 | 0.0 | unknown | {"eligible": true, "eligible_level": "Nursery (4 yrs old)", "fee_before_subsidy": 2160.0, "net_monthly_fee": 2160.0, "programme_id": "half_day_am", "status": "estimated"} |
| 2 | JOSIAH MONTESSORI : CITY CHILDCARE CENTRE (CENTRE:PT8120) | 0.0 | 0.0 | 0.0 | unknown | {"eligible": true, "eligible_level": "Nursery (4 yrs old)", "fee_before_subsidy": 1250.0, "net_monthly_fee": 1250.0, "programme_id": "flexi_care_1", "status": "estimated"} |
| 3 | PCF SPARKLETOTS PRESCHOOL @ KEBUN BARU BLK 109 (CC) (CENTRE:ST0002) | 0.0 | 0.0 | 0.0 | unknown | {"eligible": true, "eligible_level": "Nursery (4 yrs old)", "fee_before_subsidy": 516.95, "net_monthly_fee": 516.95, "programme_id": "half_day_am", "status": "estimated"} |
| 4 | PCF Sparkletots Preschool @ Tampines Changkat Blk 964A (CC) (CENTRE:ST0412) | 0.0 | 0.0 | 0.0 | unknown | {"eligible": true, "eligible_level": "Nursery (4 yrs old)", "fee_before_subsidy": 835.0, "net_monthly_fee": 835.0, "programme_id": "full_day", "status": "estimated"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:PT8120 | JOSIAH MONTESSORI : CITY CHILDCARE CENTRE | 2 | It offers the requested flexi-care programme in the saved results, but no-pork meals and Reggio Emilia pedagogy are unverified. |
| CENTRE:ST0412 | PCF Sparkletots Preschool @ Tampines Changkat Blk 964A (CC) | 1 | Its food and pedagogy offerings are unverified, and the recorded full-day programme differs from the requested flexi-care programme. |
| CENTRE:ST0002 | PCF SPARKLETOTS PRESCHOOL @ KEBUN BARU BLK 109 (CC) | 1 | There is insufficient evidence for the food and pedagogy preferences, and the saved programme differs from the requested programme. |
| CENTRE:PT5280 | KIDDIWINKIE SCHOOLHOUSE PTE LTD | 1 | Its no-pork food provision and Reggio Emilia pedagogy are unverified, and the recorded programme differs from the request. |

**Provisional reference order (ties preserved):** 1: JOSIAH MONTESSORI : CITY CHILDCARE CENTRE (CENTRE:PT8120) → 2: PCF Sparkletots Preschool @ Tampines Changkat Blk 964A (CC) (CENTRE:ST0412) → 3: PCF SPARKLETOTS PRESCHOOL @ KEBUN BARU BLK 109 (CC) (CENTRE:ST0002) → 4: KIDDIWINKIE SCHOOLHOUSE PTE LTD (CENTRE:PT5280)

**Reviewer rationale:** Josiah has a recorded flexi-care match; meal and pedagogy requirements remain unverified.

---
### 24. development-24-50fa5935ee

**Scenario:** Deterministic fictional family template development 24: explores pedagogy and language preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2021-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 7500.0 |
| Citizenship category | Others |
| Requested programme | flexi_care_2 |
| Working hours per month | 160.0 |
| Household size | 5 |
| Non-earning dependants | 5 |
| Special approval | true |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| language | Malay |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| pedagogy | Play-based | 1 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| language | Malay | required | 1.0 | supported |
| pedagogy | Play-based | nice_to_have | 1.0 | partially_supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | MOE Kindergarten @ Temasek (CENTRE:KM0048) | 0.0 | 0.0 | 0.0 | pass | {"eligible": false, "eligible_level": "Kindergarten 1 (5 yrs old)", "fee_before_subsidy": null, "net_monthly_fee": null, "programme_id": null, "status": "fee_unavailable"} |
| Not returned | CARPE DIEM KIDSWORLD PTE. LTD. (CENTRE:PT8200) | — | — | — | fail | — |
| Not returned | CREATIVELAND CHILDCARE AND DEVELOPMENT CENTRE@ADMIRALTY PTE LTD (CENTRE:PT9310) | — | — | — | fail | — |
| Not returned | PCF Sparkletots Preschool @ Clementi Blk 445 (EY) (CENTRE:ST0383) | — | — | — | fail | — |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:KM0048 | MOE Kindergarten @ Temasek | 0 | The system marks the Tamil-language hard constraint as passing, but the recorded Kindergarten 1 level and unresolved eligibility make suitability uncertain. |
| CENTRE:PT8200 | CARPE DIEM KIDSWORLD PTE. LTD. | 0 | The system marks it as failing the required Malay-language constraint, so it does not meet the family's stated requirement. |
| CENTRE:ST0383 | PCF Sparkletots Preschool @ Clementi Blk 445 (EY) | 0 | The system marks it as failing the required Malay-language constraint, making it unsuitable based on the available evaluation. |
| CENTRE:PT9310 | CREATIVELAND CHILDCARE AND DEVELOPMENT CENTRE@ADMIRALTY PTE LTD | 0 | The system marks it as failing the required Malay-language constraint, so it does not meet the hard requirement. |

**Provisional reference order (ties preserved):** 1: MOE Kindergarten @ Temasek (CENTRE:KM0048) → 2: CARPE DIEM KIDSWORLD PTE. LTD. (CENTRE:PT8200) → 3: PCF Sparkletots Preschool @ Clementi Blk 445 (EY) (CENTRE:ST0383) → 4: CREATIVELAND CHILDCARE AND DEVELOPMENT CENTRE@ADMIRALTY PTE LTD (CENTRE:PT9310)

**Reviewer rationale:** The recorded Malay result favours Temasek, but eligibility and programme suitability remain unresolved.

---
### 25. development-25-535ceba2ee

**Scenario:** Deterministic fictional family template development 25: explores care_level and full_day preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2020-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 2500.0 |
| Citizenship category | SC |
| Requested programme | flexi_care_3 |
| Working hours per month | 0.0 |
| Household size | 2 |
| Non-earning dependants | 0 |
| Special approval | false |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| level | Nursery (4 yrs old) |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| full_day | true | 4 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| care_level | Nursery (4 yrs old) | required | 1.0 | supported |
| full_day | true | high_priority | 1.0 | supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | MY FIRST SKOOL (CENTRE:NT0538) | 100.0 | 1.0 | 100.0 | pass | {"eligible": true, "eligible_level": "Kindergarten 2 (6 yrs old)", "fee_before_subsidy": 430.92, "net_monthly_fee": 375.92, "programme_id": "flexi_care_1", "status": "estimated"} |
| 2 | Kiddiwinkie Schoolhouse Singapore Pte Ltd (CENTRE:PT9007) | 100.0 | 1.0 | 100.0 | pass | {"eligible": true, "eligible_level": "Kindergarten 2 (6 yrs old)", "fee_before_subsidy": 1780.0, "net_monthly_fee": 1630.0, "programme_id": "half_day_am", "status": "estimated"} |
| 3 | PCF SPARKLETOTS PRESCHOOL @ BUKIT BATOK BLK 118 (CC) (CENTRE:ST0028) | 0.0 | 0.0 | 0.0 | pass | {"eligible": true, "eligible_level": "Kindergarten 2 (6 yrs old)", "fee_before_subsidy": 575.96, "net_monthly_fee": 425.96, "programme_id": "full_day", "status": "estimated"} |
| Not returned | Camelot Learning Centre Pte Ltd (CENTRE:PT9801) | — | — | — | fail | — |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:NT0538 | MY FIRST SKOOL | 1 | The recorded Kindergarten 2 level conflicts with the required Nursery level, despite the saved pass and high match score. |
| CENTRE:ST0028 | PCF SPARKLETOTS PRESCHOOL @ BUKIT BATOK BLK 118 (CC) | 1 | The recorded Kindergarten 2 level does not match the required Nursery level, although full-day care is listed. |
| CENTRE:PT9801 | Camelot Learning Centre Pte Ltd | 0 | The system marks it as failing the hard care-level constraint, so it should not be treated as a suitable match. |
| CENTRE:PT9007 | Kiddiwinkie Schoolhouse Singapore Pte Ltd | 1 | The recorded Kindergarten 2 level conflicts with the required Nursery level, and the saved programme is half-day rather than full-day. |

**Provisional reference order (ties preserved):** 1: MY FIRST SKOOL (CENTRE:NT0538) → 2: PCF SPARKLETOTS PRESCHOOL @ BUKIT BATOK BLK 118 (CC) (CENTRE:ST0028) → 3: Kiddiwinkie Schoolhouse Singapore Pte Ltd (CENTRE:PT9007) → 4: Camelot Learning Centre Pte Ltd (CENTRE:PT9801)

**Reviewer rationale:** The first three have Nursery/K2 mismatches; Camelot has a recorded hard-constraint failure.

---
### 26. development-26-ee34cadb78

**Scenario:** Deterministic fictional family template development 26: explores language and pedagogy preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2024-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 3500.0 |
| Citizenship category | SPR |
| Requested programme | full_day |
| Working hours per month | 56.0 |
| Household size | 3 |
| Non-earning dependants | 1 |
| Special approval | true |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| None recorded | — |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| language:Malay | Malay | 4 | true |
| pedagogy | Play-based | 3 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| language | Malay | high_priority | 1.0 | supported |
| pedagogy | Play-based | preferred | 1.0 | partially_supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | E-Bridge Pre-School Pte Ltd (CENTRE:EB0027) | 100.0 | 0.67 | 81.6 | unknown | {"eligible": true, "eligible_level": "Playgroup (18 mths to 2 yrs old)", "fee_before_subsidy": 835.0, "net_monthly_fee": 835.0, "programme_id": "full_day", "status": "estimated"} |
| 2 | PCF Sparkletots Preschool @ Sengkang East Blk 103 (EY) (CENTRE:ST0278) | 100.0 | 0.67 | 81.6 | unknown | {"eligible": true, "eligible_level": "Playgroup (18 mths to 2 yrs old)", "fee_before_subsidy": 835.0, "net_monthly_fee": 835.0, "programme_id": "full_day", "status": "estimated"} |
| 3 | PCF Sparkletots Preschool @ Zhenghua Blk 455A (KN) (CENTRE:ST0327) | 100.0 | 0.67 | 81.6 | unknown | {"eligible": false, "eligible_level": "Playgroup (18 mths to 2 yrs old)", "fee_before_subsidy": null, "net_monthly_fee": null, "programme_id": null, "status": "fee_unavailable"} |
| 4 | Baby Elk Infant Care Pte Ltd (CENTRE:PT9484) | 0.0 | 0.0 | 0.0 | unknown | {"eligible": false, "eligible_level": "Playgroup (18 mths to 2 yrs old)", "fee_before_subsidy": null, "net_monthly_fee": null, "programme_id": null, "status": "ineligible"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:ST0278 | PCF Sparkletots Preschool @ Sengkang East Blk 103 (EY) | 2 | It is a possible candidate because full-day care is recorded, but Malay-language provision and play-based pedagogy remain unverified. |
| CENTRE:ST0327 | PCF Sparkletots Preschool @ Zhenghua Blk 455A (KN) | 1 | Its language and pedagogy fit are unverified, and the saved result indicates unresolved eligibility or fee availability. |
| CENTRE:EB0027 | E-Bridge Pre-School Pte Ltd | 2 | It is a possible candidate because full-day care is listed, but the requested Malay-language provision and play-based approach need confirmation. |
| CENTRE:PT9484 | Baby Elk Infant Care Pte Ltd | 0 | The saved Stage 2 result marks it ineligible, and there is no evidence that it meets the family's language and pedagogy preferences. |

**Provisional reference order (ties preserved):** 1: PCF Sparkletots Preschool @ Sengkang East Blk 103 (EY) (CENTRE:ST0278) → 2: E-Bridge Pre-School Pte Ltd (CENTRE:EB0027) → 3: PCF Sparkletots Preschool @ Zhenghua Blk 455A (KN) (CENTRE:ST0327) → 4: Baby Elk Infant Care Pte Ltd (CENTRE:PT9484)

**Reviewer rationale:** Some candidates have full-day programme evidence; Malay and play-based requirements remain unverified.

---
### 27. development-27-fca15ee828

**Scenario:** Deterministic fictional family template development 27: explores spark_certified and transport preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2023-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 4500.0 |
| Citizenship category | Others |
| Requested programme | half_day |
| Working hours per month | 120.0 |
| Household size | 4 |
| Non-earning dependants | 1 |
| Special approval | false |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| None recorded | — |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| spark_certified | true | 3 | true |
| transport | true | 1 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| spark_certified | true | preferred | 1.0 | supported |
| transport | true | nice_to_have | 1.0 | supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | MY FIRST SKOOL (CENTRE:NT0539) | 85.7 | 1.0 | 92.6 | unknown | {"eligible": true, "eligible_level": "Pre-Nursery (3 yrs old)", "fee_before_subsidy": 891.0, "net_monthly_fee": 891.0, "programme_id": "half_day_am", "status": "estimated"} |
| 2 | Little Olive Tree (CENTRE:PW0121) | 85.7 | 1.0 | 92.6 | unknown | {"eligible": true, "eligible_level": "Pre-Nursery (3 yrs old)", "fee_before_subsidy": 1200.0, "net_monthly_fee": 1200.0, "programme_id": "half_day_am", "status": "estimated"} |
| 3 | MY WORLD PRESCHOOL LTD (CENTRE:YM0184) | 85.7 | 1.0 | 92.6 | unknown | {"eligible": true, "eligible_level": "Pre-Nursery (3 yrs old)", "fee_before_subsidy": 630.0, "net_monthly_fee": 630.0, "programme_id": "half_day_am", "status": "estimated"} |
| 4 | Skool4Kidz Preschool (CENTRE:SK0033) | 0.0 | 1.0 | 0.0 | unknown | {"eligible": true, "eligible_level": "Pre-Nursery (3 yrs old)", "fee_before_subsidy": 880.0, "net_monthly_fee": 880.0, "programme_id": "half_day_am", "status": "estimated"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:NT0539 | MY FIRST SKOOL | 3 | Strong saved match; verify certification and transport. |
| CENTRE:YM0184 | MY WORLD PRESCHOOL LTD | 3 | Strong saved match; verify certification and transport. |
| CENTRE:PW0121 | Little Olive Tree | 2 | It is a possible match based on the saved score, although certification and transport evidence are still needed. |
| CENTRE:SK0033 | Skool4Kidz Preschool | 1 | Its zero saved match score provides little support for the requested certification and transport preferences, which remain unverified. |

**Provisional reference order (ties preserved):** 1: MY FIRST SKOOL (CENTRE:NT0539) → 2: MY WORLD PRESCHOOL LTD (CENTRE:YM0184) → 3: Little Olive Tree (CENTRE:PW0121) → 4: Skool4Kidz Preschool (CENTRE:SK0033)

**Reviewer rationale:** The available notes suggest possible certification fit for the first two, but this needs verification.

---
### 28. development-28-e33d9b23bd

**Scenario:** Deterministic fictional family template development 28: explores transport and operator_scheme preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2022-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 5500.0 |
| Citizenship category | SC |
| Requested programme | flexi_care_1 |
| Working hours per month | 160.0 |
| Household size | 5 |
| Non-earning dependants | 3 |
| Special approval | true |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| None recorded | — |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| transport | false | 1 | true |
| operator_scheme | Anchor Operator Scheme | 5 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| transport | false | nice_to_have | 1.0 | supported |
| operator_scheme | Anchor Operator Scheme | required | 1.0 | partially_supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | MY FIRST SKOOL (CENTRE:NT0494) | 100.0 | 0.05 | 21.8 | unknown | {"eligible": true, "eligible_level": "Nursery (4 yrs old)", "fee_before_subsidy": 430.92, "net_monthly_fee": 430.92, "programme_id": "flexi_care_1", "status": "manual_review"} |
| 2 | Little Footprints Preschool Group Pte Ltd (CENTRE:PT9020) | 100.0 | 0.05 | 21.8 | unknown | {"eligible": true, "eligible_level": "Nursery (4 yrs old)", "fee_before_subsidy": 490.0, "net_monthly_fee": 490.0, "programme_id": "half_day_am", "status": "manual_review"} |
| 3 | PCF SPARKLETOTS PRESCHOOL @ TELOK BLANGAH BLK 44 (CC) (CENTRE:ST0031) | 100.0 | 0.05 | 21.8 | unknown | {"eligible": true, "eligible_level": "Nursery (4 yrs old)", "fee_before_subsidy": 460.0, "net_monthly_fee": 460.0, "programme_id": "half_day_am", "status": "manual_review"} |
| 4 | PCF Sparkletots Preschool @ Tampines Boulevard Blk 662C (CC) (CENTRE:ST0404) | 100.0 | 0.05 | 21.8 | unknown | {"eligible": true, "eligible_level": "Nursery (4 yrs old)", "fee_before_subsidy": 610.0, "net_monthly_fee": 610.0, "programme_id": "full_day", "status": "manual_review"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:NT0494 | MY FIRST SKOOL | 2 | It may be relevant, but the required Anchor Operator Scheme status is unverified and transport preference data is ambiguous. |
| CENTRE:ST0031 | PCF SPARKLETOTS PRESCHOOL @ TELOK BLANGAH BLK 44 (CC) | 2 | It is a possible candidate, but the scheme requirement and the meaning of the transport preference need clarification. |
| CENTRE:ST0404 | PCF Sparkletots Preschool @ Tampines Boulevard Blk 662C (CC) | 2 | It may fit the operator-scheme preference, but transport details are unverified and the recorded programme differs from the requested flexi-care option. |
| CENTRE:PT9020 | Little Footprints Preschool Group Pte Ltd | 2 | It is worth considering, although operator-scheme participation and transport suitability are not confirmed. |

**Provisional reference order (ties preserved):** 1: MY FIRST SKOOL (CENTRE:NT0494) → 2: PCF SPARKLETOTS PRESCHOOL @ TELOK BLANGAH BLK 44 (CC) (CENTRE:ST0031) → 3: Little Footprints Preschool Group Pte Ltd (CENTRE:PT9020) → 4: PCF Sparkletots Preschool @ Tampines Boulevard Blk 662C (CC) (CENTRE:ST0404)

**Reviewer rationale:** Scheme participation and transport are unclear; Tampines Boulevard also has a programme mismatch.

---
### 29. development-29-f5839126ae

**Scenario:** Deterministic fictional family template development 29: explores full_day and care_level preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2021-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 6500.0 |
| Citizenship category | SPR |
| Requested programme | flexi_care_2 |
| Working hours per month | 0.0 |
| Household size | 2 |
| Non-earning dependants | 1 |
| Special approval | false |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| level | Nursery (4 yrs old) |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| full_day | true | 5 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| care_level | Nursery (4 yrs old) | high_priority | 1.0 | supported |
| full_day | true | required | 1.0 | supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | BRIGHT KIDS SCHOOL HOUSE PTE LTD (CENTRE:PT7380) | 100.0 | 1.0 | 100.0 | pass | {"eligible": true, "eligible_level": "Kindergarten 1 (5 yrs old)", "fee_before_subsidy": 660.0, "net_monthly_fee": 660.0, "programme_id": "flexi_care_1", "status": "estimated"} |
| 2 | Greentree Montessori Children House  Pte Ltd (CENTRE:PT8541) | 100.0 | 1.0 | 100.0 | pass | {"eligible": true, "eligible_level": "Kindergarten 1 (5 yrs old)", "fee_before_subsidy": 1050.0, "net_monthly_fee": 1050.0, "programme_id": "flexi_care_1", "status": "estimated"} |
| 3 | A2E Kids (CENTRE:PT8720) | 100.0 | 1.0 | 100.0 | pass | {"eligible": true, "eligible_level": "Kindergarten 1 (5 yrs old)", "fee_before_subsidy": 688.0, "net_monthly_fee": 688.0, "programme_id": "half_day_am", "status": "estimated"} |
| 4 | Montessori Children's House (CENTRE:PT9649) | 100.0 | 1.0 | 100.0 | pass | {"eligible": false, "eligible_level": "Kindergarten 1 (5 yrs old)", "fee_before_subsidy": null, "net_monthly_fee": null, "programme_id": null, "status": "fee_unavailable"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:PT8720 | A2E Kids | 1 | The recorded Kindergarten 1 level conflicts with the required Nursery level, and the programme is listed as half-day. |
| CENTRE:PT7380 | BRIGHT KIDS SCHOOL HOUSE PTE LTD | 1 | The recorded Kindergarten 1 level does not match the required Nursery level, and the saved programme is flexi-care rather than confirmed full-day care. |
| CENTRE:PT9649 | Montessori Children's House | 1 | The recorded Kindergarten 1 level conflicts with the required Nursery level, and fee availability remains unresolved. |
| CENTRE:PT8541 | Greentree Montessori Children House  Pte Ltd | 1 | The recorded Kindergarten 1 level does not match the required Nursery level, and the saved programme is flexi-care rather than confirmed full-day care. |

**Provisional reference order (ties preserved):** 1: A2E Kids (CENTRE:PT8720) → 2: BRIGHT KIDS SCHOOL HOUSE PTE LTD (CENTRE:PT7380) → 3: Montessori Children's House (CENTRE:PT9649) → 4: Greentree Montessori Children House  Pte Ltd (CENTRE:PT8541)

**Reviewer rationale:** All have a recorded K1/Nursery mismatch; fee and flexi-care information is incomplete.

---
### 30. development-30-dde8be512f

**Scenario:** Deterministic fictional family template development 30: explores operator_scheme and transport preferences.

**Generation method:** deterministic_template. **Candidate retrieval:** not_executed.

#### Family profile

| Input | Value |
| --- | --- |
| Child date of birth | 2020-01-15 |
| Admission date | 2026-01-15 |
| Gross household income | 7500.0 |
| Citizenship category | Others |
| Requested programme | flexi_care_3 |
| Working hours per month | 56.0 |
| Household size | 3 |
| Non-earning dependants | 1 |
| Special approval | true |

#### Family preferences

**Hard constraints**

| Constraint | Value |
| --- | --- |
| None recorded | — |

**Normalized preference values**

| Preference | Value | Weight | Desired |
| --- | --- | --- | --- |
| operator_scheme | Anchor Operator Scheme | 4 | true |
| transport | false | 3 | true |

**Preference items and importance**

| Attribute | Value | Importance | Confidence | Evidence class |
| --- | --- | --- | --- | --- |
| operator_scheme | Anchor Operator Scheme | high_priority | 1.0 | partially_supported |
| transport | false | preferred | 1.0 | supported |

#### Recommended preschools and saved evaluation results

| Rank | School (ID) | Match score | Profile confidence | Combined score | Hard-constraint outcome | Stage 2 output |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | SMARTZ PLAYHOUSE PTE LTD (CENTRE:PT9006) | 100.0 | 0.33 | 57.7 | unknown | {"eligible": true, "eligible_level": "Kindergarten 2 (6 yrs old)", "fee_before_subsidy": 1150.0, "net_monthly_fee": 1150.0, "programme_id": "flexi_care_3", "status": "estimated"} |
| 2 | Learning Vision Sengkang General Hospital (CENTRE:PT9449) | 100.0 | 0.33 | 57.7 | unknown | {"eligible": true, "eligible_level": "Kindergarten 2 (6 yrs old)", "fee_before_subsidy": 670.0, "net_monthly_fee": 670.0, "programme_id": "full_day", "status": "estimated"} |
| 3 | MY WORLD PRESCHOOL LTD. (CENTRE:YM0160) | 100.0 | 0.33 | 57.7 | unknown | {"eligible": true, "eligible_level": "Kindergarten 2 (6 yrs old)", "fee_before_subsidy": 630.0, "net_monthly_fee": 630.0, "programme_id": "half_day_am", "status": "estimated"} |
| 4 | MOE KINDERGARTEN @ PUNGGOL VIEW (CENTRE:KM0004) | 0.0 | 0.0 | 0.0 | unknown | {"eligible": false, "eligible_level": "Kindergarten 2 (6 yrs old)", "fee_before_subsidy": null, "net_monthly_fee": null, "programme_id": null, "status": "fee_unavailable"} |

#### Human review

Reviewer-supplied grade and notes; not independently audited.

| School ID | School name | Relevance label | Reviewer notes |
| --- | --- | --- | --- |
| CENTRE:YM0160 | MY WORLD PRESCHOOL LTD. | 2 | It is a possible candidate because the saved result includes the requested operator-scheme preference in its ranking, but scheme participation and transport details are unverified. |
| CENTRE:PT9006 | SMARTZ PLAYHOUSE PTE LTD | 2 | It may be relevant, but the required operator-scheme status and transport arrangements are not confirmed. |
| CENTRE:KM0004 | MOE KINDERGARTEN @ PUNGGOL VIEW | 1 | Its scheme status and transport provision are unverified, and the saved result indicates unresolved fee eligibility. |
| CENTRE:PT9449 | Learning Vision Sengkang General Hospital | 2 | It is a possible candidate, but operator-scheme participation is unverified and the recorded full-day programme differs from the requested flexi-care programme. |

**Provisional reference order (ties preserved):** 1: MY WORLD PRESCHOOL LTD. (CENTRE:YM0160) → 2: SMARTZ PLAYHOUSE PTE LTD (CENTRE:PT9006) → 3: Learning Vision Sengkang General Hospital (CENTRE:PT9449) → 4: MOE KINDERGARTEN @ PUNGGOL VIEW (CENTRE:KM0004)

**Reviewer rationale:** Scheme participation and transport remain unresolved; some programme information conflicts with flexi-care needs.

---