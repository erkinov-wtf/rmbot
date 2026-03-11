from __future__ import annotations

import uuid

import pytest
from django.utils import timezone

from account.models import User
from core.utils.constants import (
    TicketColor,
    TicketStatus,
    WorkSessionStatus,
    XPTransactionEntryType,
)
from gamification.models import XPTransaction
from inventory.models import (
    Inventory,
    InventoryItem,
    InventoryItemCategory,
    InventoryItemPart,
)
from inventory.services import InventoryItemDeleteService
from ticket.models import Ticket, TicketPartSpec, WorkSession


def _build_item() -> tuple[InventoryItem, User, User]:
    suffix = uuid.uuid4().hex[:8]
    inventory = Inventory.objects.create(name=f"Inventory-{suffix}")
    category = InventoryItemCategory.objects.create(name=f"Category-{suffix}")
    item = InventoryItem.objects.create(
        inventory=inventory,
        category=category,
        name=f"Item-{suffix}",
        serial_number=f"RM-DEL-{suffix.upper()}",
    )
    master = User.objects.create_user(
        username=f"master_{suffix}",
        password="pass1234",
        first_name="Master",
        is_active=True,
    )
    technician = User.objects.create_user(
        username=f"tech_{suffix}",
        password="pass1234",
        first_name="Tech",
        is_active=True,
    )
    return item, master, technician


@pytest.mark.django_db
def test_delete_item_with_related_tickets_soft_deletes_ticket_tree_keeps_users_and_xp():
    item, master, technician = _build_item()
    part = InventoryItemPart.objects.create(
        category=item.category,
        name=f"Part-{uuid.uuid4().hex[:6]}",
    )
    ticket = Ticket.objects.create(
        inventory_item=item,
        master=master,
        technician=technician,
        status=TicketStatus.IN_PROGRESS,
        started_at=timezone.now(),
    )
    part_spec = TicketPartSpec.objects.create(
        ticket=ticket,
        inventory_item_part=part,
        color=TicketColor.GREEN,
        minutes=15,
    )
    work_session = WorkSession.objects.create(
        ticket=ticket,
        technician=technician,
        status=WorkSessionStatus.RUNNING,
        started_at=timezone.now(),
        last_started_at=timezone.now(),
        active_seconds=120,
    )
    xp_tx = XPTransaction.objects.create(
        user=technician,
        amount=12,
        entry_type=XPTransactionEntryType.MANUAL_ADJUSTMENT,
        reference=f"delete-item-test-{uuid.uuid4().hex}",
        description="Delete flow guard",
        payload={"ticket_id": ticket.id},
    )

    summary = InventoryItemDeleteService.delete_item_with_related_tickets(item=item)

    assert summary["deleted_ticket_count"] == 1

    item.refresh_from_db()
    ticket.refresh_from_db()
    part_spec.refresh_from_db()
    work_session.refresh_from_db()

    assert item.deleted_at is not None
    assert ticket.deleted_at is not None
    assert part_spec.deleted_at is not None
    assert work_session.deleted_at is not None

    assert not InventoryItem.domain.get_queryset().filter(pk=item.id).exists()
    assert not Ticket.domain.get_queryset().filter(pk=ticket.id).exists()

    assert User.objects.filter(pk=master.id).exists()
    assert User.objects.filter(pk=technician.id).exists()
    assert XPTransaction.objects.filter(pk=xp_tx.id).exists()


@pytest.mark.django_db
def test_delete_item_without_tickets_deletes_item():
    item, _master, _technician = _build_item()

    summary = InventoryItemDeleteService.delete_item_with_related_tickets(item=item)

    assert summary["deleted_ticket_count"] == 0
    item.refresh_from_db()
    assert item.deleted_at is not None
