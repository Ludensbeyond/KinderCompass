# [ Practice Module ] KinderCompass — Preschool Recommender System

**[ Naming Convention ]** `IRS-PM-YYYY-MM-DD-STKxx-GRP-TeamName-KinderCompass.zip`

**GitHub:** https://github.com/Ludensbeyond/KinderCompass

---

## SECTION 1 : PROJECT TITLE

## KinderCompass: A Preschool Recommender System

An intelligent multi-stage decision-support system that helps parents in
Singapore find, compare, and plan preschool enrolment using explainable
preference ranking, eligibility and cost rules, distance calculations, a Neo4j
knowledge graph, and grounded guidance.

---

## SECTION 2 : EXECUTIVE SUMMARY / PAPER ABSTRACT

Choosing a preschool in Singapore involves reconciling distance, fees,
eligibility, curriculum preferences, service availability, and the quality of
supporting evidence. Existing search tools provide useful catalogue information
but offer limited conversational preference handling, explainable matching, and
integrated comparison support.

KinderCompass implements a three-stage workflow:

| Stage | Capability |
|---|---|
| Stage 1 | Convert conversational preferences into validated constraints and explainably ranked Neo4j results. |
| Stage 2 | Evaluate exact-age and programme eligibility, then estimate fees using citizenship-specific centre fees and dated ECDA subsidy rules. |
| Stage 3 | Compare selected eligible centres with home using OneMap geocoding and straight-line distance. |

The system also provides evidence provenance, recommendation explanations, and
school-isolated official-webpage retrieval. Data is sourced from
[data.gov.sg](https://data.gov.sg) ECDA preschool registries. The application is
delivered through a FastAPI backend and Next.js frontend.

---

## SECTION 3 : CREDITS / PROJECT CONTRIBUTION

| Official Full Name | Student ID | Work Items (Who Did What) | Email (Optional) |
|---|---|---|---|
| Eunice Goh | [TBD] | [TBD] | [TBD] |
| Henry Foo Yong Jie | [TBD] | [TBD] | [TBD] |
| Jarebb | [TBD] | [TBD] | [TBD] |
| Jawad Bin Joha | [TBD] | [TBD] | [TBD] |

---

## SECTION 4 : VIDEO OF SYSTEM MODELLING & USE CASE DEMO

| Video | File | Status |
|---|---|---|
| Promotion (5 min) | `Video/KinderCompass-promotion.mp4` | Pending |
| System design (5 min) | `Video/KinderCompass-system.mp4` | Pending |

> Upload both videos to the `Video/` folder before final submission.  
> Note: AI-generated presentation speech is **not allowed**.

---

## SECTION 5 : Project Setup

See the detailed [KinderCompass PoC 1 guide](docs/poc1/Readme.md) and the user
guide PDF in `ProjectReport/`.

### [ 1 ] Prerequisites

- Python 3.11+
- Node.js 18+ with npm
- Neo4j database for Stage 1 knowledge-graph search
- OneMap credentials for postal-code and distance features
- optional OpenAI API credentials for enabled LLM features

Create a `.env` file in the repository root and add your environment-specific
credentials:

```dotenv
# Required for Stage 1 graph search
NEO4J_URI=
NEO4J_USERNAME=
NEO4J_PASSWORD=
NEO4J_DATABASE=neo4j

# Required for postal-code and distance features
ONEMAP_EMAIL=
ONEMAP_PASSWORD=

# Optional LLM features
OPENAI_API_KEY=
OPENAI_PREFERENCE_EXTRACTION_ENABLED=false
OPENAI_INTENT_CLASSIFICATION_ENABLED=false
OPENAI_GROUNDED_EXPLANATIONS_ENABLED=false
OPENAI_WEB_RAG_ANSWERS_ENABLED=false
```

Replace the blank values with your credentials. Keep any unused OpenAI features
set to `false`, and do not commit `.env` or place backend credentials in the
frontend `.env.local` file.

### [ 2 ] Python dependencies

Create the repository virtual environment if it does not already exist, then
install the complete Python environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

This installs the FastAPI backend, reusable Stage 1–3 packages, offline data
pipeline, evaluation utilities, and notebook dependencies.

### [ 3 ] Initialize or refresh the data pipeline when required

You do **not** run this step for every application launch. Run it only when:

- setting up an empty Neo4j database for the first time;
- replacing or refreshing files under `SystemCode/data/raw/`; or
- changing catalogue preparation or graph-loading logic.

Prepare the catalogue first, then update Neo4j:

```powershell
.\.venv\Scripts\python.exe -m SystemCode.src.scripts.prepare_data
.\.venv\Scripts\python.exe -m SystemCode.src.scripts.build_knowledge_graph
```

If `SystemCode/data/processed/kindercompass_master.json` is current and the
configured Neo4j database is already populated, skip this step. The application
launcher does not rebuild the catalogue or graph.

Raw datasets are stored in `SystemCode/data/raw/`; the generated catalogue is
written to `SystemCode/data/processed/kindercompass_master.json`. Graph updates
are non-destructive by default. See the
[offline pipeline guide](SystemCode/src/scripts/README.md) before using the
explicit destructive rebuild option. The
[knowledge graph schema](SystemCode/src/scripts/KNOWLEDGE_GRAPH_SCHEMA.md)
documents which features are properties or nodes, their relationships, source
mapping, constraints, and current limitations.

### [ 4 ] Run locally

For the first application launch, install the frontend and backend runtime
dependencies and start both services:

```powershell
.\run_poc1.ps1 -InstallDependencies
```

For normal subsequent launches:

```powershell
.\run_poc1.ps1
```

In short: initialize the data only when Neo4j or the source catalogue needs it;
otherwise start directly with `run_poc1.ps1`.

## SECTION 6 : User Guide

Start KinderCompass with `run_poc1.ps1`, wait for both services to report that
they are ready, and open `http://localhost:3000`. The following walkthroughs
exercise the main GUI inputs and expected behaviour.

### 6.1 Test family details and exact-age eligibility

In the **Form** tab, enter:

| Field | Test value |
|---|---|
| Child's date of birth | `10 June 2023` |
| Admission date | `10 June 2026` |
| Child citizenship | `Singapore Citizen` |
| Care programme | `Full day` |
| Gross monthly income | `4500` |
| Applicant working hours/month | `56` |
| Household size | `4` |
| Non-earning dependants | `2` |
| Home postal code | Any valid six-digit Singapore postal code |
| Special Approval | Unchecked |

Click **Save and continue to chat**. The chat input should become available.
After recommendations are generated, eligible schools should show
**Pre-Nursery (3 yrs old)** because the child is exactly 36 completed months old
on the admission date.

To test the age boundary, change the admission date to `9 June 2026` and repeat
the search. The child is then 35 completed months old, so the expected level is
**Playgroup (18 mths to 2 yrs old)**.

### 6.2 Test conversational preferences and ranking inputs

After saving the family form, enter the following messages into **Compass
chat**, one at a time:

```text
I need a preschool that teaches Chinese.
Montessori is preferred, but transport is required.
It must be within 2 km from my home.
```

Check the **Understood preferences** panel after each message. Chinese,
Montessori, transport, and the 2 km limit should accumulate instead of replacing
one another. Use the importance selectors to change Montessori between
**Preferred**, **High priority**, or **Nice to have**.

Click **Show recommendations**. The Results tab should:

- exclude schools with a verified failure of the required transport preference;
- preserve schools whose transport evidence is genuinely unknown, with reduced
  evidence confidence;
- rank the remaining schools by verified preference match and then evidence
  confidence; and
- retain only schools within the requested 2 km limit when location evidence is
  available.

### 6.3 Test fee and potential subsidy inputs

Run the same recommendation search several times while changing only the family
form values:

| Scenario | Inputs | Expected GUI behaviour |
|---|---|---|
| Working SC applicant | Citizenship `Singapore Citizen`, full day, income `4500`, working hours `56` | Uses the matching SC full-day fee and the applicable Basic and Additional Subsidy tables. |
| Working-hours boundary | Change working hours from `56` to `55` | Treats the applicant as non-working; Additional Subsidy becomes unavailable and the estimate increases. |
| Qualifying larger household | Income `8000`, household size `6`, non-earning dependants `3` | Uses the qualifying per-capita-income assessment; PCI is approximately `$1,333.33`. |
| Permanent Resident child | Citizenship `Permanent Resident` | Uses the matching SPR programme fee and applies no SC Basic or Additional Subsidy. |
| Flexi-care 1 or 3 | Select the corresponding flexi-care programme | Uses a matching centre fee and programme-specific policy table when offered. A school without that programme remains visible with a fallback warning and its lowest-fee supported option. |
| Flexi-care 2 | Select `Flexi-care 2 (confirm hours with centre)` | Uses a matching Flexi-care 2 fee when offered, but requires manual review and does not invent a subsidy. Otherwise, the school shows its lowest-fee supported option with a fallback warning. |
| Potential Special Approval | Check the Special Approval box | Reports that ECDA review may be required instead of presenting an approved subsidy amount. |

The displayed amount is an indicative monthly estimate based on reported facts.
It is not an ECDA subsidy approval, and GST treatment or additional centre
charges may differ.

### 6.4 Test programme selection, results, map, and explanations

After clicking **Show recommendations**:

1. Open the **Results** tab and confirm that each card shows match percentage,
   evidence confidence, eligible level, estimated fee, and home distance where
   location data is available.
2. Find a school card with more than one entry in its **Programme** selector.
   The list should contain only programmes offered by that school for the
   child's eligible level and citizenship. Full Day, Half Day AM, and Half Day
   PM appear as separate options when present in the source catalogue.
3. Record the displayed monthly fee, choose another programme, and wait for the
   selector to become active again. Confirm that the card displays the selected
   programme and its recalculated monthly estimate. Switching between Half Day
   AM and Half Day PM must use the corresponding fee rather than the cheaper of
   the two.
4. To test programme fallback, return to the **Form** tab, choose a less common
   option such as Flexi-care 3, and generate recommendations again. A school
   that does not offer the preferred programme should remain visible when it
   has another supported option. Its card should show this warning:

   ```text
   Your preferred programme is unavailable at this school; the lowest-fee available option is shown.
   ```

   The selector must not list the unavailable programme. A school with no
   supported programme for the child's level and citizenship is excluded from
   the eligible results.
5. Expand **How this score was calculated**. Verify that each ranked preference
   shows its importance, contribution, source, evidence state, and last-updated
   date.
6. Change the **Distance from home** selector between `None`, `1`, `2`, and `5`
   km. The visible result count should change while the original ranking order
   is preserved.
7. Select two or more schools. Their pins should appear on the map with the home
   pin and independently calculated straight-line distances.
8. Ask Compass chat:

   ```text
   Compare the selected schools.
   ```

   The response should compare only the selected schools using grounded match,
   fee, evidence, and distance information. You can also ask:

   ```text
   Why is the first school ranked highest?
   What are the trade-offs of the selected schools?
   Where did the information about this school come from?
   ```

If a value or official-webpage claim is unavailable, the GUI should say that
the evidence is unavailable rather than interpreting missing evidence as a
negative answer.

### 6.5 Test recommendation feedback

Generate recommendations first, then open the **Feedback** tab and test
the following inputs:

1. Choose a school from the feedback **School** selector. Only schools from the
   current recommendation result should be available.
2. Select an **Outcome**, such as `Selected for comparison`, `Rejected`,
   `Contacted centre`, `Visited centre`, or `Applied`.
3. Select the **Main reason** that best explains the outcome. Available reasons
   include match quality, fee, distance, programme, and evidence quality.
4. Leave the consent checkbox unchecked. **Submit feedback** should remain
   disabled and no feedback should be stored.
5. Check **I consent to storing this anonymous feedback for recommendation
   evaluation**, then submit. The GUI should display:

   ```text
   Thank you. Your anonymous feedback was recorded.
   ```

6. Select `Rate recommendation`. A **Usefulness** selector should appear. Test
   ratings from `1 / 5` to `5 / 5`, provide consent again, and submit.
7. Generate a new recommendation search and submit feedback for it. Feedback is
   linked to the new immutable recommendation snapshot rather than overwriting
   the earlier result.

The anonymous session identifier is generated in the browser and contains no
family information. Recommendation snapshots contain school IDs, ranks,
scores, selected programme IDs, estimated fees, and data/policy versions. They
do not store family-form values, postal codes, or chat text. Local development
feedback is written to the ignored file:

```text
SystemCode/src/backend/output/recommendation_feedback.sqlite3
```

This feedback is evaluation data for a future explainable ranking model. It
does not currently change eligibility, subsidies, required filters, or the live
ranking order.

## SECTION 7 : Repository structure

```text
KinderCompass/
├── README.md                 # This file (IRS Sections 1–5)
├── member-github.txt         # Group info for Canvas submission
├── SystemCode/               # Runnable system
│   ├── src/
│   │   ├── scripts/          # Offline data pipeline
│   │   ├── backend/          # FastAPI three-stage workflow
│   │   └── frontend/         # Next.js website
│   ├── data/
│   │   ├── raw/              # Original datasets
│   │   └── processed/        # Cleaned data and graph inputs
│   └── notebooks/            # Exploration and demonstrations
├── ProjectReport/            # Final group report and user guide PDFs
├── Video/                    # Promotion and system design videos
├── Miscellaneous/            # Supporting files
└── docs/                     # PoC documentation and working drafts
```
