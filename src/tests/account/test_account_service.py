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
