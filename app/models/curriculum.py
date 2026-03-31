from pydantic import BaseModel, Field
from datetime import datetime, timezone
from uuid import uuid4


class Concept(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str
    prerequisites: list[str] = []


class LearningObjective(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    concept_id: str
    description: str
    bloom_level: str = ""


class CurriculumItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    objective_id: str
    title: str
    content_outline: str
    material_ids: list[str] = []
    order: int
    completed: bool = False


class Curriculum(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    goal_topic: str
    concepts: list[Concept] = []
    objectives: list[LearningObjective] = []
    items: list[CurriculumItem] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
