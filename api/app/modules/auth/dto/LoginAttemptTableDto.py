from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String, func
from app.core.PostgresManager import Base


class LoginAttemptTableDto(Base):
    __tablename__ = "login_attempts"

    attempt_id = Column(BigInteger, primary_key=True, autoincrement=True)
    email_hash = Column(String(64), nullable=False, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    ip = Column(String(45), nullable=True, index=True)
    user_agent = Column(String(255), nullable=True)
    success = Column(Boolean, nullable=False, default=False)
    failure_reason = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
