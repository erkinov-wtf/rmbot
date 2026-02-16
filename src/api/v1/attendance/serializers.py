from rest_framework import serializers

from account.models import User
from attendance.models import AttendanceRecord
from attendance.services import AttendanceService


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


class AttendanceUserInputSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1, required=False)
    technician_id = serializers.IntegerField(min_value=1, required=False)

    def validate(self, attrs):
        user_id = attrs.get("user_id") or attrs.get("technician_id")
        if not user_id:
            raise serializers.ValidationError(
                {"user_id": "user_id is required."}
            )

        user = User.objects.filter(pk=user_id, is_active=True).first()
        if not user:
            raise serializers.ValidationError("Selected user does not exist.")

        attrs["user_id"] = int(user_id)
        return attrs


class AttendanceRecordListItemSerializer(AttendanceRecordSerializer):
    punctuality_status = serializers.SerializerMethodField()

    class Meta(AttendanceRecordSerializer.Meta):
        fields = AttendanceRecordSerializer.Meta.fields + ("punctuality_status",)

    def get_punctuality_status(self, obj: AttendanceRecord) -> str | None:
        return AttendanceService.resolve_punctuality_status(obj.check_in_at)
