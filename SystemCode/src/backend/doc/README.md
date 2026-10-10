# Backend directory guide

This directory documents the purpose and ownership boundary of each maintained
backend folder. The backend root contains the FastAPI entry point (`main.py`),
dependency constraints, contributor guidance, and the following areas:

| Folder | Purpose | Guide |
|---|---|---|
| `agents/` | Backend-only configuration and bounded LangGraph orchestration. | [Active LLM-first progress / readiness history](agents.md) · [Implementation 2 archive](impl2-agent-step2.md) · [Implementation 1 archive](impl1-agent-step1.md) |
| `domain/` | Infrastructure-independent data contracts. | [Domain](domain.md) |
| `repositories/` | Authoritative catalogue and policy access. | [Repositories](repositories.md) |
| `services/` | Application use cases and orchestration. | [Services](services.md) |
| `pipeline/` | Reusable recommendation and distance logic. | [Pipeline](pipeline.md) |
| `scripts/` | Offline audits, evaluations, and data preparation. | [Scripts](scripts.md) |
| `resources/` | Versioned, curated inputs used at runtime or during evaluation. | [Resources](resources.md) |
| `tests/` | Automated backend regression coverage. | [Tests](tests.md) |
| `output/` | Generated pipeline, audit, and review artifacts. | [Output](output.md) |
| `doc/` | Durable backend design and directory documentation. | This index |

The [active progress record](agents.md) links the repository LLM-first plan and
[Step 1 architecture baseline](llm-first-baseline.md). These govern the current
one-step session protocol; the completed readiness work remains historical. The
[Step 2 context contract](llm-first-context.md) documents ephemeral opt-in
history, session leases and the minimal new-flow model context. The
[Step 3 tool contract](llm-first-tools.md) documents typed capabilities and
request-local staged state. The
[Implementation 2 archive](impl2-agent-step2.md) preserves the completed
full-conversation supervisor migration, and the
[Implementation 1 archive](impl1-agent-step1.md) preserves the completed
selected-school evidence migration.

The normal request path is `main.py` → `services/` → `repositories/` and
`pipeline/`, with shared request and response shapes supplied by `domain/`.
Browser code must call the FastAPI boundary and must not access repositories,
resources, or external providers directly.

The [file-based vector store plan](../../../../docs/file-vector-store-plan.md) describes the
planned parent-guide index under `SystemCode/data/vectors/`, its source review,
agent integration, deterministic fallback, and evaluation gates.
The [step 1 source review](file-vector-source-review.md) records approved
citations, excluded claims and the fixed embedding configuration.
The [step 2 chunking guide](file-vector-chunking.md) describes offline Markdown
selection, stable chunk metadata, and preservation of table and policy context.

The [step 6 evaluation and demo guide](file-vector-demo.md) records independent
lexical/vector results, failures, memory/latency and build/query/rollback commands.
