from pydantic import BaseModel, Field
from datetime import datetime


class LearningTopicSummary(BaseModel):
    """One learning topic maps to one session file (session-per-topic)."""

    session_id: str
    topic: str = "Untitled"
    depth: str = "introductory"
    extra_goals_count: int = Field(
        default=0,
        description="Legacy sessions may have multiple goals; only goals[0] labels the topic.",
    )
    created_at: datetime | None = None
