from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from app.core.PostgresManager import Base


class PasswordHistoryTableDto(Base):
    __tablename__ = "password_history"

    history_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    password_hash = Column(String(255), nullable=False)
    algorithm = Column(String(32), nullable=False, default="argon2id")
    reason = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(Integer, nullable=True)
