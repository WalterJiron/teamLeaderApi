from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class InvitationCreateSchema(BaseModel):
    email: EmailStr
    role: str = Field(default="TEAM_LEADER", pattern="^(ADMIN|TEAM_LEADER|MEMBER)$")


class InvitationResponse(BaseModel):
    invitation_id: int
    organization_id: int
    email: EmailStr
    role: str
    expires_at: datetime
    accepted_at: datetime | None
    invitation_token: str | None = None
