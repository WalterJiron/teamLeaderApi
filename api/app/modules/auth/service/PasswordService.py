import hashlib
import logging
from datetime import datetime, timezone
import httpx
from app.common.exceptions.AppExceptions import BadRequestException
from app.core.AppConfig import AppConfig
from app.modules.auth.AuthRepository import AuthRepository
from app.modules.auth.dto.PasswordHistoryTableDto import PasswordHistoryTableDto
from app.modules.auth.dto.UserTableDto import UserTableDto
from app.modules.auth.utils.PasswordHelper import PasswordHelper

logger = logging.getLogger(__name__)


class PasswordService:

    def __init__(self, auth_repository: AuthRepository) -> None:
        """Initializes the password service with its repository.

        Args:
            auth_repository (AuthRepository): User and password history repository.
        """
        self.auth_repository = auth_repository

    @staticmethod
    async def _isBreached(password: str) -> bool:
        """Checks a password against the Have I Been Pwned k-anonymity API.

        Args:
            password (str): Plain-text password.

        Returns:
            bool: True when the password appears in a known breach corpus.
        """
        if not AppConfig.BREACHED_PASSWORD_CHECK_ENABLED:
            return False
        sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
        prefix, suffix = sha1[:5], sha1[5:]
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"https://api.pwnedpasswords.com/range/{prefix}",
                    headers={"Add-Padding": "true"},
                )
                response.raise_for_status()
            return any(line.split(":")[0] == suffix for line in response.text.splitlines())
        except Exception:
            logger.warning("Breached password check failed; continuing without it.")
            return False

    async def validatePolicy(self, password: str, user: UserTableDto | None = None, email: str | None = None) -> None:
        """Validates password length, common-password, and personal-data rules.

        Args:
            password (str): Plain-text password.
            user (UserTableDto | None, optional): Existing user for personal-data checks. Defaults to None.
            email (str | None, optional): Email used during registration. Defaults to None.

        Raises:
            BadRequestException: If the password violates the policy.
        """
        if len(password) < AppConfig.PASSWORD_MIN_LENGTH:
            raise BadRequestException(
                detail=f"Password must contain at least {AppConfig.PASSWORD_MIN_LENGTH} characters."
            )
        if len(password) > AppConfig.PASSWORD_MAX_LENGTH:
            raise BadRequestException(
                detail=f"Password must contain at most {AppConfig.PASSWORD_MAX_LENGTH} characters."
            )
        if PasswordHelper.isCommonPassword(password):
            raise BadRequestException(detail="Password is too common. Choose a stronger password.")

        normalized_email = (email or (user.email if user else "") or "").lower()
        normalized_name = (user.full_name if user else "").lower()
        if normalized_email and normalized_email.split("@")[0] and normalized_email.split("@")[0] in password.lower():
            raise BadRequestException(detail="Password must not contain your email address.")
        if normalized_name and len(normalized_name) >= 3 and normalized_name in password.lower():
            raise BadRequestException(detail="Password must not contain your full name.")
        if await self._isBreached(password):
            raise BadRequestException(detail="Password appears in a known data breach. Choose another password.")

    async def isReused(self, user: UserTableDto, new_password: str) -> bool:
        """Checks a candidate password against the current and recent password hashes.

        Args:
            user (UserTableDto): User entity.
            new_password (str): Candidate plain-text password.

        Returns:
            bool: True when the password was used recently.
        """
        if PasswordHelper.verifyPassword(new_password, user.hashed_password):
            return True
        history = await self.auth_repository.getPasswordHistory(
            user_id=user.user_id,
            limit=AppConfig.PASSWORD_HISTORY_SIZE,
        )
        return any(PasswordHelper.verifyPassword(new_password, item.password_hash) for item in history)

    async def setPassword(
        self,
        user: UserTableDto,
        new_password: str,
        reason: str,
        actor_id: int | None = None,
    ) -> None:
        """Replaces a user password and records the previous hash in history.

        Args:
            user (UserTableDto): User entity to update.
            new_password (str): New plain-text password.
            reason (str): Change reason code.
            actor_id (int | None, optional): Administrator performing the change. Defaults to None.
        """
        if user.hashed_password:
            await self.auth_repository.addPasswordHistory(
                PasswordHistoryTableDto(
                    user_id=user.user_id,
                    password_hash=user.hashed_password,
                    algorithm=user.password_algorithm or PasswordHelper.getAlgorithm(user.hashed_password),
                    reason=reason,
                    created_by=actor_id,
                )
            )
        hashed = PasswordHelper.hashPassword(new_password)
        user.hashed_password = hashed
        user.password_algorithm = PasswordHelper.getAlgorithm(hashed)
        user.password_changed_at = datetime.now(timezone.utc)
        user.must_change_password = False
        await self.auth_repository.db_session.flush()
        await self.auth_repository.prunePasswordHistory(
            user_id=user.user_id,
            keep=AppConfig.PASSWORD_HISTORY_SIZE,
        )
