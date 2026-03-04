from django.contrib import admin

from core.admin import BaseModelAdmin
from ticket.models import (
    Ticket,
    TicketPartCompletion,
    TicketPartQCFailure,
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
        "is_completed",
        "completed_by",
        "needs_rework",
        "rework_for_technician",
        "created_at",
    )
    list_filter = ("color", "is_completed", "needs_rework")
    search_fields = ("id", "ticket__id", "inventory_item_part__name")


@admin.register(TicketPartCompletion)
class TicketPartCompletionAdmin(BaseModelAdmin):
    list_display = (
        "id",
        "ticket",
        "ticket_part_spec",
        "technician",
        "is_rework",
        "completed_at",
        "created_at",
    )
    list_filter = ("is_rework",)
    search_fields = ("id", "ticket__id", "ticket_part_spec__id", "technician__username")
    readonly_fields = (
        "ticket",
        "ticket_part_spec",
        "technician",
        "completed_at",
        "note",
        "is_rework",
        "source_qc_fail_transition",
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


@admin.register(TicketPartQCFailure)
class TicketPartQCFailureAdmin(BaseModelAdmin):
    list_display = (
        "id",
        "ticket",
        "ticket_part_spec",
        "technician",
        "qc_fail_transition",
        "created_at",
    )
    search_fields = ("id", "ticket__id", "ticket_part_spec__id", "technician__username")
    readonly_fields = (
        "ticket",
        "ticket_part_spec",
        "qc_fail_transition",
        "technician",
        "ticket_part_completion",
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
