"""Local operator workflow; intentionally no HTTP mutation endpoint."""
import argparse
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from time import perf_counter
from app.config import get_settings
from app.knowledge_documents import load_dataset
from app.knowledge_store import KnowledgeStore

ROOT = Path(__file__).resolve().parents[2]


def evaluate(store, queries, min_score=.3):
    report = {"min_score":min_score, "query_count":len(queries), "methods":{}, "queries":queries}
    # Warm model outside measured per-query latency; CLI reports cold initialization separately.
    cold = perf_counter()
    store.embedder.encode(["Initialize local incident retrieval"])
    report["model_initialization_ms"] = round((perf_counter()-cold)*1000, 2)
    for method in ("semantic", "metadata_filtered", "hybrid"):
        results = []
        for query in queries:
            started = perf_counter()
            matches = store.search(query["query"], top_k=3,
                service=query["service"] if method != "semantic" else None,
                min_score=min_score, ranking="hybrid" if method == "hybrid" else "semantic")
            latency = (perf_counter()-started)*1000
            ids = [match["incident"]["id"] for match in matches]
            relevant = set(query["relevant_ids"])
            hits = len(relevant & set(ids))
            rr = next((1/(index+1) for index, id in enumerate(ids) if id in relevant), 0)
            results.append({"query_id":query["id"], "returned_ids":ids,
                "precision_at_3":hits/3 if relevant else None,
                "recall_at_3":hits/len(relevant) if relevant else None,
                "reciprocal_rank":rr if relevant else None, "latency_ms":round(latency, 3),
                "no_match_correct":not ids if not relevant else None})
        report["methods"][method] = {
            "precision_at_3":mean(item["precision_at_3"] for item in results if item["precision_at_3"] is not None),
            "recall_at_3":mean(item["recall_at_3"] for item in results if item["recall_at_3"] is not None),
            "mrr":mean(item["reciprocal_rank"] for item in results if item["reciprocal_rank"] is not None),
            "mean_latency_ms":mean(item["latency_ms"] for item in results),
            "no_match_accuracy":mean(item["no_match_correct"] for item in results if item["no_match_correct"] is not None),
            "results":results}
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["index", "evaluate", "status"])
    parser.add_argument("--dataset", type=Path, default=ROOT/"knowledge/data/incidents.json")
    parser.add_argument("--queries", type=Path, default=ROOT/"evaluation/retrieval_queries.json")
    parser.add_argument("--output", type=Path, default=ROOT/"evaluation/retrieval_results.json")
    args = parser.parse_args()
    settings = get_settings()
    if args.command == "index" and settings.environment != "development":
        parser.error("Index mutation is restricted to the local development CLI")
    store = KnowledgeStore(settings)
    try:
        if args.command == "index":
            # Entire source is validated before touching Qdrant.
            result = store.index(load_dataset(args.dataset))
        elif args.command == "evaluate":
            if store.status().get("indexed_incidents", 0) == 0:
                parser.error("Index the curated dataset before evaluation")
            result = evaluate(store, json.loads(args.queries.read_text()))
            result.update(measured_at=datetime.now(timezone.utc).isoformat(), python=platform.python_version(), platform=platform.platform(), device="cpu", model=settings.embedding_model, revision=settings.embedding_revision,
                dimension=settings.embedding_dimension, mode="server" if settings.qdrant_url else "embedded-local",
                dataset=str(args.dataset.relative_to(ROOT)) if args.dataset.is_relative_to(ROOT) else args.dataset.name)
            args.output.write_text(json.dumps(result, indent=2) + "\n")
        else: result = store.status()
        if args.command == "evaluate":
            print(json.dumps({"report":str(args.output), "methods":{name:{key:value for key,value in data.items() if key != "results"} for name,data in result["methods"].items()}}, indent=2))
        else:
            print(json.dumps(result, indent=2))
    finally:
        store.close()


if __name__ == "__main__": main()
