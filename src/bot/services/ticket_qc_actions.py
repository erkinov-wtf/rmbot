from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from django.utils.translation import gettext as django_gettext
from django.utils.translation import gettext_noop

from core.utils.constants import TicketStatus
from ticket.models import Ticket


class TicketQCActionService:
    CALLBACK_PREFIX = "tqc"

    ACTION_PASS = "pass"
    ACTION_FAIL = "fail"
    ACTION_REFRESH = "refresh"

    _ACTION_LABELS = {
        ACTION_PASS: gettext_noop("✅ QC Pass"),
        ACTION_FAIL: gettext_noop("❌ QC Fail"),
        ACTION_REFRESH: gettext_noop("🔄 Refresh ticket"),
    }
    _ACTION_FEEDBACK = {
        ACTION_PASS: gettext_noop("Ticket marked as QC passed."),
        ACTION_FAIL: gettext_noop("Ticket marked as QC failed."),
        ACTION_REFRESH: gettext_noop("Ticket details refreshed."),
    }
    _STATUS_LABELS = {
        TicketStatus.WAITING_QC: gettext_noop("Waiting QC"),
        TicketStatus.REWORK: gettext_noop("Rework"),
        TicketStatus.DONE: gettext_noop("Done"),
    }
    _ERROR_UNSUPPORTED_ACTION = gettext_noop("Unsupported QC action.")
    _ERROR_UNAVAILABLE_STATUS = gettext_noop(
        "QC action is not available for this ticket status."
    )
    _ERROR_TICKET_NOT_FOUND = gettext_noop("Ticket was not found.")

    @staticmethod
    def _translate(*, text: str, _) -> str:
        if _ is None:
            return django_gettext(text)
        return _(text)

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
    def available_actions(cls, *, ticket_status: str) -> tuple[str, ...]:
        if ticket_status == TicketStatus.WAITING_QC:
            return (cls.ACTION_PASS, cls.ACTION_FAIL, cls.ACTION_REFRESH)
        return (cls.ACTION_REFRESH,)

    @classmethod
    def can_apply_qc_decision(cls, *, ticket_status: str) -> bool:
        return ticket_status == TicketStatus.WAITING_QC

    @classmethod
    def build_action_keyboard(
        cls,
        *,
        ticket_id: int,
        ticket_status: str,
        _=None,
    ) -> InlineKeyboardMarkup | None:
        actions = cls.available_actions(ticket_status=ticket_status)
        if not actions:
            return None

        rows: list[list[InlineKeyboardButton]] = []
        action_row: list[InlineKeyboardButton] = []
        for action in actions:
            button = InlineKeyboardButton(
                text=cls._translate(text=cls._ACTION_LABELS[action], _=_),
                callback_data=cls.build_callback_data(
                    ticket_id=ticket_id, action=action
                ),
            )
            if action == cls.ACTION_REFRESH:
                if action_row:
                    rows.append(action_row)
                    action_row = []
                rows.append([button])
            else:
                action_row.append(button)
        if action_row:
            rows.insert(0, action_row)

        return InlineKeyboardMarkup(inline_keyboard=rows)

    @classmethod
    def render_ticket_message(
        cls,
        *,
        ticket: Ticket,
        _=None,
        heading: str | None = None,
    ) -> str:
        lines: list[str] = []
        if heading:
            lines.append(heading)

        lines.extend(
            [
                cls._translate(text=gettext_noop("🎫 Ticket: #%(ticket_id)s"), _=_)
                % {"ticket_id": ticket.id},
                cls._translate(text=gettext_noop("🔢 Serial number: %(serial)s"), _=_)
                % {"serial": cls._serial_number(ticket=ticket)},
                cls._translate(text=gettext_noop("📍 Status: %(status)s"), _=_)
                % {"status": cls._status_label(status=ticket.status, _=_)},
                cls._translate(text=gettext_noop("🛠 Technician: %(technician)s"), _=_)
                % {"technician": cls._technician_label(ticket=ticket)},
            ]
        )
        return "\n".join(lines)

    @classmethod
    def action_feedback(cls, *, action: str, _=None) -> str:
        message = cls._ACTION_FEEDBACK.get(action, cls._ERROR_UNSUPPORTED_ACTION)
        return cls._translate(text=message, _=_)

    @classmethod
    def status_validation_error(cls, *, _=None) -> str:
        return cls._translate(text=cls._ERROR_UNAVAILABLE_STATUS, _=_)

    @classmethod
    def ticket_not_found_error(cls, *, _=None) -> str:
        return cls._translate(text=cls._ERROR_TICKET_NOT_FOUND, _=_)

    @staticmethod
    def get_ticket(*, ticket_id: int) -> Ticket | None:
        return (
            Ticket.domain.select_related("inventory_item", "technician")
            .filter(pk=ticket_id)
            .first()
        )

    @classmethod
    def _status_label(cls, *, status: str, _=None) -> str:
        label = cls._STATUS_LABELS.get(status, str(status).replace("_", " ").title())
        return cls._translate(text=label, _=_)

    @staticmethod
    def _serial_number(*, ticket: Ticket) -> str:
        inventory_item = getattr(ticket, "inventory_item", None)
        return getattr(inventory_item, "serial_number", "") or "unknown"

    @staticmethod
    def _technician_label(*, ticket: Ticket) -> str:
        technician = getattr(ticket, "technician", None)
        if technician is None:
            return "—"
        full_name = " ".join(
            value for value in [technician.first_name, technician.last_name] if value
        ).strip()
        return (
            full_name or f"@{technician.username}"
            if technician.username
            else str(technician.id)
        )
