from datetime import timedelta

import pytest
from django.utils import timezone

from bike.models import Bike
from core.utils.constants import RoleSlug
from ticket.models import Ticket

pytestmark = pytest.mark.django_db


LIST_CREATE_URL = "/api/v1/bikes/"


def detail_url(bike_id: int) -> str:
    return f"/api/v1/bikes/{bike_id}/"


def test_list_requires_auth(api_client):
    resp = api_client.get(LIST_CREATE_URL)
    assert resp.status_code == 401


def test_create_requires_bike_manager_role(authed_client_factory, user_factory):
    regular_user = user_factory(
        username="regular_bike",
        first_name="Regular",
        email="regular_bike@example.com",
    )
    client = authed_client_factory(regular_user)

    resp = client.post(LIST_CREATE_URL, {"bike_code": "RM-0200"}, format="json")
    assert resp.status_code == 403


def test_ops_manager_can_create_bike(authed_client_factory, user_factory, assign_roles):
    manager_user = user_factory(
        username="ops_bike",
        first_name="Ops",
        email="ops_bike@example.com",
    )
    assign_roles(manager_user, RoleSlug.OPS_MANAGER)
    client = authed_client_factory(manager_user)

    resp = client.post(LIST_CREATE_URL, {"bike_code": "RM-0200"}, format="json")

    assert resp.status_code == 201
    assert resp.data["data"]["bike_code"] == "RM-0200"
    assert Bike.objects.count() == 1


def test_create_rejects_invalid_bike_code_format(
    authed_client_factory, user_factory, assign_roles
):
    manager_user = user_factory(
        username="ops_bike_regex",
        first_name="Ops",
        email="ops_bike_regex@example.com",
    )
    assign_roles(manager_user, RoleSlug.OPS_MANAGER)
    client = authed_client_factory(manager_user)

    resp = client.post(LIST_CREATE_URL, {"bike_code": "bike-0200"}, format="json")

    assert resp.status_code == 400
    assert "pattern" in resp.data["message"].lower()


def test_list_supports_query_filter_for_code_lookup(
    authed_client_factory, user_factory, bike_factory
):
    user = user_factory(
        username="bike_reader",
        first_name="Reader",
        email="bike_reader@example.com",
    )
    bike_factory(bike_code="RM-0100")
    bike_factory(bike_code="RM-0101")
    bike_factory(bike_code="RM-0200")
    client = authed_client_factory(user)

    resp = client.get(LIST_CREATE_URL, {"q": "rm-01"})

    assert resp.status_code == 200
    codes = [item["bike_code"] for item in resp.data["results"]]
    assert "RM-0100" in codes
    assert "RM-0101" in codes


def test_list_rejects_short_query(authed_client_factory, user_factory):
    user = user_factory(
        username="bike_reader_short",
        first_name="Reader",
        email="bike_reader_short@example.com",
    )
    client = authed_client_factory(user)

    resp = client.get(LIST_CREATE_URL, {"q": "R"})

    assert resp.status_code == 400
    assert "at least 2" in resp.data["message"].lower()


def test_list_supports_extended_filters(
    authed_client_factory,
    user_factory,
    bike_factory,
):
    user = user_factory(
        username="bike_reader_filters",
        first_name="Reader",
        email="bike_reader_filters@example.com",
    )
    active_bike = bike_factory(bike_code="RM-0300", status="ready", is_active=True)
    inactive_bike = bike_factory(bike_code="RM-0301", status="blocked", is_active=False)
    master = user_factory(
        username="bike_filter_master",
        first_name="Master",
        email="bike_filter_master@example.com",
    )
    Ticket.objects.create(
        bike=active_bike,
        master=master,
        status="new",
        title="Filter test ticket",
    )
    client = authed_client_factory(user)

    old_date = timezone.now() - timedelta(days=10)
    Bike.all_objects.filter(pk=inactive_bike.pk).update(created_at=old_date)

    status_filtered = client.get(
        LIST_CREATE_URL, {"status": "ready", "is_active": "true"}
    )
    assert status_filtered.status_code == 200
    status_codes = [item["bike_code"] for item in status_filtered.data["results"]]
    assert status_codes == ["RM-0300"]

    active_ticket_filtered = client.get(LIST_CREATE_URL, {"has_active_ticket": "true"})
    assert active_ticket_filtered.status_code == 200
    active_ticket_codes = [
        item["bike_code"] for item in active_ticket_filtered.data["results"]
    ]
    assert active_ticket_codes == ["RM-0300"]

    created_range_filtered = client.get(
        LIST_CREATE_URL,
        {
            "created_to": (timezone.now().date() - timedelta(days=5)).isoformat(),
        },
    )
    assert created_range_filtered.status_code == 200
    created_range_codes = [
        item["bike_code"] for item in created_range_filtered.data["results"]
    ]
    assert created_range_codes == ["RM-0301"]


def test_update_requires_bike_manager_role(
    authed_client_factory, user_factory, bike_factory
):
    regular_user = user_factory(
        username="bike_update_regular",
        first_name="Regular",
        email="bike_update_regular@example.com",
    )
    bike = bike_factory(bike_code="RM-0400")
    client = authed_client_factory(regular_user)

    resp = client.patch(detail_url(bike.id), {"status": "blocked"}, format="json")

    assert resp.status_code == 403


def test_ops_manager_can_update_bike(
    authed_client_factory, user_factory, assign_roles, bike_factory
):
    manager_user = user_factory(
        username="bike_update_ops",
        first_name="Ops",
        email="bike_update_ops@example.com",
    )
    assign_roles(manager_user, RoleSlug.OPS_MANAGER)
    bike = bike_factory(bike_code="RM-0401", status="ready", is_active=True)
    client = authed_client_factory(manager_user)

    resp = client.patch(
        detail_url(bike.id),
        {"status": "blocked", "is_active": False},
        format="json",
    )

    assert resp.status_code == 200
    assert resp.data["data"]["status"] == "blocked"
    assert resp.data["data"]["is_active"] is False

    bike.refresh_from_db()
    assert bike.status == "blocked"
    assert bike.is_active is False


def test_delete_requires_bike_manager_role(
    authed_client_factory, user_factory, bike_factory
):
    regular_user = user_factory(
        username="bike_delete_regular",
        first_name="Regular",
        email="bike_delete_regular@example.com",
    )
    bike = bike_factory(bike_code="RM-0500")
    client = authed_client_factory(regular_user)

    resp = client.delete(detail_url(bike.id))

    assert resp.status_code == 403


def test_ops_manager_can_soft_delete_bike(
    authed_client_factory, user_factory, assign_roles, bike_factory
):
    manager_user = user_factory(
        username="bike_delete_ops",
        first_name="Ops",
        email="bike_delete_ops@example.com",
    )
    assign_roles(manager_user, RoleSlug.OPS_MANAGER)
    bike = bike_factory(bike_code="RM-0501")
    client = authed_client_factory(manager_user)

    resp = client.delete(detail_url(bike.id))

    assert resp.status_code == 204
    assert Bike.objects.filter(pk=bike.pk).exists() is False
    assert Bike.all_objects.filter(pk=bike.pk, deleted_at__isnull=False).exists()
