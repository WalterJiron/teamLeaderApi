from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "TeamLeader SaaS API"
    APP_ENV: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    APP_PUBLIC_URL: str = "http://localhost:8000"
    ENABLE_DOCS: bool = True

    POSTGRES_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/saas_db"
    MONGO_URL: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "agent_memory_db"
    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "teamleader-api"
    JWT_AUDIENCE: str = "teamleader-client"
    JWT_KEY_ID: str = "primary"
    JWT_ACCESS_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_EXPIRE_MINUTES: int = 10080
    MFA_CHALLENGE_EXPIRE_MINUTES: int = 5

    DATA_ENCRYPTION_KEY: str = ""
    MFA_ISSUER_NAME: str = "TeamLeader"

    PASSWORD_MIN_LENGTH: int = 12
    PASSWORD_MAX_LENGTH: int = 128
    PASSWORD_HISTORY_SIZE: int = 5
    BREACHED_PASSWORD_CHECK_ENABLED: bool = False
    PASSWORD_RESET_EXPIRE_MINUTES: int = 30
    EMAIL_VERIFICATION_EXPIRE_HOURS: int = 24
    EMAIL_CHANGE_EXPIRE_HOURS: int = 2
    RECOVERY_EMAIL_EXPIRE_HOURS: int = 24
    INVITATION_EXPIRE_DAYS: int = 7
    ACCOUNT_RECOVERY_EXPIRE_DAYS: int = 7

    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15
    MFA_MAX_ATTEMPTS: int = 5
    MFA_LOCKOUT_MINUTES: int = 15
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_FAIL_OPEN: bool = True

    ALLOW_OPEN_REGISTRATION: bool = True
    REQUIRE_EMAIL_VERIFICATION_FOR_LOGIN: bool = False
    AUTO_CREATE_TABLES: bool = False
    AUDIT_HASH_CHAIN_ENABLED: bool = True
    EMAIL_OUTBOX_INTERVAL_SECONDS: int = 5

    CORS_ALLOW_ORIGINS: str = "*"
    CORS_ALLOW_CREDENTIALS: bool = False
    TRUSTED_HOSTS: str = "*"
    SECURITY_HSTS_ENABLED: bool = False

    EMAIL_PROVIDER: str = "smtp"
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "no-reply@teamlider.local"
    SMTP_FROM_NAME: str = "TeamLeader"
    SMTP_USE_TLS: bool = False
    SMTP_USE_SSL: bool = False

    PASSWORD_RESET_URL: str = "http://localhost:3000/reset-password"
    EMAIL_VERIFICATION_URL: str = "http://localhost:3000/verify-email"
    EMAIL_CHANGE_URL: str = "http://localhost:3000/confirm-email-change"
    RECOVERY_EMAIL_URL: str = "http://localhost:3000/confirm-recovery-email"
    INVITATION_URL: str = "http://localhost:3000/accept-invitation"

    N8N_AGENT_WEBHOOK_URL: str = "http://localhost:5678/webhook/agent"
    N8N_INTERNAL_API_KEY: str = "CHANGE_ME_INTERNAL_KEY"


AppConfig = AppSettings()
