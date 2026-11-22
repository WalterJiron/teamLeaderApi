from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, func, text
from app.common.dto.AuditMixin import AuditMixin
from app.core.PostgresManager import Base


class UserEmailTableDto(Base, AuditMixin):
    __tablename__ = "user_emails"

    email_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email = Column(String(180), nullable=False, index=True)
    is_primary = Column(Boolean, nullable=False, default=False)
    is_recovery = Column(Boolean, nullable=False, default=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "uq_user_emails_email_active",
            func.lower(email),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )
