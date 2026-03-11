from __future__ import annotations

from django.db import models
from django.db.models.functions import Coalesce

from core.utils.constants import (
    TicketColor,
    TicketStatus,
    TicketTransitionAction,
    WorkSessionStatus,
)

ACTIVE_WORKFLOW_STATUSES = (
    TicketStatus.UNDER_REVIEW,
    TicketStatus.NEW,
    TicketStatus.ASSIGNED,
    TicketStatus.IN_PROGRESS,
    TicketStatus.WAITING_QC,
    TicketStatus.REWORK,
)


class TicketQuerySet(models.QuerySet):
    def active_workflow(self):
        return self.filter(status__in=ACTIVE_WORKFLOW_STATUSES)

    def in_progress(self):
        return self.filter(status=TicketStatus.IN_PROGRESS)

    def for_inventory_item(self, inventory_item):
        return self.filter(inventory_item=inventory_item)

    def for_technician(self, *, technician_id: int):
        return self.filter(technician_id=technician_id)

    def claimable_for_technician(self, *, technician_id: int):
        base_pending_part_filter = models.Q(
            part_specs__deleted_at__isnull=True,
            part_specs__is_completed=False,
        )
        rework_pending_filter = base_pending_part_filter & models.Q(
            part_specs__needs_rework=True,
            part_specs__rework_for_technician_id=technician_id,
        )
        return (
            self.filter(technician_id__isnull=True)
            .filter(
                (models.Q(status=TicketStatus.NEW) & base_pending_part_filter)
                | (models.Q(status=TicketStatus.REWORK) & rework_pending_filter)
            )
            .distinct()
        )


class TicketDomainManager(models.Manager.from_queryset(TicketQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

    def has_active_for_inventory_item(self, *, inventory_item) -> bool:
        return (
            self.get_queryset()
            .for_inventory_item(inventory_item)
            .active_workflow()
            .exists()
        )

    def has_in_progress_for_technician(self, *, technician_id: int) -> bool:
        return (
            self.get_queryset()
            .for_technician(technician_id=technician_id)
            .in_progress()
            .exists()
        )

    def backlog_black_plus_count(self, *, min_flag_minutes: int = 180) -> int:
        del min_flag_minutes
        return (
            self.get_queryset()
            .active_workflow()
            .filter(flag_color=TicketColor.RED)
            .count()
        )

    def claimable_for_technician(self, *, technician_id: int):
        return self.get_queryset().claimable_for_technician(technician_id=technician_id)


class WorkSessionQuerySet(models.QuerySet):
    def open(self):
        return self.filter(
            status__in=[WorkSessionStatus.RUNNING, WorkSessionStatus.PAUSED]
        )

    def paused(self):
        return self.filter(status=WorkSessionStatus.PAUSED)

    def for_ticket(self, ticket):
        return self.filter(ticket=ticket)

    def for_technician(self, *, technician_id: int):
        return self.filter(technician_id=technician_id)


class WorkSessionDomainManager(models.Manager.from_queryset(WorkSessionQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

    def has_open_for_ticket(self, *, ticket) -> bool:
        return self.get_queryset().for_ticket(ticket).open().exists()

    def has_open_for_technician(self, *, technician_id: int) -> bool:
        return (
            self.get_queryset()
            .for_technician(technician_id=technician_id)
            .open()
            .filter(
                ticket__deleted_at__isnull=True,
                ticket__status=TicketStatus.IN_PROGRESS,
                ticket__technician_id=technician_id,
            )
            .exists()
        )

    def get_open_for_ticket_and_technician(self, *, ticket, technician_id: int):
        return (
            self.get_queryset()
            .for_ticket(ticket)
            .for_technician(technician_id=technician_id)
            .open()
            .order_by("-created_at")
            .first()
        )

    def get_latest_for_ticket_and_technician(self, *, ticket, technician_id: int):
        return (
            self.get_queryset()
            .for_ticket(ticket)
            .for_technician(technician_id=technician_id)
            .order_by("-created_at", "-id")
            .first()
        )

    def paused_sessions(self, *, technician_id: int | None = None):
        queryset = self.get_queryset().paused()
        if technician_id is not None:
            queryset = queryset.for_technician(technician_id=technician_id)
        return queryset

    def for_technician_overlapping_window(
        self, *, technician_id: int, window_start, window_end
    ):
        return (
            self.get_queryset()
            .for_technician(technician_id=technician_id)
            .filter(started_at__lt=window_end)
            .filter(
                models.Q(ended_at__isnull=True) | models.Q(ended_at__gte=window_start)
            )
        )

    def total_active_seconds_for_ticket(self, *, ticket) -> int:
        aggregate = (
            self.get_queryset()
            .for_ticket(ticket)
            .aggregate(total_seconds=Coalesce(models.Sum("active_seconds"), 0))
        )
        return int(aggregate.get("total_seconds") or 0)


class TicketTransitionDomainManager(models.Manager):
    def has_qc_fail_for_ticket(self, *, ticket) -> bool:
        return self.filter(
            ticket=ticket, action=TicketTransitionAction.QC_FAIL
        ).exists()


class WorkSessionTransitionDomainManager(models.Manager):
    def history_for_ticket(self, *, ticket):
        return (
            self.filter(ticket=ticket)
            .select_related("work_session", "actor")
            .order_by("-event_at", "-id")
        )
