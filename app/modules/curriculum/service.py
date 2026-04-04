import json
import logging
import re

from app.models.curriculum import Concept, LearningObjective, CurriculumItem, Curriculum
from app.utils.json_parse import extract_json
from app.models.material import Material
from app.models.user import UserProfile
from app.services.llm import LLMService
from app.config import CurriculumSettings

logger = logging.getLogger("llm_tutor.curriculum")


class CurriculumService:
    def __init__(self, llm_service: LLMService, settings: CurriculumSettings):
        self.llm = llm_service
        self.settings = settings

    def _background_summary(self, profile: UserProfile) -> str:
        return profile.background or "No background provided"

    def _normalize_material_ids(
        self,
        item: CurriculumItem,
        materials: list[Material],
    ) -> list[str]:
        valid_ids = {material.id for material in materials}
        explicit_ids = [material_id for material_id in item.material_ids if material_id in valid_ids]
        if explicit_ids:
            return explicit_ids

        item_terms = set(
            re.findall(r"\w+", f"{item.title} {item.content_outline}".lower())
        )
        if not item_terms:
            return []

        ranked: list[tuple[int, str]] = []
        for material in materials:
            material_terms = set(
                re.findall(
                    r"\w+",
                    f"{material.title} {material.summary or material.content[:600]}".lower(),
                )
            )
            overlap = len(item_terms & material_terms)
            if overlap > 0:
                ranked.append((overlap, material.id))

        ranked.sort(reverse=True)
        return [material_id for _, material_id in ranked[:3]]

    async def generate_curriculum(
        self,
        profile: UserProfile,
        materials: list[Material],
        goal_topic: str,
        depth: str = "introductory",
    ) -> Curriculum:
        material_summaries = "\n".join(
            f"- [{m.id[:8]}] {m.title}: {m.summary or m.content[:200]}"
            for m in materials
        )
        background_summary = self._background_summary(profile)

        # Step 1: Analyse — extract concepts
        concepts = await self._analyse(
            goal_topic, background_summary, depth, material_summaries, profile.id
        )

        # Step 2: Design — generate objectives
        objectives = await self._design(concepts, material_summaries, depth, profile.id)

        # Step 3: Develop — create curriculum items
        items = await self._develop(
            objectives, materials, material_summaries, depth, profile.id
        )

        curriculum = Curriculum(
            user_id=profile.id,
            goal_topic=goal_topic,
            concepts=concepts,
            objectives=objectives,
            items=items,
        )
        return curriculum

    async def _analyse(
        self,
        goal_topic: str,
        background_summary: str,
        depth: str,
        material_summaries: str,
        session_id: str,
    ) -> list[Concept]:
        messages = self.llm.build_messages(
            "curriculum", "analyse",
            {
                "goal_topic": goal_topic,
                "background_summary": background_summary,
                "depth": depth,
                "material_summaries": material_summaries,
                "max_concepts": str(self.settings.max_concepts),
            },
        )
        response = await self.llm.completion(
            "curriculum", "analyse", messages, session_id=session_id
        )
        try:
            raw = extract_json(response)
            data = json.loads(raw)
            if isinstance(data, dict):
                items = data.get("concepts", [])
            elif isinstance(data, list):
                items = data
            else:
                items = []
            if isinstance(items, list):
                return [Concept(**c) for c in items if isinstance(c, dict)]
            return []
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.error("Failed to parse analyse response: %s", e)
            return []

    async def _design(
        self,
        concepts: list[Concept],
        material_summaries: str,
        depth: str,
        session_id: str,
    ) -> list[LearningObjective]:
        concepts_json = json.dumps(
            [{"id": c.id, "name": c.name, "description": c.description} for c in concepts],
            indent=2,
        )
        messages = self.llm.build_messages(
            "curriculum", "design",
            {
                "concepts_json": concepts_json,
                "material_summaries": material_summaries,
                "depth": depth,
                "max_objectives_per_concept": str(self.settings.max_objectives_per_concept),
            },
        )
        response = await self.llm.completion(
            "curriculum", "design", messages, session_id=session_id
        )
        try:
            raw = extract_json(response)
            data = json.loads(raw)
            if isinstance(data, dict):
                items = data.get("objectives", [])
            elif isinstance(data, list):
                items = data
            else:
                items = []
            if isinstance(items, list):
                return [LearningObjective(**o) for o in items if isinstance(o, dict)]
            return []
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.error("Failed to parse design response: %s", e)
            return []

    async def _develop(
        self,
        objectives: list[LearningObjective],
        materials: list[Material],
        material_summaries: str,
        depth: str,
        session_id: str,
    ) -> list[CurriculumItem]:
        objectives_json = json.dumps(
            [{"id": o.id, "concept_id": o.concept_id, "description": o.description}
             for o in objectives],
            indent=2,
        )
        materials_with_ids = json.dumps(
            [{"id": m.id, "title": m.title, "summary": m.summary or m.content[:200]}
             for m in materials],
            indent=2,
        )
        messages = self.llm.build_messages(
            "curriculum", "develop",
            {
                "objectives_json": objectives_json,
                "materials_with_ids": materials_with_ids,
                "depth": depth,
            },
        )
        response = await self.llm.completion(
            "curriculum", "develop", messages, session_id=session_id
        )
        try:
            raw = extract_json(response)
            data = json.loads(raw)
            if isinstance(data, dict):
                items = data.get("items", [])
            elif isinstance(data, list):
                items = data
            else:
                items = []
            if isinstance(items, list):
                normalized_items: list[CurriculumItem] = []
                for idx, item_data in enumerate(items):
                    if not isinstance(item_data, dict):
                        continue
                    item = CurriculumItem(**item_data)
                    item.material_ids = self._normalize_material_ids(item, materials)
                    if not item.order:
                        item.order = idx + 1
                    normalized_items.append(item)
                return normalized_items
            return []
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.error("Failed to parse develop response: %s", e)
            return []
