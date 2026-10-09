# Persistent parent-guide index (step 3)

The explicit offline builder uses `pipeline/parent_guide_chunking.py` for reviewed
selections, `pipeline/parent_guide_embeddings.py` for injectable batched embeddings,
and `repositories/parent_guide_index.py` for validated artifact loading. It does
not run at backend startup. Retrieval, fallback and service wiring are implemented in steps 4–5;
curated remains the default runtime mode. See [evaluation and demo](file-vector-demo.md)
for step 6 results and executable rollback commands.

Install the backend requirements, including NumPy, then build from the repository
root with the existing server-side `OPENAI_API_KEY` in `.env`:

```bash
.venv/bin/python -m pip install -r SystemCode/src/backend/requirements.txt
.venv/bin/python -m SystemCode.src.backend.scripts.build_parent_guide_index
```

The command loads `.env` without overriding explicit shell configuration and
uses the Step 1 `GENERAL_KNOWLEDGE_*` embedding/path/timeout settings. The fixed
provider is OpenAI `text-embedding-3-small`, with 1536 dimensions. A new corpus
requires network/API access and incurs embedding usage. Defaults are 32 inputs
per batch, two retries after the initial attempt, and an eight-second provider
timeout per attempt. `--batch-size` accepts 1–128 and `--max-retries` accepts 0–5.
Only connection/timeout, rate-limit and temporary HTTP errors are retried, with
bounded backoff; invalid responses and permanent request failures stop the build.
SDK retries are disabled to avoid multiplying this bound. Provider errors are
reported by category without their request details or credentials.

The [official embeddings API reference](https://developers.openai.com/api/reference/resources/embeddings/methods/create)
establishes batch input, explicit dimensions, float output and response indices.
The adapter restores input order and rejects duplicate/missing indices or a
returned model identifier differing from the configured model. The exact matching
returned identifier is recorded in the manifest. No independently versioned
snapshot is available; `model_version` is null for this hosted provider. Model
alias drift cannot be detected automatically; rebuild without reusable artifacts
when changing a deployment/version whose identifier remains the same.

Every build writes an isolated `builds/<build_id>/` directory containing:

- `chunks.json`: all 23 reviewed chunks and their separate indexing timestamps;
- `embeddings.npy`: normalised float32 document vectors;
- `manifest.json`: schema/build ID, source/provenance hashes, chunking settings,
  provider/model/version/dimensions, dtype/normalisation and artifact hashes;
- `summary.json`: build ID and embedded/reused/total counts.

Writes are flushed and synced. The loader checks the completed build before
`CURRENT` is replaced atomically. Failures never replace the previous pointer;
prior builds and incomplete attempt directories are retained. Concurrent builders
use distinct directories and the last completed publisher wins. This provides
atomic visibility for build/process failures, not a power-loss durability
guarantee for directory entries. Integrity hashes detect corruption; they are
not signatures authenticating edits by someone with filesystem write access.

Reuse requires a previously validated build with identical provider, model,
version, dimensions and chunking settings. Each reused vector must also match
the stable chunk ID and embedding-text hash. Source/provenance-only changes can
retain vectors while regenerating reviewed metadata. Missing/corrupt/incompatible
artifacts cause all required vectors to be regenerated, never reused unchecked.

Loading rejects missing/duplicate IDs, invalid content hashes, row/count mismatch,
unreviewed metadata, invalid citations, non-finite/zero/non-unit vectors, incorrect
dimensions/dtype and artifact hash mismatch. NumPy loading disables pickle.
Loaded matrices are read-only. Public source fetch timestamps remain unchanged;
`indexed_at` describes index construction and is never a citation fetch date.

Validate in a fresh process without an API call or server:

```bash
.venv/bin/python -m SystemCode.src.backend.scripts.build_parent_guide_index --validate-only
```

`--vector-path` selects an alternative directory for either command. It must
contain `sources.json`, with the maintained Markdown in its parent directory at
the reviewed document-relative path. Update/review the source and provenance
together before rebuilding; the chunker rejects source drift. To force a full
rebuild while preserving the active index, build in a separate staging directory
with copies of those inputs, then deploy its completed artifacts deliberately.

For rollback, validate a retained directory with `load_build`, write its build ID
and a newline to a temporary pointer file beside `CURRENT`, then use `os.replace`
to activate it. Keep the previous completed build until the new one is verified.

Two previously generated, model-compatible builds are included for reproducible
loading and rollback. The first records 23 embedded chunks; the second records
reuse of all 23. This verification made no new provider embedding requests.
The reviewed source consists of supplied public preschool guidance; generated
artifacts contain only those reviewed selections, source metadata and vectors,
without secrets or chat data. Each build is approximately 200 KB (141,440 bytes
for the matrix). Existing corpus exclusions are unchanged, including section 11.
No query-relevance or answer-quality claim is established at this step.

Focused tests use deterministic embeddings and cover fresh-process reload,
bounded retries/timeouts, response ordering, partial/all reuse, compatibility,
corruption, pickle rejection and failed publication. Full-suite results and
baseline comparison are recorded in the implementation plan.
