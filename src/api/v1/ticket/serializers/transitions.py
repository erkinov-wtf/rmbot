from rest_framework import serializers

from ticket.models import TicketTransition, WorkSessionTransition


class TicketTransitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketTransition
        fields = (
            "id",
            "ticket",
            "from_status",
            "to_status",
            "action",
            "actor",
            "note",
            "metadata",
            "created_at",
        )


class WorkSessionTransitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkSessionTransition
        fields = (
            "id",
            "work_session",
            "ticket",
            "from_status",
            "to_status",
            "action",
            "actor",
            "event_at",
            "metadata",
            "created_at",
        )
