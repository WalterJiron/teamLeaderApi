from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, func
from app.core.PostgresManager import Base


class GithubIntegrationTableDto(Base):
    __tablename__ = "github_integrations"

    integration_id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(
        Integer,
        ForeignKey("organizations.organization_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id = Column(
        Integer,
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_owner = Column(String(120), nullable=False)
    repository_name = Column(String(120), nullable=False)
    encrypted_access_token = Column(Text, nullable=False)
    encrypted_webhook_secret = Column(Text, nullable=False)
    label_area_map = Column(JSON, nullable=False)
    blocked_label = Column(String(64), nullable=False, default="blocked")
    is_active = Column(Boolean, nullable=False, default=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index(
            "uq_github_integrations_tenant_repository",
            organization_id,
            project_id,
            func.lower(repository_owner),
            func.lower(repository_name),
            unique=True,
        ),
        Index("ix_github_integrations_tenant_active", organization_id, is_active),
    )
