from sqlalchemy import JSON, BigInteger, Column, DateTime, Integer, String, func
from app.core.PostgresManager import Base


class AuthAuditLogTableDto(Base):
    __tablename__ = "auth_audit_logs"

    audit_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, nullable=True, index=True)
    actor_user_id = Column(Integer, nullable=True, index=True)
    target_user_id = Column(Integer, nullable=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    severity = Column(String(16), nullable=False, default="INFO")
    ip = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    request_id = Column(String(64), nullable=True, index=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    previous_hash = Column(String(64), nullable=True)
    entry_hash = Column(String(64), nullable=True)
