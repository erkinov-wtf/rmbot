from __future__ import annotations

import uuid

import pytest

from api.v1.ticket.serializers import TicketSerializer, TicketUpdateSerializer
from account.models import User
from core.utils.constants import TicketStatus
from inventory.models import Inventory, InventoryItem, InventoryItemCategory, InventoryItemPart
from ticket.models import Ticket, TicketPartCompletion, TicketPartSpec, WorkSession


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


@pytest.mark.django_db
def test_ticket_update_serializer_replaces_active_part_selection_before_work_starts():
    suffix = uuid.uuid4().hex[:6]
    inventory = Inventory.objects.create(name=f"inv-update-{suffix}")
    category = InventoryItemCategory.objects.create(name=f"cat-update-{suffix}")
    part_old = InventoryItemPart.objects.create(category=category, name=f"old-{suffix}")
    part_new = InventoryItemPart.objects.create(category=category, name=f"new-{suffix}")
    master = _master_user(username=f"master_update_{suffix}")
    item = InventoryItem.objects.create(
        inventory=inventory,
        category=category,
        name=f"item-{suffix}",
        serial_number=f"UPD-{suffix}",
    )
    ticket = Ticket.objects.create(
        inventory_item=item,
        master=master,
        status=TicketStatus.NEW,
        title="Original title",
        total_duration=20,
        flag_minutes=20,
        xp_amount=1,
    )
    old_spec = TicketPartSpec.objects.create(
        ticket=ticket,
        inventory_item_part=part_old,
        color="green",
        minutes=10,
    )

    serializer = TicketUpdateSerializer(
        instance=ticket,
        data={
            "title": "Updated title",
            "flag_color": "red",
            "total_minutes": 45,
            "part_specs": [{"part_id": part_new.id}],
        },
    )

    assert serializer.is_valid(), serializer.errors
    updated_ticket = serializer.save()
    updated_ticket.refresh_from_db()
    old_spec.refresh_from_db()

    assert updated_ticket.title == "Updated title"
    assert updated_ticket.total_duration == 45
    assert updated_ticket.flag_minutes == 45
    assert updated_ticket.flag_color == "red"
    assert updated_ticket.is_manual is True
    assert old_spec.deleted_at is not None
    active_part_ids = set(
        updated_ticket.part_specs.filter(deleted_at__isnull=True).values_list(
            "inventory_item_part_id", flat=True
        )
    )
    assert active_part_ids == {part_new.id}


@pytest.mark.django_db
def test_ticket_update_serializer_allows_open_ticket_with_work_history():
    suffix = uuid.uuid4().hex[:6]
    inventory = Inventory.objects.create(name=f"inv-history-{suffix}")
    category = InventoryItemCategory.objects.create(name=f"cat-history-{suffix}")
    part_old = InventoryItemPart.objects.create(category=category, name=f"part-old-{suffix}")
    part_new = InventoryItemPart.objects.create(category=category, name=f"part-new-{suffix}")
    master = _master_user(username=f"master_history_{suffix}")
    technician = _master_user(username=f"tech_history_{suffix}")
    item = InventoryItem.objects.create(
        inventory=inventory,
        category=category,
        name=f"item-history-{suffix}",
        serial_number=f"HIST-{suffix}",
    )
    ticket = Ticket.objects.create(
        inventory_item=item,
        master=master,
        technician=technician,
        status=TicketStatus.IN_PROGRESS,
        title="Open ticket",
        total_duration=30,
        flag_minutes=30,
        xp_amount=2,
    )
    old_spec = TicketPartSpec.objects.create(
        ticket=ticket,
        inventory_item_part=part_old,
        color="green",
        minutes=10,
    )
    WorkSession.objects.create(
        ticket=ticket,
        technician=technician,
        status="stopped",
        started_at=ticket.created_at,
        active_seconds=120,
    )
    TicketPartCompletion.objects.create(
        ticket=ticket,
        ticket_part_spec=old_spec,
        technician=technician,
        completed_at=ticket.created_at,
    )

    serializer = TicketUpdateSerializer(
        instance=ticket,
        data={
            "title": "Still editable",
            "part_specs": [{"part_id": part_new.id}],
            "total_minutes": 45,
        },
    )

    assert serializer.is_valid(), serializer.errors
    updated_ticket = serializer.save()
    updated_ticket.refresh_from_db()
    old_spec.refresh_from_db()

    assert updated_ticket.title == "Still editable"
    assert updated_ticket.total_duration == 45
    assert old_spec.deleted_at is not None
    active_part_ids = set(
        updated_ticket.part_specs.filter(deleted_at__isnull=True).values_list(
            "inventory_item_part_id", flat=True
        )
    )
    assert active_part_ids == {part_new.id}


@pytest.mark.django_db
def test_ticket_update_serializer_rejects_closed_ticket():
    suffix = uuid.uuid4().hex[:6]
    inventory = Inventory.objects.create(name=f"inv-closed-{suffix}")
    category = InventoryItemCategory.objects.create(name=f"cat-closed-{suffix}")
    part = InventoryItemPart.objects.create(category=category, name=f"part-closed-{suffix}")
    master = _master_user(username=f"master_closed_{suffix}")
    item = InventoryItem.objects.create(
        inventory=inventory,
        category=category,
        name=f"item-closed-{suffix}",
        serial_number=f"CLOSED-{suffix}",
    )
    ticket = Ticket.objects.create(
        inventory_item=item,
        master=master,
        status=TicketStatus.DONE,
        title="Closed ticket",
        total_duration=30,
        flag_minutes=30,
        xp_amount=2,
    )
    TicketPartSpec.objects.create(
        ticket=ticket,
        inventory_item_part=part,
        color="green",
        minutes=10,
    )

    serializer = TicketUpdateSerializer(
        instance=ticket,
        data={"title": "Should fail"},
        partial=True,
    )

    assert not serializer.is_valid()
    assert serializer.errors == {"status": ["Closed tickets cannot be edited."]}
