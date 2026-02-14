import logging
from collections.abc import Iterable

from aiogram import Bot
from asgiref.sync import async_to_sync
from django.conf import settings
from django.db import IntegrityError, transaction

from account.models import AccessRequest, TelegramProfile, User
from core.utils.constants import AccessRequestStatus

logger = logging.getLogger(__name__)


class AccountService:
    """Account and access-request orchestration for bot and API flows."""

    PENDING_EMAIL_DOMAIN = "pending.rentmarket.local"

    @classmethod
    def _create_pending_user(
        cls,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        patronymic: str | None,
        phone: str | None,
    ) -> User:
        return User.objects.create_pending_user(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            patronymic=patronymic,
            phone=phone,
            pending_email_domain=cls.PENDING_EMAIL_DOMAIN,
        )

    @staticmethod
    def _sync_pending_user(
        user: User,
        *,
        first_name: str | None,
        last_name: str | None,
        patronymic: str | None,
        phone: str | None,
    ) -> User:
        return user.sync_pending_fields(
            first_name=first_name,
            last_name=last_name,
            patronymic=patronymic,
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
        patronymic: str | None,
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
            raise ValueError("You are already registered and linked.")

        if AccessRequest.domain.approved_exists_for_telegram(telegram_id=telegram_id):
            raise ValueError("Your access request was already approved.")

        if AccessRequest.domain.active_user_link_exists_for_telegram(
            telegram_id=telegram_id
        ):
            raise ValueError("You are already registered and linked.")

        existing = AccessRequest.domain.pending_for_telegram(telegram_id=telegram_id)
        if existing:
            pending_user = existing.user
            if pending_user:
                cls._sync_pending_user(
                    pending_user,
                    first_name=first_name,
                    last_name=last_name,
                    patronymic=patronymic,
                    phone=phone,
                )
            else:
                pending_user = cls._create_pending_user(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    patronymic=patronymic,
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
                patronymic=patronymic,
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
                    patronymic=patronymic,
                    phone=phone,
                )

        if pending_user is None:
            pending_user = cls._create_pending_user(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                patronymic=patronymic,
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

    @staticmethod
    def _build_access_request_decision_message(
        *, approved: bool, first_name: str | None
    ) -> str:
        greeting = f"Hello, {first_name}." if first_name else "Hello."
        if approved:
            return f"{greeting}\nYour access request has been approved. You can now use Rent Market."
        return f"{greeting}\nYour access request has been denied. You can submit a new request using /start."

    @staticmethod
    async def _send_telegram_notification(*, telegram_id: int, message: str) -> None:
        bot = Bot(token=settings.BOT_TOKEN)
        try:
            await bot.send_message(chat_id=telegram_id, text=message)
        finally:
            await bot.session.close()

    @classmethod
    def _notify_access_request_decision(
        cls, *, access_request: AccessRequest, approved: bool
    ) -> None:
        if getattr(settings, "IS_TEST_RUN", False):
            return
        if not settings.BOT_TOKEN:
            logger.info(
                "Skip access-request decision notification: BOT_TOKEN is not configured."
            )
            return

        message = cls._build_access_request_decision_message(
            approved=approved, first_name=access_request.first_name
        )
        try:
            async_to_sync(cls._send_telegram_notification)(
                telegram_id=access_request.telegram_id,
                message=message,
            )
        except Exception:
            logger.exception(
                "Failed to send access-request decision notification for telegram_id=%s.",
                access_request.telegram_id,
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
                patronymic=user.patronymic,
                phone=access_request.phone,
            )
        else:
            user = cls._create_pending_user(
                telegram_id=access_request.telegram_id,
                username=access_request.username,
                first_name=access_request.first_name,
                last_name=access_request.last_name,
                patronymic=None,
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
        cls._notify_access_request_decision(
            access_request=access_request, approved=True
        )
        return access_request

    @classmethod
    @transaction.atomic
    def reject_access_request(cls, access_request: AccessRequest) -> AccessRequest:
        if access_request.status != AccessRequestStatus.PENDING:
            raise ValueError("Access request is already resolved")

        access_request.mark_rejected()
        cls._notify_access_request_decision(
            access_request=access_request, approved=False
        )
        return access_request
