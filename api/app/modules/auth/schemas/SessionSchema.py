from datetime import datetime
from pydantic import BaseModel


class SessionResponse(BaseModel):
    session_id: str
    ip: str | None
    user_agent: str | None
    issued_at: datetime
    expires_at: datetime
    last_used_at: datetime | None
    current: bool = False
