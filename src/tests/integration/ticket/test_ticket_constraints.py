from django.db import IntegrityError, transaction
from django.test import TestCase

from account.models import User
from bike.models import Bike
from core.utils.constants import TicketStatus
from ticket.models import Ticket


class TicketConstraintsTests(TestCase):
    def setUp(self):
        self.master = User.objects.create_user(
            username="master_user",
            password="pass1234",
            first_name="Master",
            email="master@example.com",
        )
        self.technician = User.objects.create_user(
            username="tech_user",
            password="pass1234",
            first_name="Tech",
            email="tech@example.com",
        )
        self.bike_a = Bike.objects.create(bike_code="RM-0001")
        self.bike_b = Bike.objects.create(bike_code="RM-0002")

    def test_enforces_one_active_ticket_per_bike(self):
        Ticket.objects.create(
            bike=self.bike_a,
            master=self.master,
            status=TicketStatus.NEW,
            title="Initial intake",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Ticket.objects.create(
                    bike=self.bike_a,
                    master=self.master,
                    status=TicketStatus.ASSIGNED,
                    technician=self.technician,
                    title="Second active ticket",
                )

    def test_enforces_wip_one_per_technician(self):
        Ticket.objects.create(
            bike=self.bike_a,
            master=self.master,
            technician=self.technician,
            status=TicketStatus.IN_PROGRESS,
            title="First in-progress ticket",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Ticket.objects.create(
                    bike=self.bike_b,
                    master=self.master,
                    technician=self.technician,
                    status=TicketStatus.IN_PROGRESS,
                    title="Second in-progress ticket",
                )
