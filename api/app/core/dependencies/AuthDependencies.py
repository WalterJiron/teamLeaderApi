from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.PostgresManager import PostgresManager
from app.modules.auth.AuditRepository import AuditRepository
from app.modules.auth.AuthRepository import AuthRepository
from app.modules.auth.MfaRepository import MfaRepository
from app.modules.auth.OutboxRepository import OutboxRepository
from app.modules.auth.RecoveryRepository import RecoveryRepository
from app.modules.auth.SessionRepository import SessionRepository
from app.modules.auth.TokenRepository import TokenRepository
from app.modules.auth.service.AdminAuthService import AdminAuthService
from app.modules.auth.service.AuditService import AuditService
from app.modules.auth.service.AuthService import AuthService
from app.modules.auth.service.MfaService import MfaService
from app.modules.auth.service.OrganizationService import OrganizationService
from app.modules.auth.service.PasswordService import PasswordService
from app.modules.auth.service.RecoveryService import RecoveryService
from app.modules.auth.service.SessionService import SessionService


def getAuthRepository(db_session: AsyncSession = Depends(PostgresManager.getSession)) -> AuthRepository:
    """Provides an AuthRepository bound to the current database session.

    Args:
        db_session (AsyncSession): Active PostgreSQL session.

    Returns:
        AuthRepository: User and organization persistence repository.
    """
    return AuthRepository(db_session=db_session)


def getSessionRepository(db_session: AsyncSession = Depends(PostgresManager.getSession)) -> SessionRepository:
    """Provides a SessionRepository bound to the current database session.

    Args:
        db_session (AsyncSession): Active PostgreSQL session.

    Returns:
        SessionRepository: Session persistence repository.
    """
    return SessionRepository(db_session=db_session)


def getTokenRepository(db_session: AsyncSession = Depends(PostgresManager.getSession)) -> TokenRepository:
    """Provides a TokenRepository bound to the current database session.

    Args:
        db_session (AsyncSession): Active PostgreSQL session.

    Returns:
        TokenRepository: Single-use token persistence repository.
    """
    return TokenRepository(db_session=db_session)


def getAuditRepository(db_session: AsyncSession = Depends(PostgresManager.getSession)) -> AuditRepository:
    """Provides an AuditRepository bound to the current database session.

    Args:
        db_session (AsyncSession): Active PostgreSQL session.

    Returns:
        AuditRepository: Audit log persistence repository.
    """
    return AuditRepository(db_session=db_session)


def getMfaRepository(db_session: AsyncSession = Depends(PostgresManager.getSession)) -> MfaRepository:
    """Provides an MfaRepository bound to the current database session.

    Args:
        db_session (AsyncSession): Active PostgreSQL session.

    Returns:
        MfaRepository: MFA persistence repository.
    """
    return MfaRepository(db_session=db_session)


def getOutboxRepository(db_session: AsyncSession = Depends(PostgresManager.getSession)) -> OutboxRepository:
    """Provides an OutboxRepository bound to the current database session.

    Args:
        db_session (AsyncSession): Active PostgreSQL session.

    Returns:
        OutboxRepository: Email outbox persistence repository.
    """
    return OutboxRepository(db_session=db_session)


def getRecoveryRepository(db_session: AsyncSession = Depends(PostgresManager.getSession)) -> RecoveryRepository:
    """Provides a RecoveryRepository bound to the current database session.

    Args:
        db_session (AsyncSession): Active PostgreSQL session.

    Returns:
        RecoveryRepository: Account recovery persistence repository.
    """
    return RecoveryRepository(db_session=db_session)


def getAuditService(audit_repository: AuditRepository = Depends(getAuditRepository)) -> AuditService:
    """Provides an AuditService with its injected repository.

    Args:
        audit_repository (AuditRepository): Injected audit repository.

    Returns:
        AuditService: Security audit service.
    """
    return AuditService(audit_repository=audit_repository)


def getPasswordService(auth_repository: AuthRepository = Depends(getAuthRepository)) -> PasswordService:
    """Provides a PasswordService with its injected repository.

    Args:
        auth_repository (AuthRepository): Injected user repository.

    Returns:
        PasswordService: Password policy and history service.
    """
    return PasswordService(auth_repository=auth_repository)


def getSessionService(session_repository: SessionRepository = Depends(getSessionRepository)) -> SessionService:
    """Provides a SessionService with its injected repository.

    Args:
        session_repository (SessionRepository): Injected session repository.

    Returns:
        SessionService: Session issuance and rotation service.
    """
    return SessionService(session_repository=session_repository)


def getMfaService(
    mfa_repository: MfaRepository = Depends(getMfaRepository),
    auth_repository: AuthRepository = Depends(getAuthRepository),
) -> MfaService:
    """Provides an MfaService with its injected repositories.

    Args:
        mfa_repository (MfaRepository): Injected MFA repository.
        auth_repository (AuthRepository): Injected user repository.

    Returns:
        MfaService: Multi-factor authentication service.
    """
    return MfaService(mfa_repository=mfa_repository, auth_repository=auth_repository)


def getAuthService(
    auth_repository: AuthRepository = Depends(getAuthRepository),
    session_repository: SessionRepository = Depends(getSessionRepository),
    token_repository: TokenRepository = Depends(getTokenRepository),
    outbox_repository: OutboxRepository = Depends(getOutboxRepository),
    password_service: PasswordService = Depends(getPasswordService),
    session_service: SessionService = Depends(getSessionService),
    mfa_service: MfaService = Depends(getMfaService),
    audit_service: AuditService = Depends(getAuditService),
) -> AuthService:
    """Provides an AuthService with all authentication collaborators.

    Args:
        auth_repository (AuthRepository): Injected user repository.
        session_repository (SessionRepository): Injected session repository.
        token_repository (TokenRepository): Injected token repository.
        outbox_repository (OutboxRepository): Injected email outbox repository.
        password_service (PasswordService): Injected password service.
        session_service (SessionService): Injected session service.
        mfa_service (MfaService): Injected MFA service.
        audit_service (AuditService): Injected audit service.

    Returns:
        AuthService: Core authentication service.
    """
    return AuthService(
        auth_repository=auth_repository,
        session_repository=session_repository,
        token_repository=token_repository,
        outbox_repository=outbox_repository,
        password_service=password_service,
        session_service=session_service,
        mfa_service=mfa_service,
        audit_service=audit_service,
    )


def getOrganizationService(
    auth_repository: AuthRepository = Depends(getAuthRepository),
    outbox_repository: OutboxRepository = Depends(getOutboxRepository),
    audit_service: AuditService = Depends(getAuditService),
) -> OrganizationService:
    """Provides an OrganizationService with its injected collaborators.

    Args:
        auth_repository (AuthRepository): Injected organization repository.
        outbox_repository (OutboxRepository): Injected email outbox repository.
        audit_service (AuditService): Injected audit service.

    Returns:
        OrganizationService: Organization and invitation service.
    """
    return OrganizationService(
        auth_repository=auth_repository,
        outbox_repository=outbox_repository,
        audit_service=audit_service,
    )


def getAdminAuthService(
    auth_repository: AuthRepository = Depends(getAuthRepository),
    session_repository: SessionRepository = Depends(getSessionRepository),
    mfa_repository: MfaRepository = Depends(getMfaRepository),
    audit_repository: AuditRepository = Depends(getAuditRepository),
    audit_service: AuditService = Depends(getAuditService),
    session_service: SessionService = Depends(getSessionService),
    auth_service: AuthService = Depends(getAuthService),
) -> AdminAuthService:
    """Provides an AdminAuthService with its injected collaborators.

    Args:
        auth_repository (AuthRepository): Injected user repository.
        session_repository (SessionRepository): Injected session repository.
        mfa_repository (MfaRepository): Injected MFA repository.
        audit_repository (AuditRepository): Injected audit repository.
        audit_service (AuditService): Injected audit service.
        session_service (SessionService): Injected session service.
        auth_service (AuthService): Injected core auth service.

    Returns:
        AdminAuthService: Administrative authentication service.
    """
    return AdminAuthService(
        auth_repository=auth_repository,
        session_repository=session_repository,
        mfa_repository=mfa_repository,
        audit_repository=audit_repository,
        audit_service=audit_service,
        session_service=session_service,
        auth_service=auth_service,
    )


def getRecoveryService(
    recovery_repository: RecoveryRepository = Depends(getRecoveryRepository),
    auth_repository: AuthRepository = Depends(getAuthRepository),
    audit_service: AuditService = Depends(getAuditService),
    auth_service: AuthService = Depends(getAuthService),
) -> RecoveryService:
    """Provides a RecoveryService with its injected collaborators.

    Args:
        recovery_repository (RecoveryRepository): Injected recovery repository.
        auth_repository (AuthRepository): Injected user repository.
        audit_service (AuditService): Injected audit service.
        auth_service (AuthService): Injected core auth service.

    Returns:
        RecoveryService: Account recovery service.
    """
    return RecoveryService(
        recovery_repository=recovery_repository,
        auth_repository=auth_repository,
        audit_service=audit_service,
        auth_service=auth_service,
    )
