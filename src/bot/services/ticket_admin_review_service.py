from __future__ import annotations

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.permissions import TicketBotPermissionSet
from bot.services import ticket_admin_support as legacy
from ticket.models import Ticket


class TicketAdminReviewService:
    QUEUE_CALLBACK_PREFIX = legacy.REVIEW_QUEUE_CALLBACK_PREFIX
    ACTION_CALLBACK_PREFIX = legacy.REVIEW_ACTION_CALLBACK_PREFIX

    REVIEW_ITEMS_PER_PAGE = legacy.REVIEW_ITEMS_PER_PAGE
    TECHNICIAN_OPTIONS_PER_PAGE = legacy.TECHNICIAN_OPTIONS_PER_PAGE

    QUEUE_ACTION_OPEN = legacy.REVIEW_QUEUE_ACTION_OPEN
    QUEUE_ACTION_REFRESH = legacy.REVIEW_QUEUE_ACTION_REFRESH

    ACTION_ASSIGN_OPEN = legacy.REVIEW_ACTION_ASSIGN_OPEN
    ACTION_ASSIGN_EXEC = legacy.REVIEW_ACTION_ASSIGN_EXEC
    ACTION_ASSIGN_PAGE = legacy.REVIEW_ACTION_ASSIGN_PAGE
    ACTION_MANUAL_OPEN = legacy.REVIEW_ACTION_MANUAL_OPEN
    ACTION_MANUAL_COLOR = legacy.REVIEW_ACTION_MANUAL_COLOR
    ACTION_MANUAL_XP = legacy.REVIEW_ACTION_MANUAL_XP
    ACTION_MANUAL_ADJ = legacy.REVIEW_ACTION_MANUAL_ADJ
    ACTION_MANUAL_SAVE = legacy.REVIEW_ACTION_MANUAL_SAVE
    ACTION_BACK = legacy.REVIEW_ACTION_BACK

    @staticmethod
    def parse_queue_callback(
        *,
        callback_data: str,
    ) -> tuple[str, int | None, int] | None:
        return legacy._parse_review_queue_callback(callback_data=callback_data)

    @staticmethod
    def parse_action_callback(
        *, callback_data: str
    ) -> tuple[str, int, str | None] | None:
        return legacy._parse_review_action_callback(callback_data=callback_data)

    @staticmethod
    def review_queue_tickets(
        *,
        page: int,
        per_page: int = REVIEW_ITEMS_PER_PAGE,
    ) -> tuple[list[Ticket], int, int, int]:
        return legacy._review_queue_tickets(page=page, per_page=per_page)

    @staticmethod
    def review_ticket(*, ticket_id: int) -> Ticket | None:
        return legacy._review_ticket(ticket_id=ticket_id)

    @staticmethod
    def list_technician_options_page(
        *,
        page: int,
        per_page: int = TECHNICIAN_OPTIONS_PER_PAGE,
    ) -> tuple[list[tuple[int, str]], int, int, int]:
        return legacy._list_technician_options_page(page=page, per_page=per_page)

    @staticmethod
    def review_queue_text(
        *,
        tickets: list[Ticket],
        page: int,
        page_count: int,
        total_count: int,
        _,
    ) -> str:
        return legacy._review_queue_text(
            tickets=tickets,
            page=page,
            page_count=page_count,
            total_count=total_count,
            _=_,
        )

    @staticmethod
    def review_queue_keyboard(*, tickets: list[Ticket], page: int, page_count: int):
        return legacy._review_queue_keyboard(
            tickets=tickets,
            page=page,
            page_count=page_count,
        )

    @staticmethod
    def review_ticket_text(*, ticket: Ticket, _) -> str:
        return legacy._review_ticket_text(ticket=ticket, _=_)

    @staticmethod
    def review_ticket_keyboard(
        *,
        ticket_id: int,
        page: int,
        permissions: TicketBotPermissionSet,
        ticket_status: str | None = None,
    ):
        return legacy._review_ticket_keyboard(
            ticket_id=ticket_id,
            page=page,
            permissions=permissions,
            ticket_status=ticket_status,
        )

    @staticmethod
    def assign_keyboard(
        *,
        ticket_id: int,
        technician_options: list[tuple[int, str]],
        page: int,
        page_count: int,
    ):
        return legacy._assign_keyboard(
            ticket_id=ticket_id,
            technician_options=technician_options,
            page=page,
            page_count=page_count,
        )

    @staticmethod
    def manual_metrics_text(
        *, ticket_id: int, flag_color: str, xp_amount: int, _
    ) -> str:
        return legacy._manual_metrics_text(
            ticket_id=ticket_id,
            flag_color=flag_color,
            xp_amount=xp_amount,
            _=_,
        )

    @staticmethod
    def manual_metrics_keyboard(*, ticket_id: int, flag_color: str, xp_amount: int):
        return legacy._manual_metrics_keyboard(
            ticket_id=ticket_id,
            flag_color=flag_color,
            xp_amount=xp_amount,
        )

    @staticmethod
    def approve_and_assign_ticket(
        *,
        ticket_id: int,
        technician_id: int,
        actor_user_id: int,
    ) -> Ticket:
        return legacy._approve_and_assign_ticket(
            ticket_id=ticket_id,
            technician_id=technician_id,
            actor_user_id=actor_user_id,
        )

    @staticmethod
    def set_ticket_manual_metrics(
        *,
        ticket_id: int,
        flag_color: str,
        xp_amount: int,
    ) -> Ticket:
        return legacy._set_ticket_manual_metrics(
            ticket_id=ticket_id,
            flag_color=flag_color,
            xp_amount=xp_amount,
        )

    @staticmethod
    async def show_review_queue(
        *,
        query: CallbackQuery,
        state: FSMContext,
        page: int,
        _,
    ) -> None:
        await legacy._show_review_queue(query=query, state=state, page=page, _=_)

    @staticmethod
    async def show_review_ticket(
        *,
        query: CallbackQuery,
        ticket_id: int,
        page: int,
        permissions: TicketBotPermissionSet,
        _,
    ) -> None:
        await legacy._show_review_ticket(
            query=query,
            ticket_id=ticket_id,
            page=page,
            permissions=permissions,
            _=_,
        )
