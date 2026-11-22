from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from app.core.PostgresManager import Base


class AccountRecoveryRequestTableDto(Base):
    __tablename__ = "account_recovery_requests"

    request_id = Column(String(36), primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        Integer,
        ForeignKey("organizations.organization_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String(16), nullable=False, default="PENDING", index=True)
    reason = Column(Text, nullable=False)
    evidence_reference = Column(String(255), nullable=True)
    requested_ip = Column(String(45), nullable=True)
    reviewed_by = Column(Integer, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
