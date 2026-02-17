from datetime import timedelta

import pytest
from django.utils import timezone

from core.utils.constants import RoleSlug
from inventory.models import Inventory, InventoryItem, InventoryItemCategory
from ticket.models import Ticket

pytestmark = pytest.mark.django_db


LIST_CREATE_URL = "/api/v1/inventory/items/"
CATEGORY_ALL_URL = "/api/v1/inventory/categories/all/"


def detail_url(inventory_item_id: int) -> str:
    return f"/api/v1/inventory/items/{inventory_item_id}/"


def test_category_all_requires_auth(api_client):
    resp = api_client.get(CATEGORY_ALL_URL)
    assert resp.status_code == 401


def test_category_all_returns_full_category_list(
    authed_client_factory,
    user_factory,
):
    user = user_factory(
        username="inventory_category_reader",
        first_name="Category Reader",
    )
    InventoryItemCategory.objects.create(name="Alpha")
    InventoryItemCategory.objects.create(name="Beta")

    client = authed_client_factory(user)
    resp = client.get(CATEGORY_ALL_URL)

    assert resp.status_code == 200
    names = [entry["name"] for entry in resp.data["data"]]
    assert names[:2] == ["Alpha", "Beta"]


def test_list_requires_auth(api_client):
    resp = api_client.get(LIST_CREATE_URL)
    assert resp.status_code == 401


def test_create_requires_inventory_item_manager_role(
    authed_client_factory, user_factory
):
    regular_user = user_factory(
        username="regular_inventory_item",
        first_name="Regular",
    )
    client = authed_client_factory(regular_user)

    resp = client.post(LIST_CREATE_URL, {"serial_number": "RM-0200"}, format="json")
    assert resp.status_code == 403


def test_superuser_can_create_inventory_item_without_assigned_roles(
    authed_client_factory, user_factory
):
    superuser = user_factory(
        username="super_inventory_item",
        first_name="Super",
        is_superuser=True,
        is_staff=True,
    )
    client = authed_client_factory(superuser)
    category = InventoryItemCategory.objects.create(name="Super Category")

    resp = client.post(
        LIST_CREATE_URL,
        {"serial_number": "RM-0202", "category": category.id},
        format="json",
    )

    assert resp.status_code == 201
    assert resp.data["data"]["serial_number"] == "RM-0202"


def test_ops_manager_can_create_inventory_item(
    authed_client_factory, user_factory, assign_roles
):
    manager_user = user_factory(
        username="ops_inventory_item",
        first_name="Ops",
    )
    assign_roles(manager_user, RoleSlug.OPS_MANAGER)
    client = authed_client_factory(manager_user)
    category = InventoryItemCategory.objects.create(name="Ops Category")

    resp = client.post(
        LIST_CREATE_URL,
        {"serial_number": "RM-0200", "category": category.id},
        format="json",
    )

    assert resp.status_code == 201
    assert resp.data["data"]["serial_number"] == "RM-0200"
    assert InventoryItem.objects.count() == 1


def test_create_accepts_non_pattern_serial_number(
    authed_client_factory, user_factory, assign_roles
):
    manager_user = user_factory(
        username="ops_inventory_item_regex",
        first_name="Ops",
    )
    assign_roles(manager_user, RoleSlug.OPS_MANAGER)
    client = authed_client_factory(manager_user)
    category = InventoryItemCategory.objects.create(name="Regex Category")

    resp = client.post(
        LIST_CREATE_URL,
        {"serial_number": "inventory_item-0200", "category": category.id},
        format="json",
    )

    assert resp.status_code == 201
    assert resp.data["data"]["serial_number"] == "INVENTORY_ITEM-0200"


def test_create_item_restores_soft_deleted_default_inventory(
    authed_client_factory, user_factory, assign_roles
):
    manager_user = user_factory(
        username="ops_inventory_item_default_inventory_restore",
        first_name="Ops",
    )
    assign_roles(manager_user, RoleSlug.OPS_MANAGER)
    default_inventory = Inventory.objects.create(name="Default Inventory")
    default_inventory.delete()
    category = InventoryItemCategory.objects.create(name="Restore Inventory Category")
    client = authed_client_factory(manager_user)

    resp = client.post(
        LIST_CREATE_URL,
        {"serial_number": "RM-0203", "category": category.id},
        format="json",
    )

    assert resp.status_code == 201
    created_item = InventoryItem.objects.get(pk=resp.data["data"]["id"])
    assert created_item.inventory_id == default_inventory.id
    assert Inventory.objects.filter(pk=default_inventory.pk).exists()
    assert Inventory.all_objects.filter(name="Default Inventory").count() == 1


def test_create_requires_category_and_does_not_create_uncategorized(
    authed_client_factory, user_factory, assign_roles
):
    manager_user = user_factory(
        username="ops_inventory_item_category_required",
        first_name="Ops",
    )
    assign_roles(manager_user, RoleSlug.OPS_MANAGER)
    InventoryItemCategory.all_objects.filter(name="Uncategorized").delete()
    client = authed_client_factory(manager_user)

    resp = client.post(LIST_CREATE_URL, {"serial_number": "RM-0204"}, format="json")

    assert resp.status_code == 400
    assert "category" in resp.data["message"].lower()
    assert InventoryItemCategory.all_objects.filter(name="Uncategorized").exists() is False


def test_list_supports_query_filter_for_serial_number_lookup(
    authed_client_factory, user_factory, inventory_item_factory
):
    user = user_factory(
        username="inventory_item_reader",
        first_name="Reader",
    )
    inventory_item_factory(serial_number="RM-0100")
    inventory_item_factory(serial_number="RM-0101")
    inventory_item_factory(serial_number="RM-0200")
    client = authed_client_factory(user)

    resp = client.get(LIST_CREATE_URL, {"q": "rm-01"})

    assert resp.status_code == 200
    codes = [item["serial_number"] for item in resp.data["results"]]
    assert "RM-0100" in codes
    assert "RM-0101" in codes


def test_list_rejects_short_query(authed_client_factory, user_factory):
    user = user_factory(
        username="inventory_item_reader_short",
        first_name="Reader",
    )
    client = authed_client_factory(user)

    resp = client.get(LIST_CREATE_URL, {"q": "R"})

    assert resp.status_code == 400
    assert "at least 2" in resp.data["message"].lower()


def test_list_supports_extended_filters(
    authed_client_factory,
    user_factory,
    inventory_item_factory,
):
    user = user_factory(
        username="inventory_item_reader_filters",
        first_name="Reader",
    )
    active_inventory_item = inventory_item_factory(
        serial_number="RM-0300", status="ready", is_active=True
    )
    inactive_inventory_item = inventory_item_factory(
        serial_number="RM-0301", status="blocked", is_active=False
    )
    master = user_factory(
        username="inventory_item_filter_master",
        first_name="Master",
    )
    Ticket.objects.create(
        inventory_item=active_inventory_item,
        master=master,
        status="new",
        title="Filter test ticket",
    )
    client = authed_client_factory(user)

    old_date = timezone.now() - timedelta(days=10)
    InventoryItem.all_objects.filter(pk=inactive_inventory_item.pk).update(
        created_at=old_date
    )

    status_filtered = client.get(
        LIST_CREATE_URL, {"status": "ready", "is_active": "true"}
    )
    assert status_filtered.status_code == 200
    status_codes = [item["serial_number"] for item in status_filtered.data["results"]]
    assert status_codes == ["RM-0300"]

    active_ticket_filtered = client.get(LIST_CREATE_URL, {"has_active_ticket": "true"})
    assert active_ticket_filtered.status_code == 200
    active_ticket_codes = [
        item["serial_number"] for item in active_ticket_filtered.data["results"]
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
        item["serial_number"] for item in created_range_filtered.data["results"]
    ]
    assert created_range_codes == ["RM-0301"]


def test_update_requires_inventory_item_manager_role(
    authed_client_factory, user_factory, inventory_item_factory
):
    regular_user = user_factory(
        username="inventory_item_update_regular",
        first_name="Regular",
    )
    inventory_item = inventory_item_factory(serial_number="RM-0400")
    client = authed_client_factory(regular_user)

    resp = client.patch(
        detail_url(inventory_item.id), {"status": "blocked"}, format="json"
    )

    assert resp.status_code == 403


def test_ops_manager_can_update_inventory_item(
    authed_client_factory, user_factory, assign_roles, inventory_item_factory
):
    manager_user = user_factory(
        username="inventory_item_update_ops",
        first_name="Ops",
    )
    assign_roles(manager_user, RoleSlug.OPS_MANAGER)
    inventory_item = inventory_item_factory(
        serial_number="RM-0401", status="ready", is_active=True
    )
    client = authed_client_factory(manager_user)

    resp = client.patch(
        detail_url(inventory_item.id),
        {"status": "blocked", "is_active": False},
        format="json",
    )

    assert resp.status_code == 200
    assert resp.data["data"]["status"] == "blocked"
    assert resp.data["data"]["is_active"] is False

    inventory_item.refresh_from_db()
    assert inventory_item.status == "blocked"
    assert inventory_item.is_active is False


def test_delete_requires_inventory_item_manager_role(
    authed_client_factory, user_factory, inventory_item_factory
):
    regular_user = user_factory(
        username="inventory_item_delete_regular",
        first_name="Regular",
    )
    inventory_item = inventory_item_factory(serial_number="RM-0500")
    client = authed_client_factory(regular_user)

    resp = client.delete(detail_url(inventory_item.id))

    assert resp.status_code == 403


def test_ops_manager_can_soft_delete_inventory_item(
    authed_client_factory, user_factory, assign_roles, inventory_item_factory
):
    manager_user = user_factory(
        username="inventory_item_delete_ops",
        first_name="Ops",
    )
    assign_roles(manager_user, RoleSlug.OPS_MANAGER)
    inventory_item = inventory_item_factory(serial_number="RM-0501")
    client = authed_client_factory(manager_user)

    resp = client.delete(detail_url(inventory_item.id))

    assert resp.status_code == 204
    assert resp.content == b""
    assert InventoryItem.objects.filter(pk=inventory_item.pk).exists() is False
    assert InventoryItem.all_objects.filter(
        pk=inventory_item.pk, deleted_at__isnull=False
    ).exists()
