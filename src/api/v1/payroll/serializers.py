from rest_framework import serializers

from core.utils.constants import EmployeeLevel, PayrollAllowanceDecision
from payroll.models import (
    PayrollAllowanceGateDecision,
    PayrollMonthly,
    PayrollMonthlyLine,
)


class PayrollMonthlyLineSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    level_label = serializers.SerializerMethodField()

    class Meta:
        model = PayrollMonthlyLine
        fields = (
            "id",
            "user",
            "username",
            "level",
            "level_label",
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
        )
        read_only_fields = fields

    @staticmethod
    def get_level_label(obj: PayrollMonthlyLine) -> str:
        return str(EmployeeLevel(obj.level).label)


class PayrollAllowanceGateDecisionSerializer(serializers.ModelSerializer):
    decided_by_username = serializers.CharField(
        source="decided_by.username", read_only=True
    )

    class Meta:
        model = PayrollAllowanceGateDecision
        fields = (
            "id",
            "decision",
            "decided_by",
            "decided_by_username",
            "affected_lines_count",
            "total_allowance_delta",
            "note",
            "payload",
            "created_at",
        )
        read_only_fields = fields


class PayrollAllowanceGateDecisionInputSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=PayrollAllowanceDecision.values)
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)


class PayrollMonthlySerializer(serializers.ModelSerializer):
    month_key = serializers.SerializerMethodField()
    lines = PayrollMonthlyLineSerializer(many=True, read_only=True)
    allowance_gate_decisions = PayrollAllowanceGateDecisionSerializer(
        many=True, read_only=True
    )

    class Meta:
        model = PayrollMonthly
        fields = (
            "id",
            "month",
            "month_key",
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
            "lines",
            "allowance_gate_decisions",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    @staticmethod
    def get_month_key(obj: PayrollMonthly) -> str:
        return obj.month.strftime("%Y-%m")
