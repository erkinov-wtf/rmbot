import math

from django.db import IntegrityError, transaction
from django.utils import timezone

from core.utils.constants import (
    BikeStatus,
    TicketStatus,
    TicketTransitionAction,
    WorkSessionStatus,
    WorkSessionTransitionAction,
    XPLedgerEntryType,
)
from gamification.services import GamificationService
from rules.services import RulesService
from ticket.models import Ticket, TicketTransition, WorkSession, WorkSessionTransition


class TicketService:
    @staticmethod
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

    @classmethod
    @transaction.atomic
    def assign_ticket(
        cls, ticket: Ticket, technician_id: int, actor_user_id: int | None = None
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

        cls.log_ticket_transition(
            ticket=ticket,
            from_status=from_status,
            to_status=ticket.status,
            action=TicketTransitionAction.ASSIGNED,
            actor_user_id=actor_user_id,
            metadata={"technician_id": technician_id},
        )
        return ticket

    @classmethod
    @transaction.atomic
    def start_ticket(cls, ticket: Ticket, actor_user_id: int) -> Ticket:
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

        cls.log_ticket_transition(
            ticket=ticket,
            from_status=from_status,
            to_status=ticket.status,
            action=TicketTransitionAction.STARTED,
            actor_user_id=actor_user_id,
        )
        return ticket

    @classmethod
    @transaction.atomic
    def move_ticket_to_waiting_qc(cls, ticket: Ticket, actor_user_id: int) -> Ticket:
        from_status = ticket.status
        if ticket.status != TicketStatus.IN_PROGRESS:
            raise ValueError("Ticket can be sent to QC only from IN_PROGRESS.")
        if not ticket.technician_id or ticket.technician_id != actor_user_id:
            raise ValueError("Only assigned technician can send ticket to QC.")

        ticket.status = TicketStatus.WAITING_QC
        ticket.save(update_fields=["status"])
        cls.log_ticket_transition(
            ticket=ticket,
            from_status=from_status,
            to_status=ticket.status,
            action=TicketTransitionAction.TO_WAITING_QC,
            actor_user_id=actor_user_id,
        )
        return ticket

    @classmethod
    @transaction.atomic
    def qc_pass_ticket(cls, ticket: Ticket, actor_user_id: int | None = None) -> Ticket:
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

        cls.log_ticket_transition(
            ticket=ticket,
            from_status=from_status,
            to_status=ticket.status,
            action=TicketTransitionAction.QC_PASS,
            actor_user_id=actor_user_id,
        )

        rules = RulesService.get_active_rules_config()
        ticket_rules = rules.get("ticket_xp", {})
        base_divisor = int(ticket_rules.get("base_divisor", 20) or 20)
        if base_divisor <= 0:
            base_divisor = 20
        first_pass_bonus = int(ticket_rules.get("first_pass_bonus", 1) or 0)
        if first_pass_bonus < 0:
            first_pass_bonus = 0

        base_xp = math.ceil((ticket.srt_total_minutes or 0) / base_divisor)
        GamificationService.append_xp_entry(
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
            GamificationService.append_xp_entry(
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

    @classmethod
    @transaction.atomic
    def qc_fail_ticket(cls, ticket: Ticket, actor_user_id: int | None = None) -> Ticket:
        from_status = ticket.status
        if ticket.status != TicketStatus.WAITING_QC:
            raise ValueError("QC FAIL allowed only from WAITING_QC.")

        ticket.status = TicketStatus.REWORK
        ticket.done_at = None
        ticket.save(update_fields=["status", "done_at"])
        cls.log_ticket_transition(
            ticket=ticket,
            from_status=from_status,
            to_status=ticket.status,
            action=TicketTransitionAction.QC_FAIL,
            actor_user_id=actor_user_id,
        )
        return ticket

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
        *,
        session: WorkSession,
        until_dt,
    ) -> int:
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

    @classmethod
    @transaction.atomic
    def start_work_session(cls, ticket: Ticket, actor_user_id: int) -> WorkSession:
        if not ticket.technician_id or ticket.technician_id != actor_user_id:
            raise ValueError("Only assigned technician can start work session.")
        if ticket.status != TicketStatus.IN_PROGRESS:
            if ticket.status in (TicketStatus.ASSIGNED, TicketStatus.REWORK):
                cls.start_ticket(ticket=ticket, actor_user_id=actor_user_id)
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
        TicketService._log_work_session_transition(
            session=session,
            action=WorkSessionTransitionAction.STARTED,
            from_status=None,
            to_status=WorkSessionStatus.RUNNING,
            actor_user_id=actor_user_id,
            event_at=now_dt,
        )
        return session

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

        from_status = session.status
        cls._log_work_session_transition(
            session=session,
            action=WorkSessionTransitionAction.STOPPED,
            from_status=from_status,
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
            .select_related(
                "work_session",
                "actor",
            )
            .order_by("-event_at", "-id")
        )
