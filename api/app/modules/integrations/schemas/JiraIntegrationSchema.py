from datetime import date, datetime
from urllib.parse import urlparse

from pydantic import BaseModel, EmailStr, Field, SecretStr, field_validator

from app.modules.metrics.schemas.DelayRiskSchema import (
    DelayRiskAssessmentResponseSchema,
)


class JiraIntegrationCreateSchema(BaseModel):
    project_id: int = Field(..., ge=1)
    jira_base_url: str = Field(..., min_length=1, max_length=255)
    jira_project_key: str = Field(..., min_length=1, max_length=80)
    jira_email: EmailStr
    api_token: SecretStr = Field(..., min_length=8, max_length=2048)
    project_deadline: date | None = None

    @field_validator("jira_base_url")
    @classmethod
    def validateJiraBaseUrl(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlparse(normalized)
        host = (parsed.hostname or "").casefold()
        if (
            parsed.scheme != "https"
            or not host.endswith(".atlassian.net")
            or host == "atlassian.net"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Use the HTTPS origin of a Jira Cloud tenant.")
        return f"https://{host}"

    @field_validator("jira_project_key")
    @classmethod
    def normalizeProjectKey(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized or not normalized[0].isalpha():
            raise ValueError("Jira project keys must start with a letter.")
        if any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for character in normalized):
            raise ValueError("Jira project keys contain unsupported characters.")
        return normalized


class JiraIntegrationResponseSchema(BaseModel):
    integration_id: int
    organization_id: int
    project_id: int
    jira_base_url: str
    jira_project_key: str
    jira_project_name: str
    jira_email: str
    project_deadline: date | None
    is_active: bool
    last_synced_at: datetime | None
    created_at: datetime
    masked_api_token: str


class JiraSyncResponseSchema(BaseModel):
    integration_id: int
    internal_project_id: int
    jira_project_key: str
    synced_at: datetime
    assessment: DelayRiskAssessmentResponseSchema
    warnings: list[str]
