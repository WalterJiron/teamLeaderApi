from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AreaSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    snapshot_id: int
    organization_id: int
    project_id: int
    area_id: int
    total_tasks: int
    completed_tasks: int
    blocked_tasks: int
    remaining_days: int
    deadline_probability: float
    health_status: str
    state_hash: str
    captured_at: datetime
