# KinderCompass agent architecture

The backend uses a bounded LangGraph conversation supervisor with typed capability
tools and an independently configurable selected-school evidence graph. School
facts, preference changes, ranking, eligibility, fees, and distance calculations
remain backend-owned.

```mermaid
flowchart TD
    browser["Next.js chat: message, profile, family inputs and school IDs"]
    api["FastAPI: POST /api/preferences"]
    context["PreferenceService: classify intent and build authoritative context"]
    mode{"CONVERSATION_AGENT_MODE"}

    browser --> api --> context --> mode

    subgraph controller["Existing conversation path"]
        legacy["Conversation controller: preferences, decisions and evidence"]
        evidenceMode{"Selected-school evidence question and WEB_RAG_ANSWER_MODE=agent?"}
        evidenceGraph["Selected-school graph: retrieve for one school, compose and validate citations"]
        legacyResult["Controller response"]
        legacy --> evidenceMode
        evidenceMode -->|"Yes, in deterministic conversation mode"| evidenceGraph
        evidenceMode -->|"No, or graph entry disabled"| legacyResult
        evidenceGraph -->|"Validated answer or controller fallback"| legacyResult
    end

    mode -->|"deterministic: explicit override"| legacy
    mode -->|"shadow: disable selected-school graph"| legacy

    subgraph agent["Full-conversation LangGraph supervisor"]
        route["Route: server-classified intent, otherwise model routing"]
        select["Model selects from intent-scoped tools"]
        tools["Execute typed, context-bound capability tools"]
        compose["Model composes from tool output; use authoritative wording when needed"]
        validate{"Validate route, execution, profile, grounding and citations"}
        candidate["Accepted agent response"]
        fallback["Controller fallback with both graph entry points disabled"]
        route --> select --> tools --> compose --> validate
        validate -->|"Accepted"| candidate
        validate -->|"Rejected"| fallback
        route -.->|"Clarification or execution failure"| fallback
        select -.->|"Failure or execution limit"| fallback
        tools -.->|"Failure"| fallback
        compose -.->|"Failure"| fallback
    end

    mode -->|"agent: default, including blank or invalid configuration"| route
    legacyResult -->|"shadow only: retain response and evaluate candidate inline"| route

    subgraph capabilities["15 registered capabilities"]
        preferences["Preference state: update, reset, continue pending flow"]
        decisions["Decisions and calculations: nearest, top rank, compare, trade-offs, provenance, recommend, assess, what-if, exclusion"]
        facts["Allowlisted structured school facts"]
        retrieval["School evidence and general guidance retrieval"]
    end

    tools --> preferences
    tools --> decisions
    tools --> facts
    tools --> retrieval

    sources["Backend sources: school repository and Neo4j, dated policy, OneMap, curated evidence indexes"]
    sources -.->|"Authoritative context"| context
    sources -.->|"Facts and calculations"| decisions
    sources -.-> facts
    sources -.-> retrieval
    sources -.-> evidenceGraph

    serve{"Select served response"}
    legacyResult -->|"deterministic"| serve
    candidate -->|"agent: serve candidate; shadow: serve retained controller response"| serve
    fallback -->|"agent: serve fallback; shadow: serve retained controller response"| serve
    response["Decision-state enrichment and unchanged PreferenceResponse contract"]
    persistence["API: optional structured preference memory and one answer-feedback record"]
    serve --> response --> persistence --> browser

    observations["Privacy-safe telemetry: mode, counts, latency, validation and fallback categories"]
    candidate -.-> observations
    fallback -.-> observations
```

- **Bounds:** the supervisor allows at most three capability calls and one profile
  mutation per turn; the default route/model iteration limit is six. The separate
  selected-school graph defaults to one retrieval call and three model iterations.
- **State:** each graph runs for one request. The returned profile carries
  conversation continuity; opt-in SQLite memory stores selected structured
  profile fields with 180-day retention rather than raw chat or family inputs.
- **Rollout:** agent is the default for missing, blank, or invalid configuration.
  Set `CONVERSATION_AGENT_MODE=deterministic` to use the existing controller.
  Shadow evaluates inline without
  changing the served controller response. Agent mode serves validated output
  and falls back to the controller on failure.
- **Grounding:** citation validation enforces source and school scope. General
  supervisor wording validation is lexical; selected-school evidence answers
  preserve the retrieval adapter's wording.

Implementation references: [PreferenceService](../SystemCode/src/backend/services/preference_service.py),
[supervisor](../SystemCode/src/backend/agents/supervisor.py),
[tools](../SystemCode/src/backend/agents/tools.py),
[validation](../SystemCode/src/backend/agents/validation.py), and
[readiness and rollout record](../SystemCode/src/backend/doc/agents.md).
