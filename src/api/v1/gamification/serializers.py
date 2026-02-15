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
