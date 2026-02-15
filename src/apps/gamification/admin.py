from django.contrib import admin

from core.admin import BaseModelAdmin
from gamification.models import LevelUpCouponEvent, WeeklyLevelEvaluation, XPTransaction


@admin.register(XPTransaction)
class XPTransactionAdmin(BaseModelAdmin):
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


@admin.register(WeeklyLevelEvaluation)
class WeeklyLevelEvaluationAdmin(BaseModelAdmin):
    list_display = (
        "id",
        "user",
        "week_start",
        "raw_xp",
        "previous_level",
        "new_level",
        "is_level_up",
        "created_at",
    )
    list_filter = ("is_level_up", "previous_level", "new_level")
    search_fields = ("id", "user__username", "week_start")
    readonly_fields = (
        "user",
        "week_start",
        "week_end",
        "raw_xp",
        "previous_level",
        "new_level",
        "is_level_up",
        "rules_version",
        "rules_cache_key",
        "evaluated_by",
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


@admin.register(LevelUpCouponEvent)
class LevelUpCouponEventAdmin(BaseModelAdmin):
    list_display = (
        "id",
        "user",
        "week_start",
        "amount",
        "currency",
        "reference",
        "created_at",
    )
    list_filter = ("currency",)
    search_fields = ("id", "reference", "user__username", "week_start")
    readonly_fields = (
        "user",
        "evaluation",
        "week_start",
        "amount",
        "currency",
        "reference",
        "description",
        "issued_by",
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
