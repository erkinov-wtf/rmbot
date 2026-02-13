from django.contrib import admin

from core.admin import BaseModelAdmin
from payroll.models import (
    PayrollAllowanceGateDecision,
    PayrollMonthly,
    PayrollMonthlyLine,
)


class PayrollAllowanceGateDecisionInline(admin.TabularInline):
    model = PayrollAllowanceGateDecision
    extra = 0
    can_delete = False
    fields = (
        "decision",
        "decided_by",
        "affected_lines_count",
        "total_allowance_delta",
        "note",
        "created_at",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PayrollMonthly)
class PayrollMonthlyAdmin(BaseModelAdmin):
    list_display = (
        "id",
        "month",
        "status",
        "total_raw_xp",
        "total_paid_xp",
        "total_payout_amount",
        "closed_at",
        "approved_at",
    )
    list_filter = ("status",)
    search_fields = ("id", "month")
    readonly_fields = (
        "month",
        "status",
        "closed_at",
        "approved_at",
        "closed_by",
        "approved_by",
        "rules_snapshot",
        "total_raw_xp",
        "total_paid_xp",
        "total_fix_salary",
        "total_bonus_amount",
        "total_allowance_amount",
        "total_payout_amount",
        "created_at",
        "updated_at",
    )
    inlines = (PayrollAllowanceGateDecisionInline,)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PayrollMonthlyLine)
class PayrollMonthlyLineAdmin(BaseModelAdmin):
    list_display = (
        "id",
        "payroll_monthly",
        "user",
        "level",
        "raw_xp",
        "paid_xp",
        "total_amount",
    )
    list_filter = ("level",)
    search_fields = ("id", "payroll_monthly__month", "user__username")
    readonly_fields = (
        "payroll_monthly",
        "user",
        "level",
        "raw_xp",
        "paid_xp",
        "paid_xp_cap",
        "fix_salary",
        "allowance_amount",
        "bonus_rate",
        "bonus_amount",
        "total_amount",
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


@admin.register(PayrollAllowanceGateDecision)
class PayrollAllowanceGateDecisionAdmin(BaseModelAdmin):
    list_display = (
        "id",
        "payroll_monthly",
        "decision",
        "decided_by",
        "affected_lines_count",
        "total_allowance_delta",
        "created_at",
    )
    list_filter = ("decision",)
    search_fields = ("id", "payroll_monthly__month", "decided_by__username")
    readonly_fields = (
        "payroll_monthly",
        "decision",
        "decided_by",
        "affected_lines_count",
        "total_allowance_delta",
        "note",
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
