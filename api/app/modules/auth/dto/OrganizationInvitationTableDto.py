from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from app.common.dto.AuditMixin import AuditMixin
from app.core.PostgresManager import Base


class OrganizationInvitationTableDto(Base, AuditMixin):
    __tablename__ = "organization_invitations"

    invitation_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    organization_id = Column(
        Integer,
        ForeignKey("organizations.organization_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email = Column(String(180), nullable=False, index=True)
    role = Column(String(32), nullable=False, default="TEAM_LEADER")
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    invited_by = Column(Integer, nullable=True)
