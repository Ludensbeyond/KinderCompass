# Backend directory guide

This directory documents the purpose and ownership boundary of each maintained
backend folder. The backend root contains the FastAPI entry point (`main.py`),
dependency constraints, contributor guidance, and the following areas:

| Folder | Purpose | Guide |
|---|---|---|
| `domain/` | Infrastructure-independent data contracts. | [Domain](domain.md) |
| `repositories/` | Authoritative catalogue and policy access. | [Repositories](repositories.md) |
| `services/` | Application use cases and orchestration. | [Services](services.md) |
| `pipeline/` | Reusable recommendation and distance logic. | [Pipeline](pipeline.md) |
| `scripts/` | Offline audits, evaluations, and data preparation. | [Scripts](scripts.md) |
| `resources/` | Versioned, curated inputs used at runtime or during evaluation. | [Resources](resources.md) |
| `tests/` | Automated backend regression coverage. | [Tests](tests.md) |
| `output/` | Generated pipeline, audit, and review artifacts. | [Output](output.md) |
| `doc/` | Durable backend design and directory documentation. | This index |

The normal request path is `main.py` → `services/` → `repositories/` and
`pipeline/`, with shared request and response shapes supplied by `domain/`.
Browser code must call the FastAPI boundary and must not access repositories,
resources, or external providers directly.
