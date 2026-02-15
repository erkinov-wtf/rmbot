import pytest
from django.db import IntegrityError, transaction

from core.utils.constants import TicketStatus
from ticket.models import Ticket

pytestmark = pytest.mark.django_db


def test_enforces_one_active_ticket_per_inventory_item(
    user_factory, inventory_item_factory
):
    master = user_factory(
        username="master_user",
        first_name="Master",
        email="master@example.com",
    )
    technician = user_factory(
        username="tech_user",
        first_name="Tech",
        email="tech@example.com",
    )
    inventory_item_a = inventory_item_factory(serial_number="RM-0001")

    Ticket.objects.create(
        inventory_item=inventory_item_a,
        master=master,
        status=TicketStatus.UNDER_REVIEW,
        title="Initial intake",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Ticket.objects.create(
                inventory_item=inventory_item_a,
                master=master,
                status=TicketStatus.ASSIGNED,
                technician=technician,
                title="Second active ticket",
            )


def test_enforces_wip_one_per_technician(user_factory, inventory_item_factory):
    master = user_factory(
        username="master_user2",
        first_name="Master",
        email="master2@example.com",
    )
    technician = user_factory(
        username="tech_user2",
        first_name="Tech",
        email="tech2@example.com",
    )
    inventory_item_a = inventory_item_factory(serial_number="RM-0002")
    inventory_item_b = inventory_item_factory(serial_number="RM-0003")

    Ticket.objects.create(
        inventory_item=inventory_item_a,
        master=master,
        technician=technician,
        status=TicketStatus.IN_PROGRESS,
        title="First in-progress ticket",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Ticket.objects.create(
                inventory_item=inventory_item_b,
                master=master,
                technician=technician,
                status=TicketStatus.IN_PROGRESS,
                title="Second in-progress ticket",
            )
