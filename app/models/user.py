from pydantic import BaseModel, Field
from datetime import datetime, timezone
from uuid import uuid4


class LearningGoal(BaseModel):
    topic: str
    depth: str = "introductory"
    specific_interests: list[str] = Field(default_factory=list)


class UserProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    background: str = ""
    goals: list[LearningGoal] = Field(default_factory=list)
    hooks: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
