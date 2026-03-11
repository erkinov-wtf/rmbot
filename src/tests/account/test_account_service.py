import pytest

from account.models import AccessRequest, TelegramProfile, User
from account.services import AccountService
from core.api.exceptions import DomainValidationError
from core.utils.constants import AccessRequestStatus


@pytest.mark.django_db
def test_bot_access_request_reclaims_phone_from_inactive_user():
    phone = "+998900001111"
    telegram_id = 910001
    User.objects.create_user(
        username="stale_phone_owner",
        password="pass1234",
        first_name="Stale",
        phone=phone,
        is_active=False,
    )

    access_request, created = AccountService.ensure_pending_access_request_from_bot(
        telegram_id=telegram_id,
        username="new_user",
        first_name="New",
        last_name="User",
        phone=phone,
    )

    stale_user = User.all_objects.get(username="stale_phone_owner")
    stale_user.refresh_from_db()
    access_request.refresh_from_db()

    assert created is True
    assert stale_user.phone is None
    assert access_request.status == AccessRequestStatus.PENDING
    assert access_request.phone == phone
    assert access_request.user is not None
    assert access_request.user.phone == phone

    profile = TelegramProfile.all_objects.get(telegram_id=telegram_id)
    assert profile.user_id == access_request.user_id


@pytest.mark.django_db
def test_bot_access_request_rejects_phone_from_active_user():
    phone = "+998900002222"
    telegram_id = 910002
    User.objects.create_user(
        username="active_phone_owner",
        password="pass1234",
        first_name="Active",
        phone=phone,
        is_active=True,
    )

    with pytest.raises(
        DomainValidationError,
        match="Phone number is already used by another account.",
    ):
        AccountService.ensure_pending_access_request_from_bot(
            telegram_id=telegram_id,
            username="new_user_2",
            first_name="Another",
            last_name="Person",
            phone=phone,
        )

    assert not AccessRequest.all_objects.filter(telegram_id=telegram_id).exists()


@pytest.mark.django_db
def test_bot_access_request_allows_when_only_approved_with_inactive_user_exists():
    phone = "+998900003333"
    telegram_id = 910003
    stale_user = User.objects.create_user(
        username="approved_inactive_owner",
        password="pass1234",
        first_name="Approved",
        phone=phone,
        is_active=False,
    )
    AccessRequest.objects.create(
        telegram_id=telegram_id,
        username="old_tg",
        first_name="Old",
        last_name="Owner",
        phone=phone,
        status=AccessRequestStatus.APPROVED,
        user=stale_user,
    )

    access_request, created = AccountService.ensure_pending_access_request_from_bot(
        telegram_id=telegram_id,
        username="new_tg",
        first_name="New",
        last_name="Owner",
        phone=phone,
    )

    stale_user.refresh_from_db()
    access_request.refresh_from_db()

    assert created is True
    assert access_request.status == AccessRequestStatus.PENDING
    assert access_request.telegram_id == telegram_id
    assert stale_user.phone is None
    assert access_request.user is not None
    assert access_request.user.phone == phone
