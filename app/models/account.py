from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


class UserAccount(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    email: str
    password_hash: str
    role: str = "user"  # "user" | "admin"
    total_upload_bytes: int = 0
    session_ids: list[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
