from rest_framework import serializers

from ticket.models import WorkSession


class WorkSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkSession
        fields = (
            "id",
            "ticket",
            "technician",
            "status",
            "started_at",
            "last_started_at",
            "ended_at",
            "active_seconds",
            "created_at",
            "updated_at",
        )
