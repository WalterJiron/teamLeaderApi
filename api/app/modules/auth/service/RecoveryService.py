from datetime import datetime, timedelta, timezone
from app.common.exceptions.AppExceptions import BadRequestException, ForbiddenException
from app.core.AppConfig import AppConfig
from app.core.RequestContext import getClientIp
from app.modules.auth.AuthRepository import AuthRepository
from app.modules.auth.RecoveryRepository import RecoveryRepository
from app.modules.auth.dto.AccountRecoveryRequestTableDto import AccountRecoveryRequestTableDto
from app.modules.auth.dto.UserTableDto import UserTableDto
from app.modules.auth.schemas.RecoverySchema import (
    RecoveryApprovalRequest,
    RecoveryApprovalResponse,
    RecoveryRequestResponse,
)
from app.modules.auth.service.AuditService import AuditService
from app.modules.auth.service.AuthService import AuthService
from app.modules.auth.utils.TokenHelper import TokenHelper


class RecoveryService:

    def __init__(
        self,
        recovery_repository: RecoveryRepository,
        auth_repository: AuthRepository,
        audit_service: AuditService,
        auth_service: AuthService,
    ) -> None:
        """Initializes the account recovery service.

        Args:
            recovery_repository (RecoveryRepository): Recovery request persistence repository.
            auth_repository (AuthRepository): User persistence repository.
            audit_service (AuditService): Security audit service.
            auth_service (AuthService): Core authentication service.
        """
        self.recovery_repository = recovery_repository
        self.auth_repository = auth_repository
        self.audit_service = audit_service
        self.auth_service = auth_service

    async def requestRecovery(self, email: str, reason: str) -> None:
        """Files an administrator-assisted recovery request without revealing account existence.

        Args:
            email (str): Primary or recovery email address.
            reason (str): Explanation of why access was lost.
        """
        normalized = AuthRepository.normalizeEmail(email)
        user = await self.auth_repository.getByEmail(email=normalized)
        if user is None:
            user = await self.auth_repository.getByAnyEmail(email=normalized)
        if user is None:
            await self.audit_service.record(
                event_type="ACCOUNT_RECOVERY_REQUESTED",
                severity="WARN",
                metadata={"email_hash": TokenHelper.hashEmail(normalized), "found": False},
            )
            return

        existing = await self.recovery_repository.getPendingByUser(user_id=user.user_id)
        if existing is not None:
            return

        await self.recovery_repository.addRequest(
            AccountRecoveryRequestTableDto(
                request_id=TokenHelper.newId(),
                user_id=user.user_id,
                organization_id=user.organization_id,
                status="PENDING",
                reason=reason.strip(),
                requested_ip=getClientIp(),
                expires_at=datetime.now(timezone.utc) + timedelta(days=AppConfig.ACCOUNT_RECOVERY_EXPIRE_DAYS),
            )
        )
        await self.audit_service.record(
            event_type="ACCOUNT_RECOVERY_REQUESTED",
            target_user_id=user.user_id,
            organization_id=user.organization_id,
            severity="WARN",
            metadata={"email_hash": TokenHelper.hashEmail(normalized), "found": True},
        )

    async def listRequests(
        self,
        admin: UserTableDto,
        page: int,
        limit: int,
        status: str | None = None,
    ) -> tuple[list[RecoveryRequestResponse], int]:
        """Lists recovery requests for the administrator's organization.

        Args:
            admin (UserTableDto): Authenticated administrator.
            page (int): One-based page number.
            limit (int): Page size.
            status (str | None, optional): Optional status filter. Defaults to None.

        Returns:
            tuple[list[RecoveryRequestResponse], int]: Requests and total count.

        Raises:
            ForbiddenException: If the caller is not an administrator.
        """
        if admin.role != "ADMIN":
            raise ForbiddenException(detail="Administrator privileges are required.")
        offset = max(page - 1, 0) * limit
        requests = await self.recovery_repository.listRequests(
            organization_id=admin.organization_id,
            offset=offset,
            limit=limit,
            status=status,
        )
        total = await self.recovery_repository.countRequests(
            organization_id=admin.organization_id,
            status=status,
        )
        return [self._toResponse(item) for item in requests], total

    @staticmethod
    def _toResponse(item: AccountRecoveryRequestTableDto) -> RecoveryRequestResponse:
        """Serializes a recovery request entity.

        Args:
            item (AccountRecoveryRequestTableDto): Recovery request entity.

        Returns:
            RecoveryRequestResponse: Public recovery request representation.
        """
        return RecoveryRequestResponse(
            request_id=item.request_id,
            user_id=item.user_id,
            organization_id=item.organization_id,
            status=item.status,
            reason=item.reason,
            evidence_reference=item.evidence_reference,
            requested_ip=item.requested_ip,
            reviewed_by=item.reviewed_by,
            reviewed_at=item.reviewed_at,
            expires_at=item.expires_at,
            created_at=item.created_at,
        )

    async def reviewRequest(
        self,
        admin: UserTableDto,
        request_id: str,
        payload: RecoveryApprovalRequest,
    ) -> RecoveryApprovalResponse:
        """Approves or rejects a recovery request and issues an out-of-band token when approved.

        Args:
            admin (UserTableDto): Authenticated administrator.
            request_id (str): Recovery request identifier.
            payload (RecoveryApprovalRequest): Decision and optional evidence reference.

        Returns:
            RecoveryApprovalResponse: Decision message and one-time recovery token.

        Raises:
            ForbiddenException: If the caller is not an administrator.
            BadRequestException: If the request is missing, already reviewed, or expired.
        """
        if admin.role != "ADMIN":
            raise ForbiddenException(detail="Administrator privileges are required.")

        request = await self.recovery_repository.getById(request_id=request_id)
        if request is None or request.organization_id != admin.organization_id:
            raise BadRequestException(detail="Recovery request not found.")
        if request.status != "PENDING":
            raise BadRequestException(detail="Recovery request has already been reviewed.")
        if request.expires_at <= datetime.now(timezone.utc):
            request.status = "EXPIRED"
            request.reviewed_by = admin.user_id
            request.reviewed_at = datetime.now(timezone.utc)
            await self.recovery_repository.db_session.flush()
            raise BadRequestException(detail="Recovery request has expired.")

        request.status = payload.status
        request.evidence_reference = payload.evidence_reference
        request.reviewed_by = admin.user_id
        request.reviewed_at = datetime.now(timezone.utc)
        await self.recovery_repository.db_session.flush()

        recovery_token: str | None = None
        if payload.status == "APPROVED":
            user = await self.auth_repository.getById(user_id=request.user_id)
            if user is None:
                raise BadRequestException(detail="Recovery user no longer exists.")
            recovery_token = await self.auth_service.issueAccountRecoveryToken(user=user)

        await self.audit_service.record(
            event_type=f"ACCOUNT_RECOVERY_{payload.status}",
            actor_user_id=admin.user_id,
            target_user_id=request.user_id,
            organization_id=admin.organization_id,
            severity="CRITICAL",
            metadata={"request_id": request_id, "evidence_reference": payload.evidence_reference},
        )
        return RecoveryApprovalResponse(
            message=f"Recovery request {payload.status.lower()}.",
            recovery_token=recovery_token,
        )

    async def confirmRecovery(self, token: str, new_password: str) -> None:
        """Completes an approved account recovery by setting a new password.

        Args:
            token (str): Raw account recovery token.
            new_password (str): New plain-text password.
        """
        await self.auth_service.confirmAccountRecovery(token=token, new_password=new_password)
