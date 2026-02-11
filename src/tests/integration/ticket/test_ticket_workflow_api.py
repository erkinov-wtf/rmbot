import pytest

from core.utils.constants import BikeStatus, RoleSlug, TicketStatus, TicketTransitionAction
from ticket.models import TicketTransition


pytestmark = pytest.mark.django_db


@pytest.fixture
def workflow_context(user_factory, assign_roles, bike_factory, ticket_factory):
    master = user_factory(
        username="wf_master",
        first_name="Master",
        email="wf_master@example.com",
    )
    ops = user_factory(
        username="wf_ops",
        first_name="Ops",
        email="wf_ops@example.com",
    )
    tech = user_factory(
        username="wf_tech",
        first_name="Tech",
        email="wf_tech@example.com",
    )
    other_tech = user_factory(
        username="wf_other_tech",
        first_name="Other",
        email="wf_other_tech@example.com",
    )
    qc = user_factory(
        username="wf_qc",
        first_name="QC",
        email="wf_qc@example.com",
    )

    assign_roles(master, RoleSlug.MASTER)
    assign_roles(ops, RoleSlug.OPS_MANAGER)
    assign_roles(tech, RoleSlug.TECHNICIAN)
    assign_roles(other_tech, RoleSlug.TECHNICIAN)
    assign_roles(qc, RoleSlug.QC_INSPECTOR)

    bike = bike_factory(bike_code="RM-WF-0001")
    ticket = ticket_factory(
        bike=bike,
        master=master,
        status=TicketStatus.NEW,
        title="Workflow ticket",
    )

    return {
        "master": master,
        "ops": ops,
        "tech": tech,
        "other_tech": other_tech,
        "qc": qc,
        "bike": bike,
        "ticket": ticket,
    }


def test_master_can_assign_technician(authed_client_factory, workflow_context):
    client = authed_client_factory(workflow_context["master"])
    ticket = workflow_context["ticket"]
    tech = workflow_context["tech"]

    resp = client.post(
        f"/api/v1/tickets/{ticket.id}/assign/",
        {"technician_id": tech.id},
        format="json",
    )

    assert resp.status_code == 200
    ticket.refresh_from_db()
    assert ticket.status == TicketStatus.ASSIGNED
    assert ticket.technician_id == tech.id
    assert ticket.assigned_at is not None


def test_only_assigned_technician_can_start(authed_client_factory, workflow_context):
    ticket = workflow_context["ticket"]
    ticket.status = TicketStatus.ASSIGNED
    ticket.technician = workflow_context["tech"]
    ticket.save(update_fields=["status", "technician"])

    other_client = authed_client_factory(workflow_context["other_tech"])
    denied = other_client.post(f"/api/v1/tickets/{ticket.id}/start/", {}, format="json")
    assert denied.status_code == 400
    assert "assigned technician" in denied.data["error"]["detail"].lower()

    tech_client = authed_client_factory(workflow_context["tech"])
    allowed = tech_client.post(f"/api/v1/tickets/{ticket.id}/start/", {}, format="json")
    assert allowed.status_code == 200

    ticket.refresh_from_db()
    workflow_context["bike"].refresh_from_db()
    assert ticket.status == TicketStatus.IN_PROGRESS
    assert workflow_context["bike"].status == BikeStatus.IN_SERVICE


def test_technician_moves_to_waiting_qc(authed_client_factory, workflow_context):
    ticket = workflow_context["ticket"]
    ticket.status = TicketStatus.IN_PROGRESS
    ticket.technician = workflow_context["tech"]
    ticket.save(update_fields=["status", "technician"])

    client = authed_client_factory(workflow_context["tech"])
    resp = client.post(f"/api/v1/tickets/{ticket.id}/to-waiting-qc/", {}, format="json")

    assert resp.status_code == 200
    ticket.refresh_from_db()
    assert ticket.status == TicketStatus.WAITING_QC


def test_qc_pass_marks_done_and_sets_bike_ready(authed_client_factory, workflow_context):
    ticket = workflow_context["ticket"]
    bike = workflow_context["bike"]
    bike.status = BikeStatus.IN_SERVICE
    bike.save(update_fields=["status"])
    ticket.status = TicketStatus.WAITING_QC
    ticket.technician = workflow_context["tech"]
    ticket.save(update_fields=["status", "technician"])

    client = authed_client_factory(workflow_context["qc"])
    resp = client.post(f"/api/v1/tickets/{ticket.id}/qc-pass/", {}, format="json")

    assert resp.status_code == 200
    ticket.refresh_from_db()
    bike.refresh_from_db()
    assert ticket.status == TicketStatus.DONE
    assert ticket.done_at is not None
    assert bike.status == BikeStatus.READY


def test_qc_fail_moves_to_rework_then_technician_can_restart(authed_client_factory, workflow_context):
    ticket = workflow_context["ticket"]
    ticket.status = TicketStatus.WAITING_QC
    ticket.technician = workflow_context["tech"]
    ticket.save(update_fields=["status", "technician"])

    qc_client = authed_client_factory(workflow_context["qc"])
    fail = qc_client.post(f"/api/v1/tickets/{ticket.id}/qc-fail/", {}, format="json")
    assert fail.status_code == 200

    ticket.refresh_from_db()
    assert ticket.status == TicketStatus.REWORK

    tech_client = authed_client_factory(workflow_context["tech"])
    restart = tech_client.post(f"/api/v1/tickets/{ticket.id}/start/", {}, format="json")
    assert restart.status_code == 200

    ticket.refresh_from_db()
    assert ticket.status == TicketStatus.IN_PROGRESS


def test_transition_history_endpoint_returns_ordered_audit_records(authed_client_factory, workflow_context):
    ticket = workflow_context["ticket"]

    master_client = authed_client_factory(workflow_context["master"])
    master_client.post(f"/api/v1/tickets/{ticket.id}/assign/", {"technician_id": workflow_context['tech'].id}, format="json")

    tech_client = authed_client_factory(workflow_context["tech"])
    tech_client.post(f"/api/v1/tickets/{ticket.id}/start/", {}, format="json")
    tech_client.post(f"/api/v1/tickets/{ticket.id}/to-waiting-qc/", {}, format="json")

    qc_client = authed_client_factory(workflow_context["qc"])
    qc_client.post(f"/api/v1/tickets/{ticket.id}/qc-pass/", {}, format="json")

    transitions = TicketTransition.objects.filter(ticket=ticket).order_by("created_at")
    assert transitions.count() == 4
    assert transitions[0].action == TicketTransitionAction.ASSIGNED
    assert transitions[1].action == TicketTransitionAction.STARTED
    assert transitions[2].action == TicketTransitionAction.TO_WAITING_QC
    assert transitions[3].action == TicketTransitionAction.QC_PASS

    history_resp = master_client.get(f"/api/v1/tickets/{ticket.id}/transitions/")
    assert history_resp.status_code == 200
    history = history_resp.data["data"]
    assert len(history) == 4
    assert history[0]["action"] == TicketTransitionAction.QC_PASS
