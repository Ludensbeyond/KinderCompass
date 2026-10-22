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

KinderCompass organises its recommendation process into three principal stages, although conversational tools may invoke the underlying capabilities independently according to the user’s request.:

| Stage | Capability |
|---|---|
| Stage 1 | Convert conversational preferences into validated constraints, retrieve candidates, and rank them using preference match and evidence completeness. |
| Stage 2 | Evaluate exact-age and programme eligibility, then estimate fees using citizenship-specific centre fees and dated ECDA subsidy rules. |
| Stage 3 | Compare selected eligible centres with home using OneMap geocoding and straight-line distance. |

The system also provides evidence provenance, recommendation explanations, and
separate text-retrieval channels for parent guidance and school-isolated
official-webpage evidence. Neo4j supports relationship-based candidate retrieval;
the conversational path applies equivalent supported constraints to the processed
catalogue before invoking the shared scorer. Data is sourced from
[data.gov.sg](https://data.gov.sg) ECDA preschool registries. The application is
delivered through a FastAPI backend and Next.js frontend.

---

## SECTION 3 : CREDITS / PROJECT CONTRIBUTION

| Official Full Name | Student ID | Work Items (Who Did What) | Email (Optional) |
|---|---|---|---|
| Eunice Goh | XXXXX751A | Deterministic eligibility and subsidy estimation; evidence-aware recommendation ranking | — |
| Henry Foo Yong Jie | XXXXX999B | Data preparation; Neo4j knowledge graph; hybrid retrieval; provenance and RAG | — |
| Jarebb Ng | XXXXX998A | Conversational AI; preference modelling; tool and response validation | — |
| Jawad Bin Joha | XXXXX585U | FastAPI and frontend application; OneMap integration; evaluation and testing | — |

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

See the detailed [KinderCompass PoC 1 guide](docs/poc1/Readme.md) and the latest
project report in `ProjectReport/`.

### [ 1 ] Prerequisites

- Python 3.11+
- Node.js 18+ with npm
- Neo4j database for Stage 1 knowledge-graph search
- OneMap credentials for postal-code and distance features
- OpenAI API credentials for the default LLM-first conversation flow, or an
  explicit legacy deterministic configuration

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

# Required for the default LLM-first conversation flow
OPENAI_API_KEY=

# Conversation rollout: llm-first (default), shadow, or legacy
CONVERSATION_FLOW_MODE=llm-first

# Optional retrieval and retained legacy-flow settings
GENERAL_KNOWLEDGE_RETRIEVAL_MODE=curated
OPENAI_PREFERENCE_EXTRACTION_ENABLED=false
OPENAI_INTENT_CLASSIFICATION_ENABLED=false
OPENAI_GROUNDED_EXPLANATIONS_ENABLED=false
OPENAI_WEB_RAG_ANSWERS_ENABLED=false

OPENAI_WEB_RAG_MODEL=gpt-4o-mini
OPENAI_WEB_RAG_TIMEOUT_SECONDS=8
ONEMAP_TOKEN=
WEB_RAG_ANSWER_MODE=agent
CONVERSATION_AGENT_MODE=agent
```

Replace the blank values with your credentials. `ONEMAP_TOKEN` can be used
instead of email/password when a valid token is already available. Do not commit
`.env` or place backend credentials in the frontend `.env.local` file.

`CONVERSATION_FLOW_MODE` controls the `/api/preferences` rollout. Its default,
`llm-first`, requires a valid OpenAI configuration. Set it to `legacy` to serve
the retained legacy controller, or `shadow` to serve the legacy response while
observing the LLM-first path. Invalid values fail visibly instead of silently
selecting another flow. `CONVERSATION_AGENT_MODE` configures the retained legacy
supervisor and is separate from this HTTP rollout.

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

Programme-fee normalisation retains supported Full Day, Half Day, and Flexi
Care monthly variants. Emergency Care and rates explicitly described as hourly,
daily, per-session, termly, or annual are excluded from monthly fee comparisons.

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
- rank the remaining schools by the geometric mean of verified preference match
  and weighted evidence completeness; and
- retain only schools within the requested 2 km limit when location evidence is
  available.

Evidence completeness measures how much weighted preference evidence is usable;
it does not establish that the underlying information is correct or current.
Cost and distance provide comparison context but do not increase the ranking
score.

### 6.3 Test fee and potential subsidy inputs

Run the same recommendation search several times while changing only the family
form values:

| Scenario | Inputs | Expected GUI behaviour |
|---|---|---|
| Working SC applicant | Citizenship `Singapore Citizen`, full day, income `4500`, working hours `56` | Uses the matching SC full-day fee and the applicable Basic and Additional Subsidy tables. |
| Working-hours boundary | Change working hours from `56` to `55` | Treats the applicant as non-working; Additional Subsidy becomes unavailable and the estimate increases. |
| Qualifying larger household | Income `8000`, household size `6`, non-earning dependants `3` | Uses the qualifying per-capita-income assessment; PCI is approximately `$1,333.33`. |
| Permanent Resident child | Citizenship `Permanent Resident` | Uses the matching SPR programme fee and applies no SC Basic or Additional Subsidy. |
| Flexi-care 1 or 3 | Select the corresponding flexi-care programme | Uses a matching centre fee and programme-specific policy table when offered. Flexi Care 1 AM and PM are retained as monthly variants. A school without the requested programme remains visible with a fallback warning and its lowest-fee supported option. |
| Flexi-care 2 | Select `Flexi-care 2 (confirm hours with centre)` | Uses a matching Flexi-care 2 fee when offered, but requires manual review and does not invent a subsidy. Otherwise, the school shows its lowest-fee supported option with a fallback warning. |
| Potential Special Approval | Check the Special Approval box | Reports that ECDA review may be required instead of presenting an approved subsidy amount. |

The programme selector distinguishes the estimated net amount from the fee
before subsidy. The selected card separately shows the programme fee, Basic
Subsidy, applied Additional Subsidy, applicable maximum Additional Subsidy, and
minimum co-payment when those values are available. A full-day programme can
therefore have a lower estimated amount payable than a shorter programme because
the policy subsidy amounts differ. The result remains an indicative estimate
based on reported family details; it is not an ECDA subsidy approval, and GST
treatment or additional centre charges may differ.

### 6.4 Test programme selection, results, map, and explanations

After clicking **Show recommendations**:

1. Open the **Results** tab and confirm that each card shows match percentage,
   evidence confidence, eligible level, estimated fee, and home distance where
   location data is available.
2. Find a school card with more than one entry in its **Programme and estimated
   monthly cost** selector. The list should contain only programmes offered by
   that school for the child's eligible level and citizenship. Estimated options
   display both the net amount and fee before subsidy. Full Day, Half Day AM,
   Half Day PM, and Flexi Care 1 AM/PM appear as distinct options when present
   in the source catalogue.
3. Record the displayed estimated amount payable, choose another programme, and
   wait for the selector to become active again. Confirm that the card displays
   the selected programme and its recalculated monthly estimate. Switching
   between AM and PM variants must use the corresponding fee rather than the
   cheaper sibling fee.
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
5. Expand **Optional ranking details**. Verify that the card explains preference
   match, evidence completeness, and the combined geometric-mean score. The
   explanation should state that these internal measures do not establish
   factual accuracy.
6. On the same card, **Parent mentions online** should offer Google Maps, Google
   reviews, and Reddit search links for that school name and postal code. They
   open a web search; they are not a verified listing and do not change ranking.
   Directly below, **Parent ratings on KinderCompass** should let you submit a
   1–5 rating and your experience (`Researching`, `Applied`, `Visited`, or
   `Enrolled`). Leave consent unchecked and **Submit school rating** stays
   disabled. After consent and submit, the card should show the updated average
   and count. These ratings are first-party parent sentiment and do not change
   ranking. Local development ratings are written to the ignored file:

   ```text
   SystemCode/src/backend/output/school_ratings.sqlite3
   ```
7. Change the **Distance from home** selector between `None`, `1`, `2`, and `5`
   km. The visible result count should change while the original ranking order
   is preserved.
8. Select two or more schools. Their pins should appear on the map with the home
   pin and independently calculated straight-line distances.
9. Ask Compass chat:

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

### 6.5 Test the map tab

The third tab is **Map**. Recommendation-outcome feedback is no longer a tab.
School ratings stay on each result card, as described in section 6.4, and they
do not change ranking.

1. Select two or more schools on **Results**.
2. Open **Map**.
3. Confirm the home pin, one pin for each selected preschool, and the Home /
   Preschools legend. The legend is hidden when the window is narrower than
   600 pixels.
4. Open **Form** after recommendations. **Edit family details** should be
   available so hours, citizenship, care programme, and Special Approval can
   be changed. Save, then click **Show recommendations** again.

### 6.6 Test conversation continuity and lost-in-the-middle handling

1. Complete the family form and enable **Remember my conversation and
   preferences** below the chat box.
2. Enter several preferences over separate turns, for example a required
   language, preferred pedagogy, maximum distance, and SPARK preference.
3. Change an earlier preference. Confirm that **Understood preferences** shows
   the latest value rather than the superseded one.
4. Create a contradiction, such as requiring Chinese and then requiring Malay.
   Do not resolve it yet. Refresh the browser. After completing the family form,
   answer the restored contradiction; the chat should continue the unresolved
   decision instead of silently replacing either requirement.
5. Enter more than six exchanges. The in-memory conversation window should
   remain bounded while the latest confirmed structured preferences continue to
   appear in **Understood preferences**.
6. Disable **Remember my conversation and preferences**, then refresh. The
   retained conversation and stored structured profile should no longer return.

With consent enabled, recent user and assistant messages are retained in
process-local memory for 30 minutes of inactivity, with a maximum of six
exchanges and 8,000 characters. The structured preference profile is stored in
SQLite for up to 180 days. The persistent profile excludes raw chat, family
details, postal codes, and selected schools; however, users should avoid placing
unnecessary personal information in chat because recent messages may contain
details they type.

## SECTION 7 : Validation

Set the backend import paths, then run the automated backend suite:

```powershell
$env:PYTHONPATH = "SystemCode/src/backend;SystemCode/src/backend/pipeline"
.\.venv\Scripts\python.exe -m unittest discover -s SystemCode/src/backend/tests -v
```

The focused fee and policy regression set can be run independently:

```powershell
$env:PYTHONPATH = "SystemCode/src/backend;SystemCode/src/backend/pipeline"
.\.venv\Scripts\python.exe -m unittest -v `
  SystemCode.src.backend.tests.test_fee_units `
  SystemCode.src.backend.tests.test_stage2_policy
```

Validate the production frontend build with:

```powershell
npm --prefix SystemCode/src/frontend run build
```

Evaluation artefacts under `SystemCode/src/backend/evaluation/` and
`SystemCode/src/backend/output/` describe specific recorded snapshots. Do not
combine figures from different snapshots unless their catalogue, configuration,
model, and run identifiers match.

## SECTION 8 : Repository structure

```text
KinderCompass/
├── README.md                 # Project overview, setup, user guide, and validation
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
├── ProjectReport/            # Report documents, presentations, and supporting files
├── Video/                    # Promotion and system design videos
├── Miscellaneous/            # Supporting files
└── docs/                     # PoC documentation and working drafts
```
