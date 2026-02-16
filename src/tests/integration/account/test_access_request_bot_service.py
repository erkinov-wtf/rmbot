import pytest

from account.models import AccessRequest, TelegramProfile, User
from account.services import AccountService
from core.utils.constants import AccessRequestStatus

pytestmark = pytest.mark.django_db


def test_bot_request_creates_pending_with_precreated_user():
    access_request, created = AccountService.ensure_pending_access_request_from_bot(
        telegram_id=700001,
        username="new.tech",
        first_name="New",
        last_name="Tech",
        phone="+998901234567",
    )

    assert created is True
    assert access_request.status == AccessRequestStatus.PENDING
    assert access_request.user_id is not None

    user = access_request.user
    assert user is not None
    assert user.is_active is False
    assert user.first_name == "New"
    assert user.last_name == "Tech"
    assert user.phone == "+998901234567"
    profile = TelegramProfile.objects.get(telegram_id=700001)
    assert profile.user_id == user.id


def test_bot_request_updates_existing_pending_user_without_duplicates():
    first_request, _ = AccountService.ensure_pending_access_request_from_bot(
        telegram_id=700002,
        username="new.tech",
        first_name="New",
        last_name="Tech",
        phone="+998900001111",
    )

    second_request, created = AccountService.ensure_pending_access_request_from_bot(
        telegram_id=700002,
        username="new.tech",
        first_name="Updated",
        last_name="Surname",
        phone="+998900002222",
    )

    assert created is False
    assert second_request.id == first_request.id
    assert second_request.user_id == first_request.user_id
    assert AccessRequest.objects.count() == 1
    assert User.objects.count() == 1

    pending_user = User.objects.get(pk=second_request.user_id)
    assert pending_user.first_name == "Updated"
    assert pending_user.last_name == "Surname"
    assert pending_user.phone == "+998900002222"
    profile = TelegramProfile.objects.get(telegram_id=700002)
    assert profile.user_id == pending_user.id


def test_bot_request_rejects_phone_that_belongs_to_another_user(user_factory):
    user_factory(
        username="existing_user",
        first_name="Existing",
        phone="+998909999999",
    )

    with pytest.raises(ValueError, match="Phone number is already used"):
        AccountService.ensure_pending_access_request_from_bot(
            telegram_id=700003,
            username="incoming",
            first_name="Incoming",
            last_name="User",
            phone="+998909999999",
        )


def test_bot_request_rejects_when_access_request_was_already_approved(user_factory):
    approved_user = user_factory(
        username="approved_user",
        first_name="Approved",
        phone="+998901111111",
        is_active=True,
    )
    AccessRequest.objects.create(
        telegram_id=700004,
        username="approved.user",
        first_name="Approved",
        last_name="User",
        phone="+998901111111",
        status=AccessRequestStatus.APPROVED,
        user=approved_user,
    )

    with pytest.raises(ValueError, match="already approved"):
        AccountService.ensure_pending_access_request_from_bot(
            telegram_id=700004,
            username="approved.user",
            first_name="Approved",
            last_name="User",
            phone="+998901111111",
        )


def test_bot_request_rejects_when_telegram_is_linked_to_active_user(user_factory):
    active_user = user_factory(
        username="linked_active",
        first_name="Linked",
        phone="+998902222222",
        is_active=True,
    )
    TelegramProfile.objects.create(
        telegram_id=700005,
        user=active_user,
        username="linked.active",
        first_name="Linked",
    )

    with pytest.raises(ValueError, match="already registered and linked"):
        AccountService.ensure_pending_access_request_from_bot(
            telegram_id=700005,
            username="linked.active",
            first_name="Linked",
            last_name="Active",
            phone="+998902222222",
        )


def test_bot_request_after_rejection_reuses_user_with_same_phone():
    first_request, created = AccountService.ensure_pending_access_request_from_bot(
        telegram_id=700006,
        username="retry.user",
        first_name="Retry",
        last_name="User",
        phone="+998903333333",
    )
    assert created is True

    rejected = AccountService.reject_access_request(first_request)
    assert rejected.status == AccessRequestStatus.REJECTED

    second_request, created_again = (
        AccountService.ensure_pending_access_request_from_bot(
            telegram_id=700006,
            username="retry.user",
            first_name="Retry2",
            last_name="User2",
            phone="+998903333333",
        )
    )

    assert created_again is True
    assert second_request.status == AccessRequestStatus.PENDING
    assert second_request.user_id == first_request.user_id
    assert AccessRequest.all_objects.filter(telegram_id=700006).count() == 2


def test_resolve_bot_actor_returns_existing_active_link(user_factory):
    user = user_factory(
        username="resolve_active_user",
        first_name="Resolve",
        is_active=True,
    )
    profile = TelegramProfile.objects.create(
        telegram_id=700007,
        user=user,
        username="resolve_active_user",
        first_name="Resolve",
    )

    from_user = type(
        "FromUser",
        (),
        {
            "id": 700007,
            "username": "resolve_active_user",
            "first_name": "Resolve",
            "last_name": "User",
            "language_code": "en",
            "is_bot": False,
            "is_premium": False,
        },
    )()

    resolved_profile, resolved_user = AccountService.resolve_bot_actor(from_user)

    assert resolved_profile.id == profile.id
    assert resolved_user is not None
    assert resolved_user.id == user.id


def test_resolve_bot_actor_recovers_profile_user_link(user_factory):
    inactive_user = user_factory(
        username="resolve_inactive_user",
        first_name="Inactive",
        is_active=False,
    )
    active_user = user_factory(
        username="resolve_recovered_user",
        first_name="Recovered",
        is_active=True,
    )
    profile = TelegramProfile.objects.create(
        telegram_id=700008,
        user=inactive_user,
        username="resolve_inactive_user",
        first_name="Inactive",
    )
    AccessRequest.objects.create(
        telegram_id=700008,
        username="resolve_recovered_user",
        first_name="Recovered",
        status=AccessRequestStatus.APPROVED,
        user=active_user,
    )

    from_user = type(
        "FromUser",
        (),
        {
            "id": 700008,
            "username": "resolve_recovered_user",
            "first_name": "Recovered",
            "last_name": "User",
            "language_code": "en",
            "is_bot": False,
            "is_premium": False,
        },
    )()

    resolved_profile, resolved_user = AccountService.resolve_bot_actor(from_user)
    profile.refresh_from_db()

    assert resolved_user is not None
    assert resolved_user.id == active_user.id
    assert resolved_profile.id == profile.id
    assert profile.user_id == active_user.id
