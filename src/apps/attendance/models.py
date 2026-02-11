from django.db import models

from core.models import SoftDeleteModel, TimestampedModel


class AttendanceRecord(TimestampedModel, SoftDeleteModel):
    user = models.ForeignKey("account.User", on_delete=models.CASCADE, related_name="attendance_records")
    work_date = models.DateField(db_index=True)
    check_in_at = models.DateTimeField(null=True, blank=True, db_index=True)
    check_out_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "work_date"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "work_date"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_attendance_record_per_user_date",
            )
        ]

    def __str__(self) -> str:
        return f"Attendance#{self.pk} user={self.user_id} date={self.work_date}"
