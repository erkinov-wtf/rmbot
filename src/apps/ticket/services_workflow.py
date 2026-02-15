import math

from django.db import transaction
from django.utils import timezone

from core.services.notifications import UserNotificationService
from core.utils.constants import (
    TicketTransitionAction,
    WorkSessionStatus,
    XPLedgerEntryType,
)
from gamification.services import GamificationService
from rules.services import RulesService
from ticket.models import Ticket, TicketTransition, WorkSession


class TicketWorkflowService:
    """Canonical ticket state machine with audit logging and XP side effects."""

    @classmethod
    @transaction.atomic
    def assign_ticket(
        cls, ticket: Ticket, technician_id: int, actor_user_id: int | None = None
    ) -> Ticket:
        from_status = ticket.assign_to_technician(
            technician_id=technician_id,
            assigned_at=timezone.now(),
        )

        cls.log_ticket_transition(
            ticket=ticket,
            from_status=from_status,
            to_status=ticket.status,
            action=TicketTransitionAction.ASSIGNED,
            actor_user_id=actor_user_id,
            metadata={"technician_id": technician_id},
        )
        UserNotificationService.notify_ticket_assigned(
            ticket=ticket,
            actor_user_id=actor_user_id,
        )
        return ticket

    @classmethod
    @transaction.atomic
    def start_ticket(cls, ticket: Ticket, actor_user_id: int) -> Ticket:
        now_dt = timezone.now()
        from_status = ticket.start_progress(
            actor_user_id=actor_user_id,
            started_at=now_dt,
        )
        ticket.inventory_item.mark_in_service()

        cls.log_ticket_transition(
            ticket=ticket,
            from_status=from_status,
            to_status=ticket.status,
            action=TicketTransitionAction.STARTED,
            actor_user_id=actor_user_id,
        )
        WorkSession.start_for_ticket(
            ticket=ticket,
            actor_user_id=actor_user_id,
            started_at=now_dt,
        )
        UserNotificationService.notify_ticket_started(
            ticket=ticket,
            actor_user_id=actor_user_id,
        )
        return ticket

    @classmethod
    @transaction.atomic
    def move_ticket_to_waiting_qc(cls, ticket: Ticket, actor_user_id: int) -> Ticket:
        latest_session = WorkSession.domain.get_latest_for_ticket_and_technician(
            ticket=ticket,
            technician_id=actor_user_id,
        )
        if latest_session is None or latest_session.status != WorkSessionStatus.STOPPED:
            raise ValueError(
                "Work session must be stopped before moving ticket to waiting QC."
            )

        from_status = ticket.move_to_waiting_qc(actor_user_id=actor_user_id)
        cls.log_ticket_transition(
            ticket=ticket,
            from_status=from_status,
            to_status=ticket.status,
            action=TicketTransitionAction.TO_WAITING_QC,
            actor_user_id=actor_user_id,
        )
        UserNotificationService.notify_ticket_waiting_qc(
            ticket=ticket,
            actor_user_id=actor_user_id,
        )
        return ticket

    @classmethod
    @transaction.atomic
    def qc_pass_ticket(cls, ticket: Ticket, actor_user_id: int | None = None) -> Ticket:
        had_rework = TicketTransition.domain.has_qc_fail_for_ticket(ticket=ticket)
        from_status = ticket.mark_qc_pass(done_at=timezone.now())
        ticket.inventory_item.mark_ready()

        cls.log_ticket_transition(
            ticket=ticket,
            from_status=from_status,
            to_status=ticket.status,
            action=TicketTransitionAction.QC_PASS,
            actor_user_id=actor_user_id,
        )

        base_divisor, first_pass_bonus = cls._ticket_xp_rules()
        # Base XP is always granted on successful QC PASS completion.
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

        awarded_first_pass_bonus = 0
        if not had_rework and first_pass_bonus > 0:
            awarded_first_pass_bonus = first_pass_bonus
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
        UserNotificationService.notify_ticket_qc_pass(
            ticket=ticket,
            actor_user_id=actor_user_id,
            base_xp=base_xp,
            first_pass_bonus=awarded_first_pass_bonus,
        )
        return ticket

    @classmethod
    @transaction.atomic
    def qc_fail_ticket(cls, ticket: Ticket, actor_user_id: int | None = None) -> Ticket:
        from_status = ticket.mark_qc_fail()
        cls.log_ticket_transition(
            ticket=ticket,
            from_status=from_status,
            to_status=ticket.status,
            action=TicketTransitionAction.QC_FAIL,
            actor_user_id=actor_user_id,
        )
        UserNotificationService.notify_ticket_qc_fail(
            ticket=ticket,
            actor_user_id=actor_user_id,
        )
        return ticket

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
        return ticket.add_transition(
            from_status=from_status,
            to_status=to_status,
            action=action,
            actor_user_id=actor_user_id,
            note=note,
            metadata=metadata,
        )

    @staticmethod
    def _ticket_xp_rules() -> tuple[int, int]:
        rules = RulesService.get_active_rules_config()
        ticket_rules = rules.get("ticket_xp", {})
        base_divisor = int(ticket_rules.get("base_divisor", 20) or 20)
        if base_divisor <= 0:
            base_divisor = 20
        first_pass_bonus = int(ticket_rules.get("first_pass_bonus", 1) or 0)
        if first_pass_bonus < 0:
            first_pass_bonus = 0
        return base_divisor, first_pass_bonus
