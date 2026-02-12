import math

from django.db import IntegrityError, transaction
from django.utils import timezone

from core.utils.constants import (
    BikeStatus,
    TicketStatus,
    TicketTransitionAction,
    XPLedgerEntryType,
)
from gamification.services import GamificationService
from rules.services import RulesService
from ticket.models import Ticket, TicketTransition


class TicketWorkflowService:
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

        base_divisor, first_pass_bonus = cls._ticket_xp_rules()
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
