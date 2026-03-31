from pydantic import BaseModel, Field
from datetime import datetime, timezone
from uuid import uuid4


class APICallLog(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    module: str
    operation: str
    service: str
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: float = 0.0
    cost_estimate_usd: float | None = None
    request_payload: dict = {}
    response_payload: dict = {}
    error: str | None = None
    session_id: str | None = None
