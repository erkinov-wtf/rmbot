from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils.translation import gettext as django_gettext
from django.utils.translation import gettext_noop

from core.utils.constants import TicketStatus, WorkSessionStatus
from gamification.models import XPTransaction
from ticket.models import Ticket, WorkSession


@dataclass(frozen=True)
class TechnicianTicketState:
    ticket_id: int
    serial_number: str
    ticket_status: str
    session_status: str | None
    potential_xp: int
    acquired_xp: int
    actions: tuple[str, ...]


class TechnicianTicketActionService:
    """Technician-side ticket action helper for Telegram-driven workflows."""

    CALLBACK_PREFIX = "tt"
    QUEUE_CALLBACK_PREFIX = "ttq"

    ACTION_START = "start"
    ACTION_PAUSE = "pause"
    ACTION_RESUME = "resume"
    ACTION_STOP = "stop"
    ACTION_TO_WAITING_QC = "to_waiting_qc"
    ACTION_REFRESH = "refresh"

    QUEUE_ACTION_OPEN = "open"
    QUEUE_ACTION_REFRESH = "refresh"

    VIEW_SCOPE_ACTIVE = "active"
    VIEW_SCOPE_UNDER_QC = "under_qc"
    VIEW_SCOPE_PAST = "past"
    QUEUE_PAGE_SIZE = 5

    _ACTION_ORDER = (
        ACTION_START,
        ACTION_PAUSE,
        ACTION_RESUME,
        ACTION_STOP,
        ACTION_TO_WAITING_QC,
    )
    _ACTION_LABELS = {
        ACTION_START: gettext_noop("▶ Start work"),
        ACTION_PAUSE: gettext_noop("⏸ Pause work"),
        ACTION_RESUME: gettext_noop("▶ Resume work"),
        ACTION_STOP: gettext_noop("⏹ Stop session"),
        ACTION_TO_WAITING_QC: gettext_noop("🧪 Send to QC"),
        ACTION_REFRESH: gettext_noop("🔄 Refresh ticket"),
    }
    _QUEUE_ACTION_LABELS = {
        QUEUE_ACTION_REFRESH: gettext_noop("🔄 Refresh list"),
    }
    _VIEW_SCOPE_STATUSES = {
        VIEW_SCOPE_ACTIVE: (
            TicketStatus.ASSIGNED,
            TicketStatus.REWORK,
            TicketStatus.IN_PROGRESS,
        ),
        VIEW_SCOPE_UNDER_QC: (TicketStatus.WAITING_QC,),
        VIEW_SCOPE_PAST: (TicketStatus.DONE,),
    }
    _VIEW_SCOPE_EMPTY_MESSAGES = {
        VIEW_SCOPE_ACTIVE: gettext_noop("No active tickets assigned right now."),
        VIEW_SCOPE_UNDER_QC: gettext_noop("No tickets are currently waiting QC."),
        VIEW_SCOPE_PAST: gettext_noop("No past tickets found yet."),
    }
    _VIEW_SCOPE_TOTAL_LABELS = {
        VIEW_SCOPE_ACTIVE: gettext_noop("Total active tickets"),
        VIEW_SCOPE_UNDER_QC: gettext_noop("Total waiting QC tickets"),
        VIEW_SCOPE_PAST: gettext_noop("Total past tickets"),
    }
    _TICKET_STATUS_LABELS = {
        TicketStatus.ASSIGNED: gettext_noop("Assigned"),
        TicketStatus.REWORK: gettext_noop("Rework"),
        TicketStatus.IN_PROGRESS: gettext_noop("In progress"),
        TicketStatus.WAITING_QC: gettext_noop("Waiting QC"),
        TicketStatus.DONE: gettext_noop("Done"),
    }
    _SESSION_STATUS_LABELS = {
        WorkSessionStatus.RUNNING: gettext_noop("Running"),
        WorkSessionStatus.PAUSED: gettext_noop("Paused"),
        WorkSessionStatus.STOPPED: gettext_noop("Stopped"),
    }
    _ACTION_FEEDBACK = {
        ACTION_START: gettext_noop("Work session started."),
        ACTION_PAUSE: gettext_noop("Work session paused."),
        ACTION_RESUME: gettext_noop("Work session resumed."),
        ACTION_STOP: gettext_noop("Work session stopped."),
        ACTION_TO_WAITING_QC: gettext_noop("Ticket sent to QC."),
        ACTION_REFRESH: gettext_noop("Ticket details refreshed."),
    }
    _ERROR_TICKET_NOT_ASSIGNED = gettext_noop(
        "Ticket is not found or is not assigned to you."
    )
    _ERROR_WRONG_TECHNICIAN = gettext_noop("Ticket is not assigned to this technician.")
    _ERROR_UNSUPPORTED_QUEUE_CALLBACK = gettext_noop(
        "Unsupported queue callback action."
    )
    _ERROR_UNSUPPORTED_VIEW_SCOPE = gettext_noop("Unsupported ticket view scope.")
    _ERROR_ACTION_NOT_AVAILABLE = gettext_noop(
        "Action is not available for this ticket right now."
    )
    _ERROR_UNSUPPORTED_ACTION = gettext_noop("Unsupported action.")
    _SERIAL_UNKNOWN = gettext_noop("unknown")

    @staticmethod
    def _translate(*, text: str, _) -> str:
        if _ is None:
            return django_gettext(text)
        return _(text)

    @classmethod
    def queue_states_for_technician(
        cls, *, technician_id: int
    ) -> list[TechnicianTicketState]:
        return cls.view_states_for_technician(
            technician_id=technician_id,
            scope=cls.VIEW_SCOPE_ACTIVE,
        )

    @classmethod
    def view_states_for_technician(
        cls,
        *,
        technician_id: int,
        scope: str,
        limit: int = 20,
    ) -> list[TechnicianTicketState]:
        tickets = cls._queue_tickets_for_technician(
            technician_id=technician_id,
            scope=scope,
            limit=limit,
        )
        return [
            cls.state_for_ticket(ticket=ticket, technician_id=technician_id)
            for ticket in tickets
        ]

    @classmethod
    def paginated_view_states_for_technician(
        cls,
        *,
        technician_id: int,
        scope: str,
        page: int = 1,
        per_page: int = QUEUE_PAGE_SIZE,
    ) -> tuple[list[TechnicianTicketState], int, int, int]:
        cls._validate_view_scope(scope=scope)
        normalized_per_page = cls._normalize_per_page(per_page=per_page)
        total_count = cls._queue_ticket_count_for_technician(
            technician_id=technician_id,
            scope=scope,
        )
        page_count = max(1, math.ceil(total_count / normalized_per_page))
        safe_page = min(cls._normalize_page(page=page), page_count)
        offset = (safe_page - 1) * normalized_per_page
        tickets = cls._queue_tickets_for_technician(
            technician_id=technician_id,
            scope=scope,
            limit=normalized_per_page,
            offset=offset,
        )
        states = [
            cls.state_for_ticket(ticket=ticket, technician_id=technician_id)
            for ticket in tickets
        ]
        return states, safe_page, page_count, total_count

    @classmethod
    def state_for_technician_and_ticket(
        cls, *, technician_id: int, ticket_id: int
    ) -> TechnicianTicketState:
        ticket = cls.get_ticket_for_technician(
            technician_id=technician_id,
            ticket_id=ticket_id,
        )
        if ticket is None:
            raise ValueError(cls._ERROR_TICKET_NOT_ASSIGNED)
        return cls.state_for_ticket(ticket=ticket, technician_id=technician_id)

    @classmethod
    def execute_for_technician(
        cls,
        *,
        technician_id: int,
        ticket_id: int,
        action: str,
    ) -> TechnicianTicketState:
        ticket = cls.get_ticket_for_technician(
            technician_id=technician_id,
            ticket_id=ticket_id,
        )
        if ticket is None:
            raise ValueError(cls._ERROR_TICKET_NOT_ASSIGNED)

        cls._execute_action(ticket=ticket, technician_id=technician_id, action=action)

        refreshed_ticket = cls.get_ticket_for_technician(
            technician_id=technician_id,
            ticket_id=ticket_id,
        )
        if refreshed_ticket is None:
            raise ValueError(cls._ERROR_TICKET_NOT_ASSIGNED)
        return cls.state_for_ticket(
            ticket=refreshed_ticket, technician_id=technician_id
        )

    @classmethod
    def state_for_ticket(
        cls, *, ticket: Ticket, technician_id: int
    ) -> TechnicianTicketState:
        if ticket.technician_id != technician_id:
            raise ValueError(cls._ERROR_WRONG_TECHNICIAN)

        session_status = cls._latest_session_status(
            ticket=ticket,
            technician_id=technician_id,
        )
        actions = tuple(
            cls.available_actions(
                ticket=ticket,
                technician_id=technician_id,
                latest_session_status=session_status,
            )
        )
        return TechnicianTicketState(
            ticket_id=ticket.id,
            serial_number=cls._serial_number(ticket=ticket),
            ticket_status=str(ticket.status),
            session_status=session_status,
            potential_xp=cls._potential_xp_for_ticket(ticket=ticket),
            acquired_xp=cls._acquired_xp_for_ticket_and_technician(
                ticket=ticket,
                technician_id=technician_id,
            ),
            actions=actions,
        )

    @classmethod
    def available_actions(
        cls,
        *,
        ticket: Ticket,
        technician_id: int,
        latest_session_status: str | None = None,
    ) -> list[str]:
        if ticket.technician_id != technician_id:
            return []

        if ticket.status in (TicketStatus.ASSIGNED, TicketStatus.REWORK):
            if WorkSession.domain.has_open_for_technician(technician_id=technician_id):
                return []
            return [cls.ACTION_START]

        if ticket.status != TicketStatus.IN_PROGRESS:
            return []

        session_status = latest_session_status or cls._latest_session_status(
            ticket=ticket,
            technician_id=technician_id,
        )
        if session_status == WorkSessionStatus.RUNNING:
            return [cls.ACTION_PAUSE, cls.ACTION_STOP]
        if session_status == WorkSessionStatus.PAUSED:
            return [cls.ACTION_RESUME, cls.ACTION_STOP]
        if session_status == WorkSessionStatus.STOPPED:
            return [cls.ACTION_TO_WAITING_QC]
        return []

    @classmethod
    def build_queue_keyboard(
        cls,
        *,
        states: Iterable[TechnicianTicketState],
        scope: str = VIEW_SCOPE_ACTIVE,
        page: int = 1,
        page_count: int = 1,
        _=None,
    ) -> InlineKeyboardMarkup | None:
        cls._validate_view_scope(scope=scope)
        states_list = list(states)
        safe_page_count = max(1, int(page_count or 1))
        safe_page = min(cls._normalize_page(page=page), safe_page_count)
        inline_keyboard: list[list[InlineKeyboardButton]] = []
        for state in states_list:
            status_label = cls._ticket_status_label(status=state.ticket_status, _=_)
            inline_keyboard.append(
                [
                    InlineKeyboardButton(
                        text=(
                            f"{cls._status_icon(status=state.ticket_status)} "
                            f"#{state.ticket_id} · {state.serial_number} · {status_label}"
                        ),
                        callback_data=cls.build_queue_callback_data(
                            action=cls.QUEUE_ACTION_OPEN,
                            ticket_id=state.ticket_id,
                            scope=scope,
                            page=safe_page,
                        ),
                    )
                ]
            )

        prev_page = max(1, safe_page - 1)
        next_page = min(safe_page_count, safe_page + 1)
        inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text="<",
                    callback_data=cls.build_queue_callback_data(
                        action=cls.QUEUE_ACTION_REFRESH,
                        scope=scope,
                        page=prev_page,
                    ),
                ),
                InlineKeyboardButton(
                    text=f"{safe_page}/{safe_page_count}",
                    callback_data=cls.build_queue_callback_data(
                        action=cls.QUEUE_ACTION_REFRESH,
                        scope=scope,
                        page=safe_page,
                    ),
                ),
                InlineKeyboardButton(
                    text=">",
                    callback_data=cls.build_queue_callback_data(
                        action=cls.QUEUE_ACTION_REFRESH,
                        scope=scope,
                        page=next_page,
                    ),
                ),
            ]
        )

        if not inline_keyboard:
            return None
        return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    @classmethod
    def build_action_keyboard(
        cls,
        *,
        ticket_id: int,
        actions: Iterable[str],
        include_refresh: bool = True,
        _=None,
    ) -> InlineKeyboardMarkup | None:
        action_set = {
            action
            for action in actions
            if action in cls._ACTION_LABELS and action != cls.ACTION_REFRESH
        }
        ordered_actions = [
            action for action in cls._ACTION_ORDER if action in action_set
        ]
        if include_refresh and ordered_actions:
            ordered_actions.append(cls.ACTION_REFRESH)
        if not ordered_actions:
            return None

        inline_keyboard: list[list[InlineKeyboardButton]] = []
        row: list[InlineKeyboardButton] = []
        for action in ordered_actions:
            row.append(
                InlineKeyboardButton(
                    text=cls._translate(text=cls._ACTION_LABELS[action], _=_),
                    callback_data=cls.build_callback_data(
                        ticket_id=ticket_id,
                        action=action,
                    ),
                )
            )
            if len(row) == 2:
                inline_keyboard.append(row)
                row = []
        if row:
            inline_keyboard.append(row)
        return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    @classmethod
    def render_state_message(
        cls,
        *,
        state: TechnicianTicketState,
        heading: str | None = None,
        _=None,
    ) -> str:
        _ = _ or django_gettext
        serial_number = (
            _(cls._SERIAL_UNKNOWN)
            if state.serial_number == cls._SERIAL_UNKNOWN
            else state.serial_number
        )
        lines: list[str] = []
        if heading:
            lines.append(heading)

        lines.append("━━━━━━━━━━━━━━━━━━")
        lines.extend(
            [
                _("🎫 Ticket: #%(ticket_id)s") % {"ticket_id": state.ticket_id},
                _("🔢 Serial number: %(serial)s") % {"serial": serial_number},
                _("📍 Status: %(status)s")
                % {
                    "status": cls._ticket_status_label(
                        status=state.ticket_status,
                        _=_,
                    )
                },
            ]
        )
        if state.session_status:
            lines.append(
                _("🛠 Work session: %(session)s")
                % {
                    "session": cls._session_status_label(
                        status=state.session_status,
                        _=_,
                    )
                }
            )
        if state.potential_xp > 0:
            lines.append(_("🎯 Potential XP: +%(xp)s") % {"xp": state.potential_xp})
        else:
            lines.append(_("🎯 Potential XP: pending metrics"))
        lines.append(_("🏆 Acquired XP: +%(xp)s") % {"xp": state.acquired_xp})
        if state.potential_xp > 0:
            lines.append(
                _("📈 XP progress: %(current)s/%(target)s")
                % {
                    "current": state.acquired_xp,
                    "target": state.potential_xp,
                }
            )
        lines.append("━━━━━━━━━━━━━━━━━━")

        available_labels = [
            cls._translate(text=cls._ACTION_LABELS[action], _=_)
            for action in state.actions
            if action != cls.ACTION_REFRESH and action in cls._ACTION_LABELS
        ]
        if available_labels:
            lines.append(_("⚡ Available actions:"))
            lines.extend(f"• {label}" for label in available_labels)
        else:
            lines.append(_("🧊 No technician actions are available right now."))
        return "\n".join(lines)

    @classmethod
    def render_queue_summary(
        cls,
        *,
        states: Iterable[TechnicianTicketState],
        scope: str = VIEW_SCOPE_ACTIVE,
        heading: str | None = None,
        total_count: int | None = None,
        page: int | None = None,
        page_count: int | None = None,
        _=None,
    ) -> str:
        cls._validate_view_scope(scope=scope)
        _ = _ or django_gettext
        states_list = list(states)
        lines: list[str] = []
        if heading:
            lines.append(heading)

        if not states_list:
            lines.append(
                _(
                    cls._VIEW_SCOPE_EMPTY_MESSAGES.get(
                        scope,
                        cls._VIEW_SCOPE_EMPTY_MESSAGES[cls.VIEW_SCOPE_ACTIVE],
                    )
                )
            )
            return "\n".join(lines)

        total_label = _(
            cls._VIEW_SCOPE_TOTAL_LABELS.get(
                scope,
                cls._VIEW_SCOPE_TOTAL_LABELS[cls.VIEW_SCOPE_ACTIVE],
            )
        )
        resolved_total_count = (
            max(0, int(total_count)) if total_count is not None else len(states_list)
        )
        lines.append(
            _("%(label)s: %(count)s")
            % {"label": total_label, "count": resolved_total_count}
        )
        if page is not None and page_count is not None:
            safe_page_count = max(1, int(page_count))
            safe_page = min(cls._normalize_page(page=page), safe_page_count)
            lines.append(
                _("Page: %(page)s/%(page_count)s")
                % {"page": safe_page, "page_count": safe_page_count}
            )
        for state in states_list:
            serial_number = (
                _(cls._SERIAL_UNKNOWN)
                if state.serial_number == cls._SERIAL_UNKNOWN
                else state.serial_number
            )
            session_suffix = (
                (
                    _(" | session: %(session)s")
                    % {
                        "session": cls._session_status_label(
                            status=state.session_status,
                            _=_,
                        )
                    }
                )
                if state.session_status
                else ""
            )
            potential_xp = str(state.potential_xp) if state.potential_xp > 0 else "?"
            xp_suffix = _(" | xp: +%(current)s/%(target)s") % {
                "current": state.acquired_xp,
                "target": potential_xp,
            }
            ticket_line = (
                f"{cls._status_icon(status=state.ticket_status)} "
                f"#{state.ticket_id} | {serial_number} | "
                f"{cls._ticket_status_label(status=state.ticket_status, _=_)}"
                f"{session_suffix}{xp_suffix}"
            )
            lines.append(ticket_line)
        lines.append(_("Use the inline buttons below to open ticket details."))
        return "\n".join(lines)

    @classmethod
    def scope_for_ticket_status(cls, *, status: str) -> str:
        for scope, statuses in cls._VIEW_SCOPE_STATUSES.items():
            if status in statuses:
                return scope
        return cls.VIEW_SCOPE_ACTIVE

    @classmethod
    def action_feedback(cls, *, action: str, _=None) -> str:
        feedback = cls._ACTION_FEEDBACK.get(
            action, gettext_noop("Ticket state updated.")
        )
        return cls._translate(text=feedback, _=_)

    @classmethod
    def build_callback_data(cls, *, ticket_id: int, action: str) -> str:
        return f"{cls.CALLBACK_PREFIX}:{int(ticket_id)}:{action}"

    @classmethod
    def parse_callback_data(cls, *, callback_data: str) -> tuple[int, str] | None:
        parts = str(callback_data or "").split(":", 2)
        if len(parts) != 3 or parts[0] != cls.CALLBACK_PREFIX:
            return None

        ticket_id_raw, action = parts[1], parts[2]
        if action not in cls._ACTION_LABELS:
            return None

        try:
            ticket_id = int(ticket_id_raw)
        except (TypeError, ValueError):
            return None

        return ticket_id, action

    @classmethod
    def build_queue_callback_data(
        cls,
        *,
        action: str,
        ticket_id: int | None = None,
        scope: str = VIEW_SCOPE_ACTIVE,
        page: int = 1,
    ) -> str:
        cls._validate_view_scope(scope=scope)
        safe_page = cls._normalize_page(page=page)
        if action == cls.QUEUE_ACTION_REFRESH:
            return f"{cls.QUEUE_CALLBACK_PREFIX}:{action}:{scope}:{safe_page}"
        if action == cls.QUEUE_ACTION_OPEN and ticket_id is not None:
            return (
                f"{cls.QUEUE_CALLBACK_PREFIX}:{action}:{int(ticket_id)}:{scope}:"
                f"{safe_page}"
            )
        raise ValueError(cls._ERROR_UNSUPPORTED_QUEUE_CALLBACK)

    @classmethod
    def parse_queue_callback_data(
        cls, *, callback_data: str
    ) -> tuple[str, int | None, str, int] | None:
        parts = str(callback_data or "").split(":")
        if len(parts) < 2 or parts[0] != cls.QUEUE_CALLBACK_PREFIX:
            return None

        action = parts[1]
        if action == cls.QUEUE_ACTION_REFRESH:
            scope = parts[2] if len(parts) >= 3 else cls.VIEW_SCOPE_ACTIVE
            if scope not in cls._VIEW_SCOPE_STATUSES:
                return None
            if len(parts) >= 4:
                try:
                    page = int(parts[3])
                except (TypeError, ValueError):
                    return None
            else:
                page = 1
            return action, None, scope, cls._normalize_page(page=page)

        if action == cls.QUEUE_ACTION_OPEN:
            try:
                ticket_id = int(parts[2])
            except (IndexError, TypeError, ValueError):
                return None
            scope = parts[3] if len(parts) >= 4 else cls.VIEW_SCOPE_ACTIVE
            if scope not in cls._VIEW_SCOPE_STATUSES:
                return None
            if len(parts) >= 5:
                try:
                    page = int(parts[4])
                except (TypeError, ValueError):
                    return None
            else:
                page = 1
            return action, ticket_id, scope, cls._normalize_page(page=page)

        return None

    @classmethod
    def get_ticket_for_technician(
        cls, *, technician_id: int, ticket_id: int
    ) -> Ticket | None:
        return (
            Ticket.domain.select_related("inventory_item")
            .filter(pk=ticket_id, technician_id=technician_id)
            .first()
        )

    @classmethod
    def _queue_tickets_for_technician(
        cls,
        *,
        technician_id: int,
        scope: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Ticket]:
        cls._validate_view_scope(scope=scope)
        queryset = (
            Ticket.domain.select_related("inventory_item")
            .filter(
                technician_id=technician_id,
                status__in=list(cls._VIEW_SCOPE_STATUSES[scope]),
            )
            .order_by("-created_at", "-id")
        )
        normalized_offset = max(0, int(offset or 0))
        if normalized_offset > 0:
            queryset = queryset[normalized_offset:]
        if limit > 0:
            queryset = queryset[:limit]
        return list(queryset)

    @classmethod
    def _queue_ticket_count_for_technician(
        cls, *, technician_id: int, scope: str
    ) -> int:
        cls._validate_view_scope(scope=scope)
        return int(
            Ticket.domain.filter(
                technician_id=technician_id,
                status__in=list(cls._VIEW_SCOPE_STATUSES[scope]),
            ).count()
        )

    @staticmethod
    def _normalize_page(*, page: int) -> int:
        try:
            normalized_page = int(page)
        except (TypeError, ValueError):
            return 1
        return max(1, normalized_page)

    @classmethod
    def _normalize_per_page(cls, *, per_page: int) -> int:
        try:
            normalized = int(per_page)
        except (TypeError, ValueError):
            return cls.QUEUE_PAGE_SIZE
        return max(1, normalized)

    @classmethod
    def _validate_view_scope(cls, *, scope: str) -> None:
        if scope not in cls._VIEW_SCOPE_STATUSES:
            raise ValueError(cls._ERROR_UNSUPPORTED_VIEW_SCOPE)

    @classmethod
    def _status_icon(cls, *, status: str) -> str:
        return {
            TicketStatus.ASSIGNED: "🟡",
            TicketStatus.REWORK: "🟠",
            TicketStatus.IN_PROGRESS: "🟢",
            TicketStatus.WAITING_QC: "🧪",
            TicketStatus.DONE: "✅",
        }.get(status, "🎟")

    @classmethod
    def _ticket_status_label(cls, *, status: str, _=None) -> str:
        label = cls._TICKET_STATUS_LABELS.get(status, str(status))
        return cls._translate(text=label, _=_)

    @classmethod
    def _session_status_label(cls, *, status: str, _=None) -> str:
        label = cls._SESSION_STATUS_LABELS.get(status, str(status))
        return cls._translate(text=label, _=_)

    @classmethod
    def _potential_xp_for_ticket(cls, *, ticket: Ticket) -> int:
        explicit = int(ticket.xp_amount or 0)
        if explicit > 0:
            return explicit
        total_duration = int(ticket.total_duration or 0)
        if total_duration <= 0:
            return 0
        return math.ceil(total_duration / 20)

    @classmethod
    def _acquired_xp_for_ticket_and_technician(
        cls,
        *,
        ticket: Ticket,
        technician_id: int,
    ) -> int:
        aggregate = XPTransaction.objects.filter(
            user_id=technician_id,
            payload__ticket_id=ticket.id,
        ).aggregate(total_amount=Coalesce(Sum("amount"), 0))
        return int(aggregate.get("total_amount") or 0)

    @classmethod
    def _latest_session_status(
        cls, *, ticket: Ticket, technician_id: int
    ) -> str | None:
        open_session = WorkSession.domain.get_open_for_ticket_and_technician(
            ticket=ticket,
            technician_id=technician_id,
        )
        if open_session is not None:
            return str(open_session.status)

        latest_session = WorkSession.domain.get_latest_for_ticket_and_technician(
            ticket=ticket,
            technician_id=technician_id,
        )
        if latest_session is None:
            return None
        return str(latest_session.status)

    @classmethod
    def _execute_action(
        cls,
        *,
        ticket: Ticket,
        technician_id: int,
        action: str,
    ) -> None:
        if action == cls.ACTION_REFRESH:
            return

        available_actions = cls.available_actions(
            ticket=ticket,
            technician_id=technician_id,
        )
        if action not in available_actions:
            raise ValueError(cls._ERROR_ACTION_NOT_AVAILABLE)

        if action == cls.ACTION_START:
            from ticket.services_workflow import TicketWorkflowService

            TicketWorkflowService.start_ticket(
                ticket=ticket,
                actor_user_id=technician_id,
            )
            return

        if action == cls.ACTION_PAUSE:
            from ticket.services_work_session import TicketWorkSessionService

            TicketWorkSessionService.pause_work_session(
                ticket=ticket,
                actor_user_id=technician_id,
            )
            return

        if action == cls.ACTION_RESUME:
            from ticket.services_work_session import TicketWorkSessionService

            TicketWorkSessionService.resume_work_session(
                ticket=ticket,
                actor_user_id=technician_id,
            )
            return

        if action == cls.ACTION_STOP:
            from ticket.services_work_session import TicketWorkSessionService

            TicketWorkSessionService.stop_work_session(
                ticket=ticket,
                actor_user_id=technician_id,
            )
            return

        if action == cls.ACTION_TO_WAITING_QC:
            from ticket.services_workflow import TicketWorkflowService

            TicketWorkflowService.move_ticket_to_waiting_qc(
                ticket=ticket,
                actor_user_id=technician_id,
            )
            return

        raise ValueError(cls._ERROR_UNSUPPORTED_ACTION)

    @staticmethod
    def _serial_number(*, ticket: Ticket) -> str:
        inventory_item = getattr(ticket, "inventory_item", None)
        return (
            getattr(inventory_item, "serial_number", "")
            or TechnicianTicketActionService._SERIAL_UNKNOWN
        )
