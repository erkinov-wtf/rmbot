from django.utils import timezone
from rest_framework import serializers

from account.models import User
from core.utils.constants import RoleSlug
from ticket.models import (
    ACTIVE_TICKET_STATUSES,
    Ticket,
    TicketTransition,
    WorkSession,
    WorkSessionTransition,
)


class TicketSerializer(serializers.ModelSerializer):
    checklist_snapshot = serializers.JSONField(required=True)
    srt_total_minutes = serializers.IntegerField(required=True)
    approve_srt = serializers.BooleanField(write_only=True, required=True)

    class Meta:
        model = Ticket
        fields = (
            "id",
            "bike",
            "master",
            "technician",
            "title",
            "checklist_snapshot",
            "srt_total_minutes",
            "srt_approved_by",
            "srt_approved_at",
            "approve_srt",
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
            "srt_approved_by",
            "srt_approved_at",
        )

    @staticmethod
    def _is_valid_checklist_item(item) -> bool:
        if isinstance(item, str):
            return bool(item.strip())
        if isinstance(item, dict):
            task = item.get("task")
            return isinstance(task, str) and bool(task.strip())
        return False

    def validate_checklist_snapshot(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "checklist_snapshot must be an array of checklist items."
            )
        if len(value) < 10:
            raise serializers.ValidationError(
                "checklist_snapshot must include at least 10 items."
            )
        invalid_indexes = [
            idx
            for idx, item in enumerate(value)
            if not self._is_valid_checklist_item(item)
        ]
        if invalid_indexes:
            first_bad = invalid_indexes[0]
            raise serializers.ValidationError(
                f"checklist_snapshot[{first_bad}] must be a non-empty task string or object with non-empty 'task'."
            )
        return value

    def validate_srt_total_minutes(self, value: int) -> int:
        if value <= 0:
            raise serializers.ValidationError(
                "srt_total_minutes must be greater than 0."
            )
        return value

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
        if not attrs.get("approve_srt"):
            raise serializers.ValidationError(
                {"approve_srt": "SRT must be approved by Master during intake."}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop("approve_srt", None)
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["srt_approved_by"] = request.user
            validated_data["srt_approved_at"] = timezone.now()
        return super().create(validated_data)


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
