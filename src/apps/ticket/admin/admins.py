from django.contrib import admin

from core.admin import BaseModelAdmin
from ticket.models import Ticket, TicketTransition, WorkSession


@admin.register(Ticket)
class TicketAdmin(BaseModelAdmin):
    list_display = ("id", "bike", "master", "technician", "status", "srt_total_minutes", "created_at")
    list_filter = ("status",)
    search_fields = ("id", "bike__bike_code", "master__username", "technician__username")


@admin.register(WorkSession)
class WorkSessionAdmin(BaseModelAdmin):
    list_display = ("id", "ticket", "technician", "status", "active_seconds", "started_at", "ended_at")
    list_filter = ("status",)
    search_fields = ("id", "ticket__id", "technician__username")


@admin.register(TicketTransition)
class TicketTransitionAdmin(BaseModelAdmin):
    list_display = ("id", "ticket", "action", "from_status", "to_status", "actor", "created_at")
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
