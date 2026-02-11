from django.test import TestCase
from rest_framework.test import APIClient

from account.models import Role, User
from bike.models import Bike
from core.utils.constants import RoleSlug, TicketStatus, WorkSessionStatus
from ticket.models import Ticket, WorkSession


class TicketWorkSessionAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.master = User.objects.create_user(
            username="ws_master",
            password="pass1234",
            first_name="Master",
            email="ws_master@example.com",
        )
        self.tech = User.objects.create_user(
            username="ws_tech",
            password="pass1234",
            first_name="Tech",
            email="ws_tech@example.com",
        )
        self.other_tech = User.objects.create_user(
            username="ws_other_tech",
            password="pass1234",
            first_name="Other",
            email="ws_other_tech@example.com",
        )

        master_role, _ = Role.objects.update_or_create(
            slug=RoleSlug.MASTER,
            defaults={"name": "Master (Service Lead)"},
        )
        tech_role, _ = Role.objects.update_or_create(
            slug=RoleSlug.TECHNICIAN,
            defaults={"name": "Technician"},
        )
        self.master.roles.add(master_role)
        self.tech.roles.add(tech_role)
        self.other_tech.roles.add(tech_role)

        self.bike = Bike.objects.create(bike_code="RM-WS-0001")
        self.ticket = Ticket.objects.create(
            bike=self.bike,
            master=self.master,
            technician=self.tech,
            status=TicketStatus.IN_PROGRESS,
            title="Session ticket",
        )

    def test_technician_session_lifecycle(self):
        self.client.force_authenticate(user=self.tech)

        start = self.client.post(f"/api/v1/tickets/{self.ticket.id}/work-session/start/", {}, format="json")
        self.assertEqual(start.status_code, 200)
        self.assertEqual(start.data["data"]["status"], WorkSessionStatus.RUNNING)

        pause = self.client.post(f"/api/v1/tickets/{self.ticket.id}/work-session/pause/", {}, format="json")
        self.assertEqual(pause.status_code, 200)
        self.assertEqual(pause.data["data"]["status"], WorkSessionStatus.PAUSED)

        resume = self.client.post(f"/api/v1/tickets/{self.ticket.id}/work-session/resume/", {}, format="json")
        self.assertEqual(resume.status_code, 200)
        self.assertEqual(resume.data["data"]["status"], WorkSessionStatus.RUNNING)

        stop = self.client.post(f"/api/v1/tickets/{self.ticket.id}/work-session/stop/", {}, format="json")
        self.assertEqual(stop.status_code, 200)
        self.assertEqual(stop.data["data"]["status"], WorkSessionStatus.STOPPED)

        session = WorkSession.objects.get(ticket=self.ticket, technician=self.tech)
        self.assertEqual(session.status, WorkSessionStatus.STOPPED)
        self.assertIsNotNone(session.ended_at)

    def test_other_technician_cannot_control_session(self):
        WorkSession.objects.create(
            ticket=self.ticket,
            technician=self.tech,
            status=WorkSessionStatus.RUNNING,
            started_at=self.ticket.created_at,
            last_started_at=self.ticket.created_at,
        )
        self.client.force_authenticate(user=self.other_tech)
        resp = self.client.post(f"/api/v1/tickets/{self.ticket.id}/work-session/pause/", {}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("no active work session", resp.data["error"]["detail"].lower())

    def test_cannot_start_session_when_ticket_not_in_progress(self):
        self.ticket.status = TicketStatus.ASSIGNED
        self.ticket.save(update_fields=["status"])
        self.client.force_authenticate(user=self.tech)
        resp = self.client.post(f"/api/v1/tickets/{self.ticket.id}/work-session/start/", {}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("in_progress", resp.data["error"]["detail"].lower())
