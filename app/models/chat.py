from pydantic import BaseModel, Field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rag_chunk_ids: list[str] | None = None
    curriculum_item_id: str | None = None


class ChatSession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    curriculum_id: str | None = None
    active_item_id: str | None = None
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatRequest(BaseModel):
    session_id: str
    message: str
    curriculum_item_id: str | None = None
