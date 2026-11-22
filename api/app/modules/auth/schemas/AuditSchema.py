from datetime import datetime
from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    audit_id: int
    organization_id: int | None
    actor_user_id: int | None
    target_user_id: int | None
    event_type: str
    severity: str
    ip: str | None
    user_agent: str | None
    request_id: str | None
    metadata_json: dict | None
    created_at: datetime
    entry_hash: str | None
