from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from attendance.models import AttendanceRecord
from core.utils.constants import XPTransactionEntryType
from gamification.services import GamificationService
from rules.services import RulesService


class AttendanceService:
    """Daily attendance check-in/out service with punctuality XP calculation."""

    BUSINESS_TZ = ZoneInfo("Asia/Tashkent")

    @classmethod
    def _attendance_rules(cls) -> tuple[int, int, int, int, int, ZoneInfo]:
        rules = RulesService.get_active_rules_config().get("attendance", {})
        on_time_xp = int(rules.get("on_time_xp", 2) or 0)
        grace_xp = int(rules.get("grace_xp", 0) or 0)
        late_xp = int(rules.get("late_xp", -1) or 0)

        on_time_cutoff = str(rules.get("on_time_cutoff", "10:00"))
        grace_cutoff = str(rules.get("grace_cutoff", "10:20"))

        try:
            on_h, on_m = on_time_cutoff.split(":")
            grace_h, grace_m = grace_cutoff.split(":")
            on_minutes = int(on_h) * 60 + int(on_m)
            grace_minutes = int(grace_h) * 60 + int(grace_m)
        except (ValueError, TypeError):
            on_minutes = 10 * 60
            grace_minutes = 10 * 60 + 20

        timezone_name = str(rules.get("timezone", str(cls.BUSINESS_TZ)))
        try:
            local_tz = ZoneInfo(timezone_name)
        except Exception:
            local_tz = cls.BUSINESS_TZ

        return on_time_xp, grace_xp, late_xp, on_minutes, grace_minutes, local_tz

    @classmethod
    def _business_date(cls, now_dt: datetime) -> date:
        _, _, _, _, _, local_tz = cls._attendance_rules()
        return now_dt.astimezone(local_tz).date()

    @classmethod
    def _punctuality_xp(cls, check_in_dt: datetime) -> int:
        on_time_xp, grace_xp, late_xp, cutoff_10_00, cutoff_10_20, local_tz = (
            cls._attendance_rules()
        )
        local_dt = check_in_dt.astimezone(local_tz)
        minutes = local_dt.hour * 60 + local_dt.minute
        if minutes <= cutoff_10_00:
            return on_time_xp
        if minutes <= cutoff_10_20:
            return grace_xp
        return late_xp

    @classmethod
    def resolve_punctuality_status(cls, check_in_dt: datetime | None) -> str | None:
        if not check_in_dt:
            return None

        _, _, _, cutoff_10_00, cutoff_10_20, local_tz = cls._attendance_rules()
        local_dt = check_in_dt.astimezone(local_tz)
        minutes = local_dt.hour * 60 + local_dt.minute

        if minutes < cutoff_10_00:
            return "early"
        if minutes <= cutoff_10_20:
            return "on_time"
        return "late"

    @classmethod
    def list_today_records(
        cls,
        *,
        work_date: date | None,
        technician_id: int | None,
        punctuality: str | None,
    ) -> list[AttendanceRecord]:
        target_date = work_date or cls._business_date(timezone.now())
        queryset = AttendanceRecord.domain.for_work_date(work_date=target_date)

        if technician_id is not None:
            queryset = queryset.for_user(user_id=technician_id)

        records = list(queryset.order_by("user_id", "id"))
        filtered_records: list[AttendanceRecord] = []
        for record in records:
            status = cls.resolve_punctuality_status(record.check_in_at)
            if punctuality and status != punctuality:
                continue
            record.punctuality_status = status
            filtered_records.append(record)

        return filtered_records

    @classmethod
    @transaction.atomic
    def check_in(cls, user_id: int) -> tuple[AttendanceRecord, int]:
        now_dt = timezone.now()
        today = cls._business_date(now_dt)

        record = AttendanceRecord.domain.get_or_restore_for_user_on_date(
            user_id=user_id,
            work_date=today,
        )
        if not record:
            record = AttendanceRecord.objects.create(
                user_id=user_id,
                work_date=today,
            )

        record.mark_check_in(check_in_at=now_dt)

        xp_amount = cls._punctuality_xp(record.check_in_at)
        reference = f"attendance_checkin:{user_id}:{today.isoformat()}"
        GamificationService.append_xp_entry(
            user_id=user_id,
            amount=xp_amount,
            entry_type=XPTransactionEntryType.ATTENDANCE_PUNCTUALITY,
            reference=reference,
            description="Attendance punctuality XP",
            payload={
                "work_date": today.isoformat(),
                "check_in_at": record.check_in_at.isoformat(),
                "timezone": str(cls._attendance_rules()[-1]),
            },
        )
        return record, xp_amount

    @classmethod
    @transaction.atomic
    def check_out(cls, user_id: int) -> AttendanceRecord:
        now_dt = timezone.now()
        today = cls._business_date(now_dt)
        record = AttendanceRecord.domain.for_user_on_date(
            user_id=user_id,
            work_date=today,
        )
        if not record:
            raise ValueError("Cannot check out before check in.")

        record.mark_check_out(check_out_at=now_dt)
        return record
