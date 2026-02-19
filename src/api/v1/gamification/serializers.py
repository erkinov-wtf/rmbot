from rest_framework import serializers

from gamification.models import XPTransaction
from core.utils.constants import EmployeeLevel


class XPTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = XPTransaction
        fields = (
            "id",
            "user",
            "amount",
            "entry_type",
            "reference",
            "description",
            "payload",
            "created_at",
        )


class XPAdjustmentSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1)
    amount = serializers.IntegerField()
    comment = serializers.CharField(max_length=500)

    def validate_amount(self, value: int) -> int:
        normalized = int(value)
        if normalized == 0:
            raise serializers.ValidationError("amount must not be 0.")
        return normalized

    def validate_comment(self, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise serializers.ValidationError("comment is required.")
        return normalized


class WeeklyEvaluationRunSerializer(serializers.Serializer):
    week_start = serializers.DateField(required=False)

    def validate_week_start(self, value):
        if value.weekday() != 0:
            raise serializers.ValidationError("week_start must be a Monday date.")
        return value


class LevelManualSetSerializer(serializers.Serializer):
    level = serializers.ChoiceField(choices=EmployeeLevel.values)
    note = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
    )
    clear_warning = serializers.BooleanField(required=False, default=False)
    warning_active = serializers.BooleanField(required=False)
