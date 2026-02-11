from django.contrib import admin

from core.admin import BaseModelAdmin
from gamification.models import XPLedger


@admin.register(XPLedger)
class XPLedgerAdmin(BaseModelAdmin):
    list_display = ("id", "user", "amount", "entry_type", "reference", "created_at")
    list_filter = ("entry_type",)
    search_fields = ("id", "reference", "user__username")
    readonly_fields = (
        "user",
        "amount",
        "entry_type",
        "reference",
        "description",
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
