import hmac
from datetime import datetime, timedelta, timezone
from app.common.exceptions.AppExceptions import BadRequestException, TooManyRequestsException, UnauthorizedException
from app.core.AppConfig import AppConfig
from app.core.EncryptionManager import EncryptionManager
from app.modules.auth.AuthRepository import AuthRepository
from app.modules.auth.MfaRepository import MfaRepository
from app.modules.auth.dto.UserMfaSettingTableDto import UserMfaSettingTableDto
from app.modules.auth.dto.UserRecoveryCodeTableDto import UserRecoveryCodeTableDto
from app.modules.auth.dto.UserTableDto import UserTableDto
from app.modules.auth.schemas.MfaSchema import MfaSetupResponse
from app.modules.auth.utils.PasswordHelper import PasswordHelper
from app.modules.auth.utils.TokenHelper import TokenHelper
from app.modules.auth.utils.TotpHelper import TotpHelper


class MfaService:

    RECOVERY_CODE_COUNT = 10

    def __init__(self, mfa_repository: MfaRepository, auth_repository: AuthRepository) -> None:
        """Initializes the MFA service with its repositories.

        Args:
            mfa_repository (MfaRepository): MFA settings and recovery code repository.
            auth_repository (AuthRepository): User persistence repository.
        """
        self.mfa_repository = mfa_repository
        self.auth_repository = auth_repository

    async def beginSetup(self, user: UserTableDto) -> MfaSetupResponse:
        """Generates a new TOTP secret and stores it pending confirmation.

        Args:
            user (UserTableDto): Authenticated user entity.

        Returns:
            MfaSetupResponse: Base32 secret and otpauth provisioning URI.
        """
        secret = TotpHelper.generateSecret()
        setting = UserMfaSettingTableDto(
            user_id=user.user_id,
            totp_secret_encrypted=EncryptionManager.encrypt(secret),
            totp_enabled=False,
            failed_attempts=0,
        )
        await self.mfa_repository.upsertSetting(setting=setting)
        return MfaSetupResponse(
            secret=secret,
            provisioning_uri=TotpHelper.buildProvisioningUri(secret=secret, account_name=user.email),
        )

    async def confirmSetup(self, user: UserTableDto, code: str) -> list[str]:
        """Confirms TOTP enrollment and issues a fresh batch of recovery codes.

        Args:
            user (UserTableDto): Authenticated user entity.
            code (str): Six-digit TOTP code.

        Returns:
            list[str]: Plain-text one-time recovery codes.

        Raises:
            BadRequestException: If no pending MFA setup exists or the code is invalid.
        """
        setting = await self.mfa_repository.getByUserId(user_id=user.user_id)
        if setting is None or not setting.totp_secret_encrypted:
            raise BadRequestException(detail="MFA setup has not been started.")

        secret = EncryptionManager.decrypt(setting.totp_secret_encrypted)
        if not TotpHelper.verifyCode(secret=secret, code=code):
            raise BadRequestException(detail="Invalid verification code.")

        setting.totp_enabled = True
        setting.confirmed_at = datetime.now(timezone.utc)
        setting.failed_attempts = 0
        setting.locked_until = None
        await self.mfa_repository.upsertSetting(setting=setting)

        user.mfa_enabled = True
        await self.auth_repository.db_session.flush()
        return await self.regenerateRecoveryCodes(user=user)

    async def regenerateRecoveryCodes(self, user: UserTableDto) -> list[str]:
        """Replaces all recovery codes with a new batch.

        Args:
            user (UserTableDto): Authenticated user entity.

        Returns:
            list[str]: Newly generated plain-text recovery codes.
        """
        await self.mfa_repository.deleteRecoveryCodes(user_id=user.user_id)
        batch_id = TokenHelper.newId()
        plain_codes: list[str] = []
        entities: list[UserRecoveryCodeTableDto] = []
        for _ in range(self.RECOVERY_CODE_COUNT):
            code = PasswordHelper.generateRecoveryCode()
            plain_codes.append(code)
            entities.append(
                UserRecoveryCodeTableDto(
                    code_id=TokenHelper.newId(),
                    user_id=user.user_id,
                    batch_id=batch_id,
                    code_hash=PasswordHelper.hashRecoveryCode(code),
                )
            )
        await self.mfa_repository.addRecoveryCodes(codes=entities)
        return plain_codes

    async def _verifyRecoveryCode(self, user: UserTableDto, code: str) -> bool:
        """Verifies and consumes a one-time recovery code.

        Args:
            user (UserTableDto): Authenticated user entity.
            code (str): User-provided recovery code.

        Returns:
            bool: True when an unused matching code was found.
        """
        candidate = PasswordHelper.hashRecoveryCode(code)
        unused = await self.mfa_repository.getUnusedRecoveryCodes(user_id=user.user_id)
        for item in unused:
            if hmac.compare_digest(item.code_hash, candidate):
                item.used_at = datetime.now(timezone.utc)
                await self.auth_repository.db_session.flush()
                return True
        return False

    async def verify(self, user: UserTableDto, code: str) -> bool:
        """Verifies a TOTP or recovery code and enforces MFA attempt lockout.

        Args:
            user (UserTableDto): Authenticated user entity.
            code (str): TOTP or recovery code.

        Returns:
            bool: True when the code is valid.

        Raises:
            TooManyRequestsException: If MFA verification is temporarily locked.
        """
        setting = await self.mfa_repository.getByUserId(user_id=user.user_id)
        if setting is None or not setting.totp_enabled or not setting.totp_secret_encrypted:
            return False

        now = datetime.now(timezone.utc)
        if setting.locked_until is not None and setting.locked_until > now:
            retry_after = int((setting.locked_until - now).total_seconds()) + 1
            raise TooManyRequestsException(
                detail="Too many verification attempts. Try again later.",
                retry_after=retry_after,
            )

        success = False
        normalized = code.strip()
        if normalized.isdigit() and len(normalized) == 6:
            secret = EncryptionManager.decrypt(setting.totp_secret_encrypted)
            success = TotpHelper.verifyCode(secret=secret, code=normalized)
        if not success:
            success = await self._verifyRecoveryCode(user=user, code=normalized)

        if success:
            setting.failed_attempts = 0
            setting.locked_until = None
            setting.last_used_at = now
            await self.mfa_repository.upsertSetting(setting=setting)
            return True

        setting.failed_attempts += 1
        if setting.failed_attempts >= AppConfig.MFA_MAX_ATTEMPTS:
            setting.failed_attempts = 0
            setting.locked_until = now + timedelta(minutes=AppConfig.MFA_LOCKOUT_MINUTES)
        await self.mfa_repository.upsertSetting(setting=setting)
        return False

    async def verifyOrRaise(self, user: UserTableDto, code: str | None) -> None:
        """Requires a valid MFA code for a sensitive operation.

        Args:
            user (UserTableDto): Authenticated user entity.
            code (str | None): TOTP or recovery code.

        Raises:
            UnauthorizedException: If MFA is enabled and the code is missing or invalid.
        """
        if not user.mfa_enabled:
            return
        if not code:
            raise UnauthorizedException(detail="MFA verification code is required.")
        if not await self.verify(user=user, code=code):
            raise UnauthorizedException(detail="Invalid MFA verification code.")

    async def disable(self, user: UserTableDto, code: str) -> None:
        """Disables MFA after verifying a TOTP or recovery code.

        Args:
            user (UserTableDto): Authenticated user entity.
            code (str): TOTP or recovery code.

        Raises:
            BadRequestException: If MFA is not enabled or the code is invalid.
        """
        if not user.mfa_enabled:
            raise BadRequestException(detail="MFA is not enabled for this account.")
        if not await self.verify(user=user, code=code):
            raise BadRequestException(detail="Invalid verification code.")

        await self.mfa_repository.deleteSetting(user_id=user.user_id)
        await self.mfa_repository.deleteRecoveryCodes(user_id=user.user_id)
        user.mfa_enabled = False
        await self.auth_repository.db_session.flush()
