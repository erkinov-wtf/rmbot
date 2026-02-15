import math
from datetime import datetime

from django.db import IntegrityError, models
from django.utils import timezone

from core.models import AppendOnlyModel, SoftDeleteModel, TimestampedModel
from core.utils.constants import (
    SLAAutomationDeliveryAttemptStatus,
    SLAAutomationEventSeverity,
    SLAAutomationEventStatus,
    TicketColor,
    TicketStatus,
    TicketTransitionAction,
    WorkSessionStatus,
    WorkSessionTransitionAction,
)
from ticket.managers import (
    SLAAutomationDeliveryAttemptDomainManager,
    SLAAutomationEventDomainManager,
    StockoutIncidentDomainManager,
    TicketDomainManager,
    TicketTransitionDomainManager,
    WorkSessionDomainManager,
    WorkSessionTransitionDomainManager,
)

ACTIVE_TICKET_STATUSES = [
    TicketStatus.UNDER_REVIEW,
    TicketStatus.NEW,
    TicketStatus.ASSIGNED,
    TicketStatus.IN_PROGRESS,
    TicketStatus.WAITING_QC,
    TicketStatus.REWORK,
]


class Ticket(TimestampedModel, SoftDeleteModel):
    domain = TicketDomainManager()

    inventory_item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.PROTECT,
        related_name="tickets",
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
    total_duration = models.PositiveIntegerField(default=0)
    approved_by = models.ForeignKey(
        "account.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_tickets",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    flag_minutes = models.PositiveIntegerField(default=0)
    flag_color = models.CharField(
        max_length=20,
        choices=TicketColor,
        default=TicketColor.GREEN,
        db_index=True,
    )
    xp_amount = models.PositiveIntegerField(default=0)
    is_manual = models.BooleanField(default=False, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=TicketStatus,
        default=TicketStatus.UNDER_REVIEW,
        db_index=True,
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["technician", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["inventory_item"],
                condition=models.Q(
                    status__in=ACTIVE_TICKET_STATUSES, deleted_at__isnull=True
                ),
                name="unique_active_ticket_per_inventory_item",
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

    def assign_to_technician(self, *, technician_id: int, assigned_at=None) -> str:
        from_status = self.status
        if self.status not in (
            TicketStatus.UNDER_REVIEW,
            TicketStatus.NEW,
            TicketStatus.ASSIGNED,
            TicketStatus.REWORK,
        ):
            raise ValueError("Ticket cannot be assigned in current status.")
        if (
            self.status in (TicketStatus.UNDER_REVIEW, TicketStatus.NEW)
            and not self.is_admin_reviewed
        ):
            raise ValueError("Ticket must pass admin review before assignment.")

        self.technician_id = technician_id
        self.assigned_at = assigned_at or timezone.now()
        update_fields = ["technician", "assigned_at"]
        if self.status in (TicketStatus.UNDER_REVIEW, TicketStatus.NEW):
            self.status = TicketStatus.ASSIGNED
            update_fields.append("status")
        self.save(update_fields=update_fields)
        return from_status

    @property
    def is_admin_reviewed(self) -> bool:
        return bool(self.approved_by_id and self.approved_at)

    def mark_admin_review_approved(self, *, approved_by_id: int, approved_at=None):
        if not approved_by_id:
            raise ValueError("approved_by_id is required for admin review approval.")
        self.approved_by_id = approved_by_id
        self.approved_at = approved_at or timezone.now()
        update_fields = ["approved_by", "approved_at"]
        if self.status == TicketStatus.UNDER_REVIEW:
            self.status = TicketStatus.NEW
            update_fields.append("status")
        self.save(update_fields=update_fields)

    @staticmethod
    def flag_color_from_minutes(*, total_minutes: int) -> str:
        minutes = max(int(total_minutes or 0), 0)
        if minutes <= 30:
            return TicketColor.GREEN
        if minutes <= 60:
            return TicketColor.YELLOW
        return TicketColor.RED

    def apply_auto_metrics(self, *, total_minutes: int, xp_divisor: int) -> None:
        normalized_minutes = max(int(total_minutes or 0), 0)
        normalized_divisor = max(int(xp_divisor or 0), 1)
        self.total_duration = normalized_minutes
        self.flag_minutes = normalized_minutes
        self.flag_color = self.flag_color_from_minutes(total_minutes=normalized_minutes)
        self.xp_amount = math.ceil(normalized_minutes / normalized_divisor)
        self.is_manual = False

    def apply_manual_metrics(self, *, flag_color: str, xp_amount: int) -> None:
        self.flag_color = str(flag_color)
        self.xp_amount = max(int(xp_amount or 0), 0)
        self.is_manual = True

    def start_progress(self, *, actor_user_id: int, started_at=None) -> str:
        from_status = self.status
        if self.status not in (TicketStatus.ASSIGNED, TicketStatus.REWORK):
            raise ValueError("Ticket can be started only from ASSIGNED or REWORK.")
        if not self.technician_id:
            raise ValueError("Ticket has no assigned technician.")
        if self.technician_id != actor_user_id:
            raise ValueError("Only assigned technician can start this ticket.")

        self.status = TicketStatus.IN_PROGRESS
        update_fields = ["status"]
        if not self.started_at:
            self.started_at = started_at or timezone.now()
            update_fields.append("started_at")

        try:
            self.save(update_fields=update_fields)
        except IntegrityError as exc:
            raise ValueError("Technician already has an IN_PROGRESS ticket.") from exc
        return from_status

    def move_to_waiting_qc(self, *, actor_user_id: int) -> str:
        from_status = self.status
        if self.status != TicketStatus.IN_PROGRESS:
            raise ValueError("Ticket can be sent to QC only from IN_PROGRESS.")
        if not self.technician_id or self.technician_id != actor_user_id:
            raise ValueError("Only assigned technician can send ticket to QC.")

        self.status = TicketStatus.WAITING_QC
        self.save(update_fields=["status"])
        return from_status

    def mark_qc_pass(self, *, finished_at=None) -> str:
        from_status = self.status
        if self.status != TicketStatus.WAITING_QC:
            raise ValueError("QC PASS allowed only from WAITING_QC.")
        if not self.technician_id:
            raise ValueError("Ticket must have an assigned technician before QC PASS.")

        self.status = TicketStatus.DONE
        self.finished_at = finished_at or timezone.now()
        self.save(update_fields=["status", "finished_at"])
        return from_status

    def mark_qc_fail(self) -> str:
        from_status = self.status
        if self.status != TicketStatus.WAITING_QC:
            raise ValueError("QC FAIL allowed only from WAITING_QC.")

        self.status = TicketStatus.REWORK
        self.finished_at = None
        self.save(update_fields=["status", "finished_at"])
        return from_status

    def add_transition(
        self,
        *,
        action: str,
        to_status: str,
        from_status: str | None = None,
        actor_user_id: int | None = None,
        note: str | None = None,
        metadata: dict | None = None,
    ):
        return TicketTransition.objects.create(
            ticket=self,
            from_status=from_status,
            to_status=to_status,
            action=action,
            actor_id=actor_user_id,
            note=note,
            metadata=metadata or {},
        )

    def __str__(self) -> str:
        return f"Ticket#{self.pk} {self.inventory_item.serial_number} [{self.status}]"


class TicketPartSpec(TimestampedModel, SoftDeleteModel):
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="part_specs"
    )
    inventory_item_part = models.ForeignKey(
        "inventory.InventoryItemPart",
        on_delete=models.PROTECT,
        related_name="ticket_specs",
    )
    color = models.CharField(max_length=20, choices=TicketColor, db_index=True)
    comment = models.TextField(blank=True, default="")
    minutes = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(
                fields=["ticket", "inventory_item_part"],
                name="ticket_tick_ticket__e64d6c_idx",
            ),
            models.Index(
                fields=["ticket", "color"],
                name="ticket_tick_ticket__235363_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["ticket", "inventory_item_part"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_ticket_part_spec_per_part",
            )
        ]

    def __str__(self) -> str:
        return (
            f"TicketPartSpec#{self.pk} ticket={self.ticket_id} "
            f"part={self.inventory_item_part_id} color={self.color}"
        )


class StockoutIncident(TimestampedModel):
    domain = StockoutIncidentDomainManager()

    started_at = models.DateTimeField(db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    duration_minutes = models.PositiveIntegerField(default=0)
    ready_count_at_start = models.PositiveIntegerField(default=0)
    ready_count_at_end = models.PositiveIntegerField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_active", "started_at"]),
            models.Index(fields=["started_at", "ended_at"]),
        ]

    @classmethod
    def start_incident(
        cls,
        *,
        started_at,
        ready_count_at_start: int,
        window_context: dict[str, object],
    ) -> "StockoutIncident":
        payload = {
            "timezone": window_context["timezone"],
            "business_start_hour": window_context["start_hour"],
            "business_end_hour": window_context["end_hour"],
            "working_weekdays": window_context["working_weekdays"],
            "holiday_dates": window_context["holiday_dates"],
        }
        return cls.objects.create(
            started_at=started_at,
            is_active=True,
            ready_count_at_start=max(int(ready_count_at_start), 0),
            payload=payload,
        )

    def resolve(self, *, ended_at, ready_count_at_end: int) -> int:
        duration_minutes = max(
            int((ended_at - self.started_at).total_seconds() // 60),
            0,
        )
        self.ended_at = ended_at
        self.is_active = False
        self.ready_count_at_end = max(int(ready_count_at_end), 0)
        self.duration_minutes = duration_minutes
        self.save(
            update_fields=[
                "ended_at",
                "is_active",
                "ready_count_at_end",
                "duration_minutes",
                "updated_at",
            ]
        )
        return duration_minutes

    def overlap_minutes(self, *, start_dt, end_dt, now_utc) -> int:
        effective_end = self.ended_at or now_utc
        overlap_start = max(self.started_at, start_dt)
        overlap_end = min(effective_end, end_dt)
        if overlap_end <= overlap_start:
            return 0
        return max(int((overlap_end - overlap_start).total_seconds() // 60), 0)

    def __str__(self) -> str:
        status = "active" if self.is_active else "closed"
        return f"StockoutIncident#{self.pk} [{status}] start={self.started_at.isoformat()} end={self.ended_at}"


class SLAAutomationEvent(AppendOnlyModel):
    domain = SLAAutomationEventDomainManager()

    rule_key = models.CharField(max_length=64, db_index=True)
    status = models.CharField(
        max_length=20, choices=SLAAutomationEventStatus, db_index=True
    )
    severity = models.CharField(
        max_length=20,
        choices=SLAAutomationEventSeverity,
        default=SLAAutomationEventSeverity.WARNING,
    )
    metric_value = models.FloatField(default=0)
    threshold_value = models.FloatField(default=0)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["rule_key", "created_at"]),
            models.Index(fields=["status", "created_at"]),
        ]

    @classmethod
    def create_event(
        cls,
        *,
        rule_key: str,
        status: str,
        severity: str,
        metric_value: float,
        threshold_value: float,
        payload: dict,
    ) -> "SLAAutomationEvent":
        return cls.objects.create(
            rule_key=rule_key,
            status=status,
            severity=severity,
            metric_value=metric_value,
            threshold_value=threshold_value,
            payload=payload,
        )

    def payload_data(self) -> dict:
        return self.payload if isinstance(self.payload, dict) else {}

    def is_repeat(self) -> bool:
        return self.payload_data().get("repeat") is True

    def evaluated_at_or_created(self, *, fallback_now: datetime) -> datetime:
        raw = self.payload_data().get("evaluated_at")
        if isinstance(raw, str):
            try:
                parsed = datetime.fromisoformat(raw)
                if parsed.tzinfo is None:
                    parsed = timezone.make_aware(parsed, timezone.utc)
                return parsed
            except ValueError:
                pass
        return self.created_at or fallback_now

    def __str__(self) -> str:
        return f"SLAAutomationEvent#{self.pk} rule={self.rule_key} status={self.status} metric={self.metric_value}"


class SLAAutomationDeliveryAttempt(AppendOnlyModel):
    domain = SLAAutomationDeliveryAttemptDomainManager()

    event = models.ForeignKey(
        SLAAutomationEvent,
        on_delete=models.CASCADE,
        related_name="delivery_attempts",
    )
    attempt_number = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=SLAAutomationDeliveryAttemptStatus,
        db_index=True,
    )
    delivered = models.BooleanField(default=False, db_index=True)
    should_retry = models.BooleanField(default=False, db_index=True)
    retry_backoff_seconds = models.PositiveIntegerField(default=0)
    task_id = models.CharField(max_length=128, blank=True, default="")
    reason = models.CharField(max_length=64, blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["event", "created_at"]),
            models.Index(fields=["event", "attempt_number"]),
            models.Index(fields=["status", "created_at"]),
        ]

    @staticmethod
    def status_from_response(*, response: dict) -> str:
        if response.get("reason") == "already_delivered":
            return SLAAutomationDeliveryAttemptStatus.SKIPPED
        if response.get("delivered") is True:
            return SLAAutomationDeliveryAttemptStatus.SUCCESS
        return SLAAutomationDeliveryAttemptStatus.FAILED

    @staticmethod
    def reason_from_response(*, response: dict) -> str:
        reason = response.get("reason")
        if not isinstance(reason, str):
            return ""
        return reason[:64]

    @classmethod
    def create_from_delivery_response(
        cls,
        *,
        event: SLAAutomationEvent,
        attempt_number: int,
        task_id: str,
        response: dict,
        should_retry: bool,
        retry_backoff_seconds: int,
    ) -> "SLAAutomationDeliveryAttempt":
        return cls.objects.create(
            event=event,
            attempt_number=max(int(attempt_number), 1),
            status=cls.status_from_response(response=response),
            delivered=bool(response.get("delivered")),
            should_retry=bool(should_retry),
            retry_backoff_seconds=max(int(retry_backoff_seconds), 0),
            task_id=str(task_id or "")[:128],
            reason=cls.reason_from_response(response=response),
            payload=response,
        )

    def __str__(self) -> str:
        return (
            f"SLAAutomationDeliveryAttempt#{self.pk} event={self.event_id} "
            f"attempt={self.attempt_number} status={self.status}"
        )


class WorkSession(TimestampedModel, SoftDeleteModel):
    domain = WorkSessionDomainManager()

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

    @classmethod
    def start_for_ticket(cls, *, ticket: Ticket, actor_user_id: int, started_at=None):
        if cls.domain.has_open_for_ticket(ticket=ticket):
            raise ValueError("Ticket already has an active work session.")
        if cls.domain.has_open_for_technician(technician_id=actor_user_id):
            raise ValueError("Technician already has an active work session.")

        now_dt = started_at or timezone.now()
        session = cls.objects.create(
            ticket=ticket,
            technician_id=actor_user_id,
            status=WorkSessionStatus.RUNNING,
            started_at=now_dt,
            last_started_at=now_dt,
            active_seconds=0,
        )
        session.add_transition(
            action=WorkSessionTransitionAction.STARTED,
            from_status=None,
            to_status=WorkSessionStatus.RUNNING,
            actor_user_id=actor_user_id,
            event_at=now_dt,
        )
        return session

    def add_transition(
        self,
        *,
        action: str,
        from_status: str | None,
        to_status: str,
        actor_user_id: int,
        event_at,
        metadata: dict | None = None,
    ):
        return WorkSessionTransition.objects.create(
            work_session=self,
            ticket=self.ticket,
            action=action,
            from_status=from_status,
            to_status=to_status,
            actor_id=actor_user_id,
            event_at=event_at,
            metadata=metadata or {},
        )

    def recalculate_active_seconds(self, *, until_dt) -> int:
        transitions = self.transitions.order_by("event_at", "id").only(
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

    def pause(self, *, actor_user_id: int, paused_at=None) -> None:
        if self.status != WorkSessionStatus.RUNNING:
            raise ValueError("Work session can be paused only from RUNNING state.")

        now_dt = paused_at or timezone.now()
        self.add_transition(
            action=WorkSessionTransitionAction.PAUSED,
            from_status=WorkSessionStatus.RUNNING,
            to_status=WorkSessionStatus.PAUSED,
            actor_user_id=actor_user_id,
            event_at=now_dt,
        )
        self.active_seconds = self.recalculate_active_seconds(until_dt=now_dt)
        self.status = WorkSessionStatus.PAUSED
        self.last_started_at = None
        self.save(update_fields=["active_seconds", "status", "last_started_at"])

    def resume(self, *, actor_user_id: int, resumed_at=None) -> None:
        if self.status != WorkSessionStatus.PAUSED:
            raise ValueError("Work session can be resumed only from PAUSED state.")

        now_dt = resumed_at or timezone.now()
        self.add_transition(
            action=WorkSessionTransitionAction.RESUMED,
            from_status=WorkSessionStatus.PAUSED,
            to_status=WorkSessionStatus.RUNNING,
            actor_user_id=actor_user_id,
            event_at=now_dt,
        )
        self.status = WorkSessionStatus.RUNNING
        self.last_started_at = now_dt
        self.active_seconds = self.recalculate_active_seconds(until_dt=now_dt)
        self.save(update_fields=["status", "last_started_at", "active_seconds"])

    def stop(self, *, actor_user_id: int, stopped_at=None) -> None:
        if self.status not in (WorkSessionStatus.RUNNING, WorkSessionStatus.PAUSED):
            raise ValueError(
                "Work session can be stopped only from RUNNING or PAUSED state."
            )

        now_dt = stopped_at or timezone.now()
        self.add_transition(
            action=WorkSessionTransitionAction.STOPPED,
            from_status=self.status,
            to_status=WorkSessionStatus.STOPPED,
            actor_user_id=actor_user_id,
            event_at=now_dt,
        )
        self.active_seconds = self.recalculate_active_seconds(until_dt=now_dt)
        self.status = WorkSessionStatus.STOPPED
        self.last_started_at = None
        self.ended_at = now_dt
        self.save(
            update_fields=["active_seconds", "status", "last_started_at", "ended_at"]
        )

    def __str__(self) -> str:
        return f"WorkSession#{self.pk} ticket={self.ticket_id} tech={self.technician_id} [{self.status}]"


class WorkSessionTransition(AppendOnlyModel):
    domain = WorkSessionTransitionDomainManager()

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
    domain = TicketTransitionDomainManager()

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
