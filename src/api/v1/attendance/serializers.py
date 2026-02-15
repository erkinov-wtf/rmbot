from rest_framework import serializers

from account.models import User
from attendance.models import AttendanceRecord
from attendance.services import AttendanceService
from core.utils.constants import RoleSlug


class AttendanceRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceRecord
        fields = (
            "id",
            "user",
            "work_date",
            "check_in_at",
            "check_out_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class AttendanceTechnicianInputSerializer(serializers.Serializer):
    technician_id = serializers.IntegerField(min_value=1)

    def validate_technician_id(self, value: int) -> int:
        technician = User.objects.filter(pk=value, is_active=True).first()
        if not technician:
            raise serializers.ValidationError("Technician user does not exist.")
        if not technician.roles.filter(slug=RoleSlug.TECHNICIAN).exists():
            raise serializers.ValidationError(
                "Selected user does not have TECHNICIAN role."
            )
        return value


class AttendanceRecordListItemSerializer(AttendanceRecordSerializer):
    punctuality_status = serializers.SerializerMethodField()

    class Meta(AttendanceRecordSerializer.Meta):
        fields = AttendanceRecordSerializer.Meta.fields + ("punctuality_status",)

    def get_punctuality_status(self, obj: AttendanceRecord) -> str | None:
        return AttendanceService.resolve_punctuality_status(obj.check_in_at)
