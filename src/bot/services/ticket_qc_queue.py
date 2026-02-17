from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from django.utils.translation import gettext as django_gettext
from django.utils.translation import gettext_noop

from core.utils.constants import TicketStatus
from ticket.models import Ticket


@dataclass(frozen=True)
class QCTicketQueueItem:
    ticket_id: int
    serial_number: str
    technician_label: str


class QCTicketQueueService:
    CALLBACK_PREFIX = "tqq"
    QUEUE_ACTION_OPEN = "open"
    QUEUE_ACTION_REFRESH = "refresh"
    PAGE_SIZE = 5

    _HEADING = gettext_noop("🧪 My QC checks.")
    _EMPTY_MESSAGE = gettext_noop("No QC checks assigned to you.")
    _TOTAL_LABEL = gettext_noop("Total QC checks: %(count)s")
    _PAGE_LABEL = gettext_noop("Page: %(page)s/%(page_count)s")
    _SELECT_PROMPT = gettext_noop("Select a ticket to review.")
    _BACK_TEXT = gettext_noop("⬅ Back to my QC checks")
    _ROW_TEMPLATE = gettext_noop("🧪 #%(ticket_id)s · %(serial)s · %(technician)s")
    _SERIAL_UNKNOWN = gettext_noop("unknown")
    _TECHNICIAN_UNKNOWN = gettext_noop("unassigned")

    @staticmethod
    def _translate(*, text: str, _) -> str:
        if _ is None:
            return django_gettext(text)
        return _(text)

    @classmethod
    def build_queue_callback_data(
        cls,
        *,
        action: str,
        ticket_id: int | None = None,
        page: int = 1,
    ) -> str:
        safe_page = cls._normalize_page(page=page)
        if action == cls.QUEUE_ACTION_REFRESH:
            return f"{cls.CALLBACK_PREFIX}:{cls.QUEUE_ACTION_REFRESH}:{safe_page}"
        if action == cls.QUEUE_ACTION_OPEN and ticket_id is not None:
            return (
                f"{cls.CALLBACK_PREFIX}:{cls.QUEUE_ACTION_OPEN}:{int(ticket_id)}:"
                f"{safe_page}"
            )
        raise ValueError("Unsupported QC queue callback action.")

    @classmethod
    def parse_queue_callback_data(
        cls,
        *,
        callback_data: str,
    ) -> tuple[str, int | None, int] | None:
        parts = str(callback_data or "").split(":")
        if len(parts) < 3 or parts[0] != cls.CALLBACK_PREFIX:
            return None

        action = parts[1]
        if action == cls.QUEUE_ACTION_REFRESH and len(parts) == 3:
            try:
                return action, None, cls._normalize_page(page=int(parts[2]))
            except (TypeError, ValueError):
                return None

        if action == cls.QUEUE_ACTION_OPEN and len(parts) == 4:
            try:
                ticket_id = int(parts[2])
                page = cls._normalize_page(page=int(parts[3]))
            except (TypeError, ValueError):
                return None
            return action, ticket_id, page

        return None

    @classmethod
    def paginated_queue_for_qc_user(
        cls,
        *,
        qc_user_id: int,
        page: int = 1,
        per_page: int = PAGE_SIZE,
    ) -> tuple[list[QCTicketQueueItem], int, int, int]:
        normalized_per_page = cls._normalize_per_page(per_page=per_page)
        queryset = cls._assigned_queryset_for_qc_user(qc_user_id=qc_user_id)
        total_count = queryset.count()
        page_count = max(1, math.ceil(total_count / normalized_per_page))
        safe_page = min(cls._normalize_page(page=page), page_count)
        offset = (safe_page - 1) * normalized_per_page
        tickets = list(queryset[offset : offset + normalized_per_page])
        items = [cls._item_from_ticket(ticket=ticket) for ticket in tickets]
        return items, safe_page, page_count, total_count

    @classmethod
    def get_assigned_ticket_for_qc_user(
        cls,
        *,
        qc_user_id: int,
        ticket_id: int,
    ) -> Ticket | None:
        return (
            cls._assigned_queryset_for_qc_user(qc_user_id=qc_user_id)
            .filter(pk=ticket_id)
            .first()
        )

    @classmethod
    def render_queue_summary(
        cls,
        *,
        items: Iterable[QCTicketQueueItem],
        total_count: int,
        page: int,
        page_count: int,
        heading: str | None = None,
        _=None,
    ) -> str:
        rows = list(items)
        lines = [
            heading or cls._translate(text=cls._HEADING, _=_),
            cls._translate(text=cls._TOTAL_LABEL, _=_) % {"count": total_count},
            cls._translate(text=cls._PAGE_LABEL, _=_)
            % {"page": page, "page_count": page_count},
        ]
        if not rows:
            lines.append(cls._translate(text=cls._EMPTY_MESSAGE, _=_))
            return "\n".join(lines)

        lines.append(cls._translate(text=cls._SELECT_PROMPT, _=_))
        return "\n".join(lines)

    @classmethod
    def build_queue_keyboard(
        cls,
        *,
        items: Iterable[QCTicketQueueItem],
        page: int,
        page_count: int,
        _=None,
    ) -> InlineKeyboardMarkup:
        safe_page_count = max(1, int(page_count or 1))
        safe_page = min(cls._normalize_page(page=page), safe_page_count)
        keyboard: list[list[InlineKeyboardButton]] = []

        for item in items:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        text=cls._translate(text=cls._ROW_TEMPLATE, _=_)
                        % {
                            "ticket_id": item.ticket_id,
                            "serial": item.serial_number,
                            "technician": item.technician_label,
                        },
                        callback_data=cls.build_queue_callback_data(
                            action=cls.QUEUE_ACTION_OPEN,
                            ticket_id=item.ticket_id,
                            page=safe_page,
                        ),
                    )
                ]
            )

        previous_page = max(1, safe_page - 1)
        next_page = min(safe_page_count, safe_page + 1)
        keyboard.append(
            [
                InlineKeyboardButton(
                    text="<",
                    callback_data=cls.build_queue_callback_data(
                        action=cls.QUEUE_ACTION_REFRESH,
                        page=previous_page,
                    ),
                ),
                InlineKeyboardButton(
                    text=f"{safe_page}/{safe_page_count}",
                    callback_data=cls.build_queue_callback_data(
                        action=cls.QUEUE_ACTION_REFRESH,
                        page=safe_page,
                    ),
                ),
                InlineKeyboardButton(
                    text=">",
                    callback_data=cls.build_queue_callback_data(
                        action=cls.QUEUE_ACTION_REFRESH,
                        page=next_page,
                    ),
                ),
            ]
        )
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    @classmethod
    def with_back_navigation(
        cls,
        *,
        reply_markup: InlineKeyboardMarkup | None,
        page: int,
        _=None,
    ) -> InlineKeyboardMarkup:
        rows = [
            *(reply_markup.inline_keyboard if reply_markup else []),
            [
                InlineKeyboardButton(
                    text=cls._translate(text=cls._BACK_TEXT, _=_),
                    callback_data=cls.build_queue_callback_data(
                        action=cls.QUEUE_ACTION_REFRESH,
                        page=page,
                    ),
                )
            ],
        ]
        return InlineKeyboardMarkup(inline_keyboard=rows)

    @classmethod
    def queue_page_from_markup(
        cls,
        *,
        markup: InlineKeyboardMarkup | None,
    ) -> int | None:
        if markup is None:
            return None
        for row in markup.inline_keyboard:
            for button in row:
                callback_data = getattr(button, "callback_data", None)
                if not callback_data:
                    continue
                parsed = cls.parse_queue_callback_data(callback_data=callback_data)
                if parsed is None:
                    continue
                _action, _ticket_id, page = parsed
                return page
        return None

    @classmethod
    def _assigned_queryset_for_qc_user(cls, *, qc_user_id: int):
        return (
            Ticket.domain.select_related("inventory_item", "technician")
            .filter(master_id=qc_user_id, status=TicketStatus.WAITING_QC)
            .order_by("-created_at", "-id")
        )

    @classmethod
    def _item_from_ticket(cls, *, ticket: Ticket) -> QCTicketQueueItem:
        serial_number = (
            getattr(ticket.inventory_item, "serial_number", None) or cls._SERIAL_UNKNOWN
        )
        technician_label = cls._technician_label(ticket=ticket)
        return QCTicketQueueItem(
            ticket_id=ticket.id,
            serial_number=serial_number,
            technician_label=technician_label,
        )

    @classmethod
    def _technician_label(cls, *, ticket: Ticket) -> str:
        technician = getattr(ticket, "technician", None)
        if technician is None:
            return cls._TECHNICIAN_UNKNOWN
        full_name = " ".join(
            value for value in [technician.first_name, technician.last_name] if value
        ).strip()
        if full_name:
            return full_name
        if technician.username:
            return f"@{technician.username}"
        return str(technician.id)

    @staticmethod
    def _normalize_page(*, page: int) -> int:
        try:
            normalized = int(page)
        except (TypeError, ValueError):
            return 1
        return max(1, normalized)

    @classmethod
    def _normalize_per_page(cls, *, per_page: int) -> int:
        try:
            normalized = int(per_page)
        except (TypeError, ValueError):
            return cls.PAGE_SIZE
        return max(1, normalized)
