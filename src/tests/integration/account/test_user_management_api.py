import pytest

from core.utils.constants import RoleSlug

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/users/management/"


def detail_url(user_id: int) -> str:
    return f"/api/v1/users/management/{user_id}/"


def test_user_management_list_requires_manager_role(
    authed_client_factory, user_factory, assign_roles
):
    regular_user = user_factory(username="um_regular", first_name="Regular")
    manager_user = user_factory(username="um_manager", first_name="Manager")
    assign_roles(manager_user, RoleSlug.OPS_MANAGER)

    forbidden = authed_client_factory(regular_user).get(LIST_URL)
    assert forbidden.status_code == 403

    allowed = authed_client_factory(manager_user).get(LIST_URL)
    assert allowed.status_code == 200
    assert isinstance(allowed.data["results"], list)


def test_user_management_list_supports_filters(
    authed_client_factory,
    user_factory,
    assign_roles,
):
    manager_user = user_factory(username="um_filter_manager", first_name="Manager")
    assign_roles(manager_user, RoleSlug.OPS_MANAGER)

    tech_user = user_factory(
        username="um_filter_tech",
        first_name="Tech",
        is_active=True,
    )
    assign_roles(tech_user, RoleSlug.TECHNICIAN)

    inactive_user = user_factory(
        username="um_filter_inactive",
        first_name="Inactive",
        is_active=False,
    )
    assign_roles(inactive_user, RoleSlug.MASTER)

    client = authed_client_factory(manager_user)

    tech_filtered = client.get(
        LIST_URL,
        {"role_slug": RoleSlug.TECHNICIAN, "is_active": "true"},
    )
    assert tech_filtered.status_code == 200
    tech_ids = [row["id"] for row in tech_filtered.data["results"]]
    assert tech_user.id in tech_ids
    assert inactive_user.id not in tech_ids

    inactive_filtered = client.get(LIST_URL, {"is_active": "false"})
    assert inactive_filtered.status_code == 200
    inactive_ids = [row["id"] for row in inactive_filtered.data["results"]]
    assert inactive_user.id in inactive_ids


def test_user_management_patch_updates_roles_level_and_active(
    authed_client_factory,
    user_factory,
    assign_roles,
    role_factory,
):
    manager_user = user_factory(username="um_patch_manager", first_name="Manager")
    assign_roles(manager_user, RoleSlug.OPS_MANAGER)

    target_user = user_factory(
        username="um_patch_target",
        first_name="Target",
        is_active=False,
        level=1,
    )

    role_factory(RoleSlug.MASTER, name="Master")
    role_factory(RoleSlug.QC_INSPECTOR, name="QC Inspector")

    client = authed_client_factory(manager_user)
    resp = client.patch(
        detail_url(target_user.id),
        {
            "is_active": True,
            "level": 3,
            "role_slugs": [RoleSlug.MASTER, RoleSlug.QC_INSPECTOR],
        },
        format="json",
    )

    assert resp.status_code == 200
    target_user.refresh_from_db()
    assert target_user.is_active is True
    assert target_user.level == 3
    assert set(target_user.roles.values_list("slug", flat=True)) == {
        RoleSlug.MASTER,
        RoleSlug.QC_INSPECTOR,
    }


def test_user_management_patch_rejects_self_deactivation(
    authed_client_factory, user_factory, assign_roles
):
    manager_user = user_factory(username="um_self_manager", first_name="Manager")
    assign_roles(manager_user, RoleSlug.OPS_MANAGER)

    client = authed_client_factory(manager_user)
    resp = client.patch(
        detail_url(manager_user.id),
        {"is_active": False},
        format="json",
    )

    assert resp.status_code == 400
    assert "deactivate" in str(resp.data).lower()


def test_ops_manager_cannot_patch_superuser(
    authed_client_factory, user_factory, assign_roles
):
    manager_user = user_factory(username="um_ops", first_name="Ops")
    assign_roles(manager_user, RoleSlug.OPS_MANAGER)

    superuser = user_factory(
        username="um_super",
        first_name="Super",
        is_superuser=True,
        is_staff=True,
    )

    client = authed_client_factory(manager_user)
    resp = client.patch(
        detail_url(superuser.id),
        {"is_active": False},
        format="json",
    )

    assert resp.status_code == 403
