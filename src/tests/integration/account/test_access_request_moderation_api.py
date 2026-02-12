import pytest

from account.models import AccessRequest, TelegramProfile
from account.services import AccountService
from core.utils.constants import AccessRequestStatus, RoleSlug

pytestmark = pytest.mark.django_db


LIST_URL = "/api/v1/users/access-requests/"


@pytest.fixture
def moderation_context(user_factory, assign_roles):
    pending_user = user_factory(
        username="pending_tech",
        first_name="New",
        last_name="Tech",
        patronymic="Middle",
        email="pending_tech@example.com",
        phone="+998991112233",
        is_active=False,
    )
    pending = AccessRequest.objects.create(
        telegram_id=999001,
        username="new_tech",
        first_name=pending_user.first_name,
        last_name=pending_user.last_name,
        phone=pending_user.phone,
        user=pending_user,
    )
    regular_user = user_factory(
        username="regular",
        first_name="Regular",
        email="regular@example.com",
    )
    moderator = user_factory(
        username="ops",
        first_name="Ops",
        email="ops@example.com",
    )
    assign_roles(moderator, RoleSlug.OPS_MANAGER)
    return {
        "pending": pending,
        "pending_user": pending_user,
        "regular_user": regular_user,
        "moderator": moderator,
    }


def test_list_requires_privileged_role(authed_client_factory, moderation_context):
    regular_client = authed_client_factory(moderation_context["regular_user"])
    forbidden = regular_client.get(LIST_URL)
    assert forbidden.status_code == 403

    moderator_client = authed_client_factory(moderation_context["moderator"])
    allowed = moderator_client.get(LIST_URL)
    assert allowed.status_code == 200
    assert len(allowed.data["data"]) == 1
    assert allowed.data["data"][0]["status"] == AccessRequestStatus.PENDING


def test_approve_links_profile_and_assigns_roles(
    authed_client_factory,
    moderation_context,
    role_factory,
    monkeypatch,
):
    notifications: list[dict] = []

    def _fake_notify(cls, *, access_request, approved: bool):
        notifications.append(
            {
                "access_request_id": access_request.id,
                "approved": approved,
                "status": access_request.status,
            }
        )

    monkeypatch.setattr(
        AccountService,
        "_notify_access_request_decision",
        classmethod(_fake_notify),
    )

    client = authed_client_factory(moderation_context["moderator"])
    pending = moderation_context["pending"]
    pending_user = moderation_context["pending_user"]
    role_factory(RoleSlug.TECHNICIAN, name="Technician")

    resp = client.post(
        f"/api/v1/users/access-requests/{pending.id}/approve/",
        {"role_slugs": [RoleSlug.TECHNICIAN]},
        format="json",
    )

    assert resp.status_code == 200
    pending.refresh_from_db()
    pending_user.refresh_from_db()
    assert pending.status == AccessRequestStatus.APPROVED
    assert pending.user_id == pending_user.id
    assert pending_user.is_active is True
    assert pending.resolved_at is not None

    profile = TelegramProfile.objects.get(telegram_id=pending.telegram_id)
    assert profile.user_id == pending_user.id
    assert pending_user.roles.filter(slug=RoleSlug.TECHNICIAN).exists()
    assert notifications == [
        {
            "access_request_id": pending.id,
            "approved": True,
            "status": AccessRequestStatus.APPROVED,
        }
    ]


def test_approve_legacy_pending_without_user_still_works(
    authed_client_factory, moderation_context
):
    client = authed_client_factory(moderation_context["moderator"])
    pending = AccessRequest.objects.create(
        telegram_id=999002,
        username="legacy_user",
        first_name="Legacy",
        last_name="User",
    )

    resp = client.post(
        f"/api/v1/users/access-requests/{pending.id}/approve/",
        {},
        format="json",
    )

    assert resp.status_code == 200
    pending.refresh_from_db()
    assert pending.status == AccessRequestStatus.APPROVED
    assert pending.user_id is not None

    profile = TelegramProfile.objects.get(telegram_id=pending.telegram_id)
    assert profile.user_id == pending.user_id


def test_reject_marks_request_as_rejected(
    authed_client_factory, moderation_context, monkeypatch
):
    notifications: list[dict] = []

    def _fake_notify(cls, *, access_request, approved: bool):
        notifications.append(
            {
                "access_request_id": access_request.id,
                "approved": approved,
                "status": access_request.status,
            }
        )

    monkeypatch.setattr(
        AccountService,
        "_notify_access_request_decision",
        classmethod(_fake_notify),
    )

    client = authed_client_factory(moderation_context["moderator"])
    pending = moderation_context["pending"]

    resp = client.post(
        f"/api/v1/users/access-requests/{pending.id}/reject/", {}, format="json"
    )

    assert resp.status_code == 200
    pending.refresh_from_db()
    assert pending.status == AccessRequestStatus.REJECTED
    assert pending.resolved_at is not None
    assert notifications == [
        {
            "access_request_id": pending.id,
            "approved": False,
            "status": AccessRequestStatus.REJECTED,
        }
    ]
