from __future__ import annotations

import uuid

import pytest

from api.v1.ticket.serializers import TicketSerializer
from account.models import User
from core.utils.constants import TicketStatus
from inventory.models import Inventory, InventoryItem, InventoryItemCategory, InventoryItemPart


def _master_user(*, username: str) -> User:
    return User.objects.create_user(
        username=username,
        password="pass1234",
        first_name=username,
        is_active=True,
    )


@pytest.mark.django_db
def test_ticket_serializer_allows_unknown_serial_without_confirm_flag():
    suffix = uuid.uuid4().hex[:6]
    category = InventoryItemCategory.objects.create(name=f"cat-{suffix}")
    part = InventoryItemPart.objects.create(category=category, name=f"part-{suffix}")
    master = _master_user(username=f"master_{suffix}")

    serializer = TicketSerializer(
        data={
            "serial_number": "TEST",
            "title": "Open intake",
            "total_minutes": 80,
            "flag_color": "red",
            "part_specs": [{"part_id": part.id}],
        }
    )
    assert serializer.is_valid(), serializer.errors

    ticket = serializer.save(master=master)
    ticket.refresh_from_db()

    assert ticket.status == TicketStatus.UNDER_REVIEW
    assert ticket.inventory_item.serial_number == "TEST"
    assert ticket.inventory_item.category_id == category.id


@pytest.mark.django_db
def test_ticket_serializer_restores_archived_inventory_item_for_unknown_serial():
    suffix = uuid.uuid4().hex[:6]
    inventory = Inventory.objects.create(name=f"inv-{suffix}")
    category = InventoryItemCategory.objects.create(name=f"cat-{suffix}")
    part = InventoryItemPart.objects.create(category=category, name=f"part-{suffix}")
    archived_item = InventoryItem.objects.create(
        inventory=inventory,
        category=category,
        name=f"item-{suffix}",
        serial_number=f"TST-{suffix}",
    )
    archived_item.delete()
    archived_item.refresh_from_db()
    assert archived_item.deleted_at is not None

    master = _master_user(username=f"master_restore_{suffix}")
    serializer = TicketSerializer(
        data={
            "serial_number": archived_item.serial_number,
            "title": "Restore archive flow",
            "total_minutes": 30,
            "part_specs": [{"part_id": part.id}],
        }
    )
    assert serializer.is_valid(), serializer.errors

    ticket = serializer.save(master=master)
    ticket.refresh_from_db()
    archived_item.refresh_from_db()

    assert ticket.inventory_item_id == archived_item.id
    assert archived_item.deleted_at is None
    assert archived_item.is_active is True
