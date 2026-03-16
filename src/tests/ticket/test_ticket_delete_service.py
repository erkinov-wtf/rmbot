from __future__ import annotations

import uuid

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from account.models import Role, User
from api.v1.ticket.views import TicketViewSet
from core.utils.constants import RoleSlug, TicketColor, TicketStatus
from inventory.models import (
    Inventory,
    InventoryItem,
    InventoryItemCategory,
    InventoryItemPart,
)
from ticket.models import Ticket, TicketPartSpec
from ticket.services_delete import TicketDeleteService


def _role(*, slug: str) -> Role:
    role, _ = Role.objects.get_or_create(
        slug=slug,
        defaults={"name": slug.replace("_", " ").title()},
    )
    return role


def _user(*, username: str, role_slug: str) -> User:
    user = User.objects.create_user(
        username=username,
        password="pass1234",
        first_name=username,
        is_active=True,
    )
    user.roles.add(_role(slug=role_slug))
    return user


def _ticket(*, suffix: str, status: str) -> Ticket:
    inventory = Inventory.objects.create(name=f"Inventory-{suffix}-{status}")
    category = InventoryItemCategory.objects.create(name=f"Category-{suffix}-{status}")
    item = InventoryItem.objects.create(
        inventory=inventory,
        category=category,
        name=f"Item-{suffix}-{status}",
        serial_number=f"RM-{suffix.upper()}-{status.upper()}",
    )
    part = InventoryItemPart.objects.create(
        category=category,
        name=f"Part-{suffix}-{status}",
    )
    master = User.objects.create_user(
        username=f"master_{suffix}_{status}",
        password="pass1234",
        first_name="Master",
        is_active=True,
    )
    ticket = Ticket.objects.create(
        inventory_item=item,
        master=master,
        status=status,
        title=f"Ticket-{suffix}-{status}",
    )
    TicketPartSpec.objects.create(
        ticket=ticket,
        inventory_item_part=part,
        color=TicketColor.GREEN,
        minutes=10,
    )
    return ticket


@pytest.mark.django_db
def test_delete_queryset_soft_deletes_only_matching_tickets():
    suffix = uuid.uuid4().hex[:6]
    ticket_new = _ticket(suffix=f"{suffix}-new", status=TicketStatus.NEW)
    ticket_done = _ticket(suffix=f"{suffix}-done", status=TicketStatus.DONE)

    summary = TicketDeleteService.delete_queryset(
        queryset=Ticket.domain.get_queryset().filter(status=TicketStatus.NEW)
    )

    assert summary == {"deleted_ticket_count": 1}

    ticket_new.refresh_from_db()
    ticket_done.refresh_from_db()

    assert ticket_new.deleted_at is not None
    assert ticket_done.deleted_at is None


@pytest.mark.django_db
def test_bulk_destroy_view_deletes_filtered_tickets():
    suffix = uuid.uuid4().hex[:6]
    ticket_new = _ticket(suffix=f"{suffix}-bulk-new", status=TicketStatus.NEW)
    ticket_done = _ticket(suffix=f"{suffix}-bulk-done", status=TicketStatus.DONE)
    user = _user(username=f"deleter_{suffix}", role_slug=RoleSlug.MASTER)

    request = APIRequestFactory().delete("/api/v1/tickets/?status=new")
    force_authenticate(request, user=user)

    response = TicketViewSet.as_view({"delete": "bulk_destroy"})(request)

    assert response.status_code == 200
    assert response.data == {
        "success": True,
        "message": "OK",
        "data": {"deleted_count": 1},
    }

    ticket_new.refresh_from_db()
    ticket_done.refresh_from_db()

    assert ticket_new.deleted_at is not None
    assert ticket_done.deleted_at is None
