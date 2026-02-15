from django.contrib import admin

from core.admin import BaseModelAdmin
from ticket.models import (
    SLAAutomationDeliveryAttempt,
    SLAAutomationEvent,
    StockoutIncident,
    Ticket,
    TicketPartSpec,
    TicketTransition,
    WorkSession,
    WorkSessionTransition,
)


@admin.register(Ticket)
class TicketAdmin(BaseModelAdmin):
    list_display = (
        "id",
        "inventory_item",
        "master",
        "technician",
        "status",
        "total_duration",
        "xp_amount",
        "flag_color",
        "is_manual",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = (
        "id",
        "inventory_item__serial_number",
        "master__username",
        "technician__username",
    )


@admin.register(TicketPartSpec)
class TicketPartSpecAdmin(BaseModelAdmin):
    list_display = (
        "id",
        "ticket",
        "inventory_item_part",
        "color",
        "minutes",
        "created_at",
    )
    list_filter = ("color",)
    search_fields = ("id", "ticket__id", "inventory_item_part__name")


@admin.register(WorkSession)
class WorkSessionAdmin(BaseModelAdmin):
    list_display = (
        "id",
        "ticket",
        "technician",
        "status",
        "active_seconds",
        "started_at",
        "ended_at",
    )
    list_filter = ("status",)
    search_fields = ("id", "ticket__id", "technician__username")


@admin.register(TicketTransition)
class TicketTransitionAdmin(BaseModelAdmin):
    list_display = (
        "id",
        "ticket",
        "action",
        "from_status",
        "to_status",
        "actor",
        "created_at",
    )
    list_filter = ("action", "from_status", "to_status")
    search_fields = ("id", "ticket__id", "actor__username")
    readonly_fields = (
        "ticket",
        "from_status",
        "to_status",
        "action",
        "actor",
        "note",
        "metadata",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WorkSessionTransition)
class WorkSessionTransitionAdmin(BaseModelAdmin):
    list_display = (
        "id",
        "work_session",
        "ticket",
        "action",
        "from_status",
        "to_status",
        "actor",
        "event_at",
    )
    list_filter = ("action", "from_status", "to_status")
    search_fields = ("id", "work_session__id", "ticket__id", "actor__username")
    readonly_fields = (
        "work_session",
        "ticket",
        "from_status",
        "to_status",
        "action",
        "actor",
        "event_at",
        "metadata",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StockoutIncident)
class StockoutIncidentAdmin(BaseModelAdmin):
    list_display = (
        "id",
        "is_active",
        "started_at",
        "ended_at",
        "duration_minutes",
        "ready_count_at_start",
        "ready_count_at_end",
    )
    list_filter = ("is_active",)
    search_fields = ("id",)
    readonly_fields = (
        "started_at",
        "ended_at",
        "is_active",
        "duration_minutes",
        "ready_count_at_start",
        "ready_count_at_end",
        "payload",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SLAAutomationEvent)
class SLAAutomationEventAdmin(BaseModelAdmin):
    list_display = (
        "id",
        "rule_key",
        "status",
        "severity",
        "metric_value",
        "threshold_value",
        "created_at",
    )
    list_filter = ("rule_key", "status", "severity")
    search_fields = ("id", "rule_key")
    readonly_fields = (
        "rule_key",
        "status",
        "severity",
        "metric_value",
        "threshold_value",
        "payload",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SLAAutomationDeliveryAttempt)
class SLAAutomationDeliveryAttemptAdmin(BaseModelAdmin):
    list_display = (
        "id",
        "event",
        "attempt_number",
        "status",
        "delivered",
        "should_retry",
        "retry_backoff_seconds",
        "created_at",
    )
    list_filter = ("status", "delivered", "should_retry")
    search_fields = ("id", "event__id", "task_id")
    readonly_fields = (
        "event",
        "attempt_number",
        "status",
        "delivered",
        "should_retry",
        "retry_backoff_seconds",
        "task_id",
        "reason",
        "payload",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
