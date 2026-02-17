from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from account.models import User
from bot.permissions import resolve_ticket_bot_permissions
from bot.services.ticket_qc_queue import QCTicketQueueService
from core.utils.asyncio import run_sync


class QCTicketBaseMixin:
    @classmethod
    def can_qc_ticket(cls, *, user: User | None) -> bool:
        del cls
        return bool(resolve_ticket_bot_permissions(user=user).can_qc)

    @classmethod
    async def can_qc_ticket_async(cls, *, user: User | None) -> bool:
        return await run_sync(cls.can_qc_ticket, user=user)

    @classmethod
    async def clear_state_if_active(cls, *, state: FSMContext | None) -> None:
        del cls
        if state is None:
            return
        if await state.get_state():
            await state.clear()

    @classmethod
    async def safe_edit_message(
        cls,
        *,
        query: CallbackQuery,
        text: str,
        reply_markup,
    ) -> None:
        del cls
        message = query.message
        edit_text = getattr(message, "edit_text", None)
        if edit_text is None:
            return
        try:
            await edit_text(text=text, reply_markup=reply_markup)
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                return
            raise

    @classmethod
    async def build_qc_queue_payload(
        cls,
        *,
        qc_user_id: int,
        page: int,
        _,
    ):
        del cls
        items, safe_page, page_count, total_count = await run_sync(
            QCTicketQueueService.paginated_queue_for_qc_user,
            qc_user_id=qc_user_id,
            page=page,
            per_page=QCTicketQueueService.PAGE_SIZE,
        )
        text = QCTicketQueueService.render_queue_summary(
            items=items,
            total_count=total_count,
            page=safe_page,
            page_count=page_count,
            heading=_("🧪 <b>My QC Checks</b>"),
            _=_,
        )
        markup = QCTicketQueueService.build_queue_keyboard(
            items=items,
            page=safe_page,
            page_count=page_count,
            _=_,
        )
        return text, markup
