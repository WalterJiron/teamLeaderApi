from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4
import jwt
from app.common.exceptions.AppExceptions import UnauthorizedException
from app.core.AppConfig import AppConfig
from app.modules.auth.dto.UserTableDto import UserTableDto


class JwtHelper:

    @staticmethod
    def createAccessToken(user: UserTableDto, session_id: str) -> str:
        """Signs a short-lived access token with tenant and session claims.

        Args:
            user (UserTableDto): Authenticated user entity.
            session_id (str): Active session identifier.

        Returns:
            str: Encoded access JWT.
        """
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user.user_id),
            "org": user.organization_id,
            "role": user.role,
            "type": "access",
            "ver": user.token_version,
            "sid": session_id,
            "jti": str(uuid4()),
            "iss": AppConfig.JWT_ISSUER,
            "aud": AppConfig.JWT_AUDIENCE,
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=AppConfig.JWT_ACCESS_EXPIRE_MINUTES),
        }
        return jwt.encode(
            payload,
            AppConfig.JWT_SECRET_KEY,
            algorithm=AppConfig.JWT_ALGORITHM,
            headers={"kid": AppConfig.JWT_KEY_ID},
        )

    @staticmethod
    def decodeToken(token: str) -> dict[str, Any]:
        """Decodes and validates an access JWT signature, issuer, audience, and expiry.

        Args:
            token (str): Encoded access JWT.

        Returns:
            dict[str, Any]: Validated JWT claims.

        Raises:
            UnauthorizedException: If the token is invalid, expired, or malformed.
        """
        try:
            return jwt.decode(
                token,
                AppConfig.JWT_SECRET_KEY,
                algorithms=[AppConfig.JWT_ALGORITHM],
                audience=AppConfig.JWT_AUDIENCE,
                issuer=AppConfig.JWT_ISSUER,
                options={
                    "require": ["sub", "iss", "aud", "iat", "nbf", "exp", "jti", "type"],
                },
            )
        except jwt.PyJWTError as exc:
            raise UnauthorizedException(detail="Invalid or expired access token.") from exc
