from django.contrib import admin

from attendance.models import AttendanceRecord
from core.admin import BaseModelAdmin


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(BaseModelAdmin):
    list_display = ("id", "user", "work_date", "check_in_at", "check_out_at", "created_at")
    search_fields = ("id", "user__username")
    list_filter = ("work_date",)
