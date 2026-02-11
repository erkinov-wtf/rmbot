import pytest
from django.db import IntegrityError, transaction

from core.utils.constants import TicketStatus
from ticket.models import Ticket

pytestmark = pytest.mark.django_db


def test_enforces_one_active_ticket_per_bike(user_factory, bike_factory):
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
    bike_a = bike_factory(bike_code="RM-0001")

    Ticket.objects.create(
        bike=bike_a,
        master=master,
        status=TicketStatus.NEW,
        title="Initial intake",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Ticket.objects.create(
                bike=bike_a,
                master=master,
                status=TicketStatus.ASSIGNED,
                technician=technician,
                title="Second active ticket",
            )


def test_enforces_wip_one_per_technician(user_factory, bike_factory):
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
    bike_a = bike_factory(bike_code="RM-0002")
    bike_b = bike_factory(bike_code="RM-0003")

    Ticket.objects.create(
        bike=bike_a,
        master=master,
        technician=technician,
        status=TicketStatus.IN_PROGRESS,
        title="First in-progress ticket",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Ticket.objects.create(
                bike=bike_b,
                master=master,
                technician=technician,
                status=TicketStatus.IN_PROGRESS,
                title="Second in-progress ticket",
            )
