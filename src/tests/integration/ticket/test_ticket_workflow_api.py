import pytest
from django.utils import timezone

from core.services.notifications import UserNotificationService
from core.utils.constants import (
    InventoryItemStatus,
    RoleSlug,
    TicketStatus,
    TicketTransitionAction,
    WorkSessionStatus,
)
from ticket.models import TicketTransition, WorkSession

pytestmark = pytest.mark.django_db


@pytest.fixture
def workflow_context(
    user_factory, assign_roles, inventory_item_factory, ticket_factory
):
    master = user_factory(
        username="wf_master",
        first_name="Master",
    )
    ops = user_factory(
        username="wf_ops",
        first_name="Ops",
    )
    tech = user_factory(
        username="wf_tech",
        first_name="Tech",
    )
    other_tech = user_factory(
        username="wf_other_tech",
        first_name="Other",
    )
    qc = user_factory(
        username="wf_qc",
        first_name="QC",
    )

    assign_roles(master, RoleSlug.MASTER)
    assign_roles(ops, RoleSlug.OPS_MANAGER)
    assign_roles(tech, RoleSlug.TECHNICIAN)
    assign_roles(other_tech, RoleSlug.TECHNICIAN)
    assign_roles(qc, RoleSlug.QC_INSPECTOR)

    inventory_item = inventory_item_factory(serial_number="RM-WF-0001")
    ticket = ticket_factory(
        inventory_item=inventory_item,
        master=master,
        status=TicketStatus.UNDER_REVIEW,
        title="Workflow ticket",
    )

    return {
        "master": master,
        "ops": ops,
        "tech": tech,
        "other_tech": other_tech,
        "qc": qc,
        "inventory_item": inventory_item,
        "ticket": ticket,
    }


def test_admin_can_assign_technician(authed_client_factory, workflow_context):
    client = authed_client_factory(workflow_context["ops"])
    ticket = workflow_context["ticket"]
    tech = workflow_context["tech"]
    ticket.approved_by = workflow_context["ops"]
    ticket.approved_at = timezone.now()
    ticket.status = TicketStatus.NEW
    ticket.save(update_fields=["approved_by", "approved_at", "status"])

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


def test_cannot_assign_technician_before_admin_review(
    authed_client_factory, workflow_context
):
    client = authed_client_factory(workflow_context["ops"])
    ticket = workflow_context["ticket"]
    tech = workflow_context["tech"]

    resp = client.post(
        f"/api/v1/tickets/{ticket.id}/assign/",
        {"technician_id": tech.id},
        format="json",
    )

    assert resp.status_code == 400
    assert "admin review" in resp.data["error"]["detail"].lower()


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
    workflow_context["inventory_item"].refresh_from_db()
    assert ticket.status == TicketStatus.IN_PROGRESS
    assert workflow_context["inventory_item"].status == InventoryItemStatus.IN_SERVICE
    assert WorkSession.objects.filter(
        ticket=ticket,
        technician=workflow_context["tech"],
        status=WorkSessionStatus.RUNNING,
    ).exists()


def test_technician_moves_to_waiting_qc(authed_client_factory, workflow_context):
    ticket = workflow_context["ticket"]
    ticket.status = TicketStatus.ASSIGNED
    ticket.technician = workflow_context["tech"]
    ticket.save(update_fields=["status", "technician"])

    client = authed_client_factory(workflow_context["tech"])
    start = client.post(f"/api/v1/tickets/{ticket.id}/start/", {}, format="json")
    assert start.status_code == 200
    stop = client.post(
        f"/api/v1/tickets/{ticket.id}/work-session/stop/", {}, format="json"
    )
    assert stop.status_code == 200

    resp = client.post(f"/api/v1/tickets/{ticket.id}/to-waiting-qc/", {}, format="json")

    assert resp.status_code == 200
    ticket.refresh_from_db()
    assert ticket.status == TicketStatus.WAITING_QC


def test_qc_pass_marks_done_and_sets_inventory_item_ready(
    authed_client_factory, workflow_context
):
    ticket = workflow_context["ticket"]
    inventory_item = workflow_context["inventory_item"]
    inventory_item.status = InventoryItemStatus.IN_SERVICE
    inventory_item.save(update_fields=["status"])
    ticket.status = TicketStatus.WAITING_QC
    ticket.technician = workflow_context["tech"]
    ticket.save(update_fields=["status", "technician"])

    client = authed_client_factory(workflow_context["qc"])
    resp = client.post(f"/api/v1/tickets/{ticket.id}/qc-pass/", {}, format="json")

    assert resp.status_code == 200
    ticket.refresh_from_db()
    inventory_item.refresh_from_db()
    assert ticket.status == TicketStatus.DONE
    assert ticket.finished_at is not None
    assert inventory_item.status == InventoryItemStatus.READY


def test_qc_fail_moves_to_rework_then_technician_can_restart(
    authed_client_factory, workflow_context
):
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


def test_cannot_move_to_waiting_qc_with_non_stopped_work_session(
    authed_client_factory, workflow_context
):
    ticket = workflow_context["ticket"]
    ticket.status = TicketStatus.ASSIGNED
    ticket.technician = workflow_context["tech"]
    ticket.save(update_fields=["status", "technician"])

    tech_client = authed_client_factory(workflow_context["tech"])
    start = tech_client.post(f"/api/v1/tickets/{ticket.id}/start/", {}, format="json")
    assert start.status_code == 200

    to_qc = tech_client.post(
        f"/api/v1/tickets/{ticket.id}/to-waiting-qc/", {}, format="json"
    )
    assert to_qc.status_code == 400
    assert "work session must be stopped" in to_qc.data["error"]["detail"].lower()


def test_transition_history_endpoint_returns_ordered_audit_records(
    authed_client_factory, workflow_context
):
    ticket = workflow_context["ticket"]

    ops_client = authed_client_factory(workflow_context["ops"])
    review_resp = ops_client.post(
        f"/api/v1/tickets/{ticket.id}/manual-metrics/",
        {"flag_color": "yellow", "xp_amount": 3},
        format="json",
    )
    assert review_resp.status_code == 200
    ops_client.post(
        f"/api/v1/tickets/{ticket.id}/assign/",
        {"technician_id": workflow_context["tech"].id},
        format="json",
    )

    tech_client = authed_client_factory(workflow_context["tech"])
    tech_client.post(f"/api/v1/tickets/{ticket.id}/start/", {}, format="json")
    tech_client.post(
        f"/api/v1/tickets/{ticket.id}/work-session/stop/", {}, format="json"
    )
    tech_client.post(f"/api/v1/tickets/{ticket.id}/to-waiting-qc/", {}, format="json")

    qc_client = authed_client_factory(workflow_context["qc"])
    qc_client.post(f"/api/v1/tickets/{ticket.id}/qc-pass/", {}, format="json")

    transitions = TicketTransition.objects.filter(ticket=ticket).order_by("created_at")
    assert transitions.count() == 4
    assert transitions[0].action == TicketTransitionAction.ASSIGNED
    assert transitions[1].action == TicketTransitionAction.STARTED
    assert transitions[2].action == TicketTransitionAction.TO_WAITING_QC
    assert transitions[3].action == TicketTransitionAction.QC_PASS

    history_resp = ops_client.get(f"/api/v1/tickets/{ticket.id}/transitions/")
    assert history_resp.status_code == 200
    history = history_resp.data["results"]
    assert len(history) == 4
    assert history[0]["action"] == TicketTransitionAction.QC_PASS


def test_manual_metrics_requires_admin_role(authed_client_factory, workflow_context):
    ticket = workflow_context["ticket"]
    tech_client = authed_client_factory(workflow_context["tech"])

    resp = tech_client.post(
        f"/api/v1/tickets/{ticket.id}/manual-metrics/",
        {"flag_color": "red", "xp_amount": 30},
        format="json",
    )

    assert resp.status_code == 403


def test_admin_can_set_manual_metrics(authed_client_factory, workflow_context):
    ticket = workflow_context["ticket"]
    ops_client = authed_client_factory(workflow_context["ops"])

    resp = ops_client.post(
        f"/api/v1/tickets/{ticket.id}/manual-metrics/",
        {"flag_color": "red", "xp_amount": 77},
        format="json",
    )

    assert resp.status_code == 200
    ticket.refresh_from_db()
    assert ticket.flag_color == "red"
    assert ticket.xp_amount == 77
    assert ticket.is_manual is True
    assert ticket.approved_by_id == workflow_context["ops"].id
    assert ticket.approved_at is not None
    assert ticket.status == TicketStatus.NEW
    assert resp.data["data"]["is_manual"] is True


def test_workflow_actions_emit_notification_events(
    authed_client_factory, workflow_context, monkeypatch
):
    events: list[dict] = []
    ticket = workflow_context["ticket"]
    ticket.total_duration = 40
    ticket.save(update_fields=["total_duration"])

    def _capture(event_name: str):
        def _inner(cls, **kwargs):
            payload = {
                "event": event_name,
                "ticket_id": kwargs["ticket"].id,
                "actor_user_id": kwargs.get("actor_user_id"),
            }
            if "base_xp" in kwargs:
                payload["base_xp"] = kwargs["base_xp"]
            if "first_pass_bonus" in kwargs:
                payload["first_pass_bonus"] = kwargs["first_pass_bonus"]
            events.append(payload)

        return _inner

    monkeypatch.setattr(
        UserNotificationService,
        "notify_ticket_assigned",
        classmethod(_capture("assigned")),
    )
    monkeypatch.setattr(
        UserNotificationService,
        "notify_ticket_started",
        classmethod(_capture("started")),
    )
    monkeypatch.setattr(
        UserNotificationService,
        "notify_ticket_waiting_qc",
        classmethod(_capture("to_waiting_qc")),
    )
    monkeypatch.setattr(
        UserNotificationService,
        "notify_ticket_qc_fail",
        classmethod(_capture("qc_fail")),
    )
    monkeypatch.setattr(
        UserNotificationService,
        "notify_ticket_qc_pass",
        classmethod(_capture("qc_pass")),
    )

    ops_client = authed_client_factory(workflow_context["ops"])
    review_resp = ops_client.post(
        f"/api/v1/tickets/{ticket.id}/manual-metrics/",
        {"flag_color": "yellow", "xp_amount": 2},
        format="json",
    )
    assert review_resp.status_code == 200
    assign_resp = ops_client.post(
        f"/api/v1/tickets/{ticket.id}/assign/",
        {"technician_id": workflow_context["tech"].id},
        format="json",
    )
    assert assign_resp.status_code == 200

    tech_client = authed_client_factory(workflow_context["tech"])
    start_resp = tech_client.post(
        f"/api/v1/tickets/{ticket.id}/start/", {}, format="json"
    )
    assert start_resp.status_code == 200
    stop_resp = tech_client.post(
        f"/api/v1/tickets/{ticket.id}/work-session/stop/", {}, format="json"
    )
    assert stop_resp.status_code == 200
    to_qc_resp = tech_client.post(
        f"/api/v1/tickets/{ticket.id}/to-waiting-qc/", {}, format="json"
    )
    assert to_qc_resp.status_code == 200

    qc_client = authed_client_factory(workflow_context["qc"])
    fail_resp = qc_client.post(
        f"/api/v1/tickets/{ticket.id}/qc-fail/", {}, format="json"
    )
    assert fail_resp.status_code == 200

    restart_resp = tech_client.post(
        f"/api/v1/tickets/{ticket.id}/start/",
        {},
        format="json",
    )
    assert restart_resp.status_code == 200
    stop_again_resp = tech_client.post(
        f"/api/v1/tickets/{ticket.id}/work-session/stop/", {}, format="json"
    )
    assert stop_again_resp.status_code == 200
    to_qc_again_resp = tech_client.post(
        f"/api/v1/tickets/{ticket.id}/to-waiting-qc/", {}, format="json"
    )
    assert to_qc_again_resp.status_code == 200

    pass_resp = qc_client.post(
        f"/api/v1/tickets/{ticket.id}/qc-pass/", {}, format="json"
    )
    assert pass_resp.status_code == 200

    assert [event["event"] for event in events] == [
        "assigned",
        "started",
        "to_waiting_qc",
        "qc_fail",
        "started",
        "to_waiting_qc",
        "qc_pass",
    ]
    assert events[-1]["base_xp"] >= 0
    assert events[-1]["first_pass_bonus"] == 0
