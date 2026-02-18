from __future__ import annotations

from aiogram.types import CallbackQuery, Message

from bot.permissions import TicketBotPermissionSet
from bot.services import ticket_admin_support as legacy

TicketCreateForm = legacy.TicketCreateForm
TicketReviewForm = legacy.TicketReviewForm


class TicketAdminCommonService:
    CREATE_CALLBACK_PREFIX = legacy.CREATE_CALLBACK_PREFIX
    REVIEW_QUEUE_CALLBACK_PREFIX = legacy.REVIEW_QUEUE_CALLBACK_PREFIX
    REVIEW_ACTION_CALLBACK_PREFIX = legacy.REVIEW_ACTION_CALLBACK_PREFIX

    VALID_TICKET_COLORS = legacy.VALID_TICKET_COLORS
    MANUAL_XP_PRESETS = legacy.MANUAL_XP_PRESETS

    REVIEW_QUEUE_ACTION_OPEN = legacy.REVIEW_QUEUE_ACTION_OPEN
    REVIEW_QUEUE_ACTION_REFRESH = legacy.REVIEW_QUEUE_ACTION_REFRESH

    REVIEW_ACTION_ASSIGN_OPEN = legacy.REVIEW_ACTION_ASSIGN_OPEN
    REVIEW_ACTION_ASSIGN_EXEC = legacy.REVIEW_ACTION_ASSIGN_EXEC
    REVIEW_ACTION_ASSIGN_PAGE = legacy.REVIEW_ACTION_ASSIGN_PAGE
    REVIEW_ACTION_MANUAL_OPEN = legacy.REVIEW_ACTION_MANUAL_OPEN
    REVIEW_ACTION_MANUAL_COLOR = legacy.REVIEW_ACTION_MANUAL_COLOR
    REVIEW_ACTION_MANUAL_XP = legacy.REVIEW_ACTION_MANUAL_XP
    REVIEW_ACTION_MANUAL_ADJ = legacy.REVIEW_ACTION_MANUAL_ADJ
    REVIEW_ACTION_MANUAL_SAVE = legacy.REVIEW_ACTION_MANUAL_SAVE
    REVIEW_ACTION_BACK = legacy.REVIEW_ACTION_BACK

    @staticmethod
    async def ticket_permissions(*, user) -> TicketBotPermissionSet:
        return await legacy._ticket_permissions(user=user)

    @staticmethod
    async def notify_not_registered_message(*, message: Message, _) -> None:
        await legacy._notify_not_registered_message(message=message, _=_)

    @staticmethod
    async def notify_not_registered_callback(*, query: CallbackQuery, _) -> None:
        await legacy._notify_not_registered_callback(query=query, _=_)

    @staticmethod
    def normalize_page(*, page: int) -> int:
        return legacy._normalize_page(page=page)

    @staticmethod
    def extract_error_message(detail, _=None) -> str:
        return legacy._extract_error_message(detail, _=_)

    @staticmethod
    def status_label(*, status: str, _=None) -> str:
        return legacy._status_label(status=status, _=_)

    @staticmethod
    def can_assign_ticket_status(*, status: str) -> bool:
        return legacy._can_assign_ticket_status(status=status)

    @staticmethod
    async def safe_edit_message(
        *, query: CallbackQuery, text: str, reply_markup
    ) -> None:
        await legacy._safe_edit_message(
            query=query,
            text=text,
            reply_markup=reply_markup,
        )
