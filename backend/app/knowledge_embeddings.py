"""CPU embeddings. Routine startup/tests never download model assets."""
import threading


class KnowledgeUnavailable(RuntimeError):
    pass


class LocalEmbedder:
    def __init__(self, settings):
        self.settings = settings
        self.model = None
        self.lock = threading.RLock()

    @property
    def model_key(self):
        return f"{self.settings.embedding_model}@{self.settings.embedding_revision}:{self.settings.embedding_dimension}:text-v1"

    def load(self):
        with self.lock:
            if self.model is None:
                try:
                    from sentence_transformers import SentenceTransformer
                    self.model = SentenceTransformer(
                        self.settings.embedding_model, revision=self.settings.embedding_revision,
                        device="cpu", local_files_only=self.settings.embedding_local_only,
                        trust_remote_code=False,
                    )
                    if self.model.get_embedding_dimension() != self.settings.embedding_dimension:
                        self.model = None
                        raise KnowledgeUnavailable("Embedding dimension does not match configuration")
                except KnowledgeUnavailable:
                    raise
                except Exception:
                    self.model = None
                    raise KnowledgeUnavailable("Embedding model unavailable. Install RAG dependencies and prepare the approved local model cache.") from None
            return self.model

    def split(self, text):
        model = self.load()
        tokens = model.tokenizer.encode(text, add_special_tokens=False)
        limit = min(model.max_seq_length, 256) - 2
        if len(tokens) <= limit:
            return [text]
        return [model.tokenizer.decode(tokens[start:start + limit], skip_special_tokens=True)
                for start in range(0, len(tokens), limit - 24)]

    def encode(self, texts):
        with self.lock:
            model = self.load()
            try:
                return model.encode(texts, batch_size=16, normalize_embeddings=True,
                                    convert_to_numpy=True, show_progress_bar=False).tolist()
            except Exception:
                raise KnowledgeUnavailable("Local embedding generation failed") from None
