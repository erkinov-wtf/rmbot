from django.test import TestCase
from rest_framework.test import APIClient

from account.models import Role, User
from bike.models import Bike
from core.utils.constants import BikeStatus, RoleSlug, TicketStatus, TicketTransitionAction
from ticket.models import Ticket, TicketTransition


class TicketWorkflowAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.master = User.objects.create_user(
            username="wf_master",
            password="pass1234",
            first_name="Master",
            email="wf_master@example.com",
        )
        self.ops = User.objects.create_user(
            username="wf_ops",
            password="pass1234",
            first_name="Ops",
            email="wf_ops@example.com",
        )
        self.tech = User.objects.create_user(
            username="wf_tech",
            password="pass1234",
            first_name="Tech",
            email="wf_tech@example.com",
        )
        self.other_tech = User.objects.create_user(
            username="wf_other_tech",
            password="pass1234",
            first_name="Other",
            email="wf_other_tech@example.com",
        )
        self.qc = User.objects.create_user(
            username="wf_qc",
            password="pass1234",
            first_name="QC",
            email="wf_qc@example.com",
        )

        role_specs = [
            (RoleSlug.MASTER, "Master (Service Lead)", [self.master]),
            (RoleSlug.OPS_MANAGER, "Ops Manager", [self.ops]),
            (RoleSlug.TECHNICIAN, "Technician", [self.tech, self.other_tech]),
            (RoleSlug.QC_INSPECTOR, "QC Inspector", [self.qc]),
        ]
        for slug, name, users in role_specs:
            role, _ = Role.objects.update_or_create(slug=slug, defaults={"name": name})
            for user in users:
                user.roles.add(role)

        self.bike = Bike.objects.create(bike_code="RM-WF-0001")
        self.ticket = Ticket.objects.create(
            bike=self.bike,
            master=self.master,
            status=TicketStatus.NEW,
            title="Workflow ticket",
        )

    def test_master_can_assign_technician(self):
        self.client.force_authenticate(user=self.master)
        resp = self.client.post(
            f"/api/v1/tickets/{self.ticket.id}/assign/",
            {"technician_id": self.tech.id},
            format="json",
        )

        self.assertEqual(resp.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, TicketStatus.ASSIGNED)
        self.assertEqual(self.ticket.technician_id, self.tech.id)
        self.assertIsNotNone(self.ticket.assigned_at)

    def test_only_assigned_technician_can_start(self):
        self.ticket.status = TicketStatus.ASSIGNED
        self.ticket.technician = self.tech
        self.ticket.save(update_fields=["status", "technician"])

        self.client.force_authenticate(user=self.other_tech)
        denied = self.client.post(f"/api/v1/tickets/{self.ticket.id}/start/", {}, format="json")
        self.assertEqual(denied.status_code, 400)
        self.assertIn("assigned technician", denied.data["error"]["detail"].lower())

        self.client.force_authenticate(user=self.tech)
        allowed = self.client.post(f"/api/v1/tickets/{self.ticket.id}/start/", {}, format="json")
        self.assertEqual(allowed.status_code, 200)
        self.ticket.refresh_from_db()
        self.bike.refresh_from_db()
        self.assertEqual(self.ticket.status, TicketStatus.IN_PROGRESS)
        self.assertEqual(self.bike.status, BikeStatus.IN_SERVICE)

    def test_technician_moves_to_waiting_qc(self):
        self.ticket.status = TicketStatus.IN_PROGRESS
        self.ticket.technician = self.tech
        self.ticket.save(update_fields=["status", "technician"])

        self.client.force_authenticate(user=self.tech)
        resp = self.client.post(f"/api/v1/tickets/{self.ticket.id}/to-waiting-qc/", {}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, TicketStatus.WAITING_QC)

    def test_qc_pass_marks_done_and_sets_bike_ready(self):
        self.bike.status = BikeStatus.IN_SERVICE
        self.bike.save(update_fields=["status"])
        self.ticket.status = TicketStatus.WAITING_QC
        self.ticket.technician = self.tech
        self.ticket.save(update_fields=["status", "technician"])

        self.client.force_authenticate(user=self.qc)
        resp = self.client.post(f"/api/v1/tickets/{self.ticket.id}/qc-pass/", {}, format="json")
        self.assertEqual(resp.status_code, 200)

        self.ticket.refresh_from_db()
        self.bike.refresh_from_db()
        self.assertEqual(self.ticket.status, TicketStatus.DONE)
        self.assertIsNotNone(self.ticket.done_at)
        self.assertEqual(self.bike.status, BikeStatus.READY)

    def test_qc_fail_moves_to_rework_then_technician_can_restart(self):
        self.ticket.status = TicketStatus.WAITING_QC
        self.ticket.technician = self.tech
        self.ticket.save(update_fields=["status", "technician"])

        self.client.force_authenticate(user=self.qc)
        fail = self.client.post(f"/api/v1/tickets/{self.ticket.id}/qc-fail/", {}, format="json")
        self.assertEqual(fail.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, TicketStatus.REWORK)

        self.client.force_authenticate(user=self.tech)
        restart = self.client.post(f"/api/v1/tickets/{self.ticket.id}/start/", {}, format="json")
        self.assertEqual(restart.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, TicketStatus.IN_PROGRESS)

    def test_transition_history_endpoint_returns_ordered_audit_records(self):
        self.client.force_authenticate(user=self.master)
        self.client.post(f"/api/v1/tickets/{self.ticket.id}/assign/", {"technician_id": self.tech.id}, format="json")

        self.client.force_authenticate(user=self.tech)
        self.client.post(f"/api/v1/tickets/{self.ticket.id}/start/", {}, format="json")
        self.client.post(f"/api/v1/tickets/{self.ticket.id}/to-waiting-qc/", {}, format="json")

        self.client.force_authenticate(user=self.qc)
        self.client.post(f"/api/v1/tickets/{self.ticket.id}/qc-pass/", {}, format="json")

        transitions = TicketTransition.objects.filter(ticket=self.ticket).order_by("created_at")
        self.assertEqual(transitions.count(), 4)
        self.assertEqual(transitions[0].action, TicketTransitionAction.ASSIGNED)
        self.assertEqual(transitions[1].action, TicketTransitionAction.STARTED)
        self.assertEqual(transitions[2].action, TicketTransitionAction.TO_WAITING_QC)
        self.assertEqual(transitions[3].action, TicketTransitionAction.QC_PASS)

        self.client.force_authenticate(user=self.master)
        history_resp = self.client.get(f"/api/v1/tickets/{self.ticket.id}/transitions/")
        self.assertEqual(history_resp.status_code, 200)
        history = history_resp.data["data"]
        self.assertEqual(len(history), 4)
        self.assertEqual(history[0]["action"], TicketTransitionAction.QC_PASS)
