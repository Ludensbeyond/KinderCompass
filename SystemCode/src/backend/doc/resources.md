# `resources/`

`resources/` stores versioned, curated source inputs. Unlike `output/`, these
files represent reviewed inputs and should not be overwritten casually by a
generated run.

## Subfolders

- `policy/` contains effective-dated ECDA subsidy rules consumed through the
  policy repository. Retain dates and provenance when adding a policy version.
- `web_rag/` contains general-knowledge evidence, approved school/operator page
  identities, and human-reviewed evaluation labels used by webpage RAG tooling.
- `conversation_agent_evaluation.json` is the ordered, synthetic reviewed case
  set for full-conversation routing, tool, state, grounding, and citation checks.

Treat edits as source-data changes: review provenance, schema compatibility,
and the downstream tests or audits affected. Secrets and user-specific data do
not belong here.

`parent_guide_evaluation.json` contains fixed synthetic, manually specified
all-section retrieval, qualification and routing labels. See
[evaluation and demo](file-vector-demo.md) for review limitations.

`llm_first_conversation_evaluation.json` is the fixed v1 target conversation
dataset for the new phase, separate from the legacy intent evaluator. See
[Step 1 baseline](llm-first-baseline.md) for fixture/scoring contracts.
