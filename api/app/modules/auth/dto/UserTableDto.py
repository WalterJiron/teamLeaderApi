from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, func, text
from app.common.dto.AuditMixin import AuditMixin
from app.core.PostgresManager import Base


class UserTableDto(Base, AuditMixin):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    organization_id = Column(
        Integer,
        ForeignKey("organizations.organization_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    full_name = Column(String(120), nullable=False)
    email = Column(String(180), nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    password_algorithm = Column(String(32), nullable=False, default="argon2id")
    password_changed_at = Column(DateTime(timezone=True), nullable=True)
    must_change_password = Column(Boolean, nullable=False, default=False)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    role = Column(String(32), nullable=False, default="TEAM_LEADER")
    is_active = Column(Boolean, nullable=False, default=True)
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    token_version = Column(Integer, nullable=False, default=0)
    mfa_enabled = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index(
            "uq_users_email_active",
            func.lower(email),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )
