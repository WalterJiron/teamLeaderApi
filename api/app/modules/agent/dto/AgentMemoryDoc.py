from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field


class AgentMemoryDoc(BaseModel):
    session_id: str = Field(..., max_length=128)
    organization_id: int
    user_id: int
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str
    project_id: int | None = None
    area_id: int | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def toMongoDict(self) -> dict[str, Any]:
        """Serializes the memory document for MongoDB collection insertion.

        Returns:
            dict[str, Any]: MongoDB document representation.
        """
        return {
            "session_id": self.session_id,
            "organization_id": self.organization_id,
            "user_id": self.user_id,
            "role": self.role,
            "content": self.content,
            "project_id": self.project_id,
            "area_id": self.area_id,
            "created_at": self.created_at,
        }
