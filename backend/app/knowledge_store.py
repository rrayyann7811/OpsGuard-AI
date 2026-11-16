"""A disposable search index, with attributed documents and real Qdrant scores."""
import re
import math
import threading
from datetime import datetime, timezone
from app.knowledge_documents import prepare, safe_document, document_hash, point_id
from app.knowledge_embeddings import LocalEmbedder, KnowledgeUnavailable

OWNER = "opsguard-history-v1"


class KnowledgeStore:
    def __init__(self, settings, client=None, embedder=None):
        self.settings = settings
        self.client = client
        self.embedder = embedder or LocalEmbedder(settings)
        self.lock = threading.RLock()

    def connect(self):
        if self.client is None:
            try:
                from qdrant_client import QdrantClient
                self.client = (QdrantClient(url=self.settings.qdrant_url, api_key=self.settings.qdrant_api_key or None, timeout=3)
                    if self.settings.qdrant_url else QdrantClient(path=self.settings.qdrant_path, force_disable_check_same_thread=True))
            except Exception:
                raise KnowledgeUnavailable("Qdrant unavailable or local storage is locked by another process") from None
        return self.client

    def close(self):
        if self.client is not None:
            self.client.close()
            self.client = None

    def collection(self, create=False):
        from qdrant_client import models
        client = self.connect()
        name = self.settings.qdrant_collection
        if not client.collection_exists(name):
            if not create:
                return False
            client.create_collection(name, vectors_config=models.VectorParams(size=self.settings.embedding_dimension, distance=models.Distance.COSINE))
        info = client.get_collection(name)
        vector = info.config.params.vectors
        if not isinstance(vector, models.VectorParams) or vector.size != self.settings.embedding_dimension or vector.distance != models.Distance.COSINE:
            raise KnowledgeUnavailable("Collection dimension/distance mismatch; use a new collection name. No collection was replaced.")
        return True

    def filters(self, service=None, severity=None, document_id=None, active=True):
        from qdrant_client import models
        values = {"owner": OWNER, "active": active, "model_key": self.embedder.model_key}
        if service: values["service_name"] = service
        if severity: values["severity"] = severity
        if document_id: values["document_id"] = document_id
        return models.Filter(must=[models.FieldCondition(key=key, match=models.MatchValue(value=value)) for key, value in values.items()])

    def points(self, service=None, severity=None, document_id=None):
        if not self.collection():
            return []
        result, offset = [], None
        while True:
            batch, offset = self.client.scroll(self.settings.qdrant_collection,
                scroll_filter=self.filters(service, severity, document_id), offset=offset, limit=128,
                with_payload=True, with_vectors=False)
            result.extend(batch)
            if offset is None: return result

    def documents(self, service=None, severity=None):
        with self.lock:
            unique = {}
            for point in self.points(service, severity):
                unique[point.payload["document_id"]] = point.payload["document"]
            return sorted(unique.values(), key=lambda doc: (doc["incident_date"], doc["id"]), reverse=True)

    def status(self):
        with self.lock:
            try:
                exists = self.collection()
                points = self.points() if exists else []
                docs = {point.payload["document_id"] for point in points}
                return {"status": "ready" if points else "empty", "collection_exists": exists,
                    "mode": "server" if self.settings.qdrant_url else "embedded-local",
                    "collection": self.settings.qdrant_collection, "indexed_incidents": len(docs), "indexed_chunks": len(points),
                    "source_count": len({p.payload['document']['source_ref'] for p in points}),
                    "last_indexed_at": max((p.payload["indexed_at"] for p in points), default=None),
                    "embedding_model": self.settings.embedding_model, "embedding_revision": self.settings.embedding_revision,
                    "dimension": self.settings.embedding_dimension, "embedding_loaded": self.embedder.model is not None,
                    "default_ranking": "semantic", "synthetic": True,
                    "message": ("Search index and local model available." if self.embedder.model is not None else "Search index available; the model loads on first search.") if points else "Run the authorized local indexing command."}
            except Exception:
                return {"status": "unavailable", "mode": "server" if self.settings.qdrant_url else "embedded-local",
                        "collection": self.settings.qdrant_collection, "embedding_model": self.settings.embedding_model,
                        "dimension": self.settings.embedding_dimension, "indexed_incidents": None, "indexed_chunks": None,
                        "source_count": None, "last_indexed_at": None, "embedding_loaded": False,
                        "message": "Knowledge index unavailable, incompatible, or locked. Incident monitoring remains available."}

    def index(self, documents):
        from qdrant_client import models
        with self.lock:
            self.collection(create=True)
            changed, skipped = 0, 0
            # Validate and embed each source before changing its currently searchable chunks.
            for document in documents:
                digest = document_hash(document, self.embedder.model_key)
                old = self.points(document_id=document.id)
                if old and len(old) == old[0].payload.get("chunk_count") and all(point.payload.get("content_hash") == digest for point in old):
                    skipped += 1
                    continue
                text = prepare(document)
                chunks = self.embedder.split(text)
                vectors = self.embedder.encode(chunks)
                if len(vectors) != len(chunks) or any(len(v) != self.settings.embedding_dimension or not all(math.isfinite(x) for x in v) for v in vectors):
                    raise KnowledgeUnavailable("Embedding output dimension mismatch")
                destinations = self.client.retrieve(self.settings.qdrant_collection,
                    ids=[point_id(document.id, index) for index in range(len(chunks))], with_payload=True)
                if any(point.payload.get("owner") != OWNER for point in destinations):
                    raise KnowledgeUnavailable("Destination point is not owned by OpsGuard. Use a dedicated collection.")
                # Keep old points stored but inactive; no deletes, recreations or collection drops.
                self.client.set_payload(self.settings.qdrant_collection, payload={"active": False},
                    points=self.filters(document_id=document.id))
                indexed = datetime.now(timezone.utc).isoformat()
                self.client.upsert(self.settings.qdrant_collection, wait=True, points=[
                    models.PointStruct(id=point_id(document.id, index), vector=vector,
                        payload={"owner":OWNER, "active":False, "chunk_count":len(chunks), "model_key":self.embedder.model_key,
                            "document_id":document.id, "chunk_index":index, "content_hash":digest,
                            "service_name":document.service_name, "severity":document.severity,
                            "indexed_at":indexed, "text":chunk, "document":safe_document(document)})
                    for index, (chunk, vector) in enumerate(zip(chunks, vectors))])
                self.client.set_payload(self.settings.qdrant_collection, payload={"active": True},
                    points=[point_id(document.id, index) for index in range(len(chunks))], wait=True)
                changed += 1
            return {"indexed": changed, "unchanged": skipped, **self.status()}

    def search(self, query, top_k=3, service=None, severity=None, min_score=.25, ranking="semantic"):
        with self.lock:
            if not self.collection(): return []
            # Empty indexes do not unnecessarily load/download an embedding model.
            if self.client.count(self.settings.qdrant_collection, count_filter=self.filters(service, severity), exact=True).count == 0:
                return []
            query_chunks = self.embedder.split(query)
            encoded = self.embedder.encode(query_chunks)
            vector = [sum(column) / len(encoded) for column in zip(*encoded)]
            norm = math.sqrt(sum(value * value for value in vector))
            if norm == 0 or len(vector) != self.settings.embedding_dimension or not all(math.isfinite(value) for value in vector):
                raise KnowledgeUnavailable("Invalid query embedding")
            vector = [value / norm for value in vector]
            hits = self.client.query_points(self.settings.qdrant_collection, query=vector,
                query_filter=self.filters(service, severity), limit=min(100, max(30, top_k * 5)),
                score_threshold=min_score, with_payload=True).points
            matches = {}
            terms = set(re.findall(r"[a-z_][a-z0-9_]+", query.lower()))
            for hit in hits:
                payload = hit.payload
                doc = payload["document"]
                score = float(hit.score)
                bonus = 0.0
                reasons = []
                if ranking == "hybrid":
                    if doc["error_type"].lower() in query.lower(): bonus += .08; reasons.append("error type")
                    if str(doc["http_status"]) in query: bonus += .04; reasons.append("HTTP status")
                    if doc["service_name"].lower() in query.lower(): bonus += .04; reasons.append("service hint")
                    error_terms = set(re.findall(r"[a-z_][a-z0-9_]+", (doc["error_message"] + " " + doc["code_context"]).lower()))
                    bonus += .04 * len(terms & error_terms) / max(1, len(terms | error_terms))
                result = {"incident": doc, "similarity_score": score, "rank_score": score + bonus,
                    "matched_chunk": payload["text"], "source_ref":doc["source_ref"], "ranking_signals":reasons}
                old = matches.get(doc["id"])
                if old is None or score > old["similarity_score"]: matches[doc["id"]] = result
            return sorted(matches.values(), key=lambda hit: (-hit["rank_score"], hit["incident"]["id"]))[:top_k]
