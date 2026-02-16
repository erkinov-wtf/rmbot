from rest_framework import serializers

from gamification.models import XPTransaction


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
