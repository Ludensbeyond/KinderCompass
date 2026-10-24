# [ Practice Module ] KinderCompass — Preschool Recommender System

**[ Naming Convention ]** `IRS-PM-2026-07-GRP2-KinderCompass.zip`

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

KinderCompass organises its recommendation process into three principal stages.
The conversational tools may invoke the underlying capabilities independently
according to the user's request.

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
| Promotion (5 min) | `Video/KinderCompass-promotion.mp4` | Completed |
| System design (5 min) | `Video/KinderCompass-system.mp4` | Completed |

> Upload both videos to the `Video/` folder before final submission.  
> Note: AI-generated presentation speech is **not allowed**.

---

## SECTION 5 : Project Setup

The commands below target Windows PowerShell and must be run from the repository
root. For implementation details, see the
[implementation guide](docs/impl.md) and
[offline pipeline guide](SystemCode/src/scripts/README.md).

### 5.1 Prerequisites

- Python 3.11+
- Node.js 18+ with npm
- A Neo4j database
- OneMap credentials for geocoding and distance features
- An OpenAI API key for the default LLM-first conversation flow

### 5.2 Configure backend services

Create `.env` in the repository root. For the default LLM-first flow, configure
Neo4j, one supported OneMap authentication method, and OpenAI:

```dotenv
# Required by the launcher and Stage 1 graph search
NEO4J_URI=
NEO4J_USERNAME=
NEO4J_PASSWORD=

# Required for location features: use email/password...
ONEMAP_EMAIL=
ONEMAP_PASSWORD=

# ...or use an existing token instead
# ONEMAP_TOKEN=

# Required by the default LLM-first conversation flow
OPENAI_API_KEY=
```

The following settings are optional because the application already provides
these defaults. Add only the values that you need to override or make explicit:

```dotenv
NEO4J_DATABASE=neo4j
CONVERSATION_FLOW_MODE=llm-first
GENERAL_KNOWLEDGE_RETRIEVAL_MODE=curated
CONVERSATION_AGENT_MODE=agent
WEB_RAG_ANSWER_MODE=deterministic
OPENAI_PREFERENCE_EXTRACTION_ENABLED=false
OPENAI_INTENT_CLASSIFICATION_ENABLED=true
OPENAI_GROUNDED_EXPLANATIONS_ENABLED=false
OPENAI_WEB_RAG_ANSWERS_ENABLED=true
OPENAI_WEB_RAG_MODEL=gpt-4o-mini
OPENAI_WEB_RAG_TIMEOUT_SECONDS=8
```

Do not commit `.env`, and never put backend credentials in the frontend
environment. `AURA_INSTANCEID` and `AURA_INSTANCENAME` are not used by the
application and are therefore unnecessary. The launcher validates the three
Neo4j keys; OneMap and OpenAI configuration is checked when those integrations
are used.

`CONVERSATION_FLOW_MODE=legacy` runs the retained controller; `shadow` serves
the legacy response while observing the LLM-first path. A fully deterministic
legacy configuration can omit `OPENAI_API_KEY`, but its OpenAI-backed features
and agent modes must also be disabled explicitly.

### 5.3 Install dependencies

Create the virtual environment and install the complete development toolchain:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm install --prefix SystemCode/src/frontend
```

The root Python requirements include the backend, data pipeline, evaluation, and
notebook dependencies. The launcher's `-InstallDependencies` option installs the
backend runtime subset plus frontend packages.

### 5.4 Generate the catalogue and load Neo4j

The backend requires
`SystemCode/data/processed/kindercompass_master.json`. On a fresh checkout,
generate it before starting the application, then load the graph:

```powershell
.\.venv\Scripts\python.exe -m SystemCode.src.scripts.prepare_data
.\.venv\Scripts\python.exe -m SystemCode.src.scripts.build_knowledge_graph
```

Repeat these commands only after replacing raw data or changing preparation or
graph-loading logic. Graph updates are non-destructive by default. Review the
[knowledge graph schema](SystemCode/src/scripts/KNOWLEDGE_GRAPH_SCHEMA.md)
before using the pipeline's explicit destructive rebuild option.

### 5.5 Configure and launch the frontend

Create `SystemCode/src/frontend/.env.local` if it does not exist:

```dotenv
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

This value is public and must not contain credentials. Start both services:

```powershell
.\run_poc1.ps1
```

If only the runtime dependencies still need to be installed, use:

```powershell
.\run_poc1.ps1 -InstallDependencies
```

Open:

- Frontend: `http://localhost:3000`
- Backend API: `http://127.0.0.1:8000`
- Interactive API documentation: `http://127.0.0.1:8000/docs`

Use `-BackendPort <port>` to choose another backend port. Press `Ctrl+C` in each
server window to stop the application.

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
| My circumstances may require ECDA Special Approval | Unchecked |

Click **Save and continue to chat →**. The chat input should become available.
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
one another. Under **Adjust ranking importance**, preferences can be set to
**Required**, **High priority**, **Preferred**, or **Nice to have**. Montessori
should initially remain **Preferred** unless you change it.

Click **Show recommendations**. The Results tab should:

- exclude schools with a verified failure of the required transport preference;
- preserve schools whose transport evidence is genuinely unknown, with reduced
  evidence confidence;
- rank the remaining schools by the geometric mean of preference match
  percentage, which uses verified catalogue evidence, and weighted evidence
  completeness, which may include partial or inferred evidence; and
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
| Qualifying larger household | Income `8000`, household size `6`, non-earning dependants `3` | Uses a PCI of approximately `$1,333.33` internally for the subsidy estimate. Confirm the effect through the displayed subsidies and estimated amount payable; PCI itself is not shown. |
| Permanent Resident child | Citizenship `Permanent Resident` | Uses the matching SPR programme fee and applies no SC Basic or Additional Subsidy. |
| Flexi-care 1 or 3 | Select the corresponding flexi-care programme | Uses a matching centre fee and programme-specific policy table when offered. Flexi Care 1 AM and PM are retained as monthly variants. A school without the requested programme remains visible with a fallback warning and its lowest-fee supported option. |
| Flexi-care 2 | Select `Flexi-care 2 (confirm hours with centre)` | Uses a matching Flexi-care 2 fee when offered, but requires manual review and does not invent a subsidy. Otherwise, the school shows its lowest-fee supported option with a fallback warning. |
| Potential Special Approval | Check **My circumstances may require ECDA Special Approval** | Reports that ECDA review may be required instead of presenting an approved subsidy amount. |

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

1. Open the **Results** tab. Confirm the eligible level in each card header, the
   **Estimated amount payable** and subsidy breakdown in the fee notes, and,
   where coordinates are available, **Distance from home** under
   **Information available**. Expand **Optional ranking details** to see
   preference match, evidence completeness, and the combined ranking score.
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
   Directly below, **School Ratings by Other Kinder Compass users** should let
   you submit a 1–5 rating and select **Your experience**: **Researching the
   school**, **Applied the school**, **Visited the school**, or **Enrolled the
   school**. Leave consent unchecked and **Submit school rating** stays disabled.
   After consent and submit, the card should show the updated average and count.
   These ratings are first-party parent sentiment and do not change ranking.
   Local development ratings are written to the ignored file:

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
   available so hours, citizenship, care programme, and
   **My circumstances may require ECDA Special Approval** can be changed. Save,
   then click **Show recommendations** again.

### 6.6 Test conversation continuity and lost-in-the-middle handling

1. Complete the family form and enable **Remember my conversation and
   preferences** below the chat box.
2. Enter several preferences over separate turns, for example a required
   language, preferred pedagogy, maximum distance, and SPARK preference.
3. Change an earlier preference. Confirm that **Understood preferences** shows
   the latest value rather than the superseded one.
4. Create a contradiction, such as requiring Chinese and then requiring Malay.
   Do not resolve it yet. Refresh the browser and complete the family form again.
   **Understood preferences** and the unresolved contradiction should restore
   from the saved structured state. Compass should continue the unresolved
   decision instead of silently replacing either requirement. Previous chat
   messages do not reappear in the panel.
5. Enter more than six exchanges. Older turns should be removed from the
   server-side LLM context as its six-exchange or 8,000-character limit is
   reached. This bounded context is not displayed in the GUI; the latest
   confirmed structured preferences should continue to appear in
   **Understood preferences**.
6. Disable **Remember my conversation and preferences**, then refresh. The
   stored structured profile and unresolved decision should no longer return.

With consent enabled, recent user and assistant messages are retained as
server-side, process-local LLM context for 30 minutes of inactivity, with a
maximum of six exchanges and 8,000 characters. This transcript is not restored
to the visible chat panel after a refresh. The structured preference profile is
stored in SQLite for up to 180 days. The persistent profile excludes raw chat,
family details, postal codes, and selected schools; however, users should avoid
placing unnecessary personal information in chat because the temporary context
may contain details they type.

## SECTION 7 : Validation

The generated catalogue must exist before importing the backend. If it is
missing, run the preparation command from Section 5.4 first.

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

Validate the offline preparation and graph-loading pipeline with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s SystemCode/src/scripts/tests -v
```

Evaluation artefacts under `SystemCode/src/backend/evaluation/` and
`SystemCode/src/backend/output/` describe specific recorded snapshots. Do not
combine figures from different snapshots unless their catalogue, configuration,
model, and run identifiers match.

## SECTION 8 : Repository structure

```text
KinderCompass/
├── README.md                 # Project overview, setup, user guide, and validation
├── requirements.txt          # Complete Python development environment
├── run_poc1.ps1              # Windows backend and frontend launcher
├── Makefile                  # Evaluation convenience targets
├── member-github.txt         # Group info for Canvas submission
├── SystemCode/               # Runnable system
│   ├── src/
│   │   ├── scripts/          # Offline data pipeline
│   │   ├── backend/          # FastAPI, agents, Stage 1–3, RAG, and tests
│   │   └── frontend/         # Next.js website
│   └── data/
│       ├── raw/              # Original datasets
│       ├── processed/        # Generated catalogue and graph inputs
│       └── vectors/          # Local retrieval indexes
├── ProjectReport/            # Report documents, presentations, and supporting files
├── Video/                    # Promotion and system design videos
├── Miscellaneous/            # Non-runnable supporting submission material
│   └── notebooks/            # Interactive pipeline demonstrations
└── docs/                     # Architecture, PoC, and evaluation documentation
```
