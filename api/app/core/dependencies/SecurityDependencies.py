from datetime import datetime, timezone
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.common.exceptions.AppExceptions import ForbiddenException, UnauthorizedException
from app.core.AuthContext import AuthContext
from app.core.dependencies.AuthDependencies import getAuthRepository, getSessionRepository
from app.modules.auth.AuthRepository import AuthRepository
from app.modules.auth.SessionRepository import SessionRepository
from app.modules.auth.dto.UserTableDto import UserTableDto
from app.modules.auth.utils.JwtHelper import JwtHelper

bearer_scheme = HTTPBearer(auto_error=False)


async def getCurrentAuth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth_repository: AuthRepository = Depends(getAuthRepository),
    session_repository: SessionRepository = Depends(getSessionRepository),
) -> AuthContext:
    """Validates the access token, user state, and active server-side session.

    Args:
        credentials (HTTPAuthorizationCredentials | None): Extracted Authorization header.
        auth_repository (AuthRepository): Repository used to resolve the user.
        session_repository (SessionRepository): Repository used to validate the session.

    Returns:
        AuthContext: Authenticated user, session identifier, and token claims.

    Raises:
        UnauthorizedException: If the token, user, or session is invalid.
    """
    if credentials is None or not credentials.credentials:
        raise UnauthorizedException(detail="Missing authentication token.")

    claims = JwtHelper.decodeToken(token=credentials.credentials)
    if claims.get("type") != "access":
        raise UnauthorizedException(detail="Invalid access token type.")

    user = await auth_repository.getById(user_id=int(claims["sub"]))
    if user is None or not user.is_active:
        raise UnauthorizedException(detail="User account not found or inactive.")
    if int(claims.get("ver", -1)) != int(user.token_version):
        raise UnauthorizedException(detail="Access token has been revoked.")

    session_id = str(claims.get("sid", ""))
    session = await session_repository.getById(session_id=session_id)
    if (
        not session_id
        or session is None
        or session.user_id != user.user_id
        or session.revoked_at is not None
        or session.expires_at <= datetime.now(timezone.utc)
    ):
        raise UnauthorizedException(detail="Session is invalid or has expired.")

    return AuthContext(user=user, session_id=session_id, claims=claims)


async def getCurrentUser(auth: AuthContext = Depends(getCurrentAuth)) -> UserTableDto:
    """Resolves the authenticated user entity from the validated auth context.

    Args:
        auth (AuthContext): Validated authentication context.

    Returns:
        UserTableDto: Authenticated user entity.
    """
    return auth.user


async def getCurrentAdmin(auth: AuthContext = Depends(getCurrentAuth)) -> UserTableDto:
    """Resolves the authenticated user and requires the administrator role.

    Args:
        auth (AuthContext): Validated authentication context.

    Returns:
        UserTableDto: Authenticated administrator.

    Raises:
        ForbiddenException: If the user is not an administrator.
    """
    if auth.user.role != "ADMIN":
        raise ForbiddenException(detail="Administrator privileges are required.")
    return auth.user


async def getCurrentManager(auth: AuthContext = Depends(getCurrentAuth)) -> UserTableDto:
    """Resolves the authenticated user and requires a team management role.

    Args:
        auth (AuthContext): Validated authentication context.

    Returns:
        UserTableDto: Authenticated team leader or administrator.

    Raises:
        ForbiddenException: If the user does not hold a management role.
    """
    if auth.user.role not in {"TEAM_LEADER", "ADMIN"}:
        raise ForbiddenException(detail="Team leader or administrator privileges are required.")
    return auth.user
