from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone

from core.utils.constants import WorkSessionStatus, WorkSessionTransitionAction
from rules.services import RulesService
from ticket.models import Ticket, WorkSession, WorkSessionTransition


class TicketWorkSessionService:
    """Session lifecycle manager for technician work time accounting."""

    DEFAULT_DAILY_PAUSE_LIMIT_MINUTES = 30
    DEFAULT_TIMEZONE = "Asia/Tashkent"

    @classmethod
    @transaction.atomic
    def pause_work_session(cls, ticket: Ticket, actor_user_id: int) -> WorkSession:
        now_dt = timezone.now()
        session = cls._get_open_session_for_ticket(
            ticket=ticket, actor_user_id=actor_user_id
        )
        remaining_pause_seconds = cls.get_remaining_pause_seconds_today(
            technician_id=actor_user_id,
            now_dt=now_dt,
        )
        if remaining_pause_seconds <= 0:
            raise ValueError("Daily pause limit is fully reached for today.")

        session.pause(
            actor_user_id=actor_user_id,
            paused_at=now_dt,
            metadata={
                "remaining_pause_seconds_today": remaining_pause_seconds,
            },
        )
        return session

    @classmethod
    @transaction.atomic
    def resume_work_session(cls, ticket: Ticket, actor_user_id: int) -> WorkSession:
        session = cls._get_open_session_for_ticket(
            ticket=ticket, actor_user_id=actor_user_id
        )
        session.resume(actor_user_id=actor_user_id)
        return session

    @classmethod
    @transaction.atomic
    def stop_work_session(cls, ticket: Ticket, actor_user_id: int) -> WorkSession:
        session = cls._get_open_session_for_ticket(
            ticket=ticket, actor_user_id=actor_user_id
        )
        session.stop(actor_user_id=actor_user_id)
        return session

    @staticmethod
    def get_ticket_work_session_history(ticket: Ticket):
        return WorkSessionTransition.domain.history_for_ticket(ticket=ticket)

    @classmethod
    @transaction.atomic
    def auto_resume_paused_sessions_if_limit_reached(
        cls,
        *,
        technician_id: int | None = None,
        now_dt=None,
    ) -> int:
        now = now_dt or timezone.now()
        paused_sessions = list(
            WorkSession.domain.paused_sessions(
                technician_id=technician_id
            ).select_related("ticket")
        )
        resumed_count = 0
        for session in paused_sessions:
            remaining_pause_seconds = cls.get_remaining_pause_seconds_today(
                technician_id=session.technician_id,
                now_dt=now,
            )
            if remaining_pause_seconds > 0:
                continue

            session.refresh_from_db(fields=["status"])
            if session.status != WorkSessionStatus.PAUSED:
                continue

            try:
                session.resume(
                    actor_user_id=session.technician_id,
                    resumed_at=now,
                    metadata={
                        "auto_resumed": True,
                        "reason": "daily_pause_limit_reached",
                    },
                )
            except ValueError:
                continue
            resumed_count += 1
        return resumed_count

    @classmethod
    def get_remaining_pause_seconds_today(
        cls,
        *,
        technician_id: int,
        now_dt=None,
    ) -> int:
        now = now_dt or timezone.now()
        daily_limit_seconds, local_tz = cls._pause_rules()
        if daily_limit_seconds <= 0:
            return 0

        day_start, day_end = cls._day_bounds(now_dt=now, local_tz=local_tz)
        used_seconds = cls._paused_seconds_for_technician_window(
            technician_id=technician_id,
            window_start=day_start,
            window_end=day_end,
            include_open_until=now,
        )
        return max(daily_limit_seconds - used_seconds, 0)

    @classmethod
    def _pause_rules(cls) -> tuple[int, ZoneInfo]:
        rules = RulesService.get_active_rules_config()
        work_session_rules = rules.get("work_session", {})

        raw_limit_minutes = work_session_rules.get(
            "daily_pause_limit_minutes", cls.DEFAULT_DAILY_PAUSE_LIMIT_MINUTES
        )
        try:
            limit_minutes = int(raw_limit_minutes)
        except (TypeError, ValueError):
            limit_minutes = cls.DEFAULT_DAILY_PAUSE_LIMIT_MINUTES
        limit_minutes = max(limit_minutes, 0)

        timezone_name = str(
            work_session_rules.get("timezone", cls.DEFAULT_TIMEZONE)
            or cls.DEFAULT_TIMEZONE
        )
        try:
            local_tz = ZoneInfo(timezone_name)
        except Exception:
            local_tz = ZoneInfo(cls.DEFAULT_TIMEZONE)
        return limit_minutes * 60, local_tz

    @classmethod
    def _day_bounds(cls, *, now_dt, local_tz: ZoneInfo):
        local_now = now_dt.astimezone(local_tz)
        local_day_start = datetime.combine(local_now.date(), time.min, tzinfo=local_tz)
        local_day_end = local_day_start + timedelta(days=1)
        return local_day_start, local_day_end

    @classmethod
    def _paused_seconds_for_technician_window(
        cls,
        *,
        technician_id: int,
        window_start,
        window_end,
        include_open_until,
    ) -> int:
        transitions_qs = (
            WorkSessionTransition.objects.filter(
                action__in=(
                    WorkSessionTransitionAction.PAUSED,
                    WorkSessionTransitionAction.RESUMED,
                    WorkSessionTransitionAction.STOPPED,
                ),
                event_at__lt=window_end,
            )
            .order_by("event_at", "id")
            .only("work_session_id", "action", "event_at")
        )
        sessions = WorkSession.domain.for_technician_overlapping_window(
            technician_id=technician_id,
            window_start=window_start,
            window_end=window_end,
        ).prefetch_related(Prefetch("transitions", queryset=transitions_qs))

        total_seconds = 0
        for session in sessions:
            paused_since = None
            for transition in session.transitions.all():
                if transition.action == WorkSessionTransitionAction.PAUSED:
                    paused_since = transition.event_at
                    continue

                if (
                    transition.action
                    in (
                        WorkSessionTransitionAction.RESUMED,
                        WorkSessionTransitionAction.STOPPED,
                    )
                    and paused_since is not None
                ):
                    total_seconds += cls._window_overlap_seconds(
                        interval_start=paused_since,
                        interval_end=transition.event_at,
                        window_start=window_start,
                        window_end=window_end,
                    )
                    paused_since = None

            if paused_since is not None:
                total_seconds += cls._window_overlap_seconds(
                    interval_start=paused_since,
                    interval_end=min(include_open_until, window_end),
                    window_start=window_start,
                    window_end=window_end,
                )
        return total_seconds

    @staticmethod
    def _window_overlap_seconds(
        *,
        interval_start,
        interval_end,
        window_start,
        window_end,
    ) -> int:
        overlap_start = max(interval_start, window_start)
        overlap_end = min(interval_end, window_end)
        if overlap_end <= overlap_start:
            return 0
        return int((overlap_end - overlap_start).total_seconds())

    @classmethod
    def _get_open_session_for_ticket(
        cls, ticket: Ticket, actor_user_id: int
    ) -> WorkSession:
        cls.auto_resume_paused_sessions_if_limit_reached(
            technician_id=actor_user_id,
            now_dt=timezone.now(),
        )
        session = WorkSession.domain.get_open_for_ticket_and_technician(
            ticket=ticket,
            technician_id=actor_user_id,
        )
        if not session:
            raise ValueError(
                "No active work session found for this ticket and technician."
            )
        return session
