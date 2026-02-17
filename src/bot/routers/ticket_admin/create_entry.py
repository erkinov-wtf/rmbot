from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.handlers import MessageHandler
from aiogram.types import Message

from account.models import User
from bot.services import ticket_admin_support
from bot.services.menu import (
    MENU_BUTTON_CREATE_TICKET_VARIANTS,
    main_menu_markup_for_user,
)
from core.utils.asyncio import run_sync

router = Router(name="ticket_admin_create_entrypoints")


class TicketCreateEntrypointSupportMixin:
    @classmethod
    async def ensure_create_access_for_message(
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
        if not permissions.can_create:
            await message.answer(
                _("⛔ <b>Your roles do not allow ticket intake.</b>"),
                reply_markup=await main_menu_markup_for_user(user=user, _=_),
            )
            return None

        return permissions


@router.message(Command("ticket_create"))
@router.message(F.text.in_(MENU_BUTTON_CREATE_TICKET_VARIANTS))
class TicketCreateEntrypointHandler(TicketCreateEntrypointSupportMixin, MessageHandler):
    async def handle(self) -> None:
        message: Message = self.event
        state: FSMContext = self.data["state"]
        _ = self.data["_"]
        user: User | None = self.data.get("user")

        permissions = await self.ensure_create_access_for_message(
            message=message,
            user=user,
            _=_,
        )
        if permissions is None:
            return

        await state.clear()
        items, safe_page, page_count, _total_count = await run_sync(
            ticket_admin_support._query_inventory_items_page,
            page=1,
        )
        await state.set_state(ticket_admin_support.TicketCreateForm.flow)
        await state.update_data(create_page=safe_page)
        await message.answer(
            ticket_admin_support._create_items_text(
                page=safe_page,
                page_count=page_count,
                items=items,
                _=_,
            ),
            reply_markup=ticket_admin_support._create_items_keyboard(
                page=safe_page,
                page_count=page_count,
                items=items,
            ),
        )
