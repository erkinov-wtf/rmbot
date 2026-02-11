from rest_framework import serializers

from gamification.models import XPLedger


class XPLedgerSerializer(serializers.ModelSerializer):
    class Meta:
        model = XPLedger
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
