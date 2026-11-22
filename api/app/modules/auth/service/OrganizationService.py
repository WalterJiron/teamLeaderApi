from datetime import datetime, timedelta, timezone
from app.common.exceptions.AppExceptions import BadRequestException, ConflictException, ForbiddenException
from app.core.AppConfig import AppConfig
from app.core.RequestContext import getClientIp, getUserAgent
from app.modules.auth.AuthRepository import AuthRepository
from app.modules.auth.OutboxRepository import OutboxRepository
from app.modules.auth.dto.OrganizationInvitationTableDto import OrganizationInvitationTableDto
from app.modules.auth.dto.UserTableDto import UserTableDto
from app.modules.auth.schemas.OrganizationSchema import InvitationCreateSchema, InvitationResponse
from app.modules.auth.service.AuditService import AuditService
from app.modules.auth.service.EmailService import EmailService
from app.modules.auth.utils.TokenHelper import TokenHelper


class OrganizationService:

    def __init__(
        self,
        auth_repository: AuthRepository,
        outbox_repository: OutboxRepository,
        audit_service: AuditService,
    ) -> None:
        """Initializes the organization service with its collaborators.

        Args:
            auth_repository (AuthRepository): Organization and invitation repository.
            outbox_repository (OutboxRepository): Transactional email outbox repository.
            audit_service (AuditService): Security audit service.
        """
        self.auth_repository = auth_repository
        self.outbox_repository = outbox_repository
        self.audit_service = audit_service

    async def createInvitation(
        self,
        admin: UserTableDto,
        payload: InvitationCreateSchema,
    ) -> InvitationResponse:
        """Invites an email address to join the administrator's organization.

        Args:
            admin (UserTableDto): Authenticated administrator.
            payload (InvitationCreateSchema): Invitation email and role.

        Returns:
            InvitationResponse: Persisted invitation including the raw token.

        Raises:
            ForbiddenException: If the caller is not an administrator.
            ConflictException: If the email is registered or already invited.
        """
        if admin.role != "ADMIN":
            raise ForbiddenException(detail="Only administrators can invite users.")

        email = AuthRepository.normalizeEmail(payload.email)
        if await self.auth_repository.emailExists(email=email):
            raise ConflictException(detail="Email address is already registered.")
        pending = await self.auth_repository.getPendingInvitation(
            organization_id=admin.organization_id,
            email=email,
        )
        if pending is not None and pending.expires_at > datetime.now(timezone.utc):
            raise ConflictException(detail="A pending invitation already exists for this email.")

        raw_token = TokenHelper.generateToken(48)
        invitation = await self.auth_repository.addInvitation(
            OrganizationInvitationTableDto(
                organization_id=admin.organization_id,
                email=email,
                role=payload.role,
                token_hash=TokenHelper.hashToken(raw_token),
                expires_at=datetime.now(timezone.utc) + timedelta(days=AppConfig.INVITATION_EXPIRE_DAYS),
                invited_by=admin.user_id,
                created_by=admin.user_id,
            )
        )
        await EmailService.enqueueEmail(
            outbox_repository=self.outbox_repository,
            recipient=email,
            template="INVITATION",
            organization_id=admin.organization_id,
            payload={
                "full_name": email,
                "action_url": f"{AppConfig.INVITATION_URL}?token={raw_token}",
                "expires_in": f"{AppConfig.INVITATION_EXPIRE_DAYS} days",
                "extra": f"You were invited as {payload.role}.",
            },
        )
        await self.audit_service.record(
            event_type="INVITATION_CREATED",
            actor_user_id=admin.user_id,
            organization_id=admin.organization_id,
            metadata={"email_hash": TokenHelper.hashEmail(email), "role": payload.role},
        )
        return InvitationResponse(
            invitation_id=invitation.invitation_id,
            organization_id=invitation.organization_id,
            email=invitation.email,
            role=invitation.role,
            expires_at=invitation.expires_at,
            accepted_at=invitation.accepted_at,
            invitation_token=raw_token,
        )

    async def listInvitations(
        self,
        admin: UserTableDto,
        page: int,
        limit: int,
    ) -> tuple[list[InvitationResponse], int]:
        """Lists invitations for the administrator's organization.

        Args:
            admin (UserTableDto): Authenticated administrator.
            page (int): One-based page number.
            limit (int): Page size.

        Returns:
            tuple[list[InvitationResponse], int]: Invitations and total count.

        Raises:
            ForbiddenException: If the caller is not an administrator.
        """
        if admin.role != "ADMIN":
            raise ForbiddenException(detail="Only administrators can list invitations.")
        offset = max(page - 1, 0) * limit
        items = await self.auth_repository.listInvitations(
            organization_id=admin.organization_id,
            offset=offset,
            limit=limit,
        )
        total = await self.auth_repository.countInvitations(organization_id=admin.organization_id)
        return (
            [
                InvitationResponse(
                    invitation_id=item.invitation_id,
                    organization_id=item.organization_id,
                    email=item.email,
                    role=item.role,
                    expires_at=item.expires_at,
                    accepted_at=item.accepted_at,
                )
                for item in items
            ],
            total,
        )

    async def cancelInvitation(self, admin: UserTableDto, invitation_id: int) -> None:
        """Soft-deletes a pending invitation.

        Args:
            admin (UserTableDto): Authenticated administrator.
            invitation_id (int): Invitation identifier.

        Raises:
            ForbiddenException: If the caller is not an administrator.
            BadRequestException: If the invitation does not belong to the organization.
        """
        if admin.role != "ADMIN":
            raise ForbiddenException(detail="Only administrators can cancel invitations.")
        invitations = await self.auth_repository.listInvitations(
            organization_id=admin.organization_id,
            offset=0,
            limit=1000,
        )
        invitation = next(
            (item for item in invitations if item.invitation_id == invitation_id),
            None,
        )
        if invitation is None:
            raise BadRequestException(detail="Invitation not found.")
        invitation.deleted_at = datetime.now(timezone.utc)
        invitation.deleted_by = admin.user_id
        await self.auth_repository.db_session.flush()
        await self.audit_service.record(
            event_type="INVITATION_CANCELLED",
            actor_user_id=admin.user_id,
            organization_id=admin.organization_id,
            metadata={"invitation_id": invitation_id, "ip": getClientIp(), "user_agent": getUserAgent()},
        )
