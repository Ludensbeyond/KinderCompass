# KinderCompass agent architecture

The default chat endpoint runs the bounded LLM-first loop. Repositories own
school facts and policy; deterministic tools own ranking, fees, eligibility,
distance and validated preference updates.

```mermaid
flowchart TD
    browser["Next.js: message, profile, family inputs, stable school IDs"]
    api["FastAPI /api/preferences: request validation"]
    mode{"CONVERSATION_FLOW_MODE"}
    browser --> api --> mode
    mode -->|"llm-first: default"| context
    context["Bounded context: current authoritative state and consented history"]
    model["LLM: interpret message, select actions or reply directly"]
    tools["Validate arguments; execute structured tools on local staged state"]
    sources["School repository, dated policy, OneMap, curated evidence"]
    context --> model
    model -->|"Needs facts or action"| tools
    sources --> tools
    tools -->|"Structured results, provenance, missing inputs"| model
    model --> validate{"Response values, attribution, citations and state valid?"}
    validate -->|"Bounded repair"| model
    validate -->|"Yes"| commit["One validated state/history commit and consented memory write"]
    validate -->|"Failure or limits"| failure["Fixed service error; discard staged changes"]
    commit --> serve["PreferenceResponse and one feedback record"]
    failure --> serve
    serve --> browser
    mode -->|"legacy or shadow"| legacy["Retained legacy service; CONVERSATION_AGENT_MODE controls old supervisor"]
    legacy -->|"Single retained response"| serve
    legacy -.->|"shadow only"| shadow["New loop on isolated request-local state; no shared transcript or persistence"]
    shadow --> compare["Scalar profile/readiness/citation comparison"]
    commit -.-> telemetry["Privacy-safe counts, elapsed time, token usage, estimated cost and failure category"]
    failure -.-> telemetry
    compare -.-> telemetry
    staged["Explicit /api/preferences/llm-first evaluation endpoint"] --> context
```

The loop permits zero-tool greetings/clarifications and dependent, combined
requests. It allows eight model invocations, twelve tool calls, four mutations
and 30 seconds by default; bounded repair shares those budgets. Failed turns
never run legacy fallback. Shadow adds inline latency but never writes history,
preference memory or answer feedback.

`CONVERSATION_FLOW_MODE=legacy` selects rollback; use the existing
`CONVERSATION_AGENT_MODE=deterministic` for controller-only rollback. Retain
legacy wrappers for the seven-day observation period and review before cleanup.
School-demo gates passed; strict evaluation and production readiness remain
unmet. See [rollout contract](../SystemCode/src/backend/doc/llm-first-rollout.md),
[HTTP integration](../SystemCode/src/backend/doc/llm-first-http.md) and
[backend progress](../SystemCode/src/backend/doc/agents.md).
