"""add Jira Cloud integrations

Revision ID: c1027d6aa890
Revises: f9e9371daaa7
Create Date: 2026-11-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1027d6aa890"
down_revision: Union[str, None] = "f9e9371daaa7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jira_integrations",
        sa.Column("integration_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("jira_base_url", sa.String(length=255), nullable=False),
        sa.Column("jira_project_key", sa.String(length=80), nullable=False),
        sa.Column("jira_project_name", sa.String(length=255), nullable=False),
        sa.Column("jira_email", sa.String(length=254), nullable=False),
        sa.Column("encrypted_api_token", sa.Text(), nullable=False),
        sa.Column("project_deadline", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.organization_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.project_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("integration_id"),
    )
    op.create_index(
        op.f("ix_jira_integrations_organization_id"),
        "jira_integrations",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_jira_integrations_project_id"),
        "jira_integrations",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "uq_jira_integrations_tenant_project",
        "jira_integrations",
        ["organization_id", "project_id"],
        unique=True,
    )
    op.create_index(
        "uq_jira_integrations_tenant_external_project",
        "jira_integrations",
        [
            "organization_id",
            sa.text("lower(jira_base_url)"),
            sa.text("lower(jira_project_key)"),
        ],
        unique=True,
    )
    op.create_index(
        "ix_jira_integrations_tenant_active",
        "jira_integrations",
        ["organization_id", "is_active"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_jira_integrations_tenant_active",
        table_name="jira_integrations",
    )
    op.drop_index(
        "uq_jira_integrations_tenant_external_project",
        table_name="jira_integrations",
    )
    op.drop_index(
        "uq_jira_integrations_tenant_project",
        table_name="jira_integrations",
    )
    op.drop_index(
        op.f("ix_jira_integrations_project_id"),
        table_name="jira_integrations",
    )
    op.drop_index(
        op.f("ix_jira_integrations_organization_id"),
        table_name="jira_integrations",
    )
    op.drop_table("jira_integrations")
