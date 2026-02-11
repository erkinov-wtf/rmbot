import pytest

from account.models import AccessRequest, TelegramProfile, User
from core.utils.constants import AccessRequestStatus, RoleSlug

pytestmark = pytest.mark.django_db


LIST_URL = "/api/v1/users/access-requests/"


@pytest.fixture
def moderation_context(user_factory, assign_roles):
    pending = AccessRequest.objects.create(
        telegram_id=999001,
        username="new_tech",
        first_name="New",
        last_name="Tech",
    )
    target_user = user_factory(
        username="worker",
        first_name="Worker",
        email="worker@example.com",
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
        "target_user": target_user,
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
):
    client = authed_client_factory(moderation_context["moderator"])
    pending = moderation_context["pending"]
    target_user = moderation_context["target_user"]
    role_factory(RoleSlug.TECHNICIAN, name="Technician")

    resp = client.post(
        f"/api/v1/users/access-requests/{pending.id}/approve/",
        {"user_id": target_user.id, "role_slugs": [RoleSlug.TECHNICIAN]},
        format="json",
    )

    assert resp.status_code == 200
    pending.refresh_from_db()
    assert pending.status == AccessRequestStatus.APPROVED
    assert pending.user_id == target_user.id
    assert pending.resolved_at is not None

    profile = TelegramProfile.objects.get(telegram_id=pending.telegram_id)
    assert profile.user_id == target_user.id
    assert target_user.roles.filter(slug=RoleSlug.TECHNICIAN).exists()


def test_approve_can_create_user_and_link(
    authed_client_factory, moderation_context, role_factory
):
    client = authed_client_factory(moderation_context["moderator"])
    pending = moderation_context["pending"]
    role_factory(RoleSlug.TECHNICIAN, name="Technician")

    resp = client.post(
        f"/api/v1/users/access-requests/{pending.id}/approve/",
        {
            "user": {
                "username": "created_worker",
                "first_name": "Created",
                "email": "created_worker@example.com",
                "phone": "+998990001122",
            },
            "role_slugs": [RoleSlug.TECHNICIAN],
        },
        format="json",
    )

    assert resp.status_code == 200
    created_user = User.objects.get(username="created_worker")
    pending.refresh_from_db()
    assert pending.status == AccessRequestStatus.APPROVED
    assert pending.user_id == created_user.id

    profile = TelegramProfile.objects.get(telegram_id=pending.telegram_id)
    assert profile.user_id == created_user.id
    assert created_user.roles.filter(slug=RoleSlug.TECHNICIAN).exists()


def test_approve_requires_user_reference_or_payload(
    authed_client_factory, moderation_context, role_factory
):
    client = authed_client_factory(moderation_context["moderator"])
    pending = moderation_context["pending"]
    role_factory(RoleSlug.TECHNICIAN, name="Technician")

    resp = client.post(
        f"/api/v1/users/access-requests/{pending.id}/approve/",
        {"role_slugs": [RoleSlug.TECHNICIAN]},
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["success"] is False
    assert "exactly one" in resp.data["message"].lower()


def test_reject_marks_request_as_rejected(authed_client_factory, moderation_context):
    client = authed_client_factory(moderation_context["moderator"])
    pending = moderation_context["pending"]

    resp = client.post(
        f"/api/v1/users/access-requests/{pending.id}/reject/", {}, format="json"
    )

    assert resp.status_code == 200
    pending.refresh_from_db()
    assert pending.status == AccessRequestStatus.REJECTED
    assert pending.resolved_at is not None
