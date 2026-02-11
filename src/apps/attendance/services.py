from datetime import datetime, date
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from attendance.models import AttendanceRecord
from core.utils.constants import XPLedgerEntryType
from gamification.services import append_xp_entry

BUSINESS_TZ = ZoneInfo("Asia/Tashkent")


def _business_date(now_dt: datetime) -> date:
    return now_dt.astimezone(BUSINESS_TZ).date()


def _punctuality_xp(check_in_dt: datetime) -> int:
    local_dt = check_in_dt.astimezone(BUSINESS_TZ)
    minutes = local_dt.hour * 60 + local_dt.minute
    cutoff_10_00 = 10 * 60
    cutoff_10_20 = 10 * 60 + 20
    if minutes <= cutoff_10_00:
        return 2
    if minutes <= cutoff_10_20:
        return 0
    return -1


def get_today_record(user_id: int) -> AttendanceRecord | None:
    today = _business_date(timezone.now())
    return AttendanceRecord.objects.filter(user_id=user_id, work_date=today).first()


@transaction.atomic
def check_in(user_id: int) -> tuple[AttendanceRecord, int]:
    now_dt = timezone.now()
    today = _business_date(now_dt)

    record = AttendanceRecord.all_objects.filter(user_id=user_id, work_date=today).first()
    if record and record.deleted_at is not None:
        record.deleted_at = None
        record.save(update_fields=["deleted_at"])
        record.refresh_from_db()

    if record and record.check_in_at:
        raise ValueError("Already checked in for today.")

    if not record:
        record = AttendanceRecord.objects.create(
            user_id=user_id,
            work_date=today,
            check_in_at=now_dt,
        )
    else:
        record.check_in_at = now_dt
        record.save(update_fields=["check_in_at"])

    xp_amount = _punctuality_xp(record.check_in_at)
    reference = f"attendance_checkin:{user_id}:{today.isoformat()}"
    append_xp_entry(
        user_id=user_id,
        amount=xp_amount,
        entry_type=XPLedgerEntryType.ATTENDANCE_PUNCTUALITY,
        reference=reference,
        description="Attendance punctuality XP",
        payload={
            "work_date": today.isoformat(),
            "check_in_at": record.check_in_at.isoformat(),
            "timezone": str(BUSINESS_TZ),
        },
    )
    return record, xp_amount


@transaction.atomic
def check_out(user_id: int) -> AttendanceRecord:
    now_dt = timezone.now()
    today = _business_date(now_dt)
    record = AttendanceRecord.objects.filter(user_id=user_id, work_date=today).first()
    if not record or not record.check_in_at:
        raise ValueError("Cannot check out before check in.")
    if record.check_out_at:
        raise ValueError("Already checked out for today.")

    record.check_out_at = now_dt
    record.save(update_fields=["check_out_at"])
    return record
