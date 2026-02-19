import pytest
from django.utils import timezone

from account.models import AccessRequest
from bot.services.technician_ticket_actions import TechnicianTicketActionService
from bot.services.ticket_qc_queue import QCTicketQueueService
from core.services.notifications import UserNotificationService
from core.utils.constants import (
    AccessRequestStatus,
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

    approve_resp = client.post(
        f"/api/v1/tickets/{ticket.id}/review-approve/",
        {},
        format="json",
    )
    assert approve_resp.status_code == 200

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
    assert "admin review" in resp.data["message"].lower()


def test_admin_can_approve_ticket_review(authed_client_factory, workflow_context):
    ticket = workflow_context["ticket"]
    ops_client = authed_client_factory(workflow_context["ops"])

    resp = ops_client.post(
        f"/api/v1/tickets/{ticket.id}/review-approve/",
        {},
        format="json",
    )

    assert resp.status_code == 200
    ticket.refresh_from_db()
    assert ticket.approved_by_id == workflow_context["ops"].id
    assert ticket.approved_at is not None
    assert ticket.status == TicketStatus.NEW


def test_review_approve_requires_admin_role(authed_client_factory, workflow_context):
    ticket = workflow_context["ticket"]
    tech_client = authed_client_factory(workflow_context["tech"])

    resp = tech_client.post(
        f"/api/v1/tickets/{ticket.id}/review-approve/",
        {},
        format="json",
    )

    assert resp.status_code == 403


def test_only_assigned_technician_can_start(authed_client_factory, workflow_context):
    ticket = workflow_context["ticket"]
    ticket.status = TicketStatus.ASSIGNED
    ticket.technician = workflow_context["tech"]
    ticket.save(update_fields=["status", "technician"])

    other_client = authed_client_factory(workflow_context["other_tech"])
    denied = other_client.post(f"/api/v1/tickets/{ticket.id}/start/", {}, format="json")
    assert denied.status_code == 400
    assert "assigned technician" in denied.data["message"].lower()

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


def test_technician_must_stop_current_session_before_starting_another_ticket(
    authed_client_factory,
    workflow_context,
    ticket_factory,
    inventory_item_factory,
):
    primary_ticket = workflow_context["ticket"]
    primary_ticket.status = TicketStatus.ASSIGNED
    primary_ticket.technician = workflow_context["tech"]
    primary_ticket.save(update_fields=["status", "technician"])

    secondary_ticket = ticket_factory(
        inventory_item=inventory_item_factory(serial_number="RM-WF-0002"),
        master=workflow_context["master"],
        technician=workflow_context["tech"],
        status=TicketStatus.ASSIGNED,
        title="Second workflow ticket",
    )

    tech_client = authed_client_factory(workflow_context["tech"])
    first_start = tech_client.post(
        f"/api/v1/tickets/{primary_ticket.id}/start/",
        {},
        format="json",
    )
    assert first_start.status_code == 200

    denied = tech_client.post(
        f"/api/v1/tickets/{secondary_ticket.id}/start/",
        {},
        format="json",
    )
    assert denied.status_code == 400
    assert "active work session" in denied.data["message"].lower()

    stop = tech_client.post(
        f"/api/v1/tickets/{primary_ticket.id}/work-session/stop/",
        {},
        format="json",
    )
    assert stop.status_code == 200

    allowed = tech_client.post(
        f"/api/v1/tickets/{secondary_ticket.id}/start/",
        {},
        format="json",
    )
    assert allowed.status_code == 200

    primary_ticket.refresh_from_db()
    secondary_ticket.refresh_from_db()
    assert primary_ticket.status == TicketStatus.IN_PROGRESS
    assert secondary_ticket.status == TicketStatus.IN_PROGRESS
    assert WorkSession.objects.filter(
        ticket=secondary_ticket,
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
    assert "work session must be stopped" in to_qc.data["message"].lower()


def test_transition_history_endpoint_returns_ordered_audit_records(
    authed_client_factory, workflow_context
):
    ticket = workflow_context["ticket"]

    ops_client = authed_client_factory(workflow_context["ops"])
    approve_resp = ops_client.post(
        f"/api/v1/tickets/{ticket.id}/review-approve/",
        {},
        format="json",
    )
    assert approve_resp.status_code == 200

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
    assert ticket.approved_by_id is None
    assert ticket.approved_at is None
    assert ticket.status == TicketStatus.UNDER_REVIEW
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
    approve_resp = ops_client.post(
        f"/api/v1/tickets/{ticket.id}/review-approve/",
        {},
        format="json",
    )
    assert approve_resp.status_code == 200

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


def test_assign_notification_includes_technician_inline_actions(
    authed_client_factory,
    workflow_context,
    monkeypatch,
):
    captured_payloads: list[dict] = []
    ticket = workflow_context["ticket"]
    ticket.approved_by = workflow_context["ops"]
    ticket.approved_at = timezone.now()
    ticket.status = TicketStatus.NEW
    ticket.save(update_fields=["approved_by", "approved_at", "status"])

    def _capture_notify_users(cls, **kwargs):
        captured_payloads.append(kwargs)

    monkeypatch.setattr(
        UserNotificationService,
        "_notify_users",
        classmethod(_capture_notify_users),
    )

    ops_client = authed_client_factory(workflow_context["ops"])
    response = ops_client.post(
        f"/api/v1/tickets/{ticket.id}/assign/",
        {"technician_id": workflow_context["tech"].id},
        format="json",
    )
    assert response.status_code == 200

    event_keys = {payload["event_key"] for payload in captured_payloads}
    assert event_keys == {"ticket_assigned_master", "ticket_assigned_technician"}

    technician_payload = next(
        payload
        for payload in captured_payloads
        if payload["event_key"] == "ticket_assigned_technician"
    )
    assert technician_payload["reply_markup"] is not None


def test_waiting_qc_notification_includes_qc_inline_actions_for_qc_creator(
    workflow_context,
    monkeypatch,
    assign_roles,
):
    ticket = workflow_context["ticket"]
    ticket.status = TicketStatus.WAITING_QC
    ticket.technician = workflow_context["tech"]
    ticket.save(update_fields=["status", "technician"])

    assign_roles(workflow_context["master"], RoleSlug.QC_INSPECTOR)

    captured_payloads: list[dict] = []

    def _capture_notify_users(cls, **kwargs):
        captured_payloads.append(kwargs)

    monkeypatch.setattr(
        UserNotificationService,
        "_notify_users",
        classmethod(_capture_notify_users),
    )

    UserNotificationService.notify_ticket_waiting_qc(
        ticket=ticket,
        actor_user_id=workflow_context["tech"].id,
    )

    assert {payload["event_key"] for payload in captured_payloads} == {
        "ticket_waiting_qc_reviewers"
    }
    reviewers_payload = captured_payloads[0]
    assert workflow_context["master"].id in reviewers_payload["user_ids"]
    assert workflow_context["qc"].id in reviewers_payload["user_ids"]
    assert reviewers_payload["reply_markup"] is not None


def test_started_notification_targets_technician_only(
    workflow_context,
    monkeypatch,
    assign_roles,
):
    ticket = workflow_context["ticket"]
    ticket.status = TicketStatus.IN_PROGRESS
    ticket.technician = workflow_context["tech"]
    ticket.save(update_fields=["status", "technician"])

    assign_roles(workflow_context["master"], RoleSlug.QC_INSPECTOR)

    captured_payloads: list[dict] = []

    def _capture_notify_users(cls, **kwargs):
        captured_payloads.append(kwargs)

    monkeypatch.setattr(
        UserNotificationService,
        "_notify_users",
        classmethod(_capture_notify_users),
    )

    UserNotificationService.notify_ticket_started(
        ticket=ticket,
        actor_user_id=workflow_context["ops"].id,
    )

    assert len(captured_payloads) == 1
    payload = captured_payloads[0]
    assert payload["event_key"] == "ticket_started_technician"
    assert payload["user_ids"] == [workflow_context["tech"].id]


def test_qc_pass_notification_targets_technician_only(
    workflow_context,
    monkeypatch,
    assign_roles,
):
    ticket = workflow_context["ticket"]
    ticket.status = TicketStatus.DONE
    ticket.technician = workflow_context["tech"]
    ticket.save(update_fields=["status", "technician"])

    assign_roles(workflow_context["master"], RoleSlug.QC_INSPECTOR)

    captured_payloads: list[dict] = []

    def _capture_notify_users(cls, **kwargs):
        captured_payloads.append(kwargs)

    monkeypatch.setattr(
        UserNotificationService,
        "_notify_users",
        classmethod(_capture_notify_users),
    )

    UserNotificationService.notify_ticket_qc_pass(
        ticket=ticket,
        actor_user_id=workflow_context["qc"].id,
        base_xp=20,
        first_pass_bonus=5,
    )

    assert len(captured_payloads) == 1
    payload = captured_payloads[0]
    assert payload["event_key"] == "ticket_qc_pass"
    assert payload["user_ids"] == [workflow_context["tech"].id]


def test_qc_fail_notification_targets_technician_only(
    workflow_context,
    monkeypatch,
    assign_roles,
):
    ticket = workflow_context["ticket"]
    ticket.status = TicketStatus.REWORK
    ticket.technician = workflow_context["tech"]
    ticket.save(update_fields=["status", "technician"])

    assign_roles(workflow_context["master"], RoleSlug.QC_INSPECTOR)

    captured_payloads: list[dict] = []

    def _capture_notify_users(cls, **kwargs):
        captured_payloads.append(kwargs)

    monkeypatch.setattr(
        UserNotificationService,
        "_notify_users",
        classmethod(_capture_notify_users),
    )

    UserNotificationService.notify_ticket_qc_fail(
        ticket=ticket,
        actor_user_id=workflow_context["qc"].id,
    )

    assert len(captured_payloads) == 1
    payload = captured_payloads[0]
    assert payload["event_key"] == "ticket_qc_fail_technician"
    assert payload["user_ids"] == [workflow_context["tech"].id]
    assert payload["reply_markup"] is not None


def test_assign_notification_falls_back_if_technician_state_build_fails(
    workflow_context,
    monkeypatch,
):
    ticket = workflow_context["ticket"]
    ticket.status = TicketStatus.ASSIGNED
    ticket.approved_by = workflow_context["ops"]
    ticket.approved_at = timezone.now()
    ticket.technician = workflow_context["tech"]
    ticket.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "technician",
        ]
    )

    captured_payloads: list[dict] = []

    def _capture_notify_users(cls, **kwargs):
        captured_payloads.append(kwargs)

    monkeypatch.setattr(
        UserNotificationService,
        "_notify_users",
        classmethod(_capture_notify_users),
    )

    def _raise_state_error(cls, **kwargs):
        raise ValueError("boom")

    monkeypatch.setattr(
        TechnicianTicketActionService,
        "state_for_ticket",
        classmethod(_raise_state_error),
    )

    UserNotificationService.notify_ticket_assigned(
        ticket=ticket,
        actor_user_id=workflow_context["ops"].id,
    )

    event_keys = {payload["event_key"] for payload in captured_payloads}
    assert event_keys == {"ticket_assigned_master", "ticket_assigned_technician"}
    technician_payload = next(
        payload
        for payload in captured_payloads
        if payload["event_key"] == "ticket_assigned_technician"
    )
    assert callable(technician_payload["message"])
    rendered = technician_payload["message"](lambda text: text)
    assert "New ticket assigned to you" in rendered
    assert callable(technician_payload["reply_markup"])
    assert technician_payload["reply_markup"](lambda text: text) is None


def test_telegram_id_lookup_falls_back_to_access_request_when_profile_missing(
    workflow_context,
):
    technician = workflow_context["tech"]
    AccessRequest.objects.create(
        telegram_id=777000111,
        username="tech_fallback",
        status=AccessRequestStatus.APPROVED,
        user=technician,
        resolved_at=timezone.now(),
    )

    telegram_ids = UserNotificationService._telegram_ids_for_user_ids([technician.id])
    assert telegram_ids == [777000111]


def test_qc_queue_contains_only_current_user_assigned_waiting_qc_checks(
    workflow_context,
    ticket_factory,
    inventory_item_factory,
):
    assigned_ticket = workflow_context["ticket"]
    assigned_ticket.status = TicketStatus.WAITING_QC
    assigned_ticket.technician = workflow_context["tech"]
    assigned_ticket.save(update_fields=["status", "technician"])

    other_ticket = ticket_factory(
        inventory_item=inventory_item_factory(serial_number="RM-WF-QUEUE-02"),
        master=workflow_context["qc"],
        technician=workflow_context["tech"],
        status=TicketStatus.WAITING_QC,
        title="Other QC queue ticket",
    )

    items, safe_page, page_count, total_count = (
        QCTicketQueueService.paginated_queue_for_qc_user(
            qc_user_id=workflow_context["master"].id,
            page=1,
            per_page=QCTicketQueueService.PAGE_SIZE,
        )
    )

    assert safe_page == 1
    assert page_count == 1
    assert total_count == 1
    assert [item.ticket_id for item in items] == [assigned_ticket.id]
    assert other_ticket.id not in [item.ticket_id for item in items]
