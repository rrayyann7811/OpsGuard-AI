# Historical incident sources

`data/incidents.json` contains 24 original, explicitly synthetic incident records (eight each for user/order/payment). This versioned JSON is the curated historical source; operational incident records remain in SQLite. The searchable index is maintained in dedicated Qdrant storage, never presented as operational incidents.

See [RAG pipeline](../docs/RAG_PIPELINE.md), [measured evaluation](../docs/RAG_EVALUATION.md), and per-query results (local-only reference; not distributed). Stop FastAPI before indexing the same persistent local path. From backend/: `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python -m app.knowledge_cli index`. An unchanged rerun reuses embeddings and creates no duplicate sources. Runtime `.qdrant` data is ignored by Git; existing collections are never deleted by this workflow.
