from __future__ import annotations

from django.db import models
from django.db.models import Q

from core.utils.constants import (
    SLAAutomationDeliveryAttemptStatus,
    TicketStatus,
    TicketTransitionAction,
    WorkSessionStatus,
)

ACTIVE_WORKFLOW_STATUSES = (
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

    def for_bike(self, bike):
        return self.filter(bike=bike)

    def for_technician(self, *, technician_id: int):
        return self.filter(technician_id=technician_id)


class TicketDomainManager(models.Manager.from_queryset(TicketQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

    def has_active_for_bike(self, *, bike) -> bool:
        return self.get_queryset().for_bike(bike).active_workflow().exists()

    def has_in_progress_for_technician(self, *, technician_id: int) -> bool:
        return (
            self.get_queryset()
            .for_technician(technician_id=technician_id)
            .in_progress()
            .exists()
        )

    def backlog_black_plus_count(self, *, min_flag_minutes: int = 180) -> int:
        return (
            self.get_queryset()
            .active_workflow()
            .filter(flag_minutes__gt=max(min_flag_minutes, 0))
            .count()
        )


class StockoutIncidentQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def latest_started(self):
        return self.order_by("-started_at")

    def overlapping_window(self, *, start_dt, end_dt):
        return self.filter(started_at__lt=end_dt).filter(
            Q(ended_at__isnull=True) | Q(ended_at__gt=start_dt)
        )


class StockoutIncidentDomainManager(
    models.Manager.from_queryset(StockoutIncidentQuerySet)
):
    def latest_active(self):
        return self.get_queryset().active().latest_started().first()

    def latest_active_for_update(self):
        return self.get_queryset().select_for_update().active().latest_started().first()

    def list_overlapping_window(self, *, start_dt, end_dt):
        return self.get_queryset().overlapping_window(start_dt=start_dt, end_dt=end_dt)


class SLAAutomationEventQuerySet(models.QuerySet):
    def for_rule(self, *, rule_key: str):
        return self.filter(rule_key=rule_key)

    def latest_first(self):
        return self.order_by("-created_at")


class SLAAutomationEventDomainManager(
    models.Manager.from_queryset(SLAAutomationEventQuerySet)
):
    def latest_for_rule(self, *, rule_key: str):
        return self.get_queryset().for_rule(rule_key=rule_key).latest_first().first()

    def get_by_id(self, *, event_id: int):
        return self.get_queryset().filter(pk=event_id).first()


class SLAAutomationDeliveryAttemptQuerySet(models.QuerySet):
    def for_event(self, *, event_id: int):
        return self.filter(event_id=event_id)

    def successful(self):
        return self.filter(
            status=SLAAutomationDeliveryAttemptStatus.SUCCESS,
            delivered=True,
        )


class SLAAutomationDeliveryAttemptDomainManager(
    models.Manager.from_queryset(SLAAutomationDeliveryAttemptQuerySet)
):
    def has_success_for_event(self, *, event_id: int) -> bool:
        return self.get_queryset().for_event(event_id=event_id).successful().exists()


class WorkSessionQuerySet(models.QuerySet):
    def open(self):
        return self.filter(
            status__in=[WorkSessionStatus.RUNNING, WorkSessionStatus.PAUSED]
        )

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
