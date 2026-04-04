from pydantic import BaseModel, Field
from datetime import datetime, timezone
from uuid import uuid4


class Concept(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str
    prerequisites: list[str] = Field(default_factory=list)


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
    material_ids: list[str] = Field(default_factory=list)
    order: int
    completed: bool = False


class Curriculum(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    goal_topic: str
    concepts: list[Concept] = Field(default_factory=list)
    objectives: list[LearningObjective] = Field(default_factory=list)
    items: list[CurriculumItem] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
