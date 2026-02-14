from __future__ import annotations

from datetime import date

from django.db import models


class AttendanceRecordQuerySet(models.QuerySet):
    def for_user(self, *, user_id: int):
        return self.filter(user_id=user_id)

    def on_work_date(self, *, work_date: date):
        return self.filter(work_date=work_date)

    def with_check_in(self):
        return self.filter(check_in_at__isnull=False)


class AttendanceRecordDomainManager(
    models.Manager.from_queryset(AttendanceRecordQuerySet)
):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

    def for_user_on_date(self, *, user_id: int, work_date: date):
        return (
            self.get_queryset()
            .for_user(user_id=user_id)
            .on_work_date(work_date=work_date)
            .first()
        )

    def get_or_restore_for_user_on_date(self, *, user_id: int, work_date: date):
        record = (
            self.model.all_objects.filter(user_id=user_id, work_date=work_date)
            .order_by("-id")
            .first()
        )
        if record and record.deleted_at is not None:
            record.deleted_at = None
            record.save(update_fields=["deleted_at"])
            record.refresh_from_db()
        return record
