from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from app.core.PostgresManager import Base


class UserMfaSettingTableDto(Base):
    __tablename__ = "user_mfa_settings"

    user_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    totp_secret_encrypted = Column(String(512), nullable=True)
    totp_enabled = Column(Boolean, nullable=False, default=False)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    failed_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
