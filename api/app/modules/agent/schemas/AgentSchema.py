from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class AgentChatRequestSchema(BaseModel):
    message: str = Field(..., min_length=1, max_length=4096)
    session_id: str | None = Field(default=None, max_length=128)
    project_id: int | None = Field(default=None, ge=1)
    area_id: int | None = Field(default=None, ge=1)


class AgentChatResponseSchema(BaseModel):
    reply: str
    session_id: str
    cached: bool = False
    tokens_spent: int = 0


class AgentMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    role: str
    content: str
    project_id: int | None = None
    area_id: int | None = None
    created_at: datetime


class AgentSessionSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    project_id: int | None = None
    area_id: int | None = None
    message_count: int
    last_message: str
    last_role: str
    updated_at: datetime
