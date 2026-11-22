from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, func
from app.core.PostgresManager import Base


class AuthTokenTableDto(Base):
    __tablename__ = "auth_tokens"

    token_id = Column(String(36), primary_key=True)
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
    purpose = Column(String(48), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_ip = Column(String(45), nullable=True)
    created_user_agent = Column(String(255), nullable=True)
    metadata_json = Column(JSON, nullable=True)
