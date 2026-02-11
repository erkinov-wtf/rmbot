from django.contrib import admin

from core.admin import BaseModelAdmin
from rules.models import RulesConfigState, RulesConfigVersion


@admin.register(RulesConfigVersion)
class RulesConfigVersionAdmin(BaseModelAdmin):
    list_display = ("id", "version", "action", "created_by", "created_at")
    list_filter = ("action",)
    search_fields = ("id", "version", "checksum", "created_by__username")
    readonly_fields = (
        "version",
        "action",
        "config",
        "diff",
        "checksum",
        "reason",
        "created_by",
        "source_version",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RulesConfigState)
class RulesConfigStateAdmin(BaseModelAdmin):
    list_display = ("id", "active_version", "cache_key", "updated_at")
    readonly_fields = (
        "singleton",
        "active_version",
        "cache_key",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
