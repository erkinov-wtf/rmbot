from django.db import models

from core.models import AppendOnlyModel, SoftDeleteModel, TimestampedModel
from core.utils.constants import (
    TicketStatus,
    TicketTransitionAction,
    WorkSessionStatus,
    WorkSessionTransitionAction,
)

ACTIVE_TICKET_STATUSES = [
    TicketStatus.NEW,
    TicketStatus.ASSIGNED,
    TicketStatus.IN_PROGRESS,
    TicketStatus.WAITING_QC,
    TicketStatus.REWORK,
]


class Ticket(TimestampedModel, SoftDeleteModel):
    bike = models.ForeignKey(
        "bike.Bike", on_delete=models.PROTECT, related_name="tickets"
    )
    master = models.ForeignKey(
        "account.User", on_delete=models.PROTECT, related_name="created_tickets"
    )
    technician = models.ForeignKey(
        "account.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )
    title = models.CharField(max_length=255, blank=True, null=True)
    srt_total_minutes = models.PositiveIntegerField(default=0)
    flag_minutes = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=TicketStatus,
        default=TicketStatus.NEW,
        db_index=True,
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    done_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["technician", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["bike"],
                condition=models.Q(
                    status__in=ACTIVE_TICKET_STATUSES, deleted_at__isnull=True
                ),
                name="unique_active_ticket_per_bike",
            ),
            models.UniqueConstraint(
                fields=["technician"],
                condition=models.Q(
                    status=TicketStatus.IN_PROGRESS,
                    technician__isnull=False,
                    deleted_at__isnull=True,
                ),
                name="unique_in_progress_ticket_per_technician",
            ),
        ]

    def __str__(self) -> str:
        return f"Ticket#{self.pk} {self.bike.bike_code} [{self.status}]"


class WorkSession(TimestampedModel, SoftDeleteModel):
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="work_sessions"
    )
    technician = models.ForeignKey(
        "account.User", on_delete=models.CASCADE, related_name="work_sessions"
    )
    status = models.CharField(
        max_length=20,
        choices=WorkSessionStatus,
        default=WorkSessionStatus.RUNNING,
        db_index=True,
    )
    started_at = models.DateTimeField(db_index=True)
    last_started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    active_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=["ticket", "status"]),
            models.Index(fields=["technician", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["ticket"],
                condition=models.Q(
                    status__in=[WorkSessionStatus.RUNNING, WorkSessionStatus.PAUSED],
                    deleted_at__isnull=True,
                ),
                name="unique_open_work_session_per_ticket",
            ),
            models.UniqueConstraint(
                fields=["technician"],
                condition=models.Q(
                    status__in=[WorkSessionStatus.RUNNING, WorkSessionStatus.PAUSED],
                    deleted_at__isnull=True,
                ),
                name="unique_open_work_session_per_technician",
            ),
        ]

    def __str__(self) -> str:
        return f"WorkSession#{self.pk} ticket={self.ticket_id} tech={self.technician_id} [{self.status}]"


class WorkSessionTransition(AppendOnlyModel):
    work_session = models.ForeignKey(
        WorkSession,
        on_delete=models.CASCADE,
        related_name="transitions",
    )
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="work_session_transitions",
    )
    from_status = models.CharField(
        max_length=20,
        choices=WorkSessionStatus,
        null=True,
        blank=True,
    )
    to_status = models.CharField(max_length=20, choices=WorkSessionStatus)
    action = models.CharField(
        max_length=20, choices=WorkSessionTransitionAction, db_index=True
    )
    actor = models.ForeignKey(
        "account.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    event_at = models.DateTimeField(db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["work_session", "event_at"]),
            models.Index(fields=["ticket", "event_at"]),
            models.Index(fields=["action", "event_at"]),
        ]

    def __str__(self) -> str:
        return (
            f"WorkSessionTransition #{self.pk} ws={self.work_session_id} "
            f"{self.from_status}>{self.to_status} ({self.action})"
        )


class TicketTransition(AppendOnlyModel):
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="transitions"
    )
    from_status = models.CharField(
        max_length=20, choices=TicketStatus, null=True, blank=True
    )
    to_status = models.CharField(max_length=20, choices=TicketStatus)
    action = models.CharField(
        max_length=30, choices=TicketTransitionAction, db_index=True
    )
    actor = models.ForeignKey(
        "account.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    note = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["ticket", "created_at"]),
            models.Index(fields=["action", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"TicketTransition #{self.pk} {self.from_status}>{self.to_status} ({self.action})"
