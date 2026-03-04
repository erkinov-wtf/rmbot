from rest_framework import serializers

from ticket.models import TicketPartCompletion, TicketTransition, WorkSessionTransition


class TicketPartCompletionSerializer(serializers.ModelSerializer):
    ticket_part = serializers.IntegerField(source="ticket_part_spec_id", read_only=True)
    part_id = serializers.IntegerField(
        source="ticket_part_spec.inventory_item_part_id",
        read_only=True,
    )
    part_name = serializers.CharField(
        source="ticket_part_spec.inventory_item_part.name",
        read_only=True,
    )
    technician_name = serializers.SerializerMethodField(read_only=True)
    action = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = TicketPartCompletion
        fields = (
            "id",
            "ticket",
            "ticket_part",
            "part_id",
            "part_name",
            "technician",
            "technician_name",
            "completed_at",
            "note",
            "is_rework",
            "action",
            "metadata",
            "created_at",
        )

    @staticmethod
    def _user_display_name(user) -> str | None:
        if not user:
            return None
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        return full_name or user.username

    def get_technician_name(self, obj: TicketPartCompletion) -> str | None:
        return self._user_display_name(obj.technician)

    def get_action(self, obj: TicketPartCompletion) -> str:
        return "rework_completed" if obj.is_rework else "completed"


class TicketTransitionSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True)
    actor_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = TicketTransition
        fields = (
            "id",
            "ticket",
            "from_status",
            "to_status",
            "action",
            "actor",
            "actor_username",
            "actor_name",
            "note",
            "metadata",
            "created_at",
        )

    @staticmethod
    def _user_display_name(user) -> str | None:
        if not user:
            return None
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        return full_name or user.username

    def get_actor_name(self, obj: TicketTransition) -> str | None:
        return self._user_display_name(obj.actor)


class WorkSessionTransitionSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True)
    actor_name = serializers.SerializerMethodField(read_only=True)

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
            "actor_username",
            "actor_name",
            "event_at",
            "metadata",
            "created_at",
        )

    @staticmethod
    def _user_display_name(user) -> str | None:
        if not user:
            return None
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        return full_name or user.username

    def get_actor_name(self, obj: WorkSessionTransition) -> str | None:
        return self._user_display_name(obj.actor)
