from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from core.utils.constants import (
    RoleSlug,
    TicketStatus,
    WorkSessionStatus,
    WorkSessionTransitionAction,
)
from rules.services import RulesService
from ticket.models import WorkSession, WorkSessionTransition
from ticket.services_work_session import TicketWorkSessionService

pytestmark = pytest.mark.django_db


def _configure_pause_limit_rules(*, actor_user_id: int, limit_minutes: int) -> None:
    config = RulesService.get_active_rules_config()
    config["work_session"] = {
        "daily_pause_limit_minutes": limit_minutes,
        "timezone": "Asia/Tashkent",
    }
    RulesService.update_rules_config(
        config=config,
        actor_user_id=actor_user_id,
        reason="Work session pause-limit test override",
    )


@pytest.fixture
def work_session_context(
    user_factory, assign_roles, inventory_item_factory, ticket_factory
):
    master = user_factory(
        username="ws_master",
        first_name="Master",
    )
    tech = user_factory(
        username="ws_tech",
        first_name="Tech",
    )
    other_tech = user_factory(
        username="ws_other_tech",
        first_name="Other",
    )
    assign_roles(master, RoleSlug.MASTER)
    assign_roles(tech, RoleSlug.TECHNICIAN)
    assign_roles(other_tech, RoleSlug.TECHNICIAN)

    inventory_item = inventory_item_factory(serial_number="RM-WS-0001")
    ticket = ticket_factory(
        inventory_item=inventory_item,
        master=master,
        technician=tech,
        status=TicketStatus.ASSIGNED,
        title="Session ticket",
    )
    return {
        "master": master,
        "tech": tech,
        "other_tech": other_tech,
        "ticket": ticket,
    }


def test_technician_session_lifecycle(authed_client_factory, work_session_context):
    client = authed_client_factory(work_session_context["tech"])
    ticket = work_session_context["ticket"]

    start = client.post(f"/api/v1/tickets/{ticket.id}/start/", {}, format="json")
    assert start.status_code == 200
    assert start.data["data"]["status"] == TicketStatus.IN_PROGRESS

    pause = client.post(
        f"/api/v1/tickets/{ticket.id}/work-session/pause/", {}, format="json"
    )
    assert pause.status_code == 200
    assert pause.data["data"]["status"] == WorkSessionStatus.PAUSED

    resume = client.post(
        f"/api/v1/tickets/{ticket.id}/work-session/resume/", {}, format="json"
    )
    assert resume.status_code == 200
    assert resume.data["data"]["status"] == WorkSessionStatus.RUNNING

    stop = client.post(
        f"/api/v1/tickets/{ticket.id}/work-session/stop/", {}, format="json"
    )
    assert stop.status_code == 200
    assert stop.data["data"]["status"] == WorkSessionStatus.STOPPED

    session = WorkSession.objects.get(
        ticket=ticket, technician=work_session_context["tech"]
    )
    assert session.status == WorkSessionStatus.STOPPED
    assert session.ended_at is not None
    transitions = list(
        WorkSessionTransition.objects.filter(work_session=session)
        .order_by("event_at", "id")
        .values_list("action", flat=True)
    )
    assert transitions == [
        WorkSessionTransitionAction.STARTED,
        WorkSessionTransitionAction.PAUSED,
        WorkSessionTransitionAction.RESUMED,
        WorkSessionTransitionAction.STOPPED,
    ]


def test_other_technician_cannot_control_session(
    authed_client_factory, work_session_context
):
    ticket = work_session_context["ticket"]
    tech_client = authed_client_factory(work_session_context["tech"])
    start = tech_client.post(f"/api/v1/tickets/{ticket.id}/start/", {}, format="json")
    assert start.status_code == 200

    client = authed_client_factory(work_session_context["other_tech"])
    resp = client.post(
        f"/api/v1/tickets/{ticket.id}/work-session/pause/", {}, format="json"
    )

    assert resp.status_code == 400
    assert "no active work session" in resp.data["error"]["detail"].lower()


def test_ticket_start_rejects_invalid_status_for_auto_session(
    authed_client_factory, work_session_context
):
    ticket = work_session_context["ticket"]
    ticket.status = TicketStatus.WAITING_QC
    ticket.save(update_fields=["status"])

    client = authed_client_factory(work_session_context["tech"])
    resp = client.post(f"/api/v1/tickets/{ticket.id}/start/", {}, format="json")

    assert resp.status_code == 400
    assert "assigned or rework" in resp.data["error"]["detail"].lower()


def test_work_session_history_endpoint_returns_ordered_events(
    authed_client_factory, work_session_context
):
    client = authed_client_factory(work_session_context["tech"])
    ticket = work_session_context["ticket"]

    client.post(f"/api/v1/tickets/{ticket.id}/start/", {}, format="json")
    client.post(f"/api/v1/tickets/{ticket.id}/work-session/pause/", {}, format="json")
    client.post(f"/api/v1/tickets/{ticket.id}/work-session/resume/", {}, format="json")
    client.post(f"/api/v1/tickets/{ticket.id}/work-session/stop/", {}, format="json")

    history = client.get(f"/api/v1/tickets/{ticket.id}/work-session/history/")

    assert history.status_code == 200
    actions = [item["action"] for item in history.data["results"]]
    assert actions[:4] == [
        WorkSessionTransitionAction.STOPPED,
        WorkSessionTransitionAction.RESUMED,
        WorkSessionTransitionAction.PAUSED,
        WorkSessionTransitionAction.STARTED,
    ]


def test_active_seconds_is_recalculated_from_persistent_history(
    authed_client_factory, work_session_context
):
    client = authed_client_factory(work_session_context["tech"])
    ticket = work_session_context["ticket"]
    start = client.post(f"/api/v1/tickets/{ticket.id}/start/", {}, format="json")
    assert start.status_code == 200

    session = WorkSession.objects.get(
        ticket=ticket,
        technician=work_session_context["tech"],
    )
    WorkSession.objects.filter(pk=session.pk).update(
        active_seconds=9_999,
        last_started_at=timezone.now() - timedelta(days=1),
    )

    pause = client.post(
        f"/api/v1/tickets/{ticket.id}/work-session/pause/", {}, format="json"
    )
    assert pause.status_code == 200

    session = WorkSession.objects.get(
        ticket=ticket,
        technician=work_session_context["tech"],
    )
    assert session.active_seconds != 9_999
    assert session.active_seconds < 60


def test_rework_ticket_can_restart_via_ticket_start_then_return_to_qc(
    authed_client_factory, work_session_context
):
    ticket = work_session_context["ticket"]
    ticket.status = TicketStatus.REWORK
    ticket.save(update_fields=["status"])

    tech_client = authed_client_factory(work_session_context["tech"])
    ws_start = tech_client.post(
        f"/api/v1/tickets/{ticket.id}/start/", {}, format="json"
    )
    assert ws_start.status_code == 200
    assert ws_start.data["data"]["status"] == TicketStatus.IN_PROGRESS

    ticket.refresh_from_db()
    assert ticket.status == TicketStatus.IN_PROGRESS

    ws_stop = tech_client.post(
        f"/api/v1/tickets/{ticket.id}/work-session/stop/",
        {},
        format="json",
    )
    assert ws_stop.status_code == 200

    to_qc = tech_client.post(
        f"/api/v1/tickets/{ticket.id}/to-waiting-qc/",
        {},
        format="json",
    )
    assert to_qc.status_code == 200
    ticket.refresh_from_db()
    assert ticket.status == TicketStatus.WAITING_QC


def test_pause_fails_when_daily_limit_is_fully_reached(
    authed_client_factory, work_session_context
):
    _configure_pause_limit_rules(
        actor_user_id=work_session_context["master"].id,
        limit_minutes=0,
    )

    client = authed_client_factory(work_session_context["tech"])
    ticket = work_session_context["ticket"]
    start = client.post(f"/api/v1/tickets/{ticket.id}/start/", {}, format="json")
    assert start.status_code == 200

    pause = client.post(
        f"/api/v1/tickets/{ticket.id}/work-session/pause/",
        {},
        format="json",
    )
    assert pause.status_code == 400
    assert "daily pause limit" in pause.data["error"]["detail"].lower()


def test_paused_session_is_auto_resumed_when_pause_limit_is_consumed(
    work_session_context,
):
    _configure_pause_limit_rules(
        actor_user_id=work_session_context["master"].id,
        limit_minutes=1,
    )
    ticket = work_session_context["ticket"]
    technician_id = work_session_context["tech"].id

    now_dt = timezone.now()
    session = WorkSession.start_for_ticket(
        ticket=ticket,
        actor_user_id=technician_id,
        started_at=now_dt - timedelta(minutes=5),
    )
    session.pause(
        actor_user_id=technician_id,
        paused_at=now_dt - timedelta(seconds=70),
    )
    resumed_count = (
        TicketWorkSessionService.auto_resume_paused_sessions_if_limit_reached(
            technician_id=technician_id,
            now_dt=now_dt,
        )
    )

    assert resumed_count == 1
    session.refresh_from_db()
    assert session.status == WorkSessionStatus.RUNNING
    assert session.last_started_at == now_dt
    latest_transition = (
        WorkSessionTransition.objects.filter(work_session=session)
        .order_by("-event_at", "-id")
        .first()
    )
    assert latest_transition is not None
    assert latest_transition.action == WorkSessionTransitionAction.RESUMED
    assert latest_transition.metadata.get("auto_resumed") is True


def test_pause_limit_resets_after_midnight(
    work_session_context,
):
    _configure_pause_limit_rules(
        actor_user_id=work_session_context["master"].id,
        limit_minutes=1,
    )
    ticket = work_session_context["ticket"]
    technician_id = work_session_context["tech"].id
    business_tz = ZoneInfo("Asia/Tashkent")

    start_dt = datetime(2026, 2, 16, 23, 55, tzinfo=business_tz)
    pause_dt = datetime(2026, 2, 16, 23, 59, tzinfo=business_tz)
    now_dt = datetime(2026, 2, 17, 0, 0, 30, tzinfo=business_tz)

    session = WorkSession.start_for_ticket(
        ticket=ticket,
        actor_user_id=technician_id,
        started_at=start_dt,
    )
    session.pause(
        actor_user_id=technician_id,
        paused_at=pause_dt,
    )

    resumed_count = (
        TicketWorkSessionService.auto_resume_paused_sessions_if_limit_reached(
            technician_id=technician_id,
            now_dt=now_dt,
        )
    )
    assert resumed_count == 0

    session.refresh_from_db()
    assert session.status == WorkSessionStatus.PAUSED

    remaining_seconds = TicketWorkSessionService.get_remaining_pause_seconds_today(
        technician_id=technician_id,
        now_dt=now_dt,
    )
    assert 0 < remaining_seconds <= 30
