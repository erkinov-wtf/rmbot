from django.db import models

from attendance.managers import AttendanceRecordDomainManager
from core.models import SoftDeleteModel, TimestampedModel


class AttendanceRecord(TimestampedModel, SoftDeleteModel):
    domain = AttendanceRecordDomainManager()

    user = models.ForeignKey(
        "account.User", on_delete=models.CASCADE, related_name="attendance_records"
    )
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

    def mark_check_in(self, *, check_in_at) -> None:
        if self.check_in_at:
            raise ValueError("Already checked in for today.")
        self.check_in_at = check_in_at
        self.save(update_fields=["check_in_at"])

    def mark_check_out(self, *, check_out_at) -> None:
        if not self.check_in_at:
            raise ValueError("Cannot check out before check in.")
        if self.check_out_at:
            raise ValueError("Already checked out for today.")
        self.check_out_at = check_out_at
        self.save(update_fields=["check_out_at"])

    def __str__(self) -> str:
        return f"Attendance#{self.pk} user={self.user_id} date={self.work_date}"
