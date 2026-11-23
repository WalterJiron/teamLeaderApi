from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class GithubIntegrationCreateSchema(BaseModel):
    project_id: int = Field(..., ge=1)
    repository_owner: str = Field(..., min_length=1, max_length=120)
    repository_name: str = Field(..., min_length=1, max_length=120)
    access_token: str = Field(..., min_length=16, max_length=2048)
    webhook_secret: str = Field(..., min_length=16, max_length=256)
    label_area_map: dict[str, int] = Field(..., min_length=1)
    blocked_label: str = Field(default="blocked", min_length=1, max_length=64)

    @field_validator("repository_owner", "repository_name")
    @classmethod
    def validateRepositoryIdentifier(cls, value: str) -> str:
        """Normalizes and validates a GitHub repository identifier.

        Args:
            value (str): Raw repository owner or name.

        Returns:
            str: Trimmed repository identifier.

        Raises:
            ValueError: If the identifier contains unsupported characters.
        """
        normalized = value.strip()
        if not normalized:
            raise ValueError("Repository identifiers cannot be empty.")
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
        if any(character not in allowed for character in normalized):
            raise ValueError("Repository identifiers contain unsupported characters.")
        if not any(character.isalnum() for character in normalized):
            raise ValueError("Repository identifiers must contain at least one alphanumeric character.")
        if ".." in normalized:
            raise ValueError("Repository identifiers cannot contain path traversal sequences.")
        return normalized

    @field_validator("label_area_map")
    @classmethod
    def validateLabelAreaMap(cls, value: dict[str, int]) -> dict[str, int]:
        """Validates GitHub label to internal area mappings.

        Args:
            value (dict[str, int]): Raw label to area identifier mapping.

        Returns:
            dict[str, int]: Normalized label mapping.

        Raises:
            ValueError: If a label is empty, too long, or maps to an invalid area.
        """
        normalized: dict[str, int] = {}
        for label, area_id in value.items():
            normalized_label = str(label).strip()
            if not normalized_label:
                raise ValueError("GitHub label names cannot be empty.")
            if len(normalized_label) > 64:
                raise ValueError("GitHub label names cannot exceed 64 characters.")
            if int(area_id) < 1:
                raise ValueError("Area identifiers must be positive integers.")
            normalized[normalized_label] = int(area_id)
        if not normalized:
            raise ValueError("At least one GitHub label to area mapping is required.")
        return normalized

    @field_validator("blocked_label")
    @classmethod
    def validateBlockedLabel(cls, value: str) -> str:
        """Normalizes the configured blocked label.

        Args:
            value (str): Raw blocked label name.

        Returns:
            str: Trimmed blocked label name.

        Raises:
            ValueError: If the blocked label is empty.
        """
        normalized = value.strip()
        if not normalized:
            raise ValueError("The blocked label cannot be empty.")
        return normalized


class GithubIntegrationResponse(BaseModel):
    integration_id: int
    organization_id: int
    project_id: int
    repository_owner: str
    repository_name: str
    label_area_map: dict[str, int]
    blocked_label: str
    is_active: bool
    last_synced_at: datetime | None
    created_at: datetime
    masked_access_token: str
    masked_webhook_secret: str


class GithubWebhookPayloadSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    action: str | None = None
    issue: dict[str, Any] | None = None
    pull_request: dict[str, Any] | None = None
    repository: dict[str, Any] | None = None
