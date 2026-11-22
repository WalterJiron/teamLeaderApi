from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field


class RegisterUserSchema(BaseModel):
    organization_id: int | None = Field(default=None, ge=1)
    invitation_token: str | None = Field(default=None, min_length=10)
    recovery_email: EmailStr | None = None
    full_name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class LoginRequestSchema(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class RefreshTokenSchema(BaseModel):
    refresh_token: str = Field(..., min_length=10)


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    organization_id: int
    full_name: str
    email: EmailStr
    role: str
    mfa_enabled: bool
    email_verified_at: datetime | None
    last_login_at: datetime | None
    created_at: datetime

    @computed_field
    @property
    def email_verified(self) -> bool:
        """Indicates whether the primary email address has been verified.

        Returns:
            bool: True when email_verified_at is populated.
        """
        return self.email_verified_at is not None


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserProfileResponse


class LoginResponseSchema(BaseModel):
    mfa_required: bool = False
    mfa_token: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    user: UserProfileResponse | None = None


class MessageResponseSchema(BaseModel):
    message: str


class UserStatusSchema(BaseModel):
    is_active: bool


class PasswordChangeSchema(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=1, max_length=128)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=32)


class PasswordResetRequestSchema(BaseModel):
    email: EmailStr


class PasswordResetSchema(BaseModel):
    token: str = Field(..., min_length=20)
    new_password: str = Field(..., min_length=1, max_length=128)


class EmailVerificationConfirmSchema(BaseModel):
    token: str = Field(..., min_length=20)


class EmailChangeRequestSchema(BaseModel):
    new_email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=32)


class EmailChangeConfirmSchema(BaseModel):
    token: str = Field(..., min_length=20)


class RecoveryEmailRequestSchema(BaseModel):
    recovery_email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class RecoveryEmailConfirmSchema(BaseModel):
    token: str = Field(..., min_length=20)
