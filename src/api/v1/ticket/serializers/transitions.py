from rest_framework import serializers

from ticket.models import TicketTransition, WorkSessionTransition


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
