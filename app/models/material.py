from pydantic import BaseModel, Field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class MaterialSource(str, Enum):
    TAVILY = "tavily"
    OPENSTAX = "openstax"
    PDF_UPLOAD = "pdf_upload"
    USER_UPLOAD = "user_upload"


class Material(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    source: MaterialSource
    title: str
    url: str | None = None
    content: str
    summary: str = ""
    relevance_score: float | None = None
    file_name: str = ""
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MaterialChunk(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    material_id: str
    content: str
    chunk_index: int
    chapter: str = ""
    section: str = ""
    curriculum_item_ids: list[str] = Field(default_factory=list)
    embedding_id: str | None = None
