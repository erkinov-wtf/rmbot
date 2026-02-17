from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.handlers import MessageHandler
from aiogram.types import Message

from account.models import User
from bot.services.menu import (
    MENU_BUTTON_ACTIVE_TICKETS_VARIANTS,
    MENU_BUTTON_PAST_TICKETS_VARIANTS,
    MENU_BUTTON_UNDER_QC_TICKETS_VARIANTS,
)
from bot.services.technician_queue import TechnicianQueueService
from bot.services.technician_ticket_actions import TechnicianTicketActionService

router = Router(name="technician_tickets_entry")


class TechnicianDashboardMessageHandler(MessageHandler):
    @classmethod
    async def clear_state_if_active(cls, *, state: FSMContext | None) -> None:
        del cls
        if state is None:
            return
        if await state.get_state():
            await state.clear()

    @classmethod
    async def open_dashboard_for_scope(
        cls,
        *,
        message: Message,
        user: User | None,
        scope: str,
        _,
        state: FSMContext | None,
    ) -> None:
        await cls.clear_state_if_active(state=state)
        await TechnicianQueueService.technician_dashboard_handler(
            message=message,
            user=user,
            scope=scope,
            _=_,
        )


@router.message(Command("queue"))
@router.message(Command("active"))
@router.message(Command("tech"))
@router.message(F.text.in_(MENU_BUTTON_ACTIVE_TICKETS_VARIANTS))
class TechnicianQueueHandler(TechnicianDashboardMessageHandler):
    async def handle(self) -> None:
        await type(self).open_dashboard_for_scope(
            message=self.event,
            user=self.data.get("user"),
            scope=TechnicianTicketActionService.VIEW_SCOPE_ACTIVE,
            _=self.data["_"],
            state=self.data.get("state"),
        )


@router.message(Command("under_qc"))
@router.message(F.text.in_(MENU_BUTTON_UNDER_QC_TICKETS_VARIANTS))
class TechnicianUnderQCHandler(TechnicianDashboardMessageHandler):
    async def handle(self) -> None:
        await type(self).open_dashboard_for_scope(
            message=self.event,
            user=self.data.get("user"),
            scope=TechnicianTicketActionService.VIEW_SCOPE_UNDER_QC,
            _=self.data["_"],
            state=self.data.get("state"),
        )


@router.message(Command("past"))
@router.message(F.text.in_(MENU_BUTTON_PAST_TICKETS_VARIANTS))
class TechnicianPastHandler(TechnicianDashboardMessageHandler):
    async def handle(self) -> None:
        await type(self).open_dashboard_for_scope(
            message=self.event,
            user=self.data.get("user"),
            scope=TechnicianTicketActionService.VIEW_SCOPE_PAST,
            _=self.data["_"],
            state=self.data.get("state"),
        )
