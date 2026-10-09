# Parent-guide backend integration (step 5)

`PreferenceService` resolves `GENERAL_KNOWLEDGE_RETRIEVAL_MODE` when its general
retrieval boundary is first needed. A lock protects construction: the service
instance used by each backend worker retains one retriever and validated build.
No startup or request builds document embeddings. Changing configuration or
`CURRENT` requires restarting workers. Invalid embedding configuration uses the
curated adapter; vector index and provider failures retain the step 4 fallbacks.

Set these variables in the repository `.env`, then start the backend using its
normal command. `main.py` loads that file with `override=True`, so edit `.env`
when configuring the running backend rather than relying on shell overrides.

```dotenv
GENERAL_KNOWLEDGE_RETRIEVAL_MODE=vector
GENERAL_KNOWLEDGE_EMBEDDING_MODEL=text-embedding-3-small
GENERAL_KNOWLEDGE_EMBEDDING_DIMENSIONS=1536
GENERAL_KNOWLEDGE_TIMEOUT_SECONDS=8
GENERAL_KNOWLEDGE_MAX_QUERY_CHARACTERS=2000
```

Vector mode needs the existing backend `OPENAI_API_KEY` and network access for
question embeddings. Use `lexical` for guide retrieval without embedding calls,
or `curated` (the default) for the original curated corpus. The normal agent
may independently require its configured model provider. To exercise guidance
without a model supervisor, set `CONVERSATION_AGENT_MODE=deterministic` and
`OPENAI_INTENT_CLASSIFICATION_ENABLED=false` in `.env`.

The agent's `search_general_knowledge` tool and deterministic general/combined
answers receive the same `GeneralKnowledgeRetriever`. Deterministic answers
validate typed passages and public citations, retain full passage text and date
labels, and preserve unknown evidence classification. Legacy direct callers
that only supply a JSON index remain supported. Agent failure uses the same
service-owned retrieval boundary through the existing bounded fallback.

Routing recognises enrolment, waitlist, CCTV, CDA, developmental support, fee
caps and dated policy questions as general guidance when phrased as questions.
Selected-school references include centre/center; combined school and general
explanations retain separately scoped evidence. Existing deterministic capability
restrictions remain in force: preference updates, structured school fees and
family calculations do not execute vector search. Tool registration and index
loading do not call the embedding provider. HTTP contracts and school evidence
retrieval remain unchanged. No new request or family-data logging is introduced.

CCTV and waitlist passages remain excluded by reviewed provenance. Routing these
questions makes the unavailable-evidence response explicit; it does not expand
the corpus. Comprehensive all-section human labels, real-provider end-to-end
smoke evaluation, and demo memory/latency measurements remain step 6.

See [standalone retrieval](file-vector-retrieval.md) for query commands and
fallback rules, [index construction](file-vector-index.md) for build/rollback,
and [source review](file-vector-source-review.md) for exclusions.
