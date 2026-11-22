from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from app.core.PostgresManager import Base


class UserRecoveryCodeTableDto(Base):
    __tablename__ = "user_recovery_codes"

    code_id = Column(String(36), primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    batch_id = Column(String(36), nullable=False, index=True)
    code_hash = Column(String(255), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
