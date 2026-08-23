# `output/`

`output/` contains generated artifacts from recommendation stages, catalogue
inventory, webpage RAG ingestion, audits, evaluations, and review exports. It is
not a source-code or hand-authored configuration directory.

The application reads `web_rag_pilot_index.json` by default unless
`WEB_RAG_INDEX_PATH` overrides it. Other files record stage results and quality
reports. `web_rag_review/` contains generated CSV packets for human review.

Regenerate files with the owning pipeline, audit, or evaluation script instead
of editing them manually. Review generated diffs before committing because
some artifacts are runtime inputs and generated output may change as upstream
sources or tools change.
