from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from app.core.PostgresManager import Base


class UserSessionTableDto(Base):
    __tablename__ = "user_sessions"

    session_id = Column(String(36), primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        Integer,
        ForeignKey("organizations.organization_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    refresh_token_hash = Column(String(64), nullable=False, unique=True, index=True)
    token_family_id = Column(String(36), nullable=False, index=True)
    replaced_by_session_id = Column(String(36), nullable=True)
    issued_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True, index=True)
    revoked_reason = Column(String(64), nullable=True)
    ip = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    mfa_verified = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
