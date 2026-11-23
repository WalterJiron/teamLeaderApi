"""merge Jira and AI agent migrations

Revision ID: d73b6b1a220d
Revises: c1027d6aa890, e1286385e66d
Create Date: 2026-11-22

"""
from typing import Sequence, Union


revision: str = "d73b6b1a220d"
down_revision: Union[str, Sequence[str], None] = (
    "c1027d6aa890",
    "e1286385e66d",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Joins independent Jira and AI agent schema changes."""


def downgrade() -> None:
    """Keeps both parent revisions applied when the merge revision is reverted."""
