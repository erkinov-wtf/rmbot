import logging
import re
from collections.abc import Iterable

from aiogram import Bot
from asgiref.sync import async_to_sync
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from account.models import AccessRequest, Role, TelegramProfile, User
from core.utils.constants import AccessRequestStatus

logger = logging.getLogger(__name__)


class AccountService:
    """Account and access-request orchestration for bot and API flows."""

    PENDING_EMAIL_DOMAIN = "pending.rentmarket.local"

    @staticmethod
    def _normalize_username_seed(raw_username: str | None, telegram_id: int) -> str:
        seed = raw_username or f"tg_{telegram_id}"
        normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", seed).strip("_").lower()
        if not normalized:
            normalized = f"tg_{telegram_id}"
        if normalized[0].isdigit():
            normalized = f"u_{normalized}"
        return normalized[:120]

    @staticmethod
    def _build_unique_username(seed: str) -> str:
        candidate = seed
        index = 1
        while User.all_objects.filter(username=candidate).exists():
            suffix = f"_{index}"
            candidate = f"{seed[: 150 - len(suffix)]}{suffix}"
            index += 1
        return candidate

    @classmethod
    def _build_unique_email(cls, username: str) -> str:
        local_base = re.sub(r"[^a-z0-9._+-]+", "", username.lower()) or "user"
        local_base = local_base[:64]
        candidate = f"{local_base}@{cls.PENDING_EMAIL_DOMAIN}"
        index = 1
        while User.all_objects.filter(email=candidate).exists():
            suffix = f".{index}"
            local_part = f"{local_base[: 64 - len(suffix)]}{suffix}"
            candidate = f"{local_part}@{cls.PENDING_EMAIL_DOMAIN}"
            index += 1
        return candidate

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
        if phone and User.all_objects.filter(phone=phone).exists():
            raise ValueError("Phone number is already used by another account.")

        # User is pre-created inactive and later activated by moderation approval.
        resolved_username = cls._build_unique_username(
            cls._normalize_username_seed(username, telegram_id)
        )
        resolved_email = cls._build_unique_email(resolved_username)
        return User.objects.create_user(
            username=resolved_username,
            password=None,
            first_name=first_name or "Unknown",
            last_name=last_name,
            patronymic=patronymic,
            phone=phone,
            email=resolved_email,
            is_active=False,
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
        updates: dict[str, object] = {}
        if user.deleted_at is not None:
            updates["deleted_at"] = None
        if first_name:
            updates["first_name"] = first_name
        if last_name:
            updates["last_name"] = last_name
        if patronymic:
            updates["patronymic"] = patronymic
        if phone and phone != user.phone:
            if User.all_objects.exclude(pk=user.pk).filter(phone=phone).exists():
                raise ValueError("Phone number is already used by another account.")
            updates["phone"] = phone
        if updates:
            User.all_objects.filter(pk=user.pk).update(**updates)
            user.refresh_from_db()
        return user

    @staticmethod
    def _link_telegram_profile_to_user(
        *,
        telegram_id: int,
        user: User,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> TelegramProfile:
        profile_defaults = {
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "verified_at": timezone.now(),
            "user": user,
        }
        profile, _ = TelegramProfile.all_objects.get_or_create(
            telegram_id=telegram_id,
            defaults=profile_defaults,
        )
        TelegramProfile.all_objects.filter(pk=profile.pk).update(
            user=user,
            deleted_at=None,
            verified_at=timezone.now(),
            username=username or profile.username,
            first_name=first_name or profile.first_name,
            last_name=last_name or profile.last_name,
        )
        profile.refresh_from_db()
        return profile

    @staticmethod
    def upsert_telegram_profile(from_user) -> TelegramProfile:
        """
        Ensure a TelegramProfile exists for a Telegram user.
        Revives soft-deleted profiles if present (uniqueness on telegram_id).
        """
        defaults = {
            "username": getattr(from_user, "username", None),
            "first_name": getattr(from_user, "first_name", None),
            "last_name": getattr(from_user, "last_name", None),
            "language_code": getattr(from_user, "language_code", None),
            "is_bot": getattr(from_user, "is_bot", False) or False,
            "is_premium": getattr(from_user, "is_premium", False) or False,
            "verified_at": timezone.now(),
        }
        profile, _ = TelegramProfile.all_objects.get_or_create(
            telegram_id=from_user.id, defaults=defaults
        )
        TelegramProfile.all_objects.filter(pk=profile.pk).update(
            deleted_at=None, **defaults
        )
        profile.refresh_from_db()
        return profile

    @staticmethod
    def get_active_profile(telegram_id: int) -> TelegramProfile | None:
        return (
            TelegramProfile.objects.select_related("user")
            .filter(telegram_id=telegram_id)
            .first()
        )

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
        existing = AccessRequest.all_objects.filter(
            telegram_id=telegram_id, status=AccessRequestStatus.PENDING
        ).first()
        if existing:
            updates = {}
            if existing.deleted_at is not None:
                updates["deleted_at"] = None
            if phone and not existing.phone:
                updates["phone"] = phone
            if note and not existing.note:
                updates["note"] = note
            if username and not existing.username:
                updates["username"] = username
            if first_name and not existing.first_name:
                updates["first_name"] = first_name
            if last_name and not existing.last_name:
                updates["last_name"] = last_name
            if updates:
                AccessRequest.all_objects.filter(pk=existing.pk).update(**updates)
                existing.refresh_from_db()
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
            existing = AccessRequest.all_objects.get(
                telegram_id=telegram_id,
                status=AccessRequestStatus.PENDING,
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
        existing_profile = (
            TelegramProfile.all_objects.select_related("user")
            .filter(telegram_id=telegram_id)
            .first()
        )

        if (
            existing_profile
            and existing_profile.user
            and existing_profile.user.is_active
        ):
            raise ValueError("You are already registered and linked.")

        if AccessRequest.all_objects.filter(
            telegram_id=telegram_id,
            status=AccessRequestStatus.APPROVED,
        ).exists():
            raise ValueError("Your access request was already approved.")

        if AccessRequest.all_objects.filter(
            telegram_id=telegram_id,
            user__is_active=True,
        ).exists():
            raise ValueError("You are already registered and linked.")

        existing = (
            AccessRequest.all_objects.select_related("user")
            .filter(telegram_id=telegram_id, status=AccessRequestStatus.PENDING)
            .first()
        )
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

            updates: dict[str, object] = {
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "phone": phone,
                "user": pending_user,
                "deleted_at": None,
            }
            if note and not existing.note:
                updates["note"] = note
            AccessRequest.all_objects.filter(pk=existing.pk).update(**updates)
            existing.refresh_from_db()
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
            latest_rejected = (
                AccessRequest.all_objects.select_related("user")
                .filter(
                    telegram_id=telegram_id,
                    status=AccessRequestStatus.REJECTED,
                    user__isnull=False,
                )
                .order_by("-resolved_at", "-created_at")
                .first()
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
        return AccessRequest.all_objects.filter(
            telegram_id=telegram_id,
            status=AccessRequestStatus.PENDING,
        ).first()

    @staticmethod
    @transaction.atomic
    def link_profile_to_user(profile: TelegramProfile, user: User) -> TelegramProfile:
        profile.user = user
        profile.deleted_at = None
        profile.save(update_fields=["user", "deleted_at"])
        return profile

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

        if role_slugs:
            roles = Role.objects.filter(
                slug__in=list(role_slugs), deleted_at__isnull=True
            )
            if roles:
                user.roles.add(*roles)

        if not user.is_active:
            User.all_objects.filter(pk=user.pk).update(is_active=True)
            user.refresh_from_db()

        access_request.status = AccessRequestStatus.APPROVED
        access_request.user = user
        access_request.resolved_at = timezone.now()
        access_request.deleted_at = None
        access_request.save(
            update_fields=["status", "user", "resolved_at", "deleted_at"]
        )
        cls._notify_access_request_decision(
            access_request=access_request, approved=True
        )
        return access_request

    @classmethod
    @transaction.atomic
    def reject_access_request(cls, access_request: AccessRequest) -> AccessRequest:
        if access_request.status != AccessRequestStatus.PENDING:
            raise ValueError("Access request is already resolved")

        access_request.status = AccessRequestStatus.REJECTED
        access_request.resolved_at = timezone.now()
        access_request.save(update_fields=["status", "resolved_at"])
        cls._notify_access_request_decision(
            access_request=access_request, approved=False
        )
        return access_request
