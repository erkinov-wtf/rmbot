import logging
import math
from collections import defaultdict

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
from ticket.models import (
    Ticket,
    TicketPartCompletion,
    TicketPartQCFailure,
    TicketPartSpec,
    TicketTransition,
    WorkSession,
)

logger = logging.getLogger(__name__)


class TicketWorkflowService:
    """Canonical ticket state machine with audit logging and XP side effects."""

    @staticmethod
    def claimable_tickets_queryset_for_technician(*, technician_id: int):
        return Ticket.domain.claimable_for_technician(technician_id=technician_id)

    @staticmethod
    def _resolve_part_spec_ids_for_ticket(
        *,
        raw_part_ids: list[int],
        part_specs: dict[int, TicketPartSpec],
        unknown_message_prefix: str,
    ) -> list[int]:
        if not raw_part_ids:
            return []

        # Backward compatibility: accept both ticket part spec ids and inventory part ids.
        inventory_part_to_spec_id: dict[int, int | None] = {}
        for spec in part_specs.values():
            inventory_part_id = int(spec.inventory_item_part_id)
            if inventory_part_id not in inventory_part_to_spec_id:
                inventory_part_to_spec_id[inventory_part_id] = int(spec.id)
                continue
            current = inventory_part_to_spec_id[inventory_part_id]
            if current != int(spec.id):
                inventory_part_to_spec_id[inventory_part_id] = None

        resolved_ids: list[int] = []
        unknown_ids: list[int] = []
        for raw_part_id in raw_part_ids:
            candidate_id = int(raw_part_id)
            if candidate_id in part_specs:
                resolved_ids.append(candidate_id)
                continue
            mapped_spec_id = inventory_part_to_spec_id.get(candidate_id)
            if mapped_spec_id is None:
                unknown_ids.append(candidate_id)
                continue
            resolved_ids.append(int(mapped_spec_id))

        if unknown_ids:
            raise DomainValidationError(
                unknown_message_prefix
                + ", ".join(str(part_id) for part_id in sorted(set(unknown_ids)))
            )

        return resolved_ids

    @classmethod
    @transaction.atomic
    def claim_ticket(
        cls,
        *,
        ticket: Ticket,
        actor_user_id: int,
    ) -> Ticket:
        locked_ticket = (
            Ticket.domain.select_for_update()
            .select_related("inventory_item", "master")
            .prefetch_related("part_specs__inventory_item_part")
            .get(pk=ticket.pk)
        )

        if locked_ticket.technician_id and locked_ticket.technician_id != actor_user_id:
            raise DomainValidationError(
                "Ticket is already claimed by another technician."
            )
        if (
            locked_ticket.technician_id == actor_user_id
            and locked_ticket.status == TicketStatus.ASSIGNED
        ):
            return locked_ticket

        is_claimable = Ticket.domain.claimable_for_technician(
            technician_id=actor_user_id
        ).filter(pk=locked_ticket.pk)
        if not is_claimable.exists():
            raise DomainValidationError("Ticket is not claimable for this technician.")

        from_status = locked_ticket.assign_to_technician(
            technician_id=actor_user_id,
            assigned_at=timezone.now(),
        )
        cls.log_ticket_transition(
            ticket=locked_ticket,
            from_status=from_status,
            to_status=locked_ticket.status,
            action=TicketTransitionAction.CLAIMED,
            actor_user_id=actor_user_id,
            metadata={"claim_source": "technician_pool"},
        )
        UserNotificationService.notify_ticket_assigned(
            ticket=locked_ticket,
            actor_user_id=actor_user_id,
        )
        return locked_ticket

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
        from ticket.services_work_session import TicketWorkSessionService

        TicketWorkSessionService.reconcile_open_sessions_for_technician(
            technician_id=actor_user_id,
            actor_user_id=actor_user_id,
            now_dt=timezone.now(),
        )
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
    def complete_ticket_parts(
        cls,
        *,
        ticket: Ticket,
        actor_user_id: int,
        part_payloads: list[dict[str, object]],
        transition_metadata: dict | None = None,
    ) -> Ticket:
        if not part_payloads:
            raise DomainValidationError("At least one part must be selected.")

        locked_ticket = (
            Ticket.domain.select_for_update()
            .select_related("inventory_item", "master")
            .prefetch_related("part_specs__inventory_item_part")
            .get(pk=ticket.pk)
        )
        if locked_ticket.technician_id != actor_user_id:
            raise DomainValidationError(
                "Ticket must be claimed by this technician before completing parts."
            )
        if locked_ticket.status not in (
            TicketStatus.ASSIGNED,
            TicketStatus.IN_PROGRESS,
            TicketStatus.REWORK,
            TicketStatus.NEW,
        ):
            raise DomainValidationError(
                "Ticket parts cannot be completed in current ticket status."
            )
        latest_session = WorkSession.domain.get_latest_for_ticket_and_technician(
            ticket=locked_ticket,
            technician_id=actor_user_id,
        )
        if latest_session is None or latest_session.status != WorkSessionStatus.STOPPED:
            raise DomainValidationError(
                "Work session must be stopped before completing ticket parts."
            )

        part_specs = {
            spec.id: spec
            for spec in locked_ticket.part_specs.filter(deleted_at__isnull=True)
        }
        requested_part_ids = [int(item["part_spec_id"]) for item in part_payloads]
        if len(set(requested_part_ids)) != len(requested_part_ids):
            raise DomainValidationError(
                "Each part can be completed only once per request."
            )
        selected_part_spec_ids = cls._resolve_part_spec_ids_for_ticket(
            raw_part_ids=requested_part_ids,
            part_specs=part_specs,
            unknown_message_prefix="Selected parts are not found in ticket: ",
        )
        if len(set(selected_part_spec_ids)) != len(selected_part_spec_ids):
            raise DomainValidationError(
                "Each part can be completed only once per request."
            )

        now_dt = timezone.now()
        completed_ids: list[int] = []
        for payload, part_spec_id in zip(part_payloads, selected_part_spec_ids):
            note = str(payload.get("note", "") or "").strip()
            part_spec = part_specs[part_spec_id]
            if part_spec.is_completed and not part_spec.needs_rework:
                raise DomainValidationError(
                    f"Ticket part #{part_spec_id} is already completed."
                )
            if (
                part_spec.needs_rework
                and part_spec.rework_for_technician_id
                and part_spec.rework_for_technician_id != actor_user_id
            ):
                raise DomainValidationError(
                    f"Ticket part #{part_spec_id} is assigned for rework to another technician."
                )

            TicketPartCompletion.objects.create(
                ticket=locked_ticket,
                ticket_part_spec=part_spec,
                technician_id=actor_user_id,
                completed_at=now_dt,
                note=note,
                is_rework=bool(part_spec.needs_rework),
                metadata={"part_spec_id": part_spec_id},
            )

            part_spec.is_completed = True
            part_spec.completed_by_id = actor_user_id
            part_spec.completed_at = now_dt
            part_spec.completion_note = note
            part_spec.needs_rework = False
            part_spec.rework_for_technician_id = None
            part_spec.save(
                update_fields=[
                    "is_completed",
                    "completed_by",
                    "completed_at",
                    "completion_note",
                    "needs_rework",
                    "rework_for_technician",
                ]
            )
            completed_ids.append(part_spec_id)

        remaining_parts_qs = locked_ticket.part_specs.filter(
            deleted_at__isnull=True,
            is_completed=False,
        )
        has_remaining_parts = remaining_parts_qs.exists()
        from_status = locked_ticket.status
        if not has_remaining_parts:
            locked_ticket.status = TicketStatus.WAITING_QC
            locked_ticket.technician_id = actor_user_id
            locked_ticket.save(update_fields=["status", "technician"])
            cls.log_ticket_transition(
                ticket=locked_ticket,
                from_status=from_status,
                to_status=locked_ticket.status,
                action=TicketTransitionAction.TO_WAITING_QC,
                actor_user_id=actor_user_id,
                metadata={
                    "completed_part_spec_ids": completed_ids,
                    "auto_waiting_qc": True,
                    **(transition_metadata or {}),
                },
            )
            UserNotificationService.notify_ticket_waiting_qc(
                ticket=locked_ticket,
                actor_user_id=actor_user_id,
            )
            return locked_ticket

        has_rework_parts = remaining_parts_qs.filter(needs_rework=True).exists()
        locked_ticket.status = (
            TicketStatus.REWORK if has_rework_parts else TicketStatus.NEW
        )
        locked_ticket.technician_id = None
        locked_ticket.save(update_fields=["status", "technician"])
        cls.log_ticket_transition(
            ticket=locked_ticket,
            from_status=from_status,
            to_status=locked_ticket.status,
            action=TicketTransitionAction.PARTS_COMPLETED,
            actor_user_id=actor_user_id,
            metadata={
                "completed_part_spec_ids": completed_ids,
                "remaining_part_spec_ids": list(
                    remaining_parts_qs.values_list("id", flat=True)
                ),
                **(transition_metadata or {}),
            },
        )
        return locked_ticket

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
        failed_part_spec_ids: list[int] | None = None,
        note: str | None = None,
    ) -> Ticket:
        locked_ticket = (
            Ticket.domain.select_for_update()
            .select_related("inventory_item", "master")
            .prefetch_related("part_specs__inventory_item_part")
            .get(pk=ticket.pk)
        )
        all_part_specs = {
            spec.id: spec
            for spec in locked_ticket.part_specs.filter(deleted_at__isnull=True)
        }
        if not all_part_specs:
            raise DomainValidationError("Ticket has no part specs configured.")

        selected_part_ids = [
            int(part_id)
            for part_id in (
                failed_part_spec_ids
                if failed_part_spec_ids is not None
                else list(all_part_specs.keys())
            )
        ]
        selected_part_ids = list(
            dict.fromkeys(
                cls._resolve_part_spec_ids_for_ticket(
                    raw_part_ids=selected_part_ids,
                    part_specs=all_part_specs,
                    unknown_message_prefix="Invalid failed_part_ids provided: ",
                )
            )
        )
        if not selected_part_ids:
            raise DomainValidationError(
                "failed_part_ids must contain at least one part."
            )

        failed_part_specs: list[TicketPartSpec] = []
        target_technician_ids: set[int] = set()
        for part_spec_id in selected_part_ids:
            part_spec = all_part_specs[part_spec_id]
            if not part_spec.is_completed:
                raise DomainValidationError(
                    f"Ticket part #{part_spec_id} is not completed and cannot fail QC."
                )
            if not part_spec.completed_by_id:
                raise DomainValidationError(
                    f"Ticket part #{part_spec_id} has no completion owner."
                )
            failed_part_specs.append(part_spec)
            target_technician_ids.add(int(part_spec.completed_by_id))

        from_status = locked_ticket.mark_qc_fail(clear_claim=True)
        transition_metadata_payload = {
            "failed_part_spec_ids": [part_spec.id for part_spec in failed_part_specs],
            "target_technician_ids": sorted(target_technician_ids),
            **(transition_metadata or {}),
        }
        transition = cls.log_ticket_transition(
            ticket=locked_ticket,
            from_status=from_status,
            to_status=locked_ticket.status,
            action=TicketTransitionAction.QC_FAIL,
            actor_user_id=actor_user_id,
            note=note,
            metadata=transition_metadata_payload,
        )
        failed_part_labels_by_technician: dict[int, list[str]] = defaultdict(list)
        for part_spec in failed_part_specs:
            completion_owner_id = (
                int(part_spec.completed_by_id) if part_spec.completed_by_id else None
            )
            latest_completion = (
                TicketPartCompletion.all_objects.filter(
                    ticket_part_spec_id=part_spec.id,
                )
                .order_by("-completed_at", "-id")
                .first()
            )
            TicketPartQCFailure.objects.create(
                ticket=locked_ticket,
                ticket_part_spec=part_spec,
                qc_fail_transition=transition,
                technician_id=completion_owner_id,
                ticket_part_completion=latest_completion,
                note=str(note or "").strip(),
                metadata={"failed_part_spec_id": part_spec.id},
            )
            part_spec.is_completed = False
            part_spec.completed_by_id = None
            part_spec.completed_at = None
            part_spec.completion_note = ""
            part_spec.needs_rework = True
            part_spec.rework_for_technician_id = completion_owner_id
            part_spec.save(
                update_fields=[
                    "is_completed",
                    "completed_by",
                    "completed_at",
                    "completion_note",
                    "needs_rework",
                    "rework_for_technician",
                ]
            )
            if completion_owner_id:
                part_name = getattr(part_spec.inventory_item_part, "name", None) or str(
                    part_spec.inventory_item_part_id
                )
                failed_part_labels_by_technician[completion_owner_id].append(str(part_name))

        _, _, qc_status_update_xp, _, _ = cls._ticket_xp_rules()
        cls._award_qc_status_update_xp(
            ticket=locked_ticket,
            transition=transition,
            actor_user_id=actor_user_id,
            amount=qc_status_update_xp,
        )
        UserNotificationService.notify_ticket_qc_fail(
            ticket=locked_ticket,
            actor_user_id=actor_user_id,
            technician_ids=sorted(target_technician_ids),
            failed_parts_by_technician={
                user_id: tuple(part_names)
                for user_id, part_names in failed_part_labels_by_technician.items()
            },
        )
        return locked_ticket

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
