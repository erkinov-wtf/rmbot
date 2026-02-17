from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.handlers import MessageHandler
from aiogram.types import Message

from account.models import User
from bot.routers.ticket_qc.base import QCTicketBaseMixin
from bot.services.menu import (
    MENU_BUTTON_QC_CHECKS_VARIANTS,
    build_main_menu_keyboard,
    main_menu_markup_for_user,
)

router = Router(name="ticket_qc_entry")


@router.message(Command("qc_checks"))
@router.message(Command("qc"))
@router.message(F.text.in_(MENU_BUTTON_QC_CHECKS_VARIANTS))
class QCQueueHandler(QCTicketBaseMixin, MessageHandler):
    async def handle(self) -> None:
        message: Message = self.event
        _ = self.data["_"]
        user: User | None = self.data.get("user")
        state: FSMContext | None = self.data.get("state")

        await type(self).clear_state_if_active(state=state)
        if not user or not user.is_active:
            await message.answer(
                _("You do not have access yet. Send /start to request access."),
                reply_markup=build_main_menu_keyboard(
                    is_technician=False,
                    include_start_access=True,
                    _=_,
                ),
            )
            return
        if not await type(self).can_qc_ticket_async(user=user):
            await message.answer(
                _("This action is available only for QC inspectors."),
                reply_markup=await main_menu_markup_for_user(user=user, _=_),
            )
            return

        text, markup = await type(self).build_qc_queue_payload(
            qc_user_id=user.id,
            page=1,
            _=_,
        )
        await message.answer(text=text, reply_markup=markup)
