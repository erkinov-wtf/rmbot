from collections.abc import Iterable

from django.db import IntegrityError, transaction

from account.models import AccessRequest, TelegramProfile, User
from core.api.exceptions import DomainValidationError
from core.services.notifications import UserNotificationService
from core.utils.constants import AccessRequestStatus


class AccountService:
    """Account and access-request orchestration for bot and API flows."""

    @classmethod
    def _create_pending_user(
        cls,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        phone: str | None,
    ) -> User:
        return User.objects.create_pending_user(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
        )

    @staticmethod
    def _sync_pending_user(
        user: User,
        *,
        first_name: str | None,
        last_name: str | None,
        phone: str | None,
    ) -> User:
        return user.sync_pending_fields(
            first_name=first_name,
            last_name=last_name,
            phone=phone,
        )

    @staticmethod
    def _link_telegram_profile_to_user(
        *,
        telegram_id: int,
        user: User,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> TelegramProfile:
        return TelegramProfile.domain.link_to_user(
            telegram_id=telegram_id,
            user=user,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )

    @staticmethod
    def upsert_telegram_profile(from_user) -> TelegramProfile:
        """
        Ensure a TelegramProfile exists for a Telegram user.
        Revives soft-deleted profiles if present (uniqueness on telegram_id).
        """
        return TelegramProfile.domain.upsert_from_telegram_user(from_user=from_user)

    @staticmethod
    def get_active_profile(telegram_id: int) -> TelegramProfile | None:
        return TelegramProfile.domain.active_for_telegram(telegram_id=telegram_id)

    @classmethod
    @transaction.atomic
    def resolve_bot_actor(cls, from_user) -> tuple[TelegramProfile, User | None]:
        """
        Resolve Telegram profile + active linked user for bot updates.

        This method is resilient for old data where profile<->user links may be
        missing: it revives/upserts profile data and restores link from the
        latest active access-request record for the same telegram id.
        """
        profile = cls.upsert_telegram_profile(from_user=from_user)
        linked_user = profile.user
        if linked_user and linked_user.is_active:
            return profile, linked_user

        recovered_request = AccessRequest.domain.latest_active_with_user(
            telegram_id=from_user.id
        )
        recovered_user = recovered_request.user if recovered_request else None
        if not recovered_user:
            return profile, None

        linked_profile = cls._link_telegram_profile_to_user(
            telegram_id=from_user.id,
            user=recovered_user,
            username=getattr(from_user, "username", None),
            first_name=getattr(from_user, "first_name", None),
            last_name=getattr(from_user, "last_name", None),
        )
        return linked_profile, recovered_user

    @staticmethod
    def ensure_pending_access_request(
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        phone: str | None = None,
        note: str | None = None,
    ) -> tuple[AccessRequest, bool]:
        """
        Create a pending access request if none exists for the telegram user.
        Returns (access_request, created).
        """
        existing = AccessRequest.domain.pending_for_telegram(telegram_id=telegram_id)
        if existing:
            existing.patch_pending_identity(
                username=username,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                note=note,
            )
            return existing, False

        try:
            created = AccessRequest.objects.create(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                note=note,
            )
            return created, True
        except IntegrityError:
            existing = AccessRequest.domain.pending_for_telegram(
                telegram_id=telegram_id
            )
            return existing, False

    @classmethod
    @transaction.atomic
    def ensure_pending_access_request_from_bot(
        cls,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str,
        last_name: str,
        phone: str,
        note: str | None = None,
    ) -> tuple[AccessRequest, bool]:
        existing_profile = TelegramProfile.domain.any_for_telegram(
            telegram_id=telegram_id
        )

        if (
            existing_profile
            and existing_profile.user
            and existing_profile.user.is_active
        ):
            raise DomainValidationError("You are already registered and linked.")

        if AccessRequest.domain.approved_exists_for_telegram(telegram_id=telegram_id):
            raise DomainValidationError("Your access request was already approved.")

        if AccessRequest.domain.active_user_link_exists_for_telegram(
            telegram_id=telegram_id
        ):
            raise DomainValidationError("You are already registered and linked.")

        existing = AccessRequest.domain.pending_for_telegram(telegram_id=telegram_id)
        if existing:
            pending_user = existing.user
            if pending_user:
                cls._sync_pending_user(
                    pending_user,
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                )
            else:
                pending_user = cls._create_pending_user(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                )

            existing.patch_pending_identity(
                username=username,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                note=note,
                user=pending_user,
            )
            cls._link_telegram_profile_to_user(
                telegram_id=telegram_id,
                user=pending_user,
                username=username,
                first_name=first_name,
                last_name=last_name,
            )
            return existing, False

        pending_user = None
        if (
            existing_profile
            and existing_profile.user
            and not existing_profile.user.is_active
        ):
            pending_user = cls._sync_pending_user(
                existing_profile.user,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
            )
        else:
            latest_rejected = AccessRequest.domain.latest_rejected_with_user(
                telegram_id=telegram_id
            )
            rejected_user = latest_rejected.user if latest_rejected else None
            if rejected_user and not rejected_user.is_active:
                pending_user = cls._sync_pending_user(
                    rejected_user,
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                )

        if pending_user is None:
            pending_user = cls._create_pending_user(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
            )
        access_request = AccessRequest.objects.create(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            note=note,
            user=pending_user,
        )
        cls._link_telegram_profile_to_user(
            telegram_id=telegram_id,
            user=pending_user,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        return access_request, True

    @staticmethod
    def get_pending_access_request(telegram_id: int) -> AccessRequest | None:
        return AccessRequest.domain.pending_for_telegram(telegram_id=telegram_id)

    @staticmethod
    @transaction.atomic
    def link_profile_to_user(profile: TelegramProfile, user: User) -> TelegramProfile:
        return TelegramProfile.domain.link_to_user(
            telegram_id=profile.telegram_id,
            user=user,
            username=profile.username,
            first_name=profile.first_name,
            last_name=profile.last_name,
        )

    @classmethod
    @transaction.atomic
    def approve_access_request(
        cls,
        access_request: AccessRequest,
        role_slugs: Iterable[str] | None = None,
    ) -> AccessRequest:
        if access_request.status != AccessRequestStatus.PENDING:
            raise ValueError("Access request is already resolved")

        user = access_request.user
        if user:
            cls._sync_pending_user(
                user,
                first_name=access_request.first_name,
                last_name=access_request.last_name,
                phone=access_request.phone,
            )
        else:
            user = cls._create_pending_user(
                telegram_id=access_request.telegram_id,
                username=access_request.username,
                first_name=access_request.first_name,
                last_name=access_request.last_name,
                phone=access_request.phone,
            )

        cls._link_telegram_profile_to_user(
            telegram_id=access_request.telegram_id,
            user=user,
            username=access_request.username,
            first_name=access_request.first_name,
            last_name=access_request.last_name,
        )

        user.assign_roles_by_slugs(role_slugs=role_slugs)
        user.activate_if_needed()
        access_request.mark_approved(user=user)
        UserNotificationService.notify_access_request_decision(
            access_request=access_request,
            approved=True,
        )
        return access_request

    @classmethod
    @transaction.atomic
    def reject_access_request(cls, access_request: AccessRequest) -> AccessRequest:
        if access_request.status != AccessRequestStatus.PENDING:
            raise ValueError("Access request is already resolved")

        access_request.mark_rejected()
        UserNotificationService.notify_access_request_decision(
            access_request=access_request,
            approved=False,
        )
        return access_request
