from rest_framework import serializers

from attendance.models import AttendanceRecord


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
