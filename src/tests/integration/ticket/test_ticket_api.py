from django.test import TestCase
from rest_framework.test import APIClient

from account.models import Role, User
from bike.models import Bike
from core.utils.constants import RoleSlug, TicketStatus, TicketTransitionAction
from ticket.models import Ticket, TicketTransition


class TicketAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.create_url = "/api/v1/tickets/create/"

        self.master_user = User.objects.create_user(
            username="master_api",
            password="pass1234",
            first_name="Master",
            email="master_api@example.com",
        )
        self.regular_user = User.objects.create_user(
            username="regular_api",
            password="pass1234",
            first_name="Regular",
            email="regular_api@example.com",
        )
        self.technician = User.objects.create_user(
            username="tech_api",
            password="pass1234",
            first_name="Tech",
            email="tech_api@example.com",
        )

        master_role, _ = Role.objects.update_or_create(
            slug=RoleSlug.MASTER,
            defaults={"name": "Master (Service Lead)"},
        )
        self.master_user.roles.add(master_role)

        self.bike = Bike.objects.create(bike_code="RM-0100")

    def test_ticket_create_requires_master_role(self):
        self.client.force_authenticate(user=self.regular_user)
        resp = self.client.post(
            self.create_url,
            {
                "bike": self.bike.id,
                "technician": self.technician.id,
                "title": "Diagnostics",
                "srt_total_minutes": 40,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_master_can_create_ticket(self):
        self.client.force_authenticate(user=self.master_user)
        resp = self.client.post(
            self.create_url,
            {
                "bike": self.bike.id,
                "technician": self.technician.id,
                "title": "Diagnostics",
                "srt_total_minutes": 40,
            },
            format="json",
        )

        self.assertEqual(resp.status_code, 201)
        payload = resp.data["data"]
        self.assertEqual(payload["master"], self.master_user.id)
        self.assertEqual(payload["status"], TicketStatus.NEW)
        self.assertEqual(Ticket.objects.count(), 1)
        transition = TicketTransition.objects.get(ticket_id=payload["id"])
        self.assertEqual(transition.action, TicketTransitionAction.CREATED)
        self.assertEqual(transition.actor_id, self.master_user.id)

    def test_rejects_second_active_ticket_for_same_bike(self):
        Ticket.objects.create(
            bike=self.bike,
            master=self.master_user,
            status=TicketStatus.NEW,
            title="Existing active ticket",
        )
        self.client.force_authenticate(user=self.master_user)
        resp = self.client.post(
            self.create_url,
            {
                "bike": self.bike.id,
                "technician": self.technician.id,
                "title": "Second ticket attempt",
                "srt_total_minutes": 30,
            },
            format="json",
        )

        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.data["success"])
        self.assertIn("bike", resp.data["message"].lower())
