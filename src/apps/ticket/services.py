import math

from django.db import IntegrityError, transaction
from django.utils import timezone

from core.utils.constants import (
    BikeStatus,
    TicketStatus,
    TicketTransitionAction,
    WorkSessionStatus,
    XPLedgerEntryType,
)
from gamification.services import append_xp_entry
from rules.services import get_active_rules_config
from ticket.models import Ticket, TicketTransition, WorkSession


def log_ticket_transition(
    ticket: Ticket,
    action: str,
    to_status: str,
    from_status: str | None = None,
    actor_user_id: int | None = None,
    note: str | None = None,
    metadata: dict | None = None,
) -> TicketTransition:
    return TicketTransition.objects.create(
        ticket=ticket,
        from_status=from_status,
        to_status=to_status,
        action=action,
        actor_id=actor_user_id,
        note=note,
        metadata=metadata or {},
    )


@transaction.atomic
def assign_ticket(
    ticket: Ticket, technician_id: int, actor_user_id: int | None = None
) -> Ticket:
    from_status = ticket.status
    if ticket.status not in (
        TicketStatus.NEW,
        TicketStatus.ASSIGNED,
        TicketStatus.REWORK,
    ):
        raise ValueError("Ticket cannot be assigned in current status.")

    ticket.technician_id = technician_id
    ticket.assigned_at = timezone.now()

    if ticket.status == TicketStatus.NEW:
        ticket.status = TicketStatus.ASSIGNED
        ticket.save(update_fields=["technician", "assigned_at", "status"])
    else:
        ticket.save(update_fields=["technician", "assigned_at"])

    log_ticket_transition(
        ticket=ticket,
        from_status=from_status,
        to_status=ticket.status,
        action=TicketTransitionAction.ASSIGNED,
        actor_user_id=actor_user_id,
        metadata={"technician_id": technician_id},
    )
    return ticket


@transaction.atomic
def start_ticket(ticket: Ticket, actor_user_id: int) -> Ticket:
    from_status = ticket.status
    if ticket.status not in (TicketStatus.ASSIGNED, TicketStatus.REWORK):
        raise ValueError("Ticket can be started only from ASSIGNED or REWORK.")
    if not ticket.technician_id:
        raise ValueError("Ticket has no assigned technician.")
    if ticket.technician_id != actor_user_id:
        raise ValueError("Only assigned technician can start this ticket.")

    ticket.status = TicketStatus.IN_PROGRESS
    update_fields = ["status"]
    if not ticket.started_at:
        ticket.started_at = timezone.now()
        update_fields.append("started_at")

    try:
        ticket.save(update_fields=update_fields)
    except IntegrityError as exc:
        raise ValueError("Technician already has an IN_PROGRESS ticket.") from exc

    # Keep bike availability in sync with active work.
    if ticket.bike.status != BikeStatus.IN_SERVICE:
        ticket.bike.status = BikeStatus.IN_SERVICE
        ticket.bike.save(update_fields=["status"])

    log_ticket_transition(
        ticket=ticket,
        from_status=from_status,
        to_status=ticket.status,
        action=TicketTransitionAction.STARTED,
        actor_user_id=actor_user_id,
    )
    return ticket


@transaction.atomic
def move_ticket_to_waiting_qc(ticket: Ticket, actor_user_id: int) -> Ticket:
    from_status = ticket.status
    if ticket.status != TicketStatus.IN_PROGRESS:
        raise ValueError("Ticket can be sent to QC only from IN_PROGRESS.")
    if not ticket.technician_id or ticket.technician_id != actor_user_id:
        raise ValueError("Only assigned technician can send ticket to QC.")

    ticket.status = TicketStatus.WAITING_QC
    ticket.save(update_fields=["status"])
    log_ticket_transition(
        ticket=ticket,
        from_status=from_status,
        to_status=ticket.status,
        action=TicketTransitionAction.TO_WAITING_QC,
        actor_user_id=actor_user_id,
    )
    return ticket


@transaction.atomic
def qc_pass_ticket(ticket: Ticket, actor_user_id: int | None = None) -> Ticket:
    from_status = ticket.status
    if ticket.status != TicketStatus.WAITING_QC:
        raise ValueError("QC PASS allowed only from WAITING_QC.")
    if not ticket.technician_id:
        raise ValueError("Ticket must have an assigned technician before QC PASS.")

    had_rework = TicketTransition.objects.filter(
        ticket=ticket,
        action=TicketTransitionAction.QC_FAIL,
    ).exists()

    ticket.status = TicketStatus.DONE
    ticket.done_at = timezone.now()
    ticket.save(update_fields=["status", "done_at"])

    if ticket.bike.status != BikeStatus.READY:
        ticket.bike.status = BikeStatus.READY
        ticket.bike.save(update_fields=["status"])

    log_ticket_transition(
        ticket=ticket,
        from_status=from_status,
        to_status=ticket.status,
        action=TicketTransitionAction.QC_PASS,
        actor_user_id=actor_user_id,
    )

    rules = get_active_rules_config()
    ticket_rules = rules.get("ticket_xp", {})
    base_divisor = int(ticket_rules.get("base_divisor", 20) or 20)
    if base_divisor <= 0:
        base_divisor = 20
    first_pass_bonus = int(ticket_rules.get("first_pass_bonus", 1) or 0)
    if first_pass_bonus < 0:
        first_pass_bonus = 0

    base_xp = math.ceil((ticket.srt_total_minutes or 0) / base_divisor)
    append_xp_entry(
        user_id=ticket.technician_id,
        amount=base_xp,
        entry_type=XPLedgerEntryType.TICKET_BASE_XP,
        reference=f"ticket_base_xp:{ticket.id}",
        description="Ticket completion base XP",
        payload={
            "ticket_id": ticket.id,
            "srt_total_minutes": ticket.srt_total_minutes,
            "formula_divisor": base_divisor,
            "qc_pass": True,
        },
    )

    if not had_rework and first_pass_bonus > 0:
        append_xp_entry(
            user_id=ticket.technician_id,
            amount=first_pass_bonus,
            entry_type=XPLedgerEntryType.TICKET_QC_FIRST_PASS_BONUS,
            reference=f"ticket_qc_first_pass_bonus:{ticket.id}",
            description="Ticket QC first-pass bonus XP",
            payload={
                "ticket_id": ticket.id,
                "first_pass": True,
                "first_pass_bonus": first_pass_bonus,
            },
        )
    return ticket


@transaction.atomic
def qc_fail_ticket(ticket: Ticket, actor_user_id: int | None = None) -> Ticket:
    from_status = ticket.status
    if ticket.status != TicketStatus.WAITING_QC:
        raise ValueError("QC FAIL allowed only from WAITING_QC.")

    ticket.status = TicketStatus.REWORK
    ticket.done_at = None
    ticket.save(update_fields=["status", "done_at"])
    log_ticket_transition(
        ticket=ticket,
        from_status=from_status,
        to_status=ticket.status,
        action=TicketTransitionAction.QC_FAIL,
        actor_user_id=actor_user_id,
    )
    return ticket


def _accumulate_active_seconds(session: WorkSession, now_dt) -> None:
    if session.last_started_at:
        elapsed_seconds = max(
            0, int((now_dt - session.last_started_at).total_seconds())
        )
        session.active_seconds += elapsed_seconds


@transaction.atomic
def start_work_session(ticket: Ticket, actor_user_id: int) -> WorkSession:
    if ticket.status != TicketStatus.IN_PROGRESS:
        raise ValueError("Work session can be started only when ticket is IN_PROGRESS.")
    if not ticket.technician_id or ticket.technician_id != actor_user_id:
        raise ValueError("Only assigned technician can start work session.")

    if WorkSession.objects.filter(
        ticket=ticket,
        status__in=[WorkSessionStatus.RUNNING, WorkSessionStatus.PAUSED],
        deleted_at__isnull=True,
    ).exists():
        raise ValueError("Ticket already has an active work session.")

    if WorkSession.objects.filter(
        technician_id=actor_user_id,
        status__in=[WorkSessionStatus.RUNNING, WorkSessionStatus.PAUSED],
        deleted_at__isnull=True,
    ).exists():
        raise ValueError("Technician already has an active work session.")

    now_dt = timezone.now()
    return WorkSession.objects.create(
        ticket=ticket,
        technician_id=actor_user_id,
        status=WorkSessionStatus.RUNNING,
        started_at=now_dt,
        last_started_at=now_dt,
        active_seconds=0,
    )


def _get_open_session_for_ticket(ticket: Ticket, actor_user_id: int) -> WorkSession:
    session = (
        WorkSession.objects.filter(
            ticket=ticket,
            technician_id=actor_user_id,
            status__in=[WorkSessionStatus.RUNNING, WorkSessionStatus.PAUSED],
            deleted_at__isnull=True,
        )
        .order_by("-created_at")
        .first()
    )
    if not session:
        raise ValueError("No active work session found for this ticket and technician.")
    return session


@transaction.atomic
def pause_work_session(ticket: Ticket, actor_user_id: int) -> WorkSession:
    session = _get_open_session_for_ticket(ticket=ticket, actor_user_id=actor_user_id)
    if session.status != WorkSessionStatus.RUNNING:
        raise ValueError("Work session can be paused only from RUNNING state.")

    now_dt = timezone.now()
    _accumulate_active_seconds(session, now_dt)
    session.status = WorkSessionStatus.PAUSED
    session.last_started_at = None
    session.save(update_fields=["active_seconds", "status", "last_started_at"])
    return session


@transaction.atomic
def resume_work_session(ticket: Ticket, actor_user_id: int) -> WorkSession:
    session = _get_open_session_for_ticket(ticket=ticket, actor_user_id=actor_user_id)
    if session.status != WorkSessionStatus.PAUSED:
        raise ValueError("Work session can be resumed only from PAUSED state.")

    session.status = WorkSessionStatus.RUNNING
    session.last_started_at = timezone.now()
    session.save(update_fields=["status", "last_started_at"])
    return session


@transaction.atomic
def stop_work_session(ticket: Ticket, actor_user_id: int) -> WorkSession:
    session = _get_open_session_for_ticket(ticket=ticket, actor_user_id=actor_user_id)
    now_dt = timezone.now()
    if session.status == WorkSessionStatus.RUNNING:
        _accumulate_active_seconds(session, now_dt)
    elif session.status != WorkSessionStatus.PAUSED:
        raise ValueError(
            "Work session can be stopped only from RUNNING or PAUSED state."
        )

    session.status = WorkSessionStatus.STOPPED
    session.last_started_at = None
    session.ended_at = now_dt
    session.save(
        update_fields=["active_seconds", "status", "last_started_at", "ended_at"]
    )
    return session
