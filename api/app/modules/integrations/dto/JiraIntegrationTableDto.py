from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from app.core.PostgresManager import Base


class JiraIntegrationTableDto(Base):
    __tablename__ = "jira_integrations"

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
    jira_base_url = Column(String(255), nullable=False)
    jira_project_key = Column(String(80), nullable=False)
    jira_project_name = Column(String(255), nullable=False)
    jira_email = Column(String(254), nullable=False)
    encrypted_api_token = Column(Text, nullable=False)
    project_deadline = Column(Date, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index(
            "uq_jira_integrations_tenant_project",
            organization_id,
            project_id,
            unique=True,
        ),
        Index(
            "uq_jira_integrations_tenant_external_project",
            organization_id,
            func.lower(jira_base_url),
            func.lower(jira_project_key),
            unique=True,
        ),
        Index("ix_jira_integrations_tenant_active", organization_id, is_active),
    )
