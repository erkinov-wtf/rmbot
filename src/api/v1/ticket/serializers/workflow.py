from rest_framework import serializers

from account.models import User
from core.utils.constants import RoleSlug, TicketColor


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


class TicketManualMetricsSerializer(serializers.Serializer):
    flag_color = serializers.ChoiceField(choices=TicketColor.choices)
    xp_amount = serializers.IntegerField(min_value=0)
