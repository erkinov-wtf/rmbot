from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.handlers import MessageHandler
from aiogram.types import Message

from account.models import TelegramProfile, User
from account.services import AccountService
from bot.routers.start.common import StartStateMixin
from bot.services.menu import (
    MENU_BUTTON_HELP_VARIANTS,
    MENU_BUTTON_MY_STATUS_VARIANTS,
    build_main_menu_keyboard,
    main_menu_markup_for_user,
)
from bot.services.start_support import (
    _build_active_status_text,
    _build_pending_status_text,
    _reply_not_registered,
    _resolve_active_user_for_status,
)
from core.utils.asyncio import run_sync

router = Router(name="start_profile")


class StartProfileSupportMixin(StartStateMixin):
    @classmethod
    def build_help_text(cls, _) -> str:
        return "\n".join(
            [
                _("Available commands:"),
                "/start - " + _("Start the bot and access setup"),
                "/my - " + _("Check my profile and access status"),
                "/ticket_create - " + _("Start ticket intake flow"),
                "/ticket_review - " + _("Open ticket review queue"),
                "/queue - " + _("Open my active ticket list"),
                "/active - " + _("Open my active ticket list"),
                "/tech - " + _("Open technician ticket controls"),
                "/under_qc - " + _("Open tickets waiting for quality check"),
                "/past - " + _("Open my completed tickets"),
                "/qc_checks - " + _("Open my assigned QC checks"),
                "/xp - " + _("Show my XP summary"),
                "/xp_history - " + _("Show my XP activity with pages"),
                "/cancel - " + _("Cancel the current form"),
                "/help - " + _("Show this help message"),
            ]
        )

    @classmethod
    async def handle_help(
        cls,
        *,
        message: Message,
        _,
        user: User | None,
        state: FSMContext | None,
    ) -> None:
        await cls.clear_state_if_active(state)
        await message.answer(
            cls.build_help_text(_),
            reply_markup=await main_menu_markup_for_user(
                user=user,
                include_start_access=not bool(user and user.is_active),
                _=_,
            ),
        )

    @classmethod
    async def handle_my_status(
        cls,
        *,
        message: Message,
        _,
        user: User | None,
        telegram_profile: TelegramProfile | None,
        state: FSMContext | None,
    ) -> None:
        from_user = message.from_user
        if from_user is None:
            return

        await cls.clear_state_if_active(state)
        pending = await run_sync(
            AccountService.get_pending_access_request, from_user.id
        )
        if pending:
            await message.answer(
                _build_pending_status_text(pending=pending, _=_),
                reply_markup=build_main_menu_keyboard(
                    is_technician=False,
                    include_start_access=False,
                    _=_,
                ),
            )
            return

        resolved_user = await _resolve_active_user_for_status(
            user=user,
            telegram_profile=telegram_profile,
        )
        if resolved_user:
            await message.answer(
                await _build_active_status_text(user=resolved_user, _=_),
                reply_markup=await main_menu_markup_for_user(user=resolved_user, _=_),
            )
            return

        await _reply_not_registered(message=message, _=_)


@router.message(Command("help"))
@router.message(F.text.in_(MENU_BUTTON_HELP_VARIANTS))
class HelpHandler(StartProfileSupportMixin, MessageHandler):
    async def handle(self) -> None:
        await self.handle_help(
            message=self.event,
            _=self.data["_"],
            user=self.data.get("user"),
            state=self.data.get("state"),
        )


@router.message(Command("my"))
@router.message(F.text.in_(MENU_BUTTON_MY_STATUS_VARIANTS))
class MyStatusHandler(StartProfileSupportMixin, MessageHandler):
    async def handle(self) -> None:
        await self.handle_my_status(
            message=self.event,
            _=self.data["_"],
            user=self.data.get("user"),
            telegram_profile=self.data.get("telegram_profile"),
            state=self.data.get("state"),
        )
