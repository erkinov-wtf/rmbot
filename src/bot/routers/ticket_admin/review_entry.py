from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.handlers import MessageHandler
from aiogram.types import Message

from account.models import User
from bot.services import ticket_admin_support
from bot.services.menu import (
    MENU_BUTTON_REVIEW_TICKETS_VARIANTS,
    main_menu_markup_for_user,
)
from core.utils.asyncio import run_sync

router = Router(name="ticket_admin_review_entrypoints")


class TicketReviewEntrypointSupportMixin:
    @classmethod
    async def ensure_review_access_for_message(
        cls,
        *,
        message: Message,
        user: User | None,
        _,
    ):
        if not user or not user.is_active:
            await ticket_admin_support._notify_not_registered_message(
                message=message, _=_
            )
            return None

        permissions = await ticket_admin_support._ticket_permissions(user=user)
        if not permissions.can_open_review_panel:
            await message.answer(
                _("Your roles do not allow ticket review actions."),
                reply_markup=await main_menu_markup_for_user(user=user, _=_),
            )
            return None

        return permissions


@router.message(Command("ticket_review"))
@router.message(F.text.in_(MENU_BUTTON_REVIEW_TICKETS_VARIANTS))
class TicketReviewEntrypointHandler(TicketReviewEntrypointSupportMixin, MessageHandler):
    async def handle(self) -> None:
        message: Message = self.event
        state: FSMContext = self.data["state"]
        _ = self.data["_"]
        user: User | None = self.data.get("user")

        permissions = await self.ensure_review_access_for_message(
            message=message,
            user=user,
            _=_,
        )
        if permissions is None:
            return

        await state.clear()
        await state.set_state(ticket_admin_support.TicketReviewForm.flow)
        tickets, safe_page, page_count, total_count = await run_sync(
            ticket_admin_support._review_queue_tickets,
            page=1,
            per_page=ticket_admin_support.REVIEW_ITEMS_PER_PAGE,
        )
        await state.update_data(review_page=safe_page)
        await message.answer(
            ticket_admin_support._review_queue_text(
                tickets=tickets,
                page=safe_page,
                page_count=page_count,
                total_count=total_count,
                _=_,
            ),
            reply_markup=ticket_admin_support._review_queue_keyboard(
                tickets=tickets,
                page=safe_page,
                page_count=page_count,
            ),
        )
