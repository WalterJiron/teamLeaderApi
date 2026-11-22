from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class RecoveryWithCodeSchema(BaseModel):
    email: EmailStr
    recovery_code: str = Field(..., min_length=6, max_length=32)
    new_password: str = Field(..., min_length=1, max_length=128)


class AccountRecoveryRequestSchema(BaseModel):
    email: EmailStr
    reason: str = Field(..., min_length=10, max_length=1000)


class RecoveryRequestResponse(BaseModel):
    request_id: str
    user_id: int
    organization_id: int
    status: str
    reason: str
    evidence_reference: str | None
    requested_ip: str | None
    reviewed_by: int | None
    reviewed_at: datetime | None
    expires_at: datetime
    created_at: datetime


class RecoveryApprovalRequest(BaseModel):
    status: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    evidence_reference: str | None = Field(default=None, max_length=255)


class RecoveryApprovalResponse(BaseModel):
    message: str
    recovery_token: str | None = None
