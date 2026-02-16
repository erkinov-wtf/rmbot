import re

from django.contrib.auth.base_user import BaseUserManager
from django.db import models
from django.utils import timezone

from core.utils.constants import AccessRequestStatus


class UserManager(BaseUserManager):
    def get_by_natural_key(self, username):
        """Returns the user by their username field."""
        return self.get(**{self.model.USERNAME_FIELD: username})

    def create_user(self, username, password=None, **extra_fields):
        """
        Creates and returns a user with given username, password.
        """
        if not username:
            raise ValueError(
                f"The username field must be set: {self.model.USERNAME_FIELD}"
            )

        user = self.model(**{self.model.USERNAME_FIELD: username}, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        """
        Creates and returns a superuser with username and password.
        """
        extra_fields["is_staff"] = True
        extra_fields["is_superuser"] = True

        return self.create_user(username, password, **extra_fields)

    @staticmethod
    def normalize_username_seed(raw_username: str | None, telegram_id: int) -> str:
        seed = raw_username or f"tg_{telegram_id}"
        normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", seed).strip("_").lower()
        if not normalized:
            normalized = f"tg_{telegram_id}"
        if normalized[0].isdigit():
            normalized = f"u_{normalized}"
        return normalized[:120]

    def build_unique_username(self, *, seed: str) -> str:
        candidate = seed
        index = 1
        while self.model.all_objects.filter(username=candidate).exists():
            suffix = f"_{index}"
            candidate = f"{seed[: 150 - len(suffix)]}{suffix}"
            index += 1
        return candidate

    def phone_in_use(
        self,
        *,
        phone: str | None,
        exclude_user_id: int | None = None,
    ) -> bool:
        if not phone:
            return False
        qs = self.model.all_objects.filter(phone=phone)
        if exclude_user_id is not None:
            qs = qs.exclude(pk=exclude_user_id)
        return qs.exists()

    def create_pending_user(
        self,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        phone: str | None,
    ):
        if self.phone_in_use(phone=phone):
            raise ValueError("Phone number is already used by another account.")

        seed = self.normalize_username_seed(username, telegram_id)
        resolved_username = self.build_unique_username(seed=seed)
        return self.create_user(
            username=resolved_username,
            password=None,
            first_name=first_name or "Unknown",
            last_name=last_name,
            phone=phone,
            is_active=False,
        )


class AccessRequestDomainManager(models.Manager):
    def pending_for_telegram(self, *, telegram_id: int):
        return (
            self.model.all_objects.select_related("user")
            .filter(
                telegram_id=telegram_id,
                status=AccessRequestStatus.PENDING,
            )
            .first()
        )

    def approved_exists_for_telegram(self, *, telegram_id: int) -> bool:
        return self.model.all_objects.filter(
            telegram_id=telegram_id,
            status=AccessRequestStatus.APPROVED,
        ).exists()

    def active_user_link_exists_for_telegram(self, *, telegram_id: int) -> bool:
        return self.model.all_objects.filter(
            telegram_id=telegram_id,
            user__is_active=True,
        ).exists()

    def latest_rejected_with_user(self, *, telegram_id: int):
        return (
            self.model.all_objects.select_related("user")
            .filter(
                telegram_id=telegram_id,
                status=AccessRequestStatus.REJECTED,
                user__isnull=False,
            )
            .order_by("-resolved_at", "-created_at")
            .first()
        )

    def latest_active_with_user(self, *, telegram_id: int):
        return (
            self.model.all_objects.select_related("user")
            .filter(
                telegram_id=telegram_id,
                user__isnull=False,
                user__is_active=True,
            )
            .order_by("-resolved_at", "-created_at", "-id")
            .first()
        )


class TelegramProfileDomainManager(models.Manager):
    def any_for_telegram(self, *, telegram_id: int):
        return (
            self.model.all_objects.select_related("user")
            .filter(telegram_id=telegram_id)
            .first()
        )

    def active_for_telegram(self, *, telegram_id: int):
        return (
            self.model.objects.select_related("user")
            .filter(telegram_id=telegram_id)
            .first()
        )

    def link_to_user(
        self,
        *,
        telegram_id: int,
        user,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ):
        profile_defaults = {
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "verified_at": timezone.now(),
            "user": user,
        }
        profile, _ = self.model.all_objects.get_or_create(
            telegram_id=telegram_id,
            defaults=profile_defaults,
        )
        self.model.all_objects.filter(pk=profile.pk).update(
            user=user,
            deleted_at=None,
            verified_at=timezone.now(),
            username=username or profile.username,
            first_name=first_name or profile.first_name,
            last_name=last_name or profile.last_name,
        )
        profile.refresh_from_db()
        return profile

    def upsert_from_telegram_user(self, *, from_user):
        defaults = {
            "username": getattr(from_user, "username", None),
            "first_name": getattr(from_user, "first_name", None),
            "last_name": getattr(from_user, "last_name", None),
            "language_code": getattr(from_user, "language_code", None),
            "is_bot": getattr(from_user, "is_bot", False) or False,
            "is_premium": getattr(from_user, "is_premium", False) or False,
            "verified_at": timezone.now(),
        }
        profile, _ = self.model.all_objects.get_or_create(
            telegram_id=from_user.id,
            defaults=defaults,
        )
        self.model.all_objects.filter(pk=profile.pk).update(
            deleted_at=None,
            **defaults,
        )
        profile.refresh_from_db()
        return profile
