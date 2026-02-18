import pytest
from rest_framework_simplejwt.tokens import AccessToken

from core.utils.constants import RoleSlug

pytestmark = pytest.mark.django_db

PHONE_LOGIN_URL = "/api/v1/auth/miniapp/phone-login/"


def test_phone_login_returns_tokens_roles_and_permissions(
    api_client, user_factory, assign_roles
):
    user = user_factory(
        username="miniapp_user",
        password="password123",
        first_name="Mini",
        phone="+998901234567",
    )
    assign_roles(user, RoleSlug.MASTER, RoleSlug.TECHNICIAN)

    response = api_client.post(
        PHONE_LOGIN_URL,
        {"phone": "998901234567"},
        format="json",
    )

    assert response.status_code == 200
    payload = response.data["data"]
    claims = AccessToken(payload["access"])

    assert sorted(claims["role_slugs"]) == sorted(
        [RoleSlug.MASTER, RoleSlug.TECHNICIAN]
    )
    assert payload["user"]["id"] == user.id
    assert sorted(payload["role_slugs"]) == sorted(
        [RoleSlug.MASTER, RoleSlug.TECHNICIAN]
    )
    assert payload["permissions"]["can_create"] is True
    assert payload["permissions"]["can_review"] is True
    assert payload["permissions"]["can_assign"] is True
    assert payload["permissions"]["can_manual_metrics"] is True
    assert payload["permissions"]["can_work"] is True
    assert payload["permissions"]["can_qc"] is False
    assert payload["permissions"]["can_open_review_panel"] is True
    assert payload["permissions"]["can_approve_and_assign"] is True


def test_phone_login_returns_not_found_for_unknown_phone(api_client):
    response = api_client.post(
        PHONE_LOGIN_URL,
        {"phone": "+998900000000"},
        format="json",
    )

    assert response.status_code == 404
    assert response.data["success"] is False
    assert "not found" in response.data["error"]["detail"].lower()


def test_phone_login_rejects_invalid_phone_format(api_client):
    response = api_client.post(
        PHONE_LOGIN_URL,
        {"phone": "bad-phone"},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["success"] is False
    assert "invalid" in str(response.data["error"]["phone"][0]).lower()
