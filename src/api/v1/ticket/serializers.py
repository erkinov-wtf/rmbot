from rest_framework import serializers

from account.models import User
from core.utils.constants import RoleSlug
from ticket.models import ACTIVE_TICKET_STATUSES, Ticket, TicketTransition, WorkSession


class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = (
            "id",
            "bike",
            "master",
            "technician",
            "title",
            "srt_total_minutes",
            "flag_minutes",
            "status",
            "assigned_at",
            "started_at",
            "done_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "master",
            "status",
            "assigned_at",
            "started_at",
            "done_at",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        bike = attrs.get("bike")
        if Ticket.objects.filter(
            bike=bike,
            status__in=ACTIVE_TICKET_STATUSES,
            deleted_at__isnull=True,
        ).exists():
            raise serializers.ValidationError(
                {"bike": "An active ticket already exists for this bike."}
            )
        return attrs


class TicketAssignSerializer(serializers.Serializer):
    technician_id = serializers.IntegerField(min_value=1)

    def validate_technician_id(self, value: int) -> int:
        user = User.objects.filter(pk=value).first()
        if not user:
            raise serializers.ValidationError("Technician user does not exist.")
        if not user.roles.filter(slug=RoleSlug.TECHNICIAN).exists():
            raise serializers.ValidationError(
                "Selected user does not have TECHNICIAN role."
            )
        return value


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
