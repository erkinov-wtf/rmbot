import logging
import math

from django.db import transaction
from django.utils import timezone

from core.api.exceptions import DomainValidationError
from core.services.notifications import UserNotificationService
from core.utils.constants import (
    TicketStatus,
    TicketTransitionAction,
    WorkSessionStatus,
    XPTransactionEntryType,
)
from gamification.services import GamificationService
from rules.services import RulesService
from ticket.models import Ticket, TicketTransition, WorkSession

logger = logging.getLogger(__name__)


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
            metadata={
                "technician_id": technician_id,
                "review_approved": from_status
                in (TicketStatus.UNDER_REVIEW, TicketStatus.NEW),
            },
        )
        UserNotificationService.notify_ticket_assigned(
            ticket=ticket,
            actor_user_id=actor_user_id,
        )
        return ticket

    @classmethod
    @transaction.atomic
    def start_ticket(cls, ticket: Ticket, actor_user_id: int) -> Ticket:
        if WorkSession.domain.has_open_for_technician(technician_id=actor_user_id):
            raise DomainValidationError(
                "Technician already has an active work session. Stop current work session "
                "or move ticket to waiting QC before starting another ticket."
            )

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
    def move_ticket_to_waiting_qc(
        cls,
        ticket: Ticket,
        actor_user_id: int,
        transition_metadata: dict | None = None,
    ) -> Ticket:
        latest_session = WorkSession.domain.get_latest_for_ticket_and_technician(
            ticket=ticket,
            technician_id=actor_user_id,
        )
        if latest_session is None or latest_session.status != WorkSessionStatus.STOPPED:
            raise DomainValidationError(
                "Work session must be stopped before moving ticket to waiting QC."
            )

        from_status = ticket.move_to_waiting_qc(actor_user_id=actor_user_id)

        cls.log_ticket_transition(
            ticket=ticket,
            from_status=from_status,
            to_status=ticket.status,
            action=TicketTransitionAction.TO_WAITING_QC,
            actor_user_id=actor_user_id,
            metadata=transition_metadata,
        )
        UserNotificationService.notify_ticket_waiting_qc(
            ticket=ticket,
            actor_user_id=actor_user_id,
        )
        return ticket

    @classmethod
    @transaction.atomic
    def qc_pass_ticket(
        cls,
        ticket: Ticket,
        actor_user_id: int | None = None,
        transition_metadata: dict | None = None,
    ) -> Ticket:
        had_rework = TicketTransition.domain.has_qc_fail_for_ticket(ticket=ticket)
        from_status = ticket.mark_qc_pass(finished_at=timezone.now())
        ticket.inventory_item.mark_ready()

        transition = cls.log_ticket_transition(
            ticket=ticket,
            from_status=from_status,
            to_status=ticket.status,
            action=TicketTransitionAction.QC_PASS,
            actor_user_id=actor_user_id,
            metadata=transition_metadata,
        )

        (
            base_divisor,
            first_pass_bonus,
            qc_status_update_xp,
            _,
            _,
        ) = cls._ticket_xp_rules()
        # Base XP comes from resolved ticket metrics (auto/manual), with formula fallback.
        base_xp = cls._base_ticket_xp(ticket=ticket, base_divisor=base_divisor)
        GamificationService.append_xp_entry(
            user_id=ticket.technician_id,
            amount=base_xp,
            entry_type=XPTransactionEntryType.TICKET_BASE_XP,
            reference=f"ticket_base_xp:{ticket.id}",
            description="Ticket completion base XP",
            payload={
                "ticket_id": ticket.id,
                "total_duration": ticket.total_duration,
                "formula_divisor": base_divisor,
                "is_manual": bool(ticket.is_manual),
                "resolved_ticket_xp": int(ticket.xp_amount or 0),
                "qc_pass": True,
            },
        )
        cls._award_qc_status_update_xp(
            ticket=ticket,
            transition=transition,
            actor_user_id=actor_user_id,
            amount=qc_status_update_xp,
        )

        awarded_first_pass_bonus = 0
        if cls._is_first_pass_bonus_eligible(
            ticket=ticket,
            had_rework=had_rework,
            first_pass_bonus=first_pass_bonus,
        ):
            awarded_first_pass_bonus = first_pass_bonus
            GamificationService.append_xp_entry(
                user_id=ticket.technician_id,
                amount=first_pass_bonus,
                entry_type=XPTransactionEntryType.TICKET_QC_FIRST_PASS_BONUS,
                reference=f"ticket_qc_first_pass_bonus:{ticket.id}",
                description="Ticket QC first-pass bonus XP",
                payload={
                    "ticket_id": ticket.id,
                    "first_pass": True,
                    "first_pass_bonus": first_pass_bonus,
                    "within_total_duration": True,
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
    def qc_fail_ticket(
        cls,
        ticket: Ticket,
        actor_user_id: int | None = None,
        transition_metadata: dict | None = None,
    ) -> Ticket:
        from_status = ticket.mark_qc_fail()
        transition = cls.log_ticket_transition(
            ticket=ticket,
            from_status=from_status,
            to_status=ticket.status,
            action=TicketTransitionAction.QC_FAIL,
            actor_user_id=actor_user_id,
            metadata=transition_metadata,
        )
        _, _, qc_status_update_xp, _, _ = cls._ticket_xp_rules()
        cls._award_qc_status_update_xp(
            ticket=ticket,
            transition=transition,
            actor_user_id=actor_user_id,
            amount=qc_status_update_xp,
        )
        UserNotificationService.notify_ticket_qc_fail(
            ticket=ticket,
            actor_user_id=actor_user_id,
        )
        return ticket

    @classmethod
    @transaction.atomic
    def approve_ticket_review(
        cls,
        *,
        ticket: Ticket,
        actor_user_id: int,
    ) -> Ticket:
        if ticket.is_admin_reviewed:
            return ticket

        if ticket.status not in (TicketStatus.UNDER_REVIEW, TicketStatus.NEW):
            raise DomainValidationError(
                "Ticket review can be approved only from UNDER_REVIEW or NEW status."
            )

        # Mark as admin reviewed
        ticket.approved_by_id = actor_user_id
        ticket.approved_at = timezone.now()
        update_fields = ["approved_by", "approved_at"]

        # Transition UNDER_REVIEW -> NEW; if already NEW, no change
        if ticket.status == TicketStatus.UNDER_REVIEW:
            ticket.status = TicketStatus.NEW
            update_fields.append("status")

        ticket.save(update_fields=update_fields)

        return ticket

    @classmethod
    @transaction.atomic
    def set_manual_ticket_metrics(
        cls,
        *,
        ticket: Ticket,
        flag_color: str,
        xp_amount: int,
    ) -> Ticket:
        ticket.apply_manual_metrics(flag_color=flag_color, xp_amount=xp_amount)
        ticket.save(
            update_fields=["flag_color", "xp_amount", "is_manual", "updated_at"]
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
        transition = ticket.add_transition(
            from_status=from_status,
            to_status=to_status,
            action=action,
            actor_user_id=actor_user_id,
            note=note,
            metadata=metadata,
        )
        logger.info(
            (
                "Ticket transition logged: ticket_id=%s transition_id=%s action=%s "
                "from_status=%s to_status=%s actor_user_id=%s metadata=%s"
            ),
            ticket.id,
            transition.id,
            action,
            from_status,
            to_status,
            actor_user_id,
            transition.metadata,
        )
        return transition

    @staticmethod
    def _ticket_xp_rules() -> tuple[int, int, int, int, int]:
        rules = RulesService.get_active_rules_config()
        ticket_rules = rules.get("ticket_xp", {})
        base_divisor = int(ticket_rules.get("base_divisor", 20) or 20)
        if base_divisor <= 0:
            base_divisor = 20
        first_pass_bonus = int(ticket_rules.get("first_pass_bonus", 1) or 0)
        if first_pass_bonus < 0:
            first_pass_bonus = 0
        qc_status_update_xp = int(ticket_rules.get("qc_status_update_xp", 1) or 0)
        if qc_status_update_xp < 0:
            qc_status_update_xp = 0
        flag_green_max_minutes = int(
            ticket_rules.get("flag_green_max_minutes", 30) or 30
        )
        if flag_green_max_minutes < 0:
            flag_green_max_minutes = 30

        flag_yellow_max_minutes = int(
            ticket_rules.get("flag_yellow_max_minutes", 60) or 60
        )
        if flag_yellow_max_minutes < flag_green_max_minutes:
            flag_yellow_max_minutes = max(flag_green_max_minutes, 60)

        return (
            base_divisor,
            first_pass_bonus,
            qc_status_update_xp,
            flag_green_max_minutes,
            flag_yellow_max_minutes,
        )

    @staticmethod
    def _base_ticket_xp(*, ticket: Ticket, base_divisor: int) -> int:
        resolved_xp = int(ticket.xp_amount or 0)
        if resolved_xp > 0:
            return resolved_xp
        return math.ceil((ticket.total_duration or 0) / max(base_divisor, 1))

    @staticmethod
    def _is_first_pass_bonus_eligible(
        *,
        ticket: Ticket,
        had_rework: bool,
        first_pass_bonus: int,
    ) -> bool:
        if had_rework:
            return False

        if first_pass_bonus <= 0:
            return False

        total_duration_minutes = max(int(ticket.total_duration or 0), 0)
        actual_work_seconds = WorkSession.domain.total_active_seconds_for_ticket(
            ticket=ticket
        )
        return actual_work_seconds <= (total_duration_minutes * 60)

    @staticmethod
    def _award_qc_status_update_xp(
        *,
        ticket: Ticket,
        transition: TicketTransition,
        actor_user_id: int | None,
        amount: int,
    ) -> None:
        if not actor_user_id or amount <= 0:
            return

        GamificationService.append_xp_entry(
            user_id=actor_user_id,
            amount=amount,
            entry_type=XPTransactionEntryType.TICKET_QC_STATUS_UPDATE,
            reference=f"ticket_qc_status_update:{ticket.id}:{transition.id}",
            description="QC status update XP",
            payload={
                "ticket_id": ticket.id,
                "ticket_transition_id": transition.id,
                "qc_action": transition.action,
                "qc_status_update_xp": amount,
            },
        )
