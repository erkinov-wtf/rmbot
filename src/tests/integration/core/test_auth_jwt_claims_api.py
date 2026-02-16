import pytest
from rest_framework_simplejwt.tokens import AccessToken

from core.utils.constants import RoleSlug

pytestmark = pytest.mark.django_db

LOGIN_URL = "/api/v1/auth/login/"
REFRESH_URL = "/api/v1/auth/refresh/"


def test_login_includes_role_claims_in_access_token(
    api_client, user_factory, assign_roles
):
    user = user_factory(
        username="claims_user",
        password="password123",
        first_name="Claims",
    )
    assign_roles(user, RoleSlug.OPS_MANAGER, RoleSlug.MASTER)

    resp = api_client.post(
        LOGIN_URL,
        {"username": "claims_user", "password": "password123"},
        format="json",
    )

    assert resp.status_code == 200
    payload = resp.data["data"]
    access_claims = AccessToken(payload["access"])

    assert sorted(access_claims["role_slugs"]) == sorted(
        [RoleSlug.OPS_MANAGER, RoleSlug.MASTER]
    )
    assert sorted(access_claims["roles"]) == sorted(
        ["Ops Manager", "Master (Service Lead)"]
    )


def test_refresh_preserves_role_claims_in_access_token(
    api_client, user_factory, assign_roles
):
    user = user_factory(
        username="refresh_user",
        password="password123",
        first_name="Refresh",
    )
    assign_roles(user, RoleSlug.TECHNICIAN)

    login_resp = api_client.post(
        LOGIN_URL,
        {"username": "refresh_user", "password": "password123"},
        format="json",
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.data["data"]["refresh"]

    refresh_resp = api_client.post(
        REFRESH_URL,
        {"refresh": refresh_token},
        format="json",
    )

    assert refresh_resp.status_code == 200
    refreshed_access_claims = AccessToken(refresh_resp.data["data"]["access"])
    assert refreshed_access_claims["role_slugs"] == [RoleSlug.TECHNICIAN]
    assert refreshed_access_claims["roles"] == ["Technician"]


def test_login_superuser_gets_super_admin_role_claim(
    api_client, user_factory
):
    user_factory(
        username="super_claims_user",
        password="password123",
        first_name="Super",
        is_superuser=True,
        is_staff=True,
    )

    resp = api_client.post(
        LOGIN_URL,
        {"username": "super_claims_user", "password": "password123"},
        format="json",
    )

    assert resp.status_code == 200
    payload = resp.data["data"]
    access_claims = AccessToken(payload["access"])
    assert RoleSlug.SUPER_ADMIN in access_claims["role_slugs"]
    assert "Super Admin" in access_claims["roles"]
