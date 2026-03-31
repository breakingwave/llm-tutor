import json
import logging
from collections.abc import Callable
from uuid import uuid4

from app.models.material import Material, MaterialChunk, MaterialSource
from app.utils.json_parse import extract_json
from app.models.user import UserProfile
from app.services.llm import LLMService
from app.services.search import SearchService
from app.services.vector_store import VectorStoreService
from app.config import GatheringSettings

logger = logging.getLogger("llm_tutor.gathering")


class GatheringService:
    def __init__(
        self,
        llm_service: LLMService,
        search_service: SearchService,
        settings: GatheringSettings,
        vector_store: VectorStoreService | None = None,
        openstax_collection_name: str | None = None,
    ):
        self.llm = llm_service
        self.search = search_service
        self.settings = settings
        self.vector_store = vector_store
        self.openstax_collection_name = openstax_collection_name

    async def extract_hooks(self, profile: UserProfile) -> list[str]:
        goal = profile.goals[0] if profile.goals else None
        messages = self.llm.build_messages(
            "gathering", "extract_hooks",
            {
                "background": profile.background or "No background provided",
                "goal_topic": goal.topic if goal else "General",
                "depth": goal.depth if goal else "introductory",
            },
        )
        response = await self.llm.completion(
            "gathering", "extract_hooks", messages, session_id=profile.id
        )
        hooks = [line.strip() for line in response.strip().split("\n") if line.strip()]
        return hooks

    async def generate_queries(
        self, topic: str, depth: str, hooks: list[str], num_queries: int | None = None,
    ) -> list[str]:
        if num_queries is None:
            num_queries = self.settings.queries_per_iteration
        messages = self.llm.build_messages(
            "gathering", "generate_queries",
            {
                "goal_topic": topic,
                "depth": depth,
                "hooks": "\n".join(hooks),
                "num_queries": str(num_queries),
            },
        )
        response = await self.llm.completion("gathering", "generate_queries", messages)
        try:
            raw = extract_json(response)
            data = json.loads(raw)
            if isinstance(data, dict):
                queries = data.get("queries", [])
            elif isinstance(data, list):
                queries = data
            else:
                queries = []
            if isinstance(queries, list) and all(isinstance(q, str) for q in queries):
                return queries
            return [topic]
        except (json.JSONDecodeError, TypeError):
            logger.error("Failed to parse queries: %s", response[:200])
            return [topic]

    async def search_and_retrieve(self, queries: list[str]) -> list[Material]:
        materials = []
        for query in queries:
            results = await self.search.search(query)
            for result in results:
                material = Material(
                    source=MaterialSource.TAVILY,
                    title=result.get("title", "Untitled"),
                    url=result.get("url"),
                    content=result.get("content", ""),
                    metadata={"query": query, "score": result.get("score")},
                )
                materials.append(material)
        return materials

    async def score_relevance(
        self,
        material: Material,
        profile: UserProfile,
        goal_topic: str,
    ) -> tuple[int, str]:
        messages = self.llm.build_messages(
            "gathering", "score_relevance",
            {
                "goal_topic": goal_topic,
                "background_summary": profile.background or "No background provided",
                "doc_title": material.title,
                "doc_excerpt": material.content[:1000],
            },
        )
        response = await self.llm.completion(
            "gathering", "score_relevance", messages, session_id=profile.id
        )
        try:
            raw = extract_json(response)
            data = json.loads(raw)
            if not isinstance(data, dict):
                return 3, "Could not parse relevance score"
            score = data.get("score", 3)
            reason = data.get("reason", "")
            if not isinstance(score, (int, float)):
                score = 3
            else:
                score = max(1, min(5, int(score)))
            return score, str(reason) if reason else ""
        except (json.JSONDecodeError, TypeError, ValueError):
            return 3, "Could not parse relevance score"

    async def summarize_material(self, material: Material) -> str:
        messages = self.llm.build_messages(
            "gathering", "summarize",
            {
                "doc_title": material.title,
                "doc_content": material.content[:2000],
            },
        )
        return await self.llm.completion("gathering", "summarize", messages)

    async def run_gathering(
        self,
        profile: UserProfile,
        goal_topic: str,
        depth: str = "introductory",
        on_progress: Callable | None = None,
    ) -> list[Material]:
        """Run the full gathering pipeline with iterative refinement."""
        hooks = await self.extract_hooks(profile)
        profile.hooks = hooks
        if on_progress:
            on_progress({"stage": "hooks_extracted", "hooks": hooks})

        all_materials: list[Material] = []
        seen_urls: set[str] = set()
        initial_queries: list[str] = []

        # Search uploaded PDF chunks via hybrid vector search
        if self.vector_store:
            try:
                initial_queries = await self.generate_queries(
                    topic=goal_topic, depth=depth, hooks=hooks,
                )
                pdf_chunks_seen: set[str] = set()
                for query in initial_queries[:3]:
                    results = await self.vector_store.query_hybrid(
                        query, top_k=5, session_id=profile.id,
                    )
                    for r in results:
                        chunk_id = r["metadata"].get("chunk_id", "")
                        if chunk_id in pdf_chunks_seen:
                            continue
                        pdf_chunks_seen.add(chunk_id)
                        material = Material(
                            source=MaterialSource.PDF_UPLOAD,
                            title=r["metadata"].get("section") or r["metadata"].get("chapter") or "PDF excerpt",
                            content=r["content"],
                            metadata=r["metadata"],
                        )
                        material.summary = await self.summarize_material(material)
                        all_materials.append(material)
                if on_progress:
                    on_progress({
                        "stage": "pdf_search_complete",
                        "count": len(all_materials),
                        "total_materials": len(all_materials),
                    })
                logger.info("PDF hybrid search: found %d relevant chunks", len(all_materials))
            except Exception as e:
                logger.error("PDF hybrid search failed: %s", e)

        # Search shared OpenStax collection
        if self.vector_store and self.openstax_collection_name:
            try:
                if not initial_queries:
                    initial_queries = await self.generate_queries(
                        topic=goal_topic, depth=depth, hooks=hooks,
                    )
                openstax_chunks_seen: set[str] = set()
                for query in initial_queries[:3]:
                    results = await self.vector_store.query_hybrid(
                        query, top_k=5, session_id=profile.id,
                        collection_name=self.openstax_collection_name,
                    )
                    for r in results:
                        chunk_id = r["metadata"].get("chunk_id", "")
                        if chunk_id in openstax_chunks_seen:
                            continue
                        openstax_chunks_seen.add(chunk_id)
                        material = Material(
                            source=MaterialSource.OPENSTAX,
                            title=r["metadata"].get("section") or r["metadata"].get("chapter") or "OpenStax excerpt",
                            content=r["content"],
                            metadata=r["metadata"],
                        )
                        material.summary = await self.summarize_material(material)
                        all_materials.append(material)
                if on_progress:
                    on_progress({
                        "stage": "openstax_search_complete",
                        "count": len(openstax_chunks_seen),
                        "total_materials": len(all_materials),
                    })
                logger.info("OpenStax search: found %d relevant chunks", len(openstax_chunks_seen))
            except Exception as e:
                logger.error("OpenStax search failed: %s", e)

        for iteration in range(self.settings.max_iterations):
            if len(all_materials) >= self.settings.max_materials:
                break

            queries = await self.generate_queries(topic=goal_topic, depth=depth, hooks=hooks)
            if on_progress:
                on_progress({"stage": "queries_generated", "iteration": iteration, "queries": queries})

            new_materials = await self.search_and_retrieve(queries)

            # Deduplicate by URL
            unique = []
            for m in new_materials:
                if m.url and m.url in seen_urls:
                    continue
                if m.url:
                    seen_urls.add(m.url)
                unique.append(m)

            # Score and filter
            filtered = []
            for m in unique:
                score, reason = await self.score_relevance(m, profile, goal_topic)
                m.relevance_score = score
                if score >= self.settings.min_relevance_score:
                    m.summary = await self.summarize_material(m)
                    filtered.append(m)
                    logger.info("Kept: [%d/5] %s — %s", score, m.title, reason)
                else:
                    logger.info("Dropped: [%d/5] %s — %s", score, m.title, reason)

            all_materials.extend(filtered)
            if on_progress:
                on_progress({
                    "stage": "iteration_complete",
                    "iteration": iteration,
                    "new_materials": len(filtered),
                    "total_materials": len(all_materials),
                })

            if not filtered:
                logger.info("No new materials found in iteration %d, stopping", iteration)
                break

        return all_materials[:self.settings.max_materials]

    async def index_materials(
        self, materials: list[Material], session_id: str | None = None,
    ) -> int:
        """Chunk and embed gathered Tavily materials into the vector store.

        Skips PDF_UPLOAD materials (already indexed at upload time).
        """
        if not self.vector_store:
            logger.warning("No vector store configured, skipping indexing")
            return 0

        chunks: list[MaterialChunk] = []
        for material in materials:
            # Skip PDF and OpenStax materials — already indexed
            if material.source in (MaterialSource.PDF_UPLOAD, MaterialSource.OPENSTAX):
                continue

            paragraphs = [p.strip() for p in material.content.split("\n\n") if p.strip()]
            current_chunk: list[str] = []
            current_words = 0
            chunk_idx = 0
            target_size = 500

            for para in paragraphs:
                para_words = len(para.split())
                if current_words + para_words > target_size and current_chunk:
                    chunks.append(MaterialChunk(
                        material_id=material.id,
                        content="\n\n".join(current_chunk),
                        chunk_index=chunk_idx,
                    ))
                    chunk_idx += 1
                    current_chunk = []
                    current_words = 0
                current_chunk.append(para)
                current_words += para_words

            if current_chunk:
                chunks.append(MaterialChunk(
                    material_id=material.id,
                    content="\n\n".join(current_chunk),
                    chunk_index=chunk_idx,
                ))

        if not chunks:
            return 0

        count = await self.vector_store.index_chunks(chunks, session_id=session_id)
        logger.info("Indexed %d chunks from %d materials", count, len(materials))
        return count
