import pytest

from core.utils.constants import RoleSlug, TicketStatus, WorkSessionStatus
from ticket.models import WorkSession

pytestmark = pytest.mark.django_db


@pytest.fixture
def work_session_context(user_factory, assign_roles, bike_factory, ticket_factory):
    master = user_factory(
        username="ws_master",
        first_name="Master",
        email="ws_master@example.com",
    )
    tech = user_factory(
        username="ws_tech",
        first_name="Tech",
        email="ws_tech@example.com",
    )
    other_tech = user_factory(
        username="ws_other_tech",
        first_name="Other",
        email="ws_other_tech@example.com",
    )
    assign_roles(master, RoleSlug.MASTER)
    assign_roles(tech, RoleSlug.TECHNICIAN)
    assign_roles(other_tech, RoleSlug.TECHNICIAN)

    bike = bike_factory(bike_code="RM-WS-0001")
    ticket = ticket_factory(
        bike=bike,
        master=master,
        technician=tech,
        status=TicketStatus.IN_PROGRESS,
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

    start = client.post(
        f"/api/v1/tickets/{ticket.id}/work-session/start/", {}, format="json"
    )
    assert start.status_code == 200
    assert start.data["data"]["status"] == WorkSessionStatus.RUNNING

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


def test_other_technician_cannot_control_session(
    authed_client_factory, work_session_context
):
    ticket = work_session_context["ticket"]
    WorkSession.objects.create(
        ticket=ticket,
        technician=work_session_context["tech"],
        status=WorkSessionStatus.RUNNING,
        started_at=ticket.created_at,
        last_started_at=ticket.created_at,
    )

    client = authed_client_factory(work_session_context["other_tech"])
    resp = client.post(
        f"/api/v1/tickets/{ticket.id}/work-session/pause/", {}, format="json"
    )

    assert resp.status_code == 400
    assert "no active work session" in resp.data["error"]["detail"].lower()


def test_cannot_start_session_when_ticket_not_in_progress(
    authed_client_factory, work_session_context
):
    ticket = work_session_context["ticket"]
    ticket.status = TicketStatus.ASSIGNED
    ticket.save(update_fields=["status"])

    client = authed_client_factory(work_session_context["tech"])
    resp = client.post(
        f"/api/v1/tickets/{ticket.id}/work-session/start/", {}, format="json"
    )

    assert resp.status_code == 400
    assert "in_progress" in resp.data["error"]["detail"].lower()
