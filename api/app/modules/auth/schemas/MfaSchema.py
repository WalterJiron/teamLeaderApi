from pydantic import BaseModel, Field


class MfaSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class MfaConfirmSchema(BaseModel):
    code: str = Field(..., min_length=6, max_length=32)


class MfaVerifySchema(BaseModel):
    mfa_token: str = Field(..., min_length=20)
    code: str = Field(..., min_length=6, max_length=32)


class MfaDisableSchema(BaseModel):
    password: str = Field(..., min_length=1, max_length=128)
    code: str = Field(..., min_length=6, max_length=32)


class MfaRecoveryCodesResponse(BaseModel):
    recovery_codes: list[str]
