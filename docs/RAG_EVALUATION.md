# Retrieval evaluation

These are measured results from the actual cached Sentence Transformers model and persistent local Qdrant. They are not mock-vector results or invented accuracy estimates. Full per-query rankings and timings: `evaluation/retrieval_results.json` (local-only reference; not included in this release). Queries/labels: `evaluation/retrieval_queries.json` (local-only reference; not included in this release).

## Data and methodology

Corpus: 24 authored synthetic incidents, eight for each of user/order/payment service, one indexed chunk each. Model: all-MiniLM-L6-v2 at pinned commit c9745ed1d9f207416be6d2e6f8de32d1f16199bf, 384 dimensions, CPU, cosine distance. The report records measurement time, Python/platform, mode and initial model load time. No model fine-tuning or answer generation occurs.

The same 24 queries run through each method: exact errors, paraphrases, multi-symptom failures, cross-service lookalikes, resource/dependency cases, two ambiguous queries and two unrelated queries. Twenty-two queries have nonempty relevance labels; two have no relevant source. Relevance IDs were curated by the same author as the corpus. They are transparent reference labels, not independent expert judgments or production-ground-truth annotations.

- Precision@3 = number of labeled relevant returned sources / 3, even if fewer than three meet the threshold.
- Recall@3 = number of labeled relevant returned sources / number of relevant labeled sources.
- Reciprocal rank = 1 / first relevant source's rank; 0 if none. MRR is its mean.
- Quality means exclude the two empty-relevance queries; their no-match accuracy is reported separately.
- Retrieval latency includes tokenization, query encoding, Qdrant query, filtering and formatting. It excludes model initialization, measured separately. Each query/method runs once; timings vary with machine workload and are not a statistically controlled benchmark.

Top-K=3 and minimum cosine=0.3 are identical across methods. Semantic searches the full corpus. Metadata-filtered adds the known service label when supplied by the query fixture; the ambiguous and unrelated fixtures have no service label. Hybrid uses the same service filter plus an evaluation-only reranker. Thus filtered results assume the service is known; this is not an inferred service classifier.

## Measured results

| Method | Precision@3 | Recall@3 | MRR | Mean retrieval ms |
| --- | --- | --- | --- | --- |
| semantic | 0.3636 | 0.9848 | 1.0000 | 5.092 |
| metadata_filtered | 0.3636 | 0.9848 | 1.0000 | 6.062 |
| hybrid | 0.3636 | 0.9848 | 1.0000 | 4.134 |

All methods returned no matches for both unrelated queries (2/2, no-match accuracy 1.0). Initial model initialization: 3719.01 ms in this run.

The hybrid heuristic did **not** improve quality, so it is not exposed as a product ranking choice. Semantic ranking remains the public API/UI behavior. The high MRR on this tiny targeted set is not evidence of production-level generalization. Precision@3 is modest: many queries have one labeled relevant source and additional returned candidates are not labeled relevant. Recall also misses one relevant source in an ambiguous configuration query. Those limitations remain visible in the full report.

## Hybrid experiment

Candidate score = actual cosine + 0.08 for an explicit error-type match + 0.04 for a matching HTTP status term + 0.04 for an explicit service-name mention + up to 0.04 error/code-token Jaccard overlap. It reranks Qdrant candidates after the same minimum-cosine filter and source deduplication. It is a hand-designed heuristic, not a trained model, and cannot recover a relevant source excluded from candidates or by a wrong metadata filter. Its implementation is retained only for reproducible evaluation.

## Reproduce

Stop any API holding the default persistent local path before running the CLI. Install requirements-rag.lock.txt and prepare the approved pinned model cache first.

```sh
cd backend
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python -m app.knowledge_cli index
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python -m app.knowledge_cli evaluate
```

The second command writes evaluation/retrieval_results.json and prints a compact method summary. Use --queries and --output for separate experiments; do not overwrite unrelated files. Re-running may change latency, while deterministic vectors, filtering and ID tie-breaking support reproducible rankings for the same model/runtime. No collection deletion or random embeddings are used.

## Limits and future evaluation

Small synthetic English corpus, overlapping author vocabulary, known-service filter labels, a single embedding model, only two unrelated queries, no held-out real incidents and no uncertainty estimates. The model is general English, not trained specifically on this project. Similarity thresholds may need validation on a broader independent corpus. The current top-candidate bound and local Qdrant mode are not production scaling tests. Long stack/query pooling may reduce relevance. No claim of excellent or universal retrieval accuracy is made. Independent relevance review, adversarial/noisy queries and held-out incident families would be appropriate next evaluation work; no Phase 5 agent has been implemented.
