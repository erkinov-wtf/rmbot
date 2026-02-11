from typing import Iterable, Optional, Tuple

from django.db import IntegrityError, transaction
from django.utils import timezone

from account.models import AccessRequest, TelegramProfile, User, Role
from core.utils.constants import AccessRequestStatus


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
        "is_bot": getattr(from_user, "is_bot", False),
        "is_premium": getattr(from_user, "is_premium", False),
        "verified_at": timezone.now(),
    }
    profile, _ = TelegramProfile.all_objects.get_or_create(telegram_id=from_user.id, defaults=defaults)
    TelegramProfile.all_objects.filter(pk=profile.pk).update(deleted_at=None, **defaults)
    profile.refresh_from_db()
    return profile


def get_active_profile(telegram_id: int) -> Optional[TelegramProfile]:
    return TelegramProfile.objects.select_related("user").filter(
        telegram_id=telegram_id, deleted_at__isnull=True
    ).first()


def ensure_pending_access_request(
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    phone: Optional[str] = None,
    note: Optional[str] = None,
) -> Tuple[AccessRequest, bool]:
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


def get_pending_access_request(telegram_id: int) -> Optional[AccessRequest]:
    return AccessRequest.all_objects.filter(
        telegram_id=telegram_id,
        status=AccessRequestStatus.PENDING,
    ).first()


@transaction.atomic
def link_profile_to_user(profile: TelegramProfile, user: User) -> TelegramProfile:
    profile.user = user
    profile.deleted_at = None
    profile.save(update_fields=["user", "deleted_at"])
    return profile


@transaction.atomic
def approve_access_request(
    access_request: AccessRequest,
    user: User,
    role_slugs: Optional[Iterable[str]] = None,
) -> AccessRequest:
    if access_request.status != AccessRequestStatus.PENDING:
        raise ValueError("Access request is already resolved")

    profile_defaults = {
        "username": access_request.username,
        "first_name": access_request.first_name,
        "last_name": access_request.last_name,
        "verified_at": timezone.now(),
    }
    profile, _ = TelegramProfile.all_objects.get_or_create(
        telegram_id=access_request.telegram_id,
        defaults=profile_defaults,
    )
    TelegramProfile.all_objects.filter(pk=profile.pk).update(
        user=user,
        deleted_at=None,
        verified_at=timezone.now(),
        username=profile.username or access_request.username,
        first_name=profile.first_name or access_request.first_name,
        last_name=profile.last_name or access_request.last_name,
    )

    if role_slugs:
        roles = Role.objects.filter(slug__in=list(role_slugs), deleted_at__isnull=True)
        if roles:
            user.roles.add(*roles)

    access_request.status = AccessRequestStatus.APPROVED
    access_request.user = user
    access_request.resolved_at = timezone.now()
    access_request.deleted_at = None
    access_request.save(update_fields=["status", "user", "resolved_at", "deleted_at"])
    return access_request


@transaction.atomic
def reject_access_request(access_request: AccessRequest) -> AccessRequest:
    if access_request.status != AccessRequestStatus.PENDING:
        raise ValueError("Access request is already resolved")

    access_request.status = AccessRequestStatus.REJECTED
    access_request.resolved_at = timezone.now()
    access_request.save(update_fields=["status", "resolved_at"])
    return access_request
