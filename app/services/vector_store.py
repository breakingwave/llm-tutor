import hashlib
import logging
import math
import re
import time
from collections import Counter

import openai
from qdrant_client import QdrantClient, models

from app.config import QdrantSettings
from app.models.material import MaterialChunk
from app.models.api_log import APICallLog
from app.services.api_logger import APILogger

logger = logging.getLogger("llm_tutor.vector_store")

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer for BM25."""
    return re.findall(r"\w+", text.lower())


def _term_to_index(term: str) -> int:
    """Deterministic term → integer index via hash."""
    return int(hashlib.md5(term.encode()).hexdigest()[:8], 16)


class VectorStoreService:
    def __init__(
        self,
        qdrant_settings: QdrantSettings,
        embedding_model: str,
        api_logger: APILogger,
    ):
        self.settings = qdrant_settings
        self.embedding_model = embedding_model
        self.api_logger = api_logger

        if qdrant_settings.path:
            self.client = QdrantClient(path=qdrant_settings.path)
        elif qdrant_settings.mode == "memory":
            self.client = QdrantClient(location=":memory:")
        else:
            self.client = QdrantClient(
                host=qdrant_settings.host,
                port=qdrant_settings.port,
            )

        self.openai_client = openai.OpenAI()

        # BM25 vocabulary per collection: collection_name → stats
        self._bm25: dict[str, dict] = {}

        self._ensure_collection(self.settings.collection_name)

    def _ensure_collection(self, collection_name: str) -> None:
        """Create collection with dense + sparse named vectors if not exists."""
        collections = [c.name for c in self.client.get_collections().collections]
        if collection_name not in collections:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    DENSE_VECTOR_NAME: models.VectorParams(
                        size=self.settings.embedding_dimension,
                        distance=models.Distance.COSINE,
                    ),
                },
                sparse_vectors_config={
                    SPARSE_VECTOR_NAME: models.SparseVectorParams(),
                },
            )
            logger.info(
                "Created collection '%s' with dense (%d) + sparse vectors",
                collection_name,
                self.settings.embedding_dimension,
            )
        if collection_name not in self._bm25:
            self._bm25[collection_name] = {
                "doc_freq": Counter(),
                "total_docs": 0,
                "avg_doc_len": 0.0,
            }

    def _embed_dense(self, texts: list[str]) -> list[list[float]]:
        """Embed texts via OpenAI embeddings API (batched)."""
        all_embeddings: list[list[float]] = []
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = self.openai_client.embeddings.create(
                model=self.embedding_model.removeprefix("openai/"),
                input=batch,
            )
            all_embeddings.extend([d.embedding for d in response.data])
        return all_embeddings

    def _fit_bm25(self, texts: list[str], collection_name: str) -> None:
        """Update BM25 vocabulary with new documents for a collection."""
        bm25 = self._bm25[collection_name]
        doc_lens = []
        for text in texts:
            tokens = set(_tokenize(text))
            for token in tokens:
                bm25["doc_freq"][token] += 1
            doc_lens.append(len(_tokenize(text)))
        bm25["total_docs"] += len(texts)
        if doc_lens:
            total_len = bm25["avg_doc_len"] * (bm25["total_docs"] - len(texts)) + sum(doc_lens)
            bm25["avg_doc_len"] = total_len / bm25["total_docs"]

    def _build_sparse(self, text: str, collection_name: str) -> models.SparseVector:
        """Build BM25-weighted sparse vector for a single text."""
        tokens = _tokenize(text)
        if not tokens:
            return models.SparseVector(indices=[], values=[])

        bm25 = self._bm25[collection_name]
        tf = Counter(tokens)
        doc_len = len(tokens)
        k1, b = 1.5, 0.75

        indices = []
        values = []
        for term, count in tf.items():
            df = bm25["doc_freq"].get(term, 0)
            if df == 0:
                continue
            idf = math.log((bm25["total_docs"] - df + 0.5) / (df + 0.5) + 1.0)
            tf_norm = (count * (k1 + 1)) / (
                count + k1 * (1 - b + b * doc_len / max(bm25["avg_doc_len"], 1))
            )
            score = idf * tf_norm
            if score > 0:
                indices.append(_term_to_index(term))
                values.append(score)

        return models.SparseVector(indices=indices, values=values)

    def _resolve_collection(self, collection_name: str | None) -> str:
        """Resolve collection name, defaulting to settings value."""
        name = collection_name or self.settings.collection_name
        self._ensure_collection(name)
        return name

    async def index_chunks(
        self,
        chunks: list[MaterialChunk],
        session_id: str | None = None,
        collection_name: str | None = None,
    ) -> int:
        """Index material chunks with dense + sparse vectors."""
        if not chunks:
            return 0

        col = self._resolve_collection(collection_name)
        start = time.perf_counter()
        error_str = None
        count = 0

        try:
            texts = [c.content for c in chunks]

            # Fit BM25 vocabulary on new texts
            self._fit_bm25(texts, col)

            # Compute embeddings
            dense_vectors = self._embed_dense(texts)
            sparse_vectors = [self._build_sparse(t, col) for t in texts]

            # Build points
            points = []
            for i, chunk in enumerate(chunks):
                point = models.PointStruct(
                    id=_term_to_index(chunk.id),  # deterministic int ID
                    vector={
                        DENSE_VECTOR_NAME: dense_vectors[i],
                        SPARSE_VECTOR_NAME: sparse_vectors[i],
                    },
                    payload={
                        "chunk_id": chunk.id,
                        "material_id": chunk.material_id,
                        "chunk_index": chunk.chunk_index,
                        "chapter": chunk.chapter,
                        "section": chunk.section,
                        "content": chunk.content,
                        **({"session_id": session_id} if session_id else {}),
                    },
                )
                points.append(point)

            # Upsert in batches
            batch_size = 100
            for i in range(0, len(points), batch_size):
                self.client.upsert(
                    collection_name=col,
                    points=points[i : i + batch_size],
                )
            count = len(points)
        except Exception as e:
            error_str = str(e)
            raise
        finally:
            latency = (time.perf_counter() - start) * 1000
            self.api_logger.log_call(APICallLog(
                module="gathering",
                operation="index_chunks",
                service="qdrant",
                latency_ms=latency,
                request_payload={"num_chunks": len(chunks), "collection": col},
                response_payload={"points_indexed": count},
                error=error_str,
                session_id=session_id,
            ))

        return count

    async def query_hybrid(
        self,
        query_text: str,
        top_k: int = 5,
        session_id: str | None = None,
        collection_name: str | None = None,
    ) -> list[dict]:
        """Hybrid dense + sparse search with RRF fusion."""
        col = self._resolve_collection(collection_name)
        start = time.perf_counter()
        error_str = None
        results = []

        try:
            # Embed query
            dense_vec = self._embed_dense([query_text])[0]
            sparse_vec = self._build_sparse(query_text, col)

            # Build session filter for per-user collections (not shared ones)
            query_filter = None
            if session_id and col == self.settings.collection_name:
                query_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="session_id",
                            match=models.MatchValue(value=session_id),
                        ),
                    ],
                )

            # Hybrid query with prefetch + RRF
            response = self.client.query_points(
                collection_name=col,
                prefetch=[
                    models.Prefetch(
                        query=dense_vec,
                        using=DENSE_VECTOR_NAME,
                        limit=top_k * 2,
                        filter=query_filter,
                    ),
                    models.Prefetch(
                        query=models.SparseVector(
                            indices=sparse_vec.indices,
                            values=sparse_vec.values,
                        ),
                        using=SPARSE_VECTOR_NAME,
                        limit=top_k * 2,
                        filter=query_filter,
                    ),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=top_k,
            )

            for point in response.points:
                payload = point.payload or {}
                results.append({
                    "content": payload.get("content", ""),
                    "score": point.score,
                    "metadata": {
                        "chunk_id": payload.get("chunk_id"),
                        "material_id": payload.get("material_id"),
                        "chunk_index": payload.get("chunk_index"),
                        "chapter": payload.get("chapter", ""),
                        "section": payload.get("section", ""),
                    },
                })
        except Exception as e:
            error_str = str(e)
            logger.error("Hybrid query failed: %s", e)
        finally:
            latency = (time.perf_counter() - start) * 1000
            self.api_logger.log_call(APICallLog(
                module="gathering",
                operation="hybrid_query",
                service="qdrant",
                latency_ms=latency,
                request_payload={"query": query_text[:200], "top_k": top_k, "collection": col},
                response_payload={"num_results": len(results)},
                error=error_str,
                session_id=session_id,
            ))

        return results

    async def delete_by_material_id(
        self,
        material_id: str,
        session_id: str | None = None,
        collection_name: str | None = None,
    ) -> None:
        """Delete all points for a given material_id."""
        col = self._resolve_collection(collection_name)
        start = time.perf_counter()
        error_str = None

        try:
            self.client.delete(
                collection_name=col,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="material_id",
                                match=models.MatchValue(value=material_id),
                            ),
                        ],
                    ),
                ),
            )
        except Exception as e:
            error_str = str(e)
            logger.error("Delete by material_id failed: %s", e)
        finally:
            latency = (time.perf_counter() - start) * 1000
            self.api_logger.log_call(APICallLog(
                module="gathering",
                operation="delete_chunks",
                service="qdrant",
                latency_ms=latency,
                request_payload={"material_id": material_id, "collection": col},
                response_payload={},
                error=error_str,
                session_id=session_id,
            ))
