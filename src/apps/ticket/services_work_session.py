from django.db import transaction
from django.utils import timezone

from core.utils.constants import (
    TicketStatus,
    WorkSessionStatus,
    WorkSessionTransitionAction,
)
from ticket.models import Ticket, WorkSession, WorkSessionTransition
from ticket.services_workflow import TicketWorkflowService


class TicketWorkSessionService:
    """Session lifecycle manager for technician work time accounting."""

    @classmethod
    @transaction.atomic
    def start_work_session(cls, ticket: Ticket, actor_user_id: int) -> WorkSession:
        if not ticket.technician_id or ticket.technician_id != actor_user_id:
            raise ValueError("Only assigned technician can start work session.")
        if ticket.status != TicketStatus.IN_PROGRESS:
            if ticket.status in (TicketStatus.ASSIGNED, TicketStatus.REWORK):
                TicketWorkflowService.start_ticket(
                    ticket=ticket,
                    actor_user_id=actor_user_id,
                )
            else:
                raise ValueError(
                    "Work session can be started only when ticket is IN_PROGRESS."
                )

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
        session = WorkSession.objects.create(
            ticket=ticket,
            technician_id=actor_user_id,
            status=WorkSessionStatus.RUNNING,
            started_at=now_dt,
            last_started_at=now_dt,
            active_seconds=0,
        )
        cls._log_work_session_transition(
            session=session,
            action=WorkSessionTransitionAction.STARTED,
            from_status=None,
            to_status=WorkSessionStatus.RUNNING,
            actor_user_id=actor_user_id,
            event_at=now_dt,
        )
        return session

    @classmethod
    @transaction.atomic
    def pause_work_session(cls, ticket: Ticket, actor_user_id: int) -> WorkSession:
        session = cls._get_open_session_for_ticket(
            ticket=ticket, actor_user_id=actor_user_id
        )
        if session.status != WorkSessionStatus.RUNNING:
            raise ValueError("Work session can be paused only from RUNNING state.")

        now_dt = timezone.now()
        cls._log_work_session_transition(
            session=session,
            action=WorkSessionTransitionAction.PAUSED,
            from_status=WorkSessionStatus.RUNNING,
            to_status=WorkSessionStatus.PAUSED,
            actor_user_id=actor_user_id,
            event_at=now_dt,
        )
        session.active_seconds = cls._calculate_active_seconds_from_transitions(
            session=session,
            until_dt=now_dt,
        )
        session.status = WorkSessionStatus.PAUSED
        session.last_started_at = None
        session.save(update_fields=["active_seconds", "status", "last_started_at"])
        return session

    @classmethod
    @transaction.atomic
    def resume_work_session(cls, ticket: Ticket, actor_user_id: int) -> WorkSession:
        session = cls._get_open_session_for_ticket(
            ticket=ticket, actor_user_id=actor_user_id
        )
        if session.status != WorkSessionStatus.PAUSED:
            raise ValueError("Work session can be resumed only from PAUSED state.")

        now_dt = timezone.now()
        cls._log_work_session_transition(
            session=session,
            action=WorkSessionTransitionAction.RESUMED,
            from_status=WorkSessionStatus.PAUSED,
            to_status=WorkSessionStatus.RUNNING,
            actor_user_id=actor_user_id,
            event_at=now_dt,
        )
        session.status = WorkSessionStatus.RUNNING
        session.last_started_at = now_dt
        session.active_seconds = cls._calculate_active_seconds_from_transitions(
            session=session,
            until_dt=now_dt,
        )
        session.save(update_fields=["status", "last_started_at", "active_seconds"])
        return session

    @classmethod
    @transaction.atomic
    def stop_work_session(cls, ticket: Ticket, actor_user_id: int) -> WorkSession:
        session = cls._get_open_session_for_ticket(
            ticket=ticket, actor_user_id=actor_user_id
        )
        now_dt = timezone.now()
        if session.status not in (WorkSessionStatus.RUNNING, WorkSessionStatus.PAUSED):
            raise ValueError(
                "Work session can be stopped only from RUNNING or PAUSED state."
            )

        cls._log_work_session_transition(
            session=session,
            action=WorkSessionTransitionAction.STOPPED,
            from_status=session.status,
            to_status=WorkSessionStatus.STOPPED,
            actor_user_id=actor_user_id,
            event_at=now_dt,
        )
        session.active_seconds = cls._calculate_active_seconds_from_transitions(
            session=session,
            until_dt=now_dt,
        )
        session.status = WorkSessionStatus.STOPPED
        session.last_started_at = None
        session.ended_at = now_dt
        session.save(
            update_fields=["active_seconds", "status", "last_started_at", "ended_at"]
        )
        return session

    @staticmethod
    def get_ticket_work_session_history(ticket: Ticket):
        return (
            WorkSessionTransition.objects.filter(ticket=ticket)
            .select_related("work_session", "actor")
            .order_by("-event_at", "-id")
        )

    @staticmethod
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
            raise ValueError(
                "No active work session found for this ticket and technician."
            )
        return session

    @staticmethod
    def _log_work_session_transition(
        *,
        session: WorkSession,
        action: str,
        from_status: str | None,
        to_status: str,
        actor_user_id: int,
        event_at,
        metadata: dict | None = None,
    ) -> WorkSessionTransition:
        return WorkSessionTransition.objects.create(
            work_session=session,
            ticket=session.ticket,
            action=action,
            from_status=from_status,
            to_status=to_status,
            actor_id=actor_user_id,
            event_at=event_at,
            metadata=metadata or {},
        )

    @staticmethod
    def _calculate_active_seconds_from_transitions(
        *, session: WorkSession, until_dt
    ) -> int:
        # Recalculate from transition history to avoid drift from partial updates.
        transitions = session.transitions.order_by("event_at", "id").only(
            "action", "event_at"
        )
        running_since = None
        total_seconds = 0

        for transition in transitions:
            if transition.action in (
                WorkSessionTransitionAction.STARTED,
                WorkSessionTransitionAction.RESUMED,
            ):
                if running_since is None:
                    running_since = transition.event_at
                continue

            if (
                transition.action
                in (
                    WorkSessionTransitionAction.PAUSED,
                    WorkSessionTransitionAction.STOPPED,
                )
                and running_since is not None
            ):
                elapsed = max(
                    0, int((transition.event_at - running_since).total_seconds())
                )
                total_seconds += elapsed
                running_since = None

        if running_since is not None:
            total_seconds += max(0, int((until_dt - running_since).total_seconds()))
        return total_seconds
