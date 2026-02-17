from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.handlers import CallbackQueryHandler, MessageHandler
from aiogram.types import CallbackQuery, Message

from account.models import TelegramProfile, User
from bot.routers.start.common import StartStateMixin
from bot.services.menu import (
    MENU_BUTTON_MY_XP_VARIANTS,
    MENU_BUTTON_XP_HISTORY_VARIANTS,
)
from bot.services.start_support import (
    XP_HISTORY_CALLBACK_PREFIX,
    _build_xp_history_pagination_markup,
    _build_xp_history_text,
    _parse_xp_history_callback_data,
    _reply_not_registered_callback,
    _reply_xp_history,
    _reply_xp_summary,
    _resolve_registered_user,
    _safe_edit_callback_message,
)

router = Router(name="start_xp")


class StartXPSupportMixin(StartStateMixin):
    @classmethod
    async def handle_my_xp(
        cls,
        *,
        message: Message,
        _,
        user: User | None,
        telegram_profile: TelegramProfile | None,
        state: FSMContext | None,
    ) -> None:
        await cls.clear_state_if_active(state)
        await _reply_xp_summary(
            message=message,
            user=user,
            telegram_profile=telegram_profile,
            _=_,
        )

    @classmethod
    async def handle_my_xp_history(
        cls,
        *,
        message: Message,
        _,
        user: User | None,
        telegram_profile: TelegramProfile | None,
        state: FSMContext | None,
    ) -> None:
        await cls.clear_state_if_active(state)
        await _reply_xp_history(
            message=message,
            user=user,
            telegram_profile=telegram_profile,
            _=_,
        )


@router.callback_query(F.data.startswith(f"{XP_HISTORY_CALLBACK_PREFIX}:"))
class XPHistoryPaginationHandler(StartXPSupportMixin, CallbackQueryHandler):
    async def handle(self) -> None:
        query: CallbackQuery = self.event
        _ = self.data["_"]
        user: User | None = self.data.get("user")
        telegram_profile: TelegramProfile | None = self.data.get("telegram_profile")

        parsed = _parse_xp_history_callback_data(callback_data=query.data or "")
        if parsed is None:
            await query.answer(_("Could not open this page."), show_alert=True)
            return
        limit, offset = parsed

        resolved_user = await _resolve_registered_user(
            user=user,
            telegram_profile=telegram_profile,
        )
        if resolved_user is None:
            await _reply_not_registered_callback(query=query, _=_)
            return

        text, total_count, normalized_limit, safe_offset = await _build_xp_history_text(
            user=resolved_user,
            _=_,
            limit=limit,
            offset=offset,
        )
        await _safe_edit_callback_message(
            query=query,
            text=text,
            reply_markup=_build_xp_history_pagination_markup(
                total_count=total_count,
                limit=normalized_limit,
                offset=safe_offset,
                _=_,
            ),
        )
        await query.answer()


@router.message(Command("xp"))
@router.message(F.text.in_(MENU_BUTTON_MY_XP_VARIANTS))
class MyXPHandler(StartXPSupportMixin, MessageHandler):
    async def handle(self) -> None:
        await self.handle_my_xp(
            message=self.event,
            _=self.data["_"],
            user=self.data.get("user"),
            telegram_profile=self.data.get("telegram_profile"),
            state=self.data.get("state"),
        )


@router.message(Command("xp_history"))
@router.message(F.text.in_(MENU_BUTTON_XP_HISTORY_VARIANTS))
class MyXPHistoryHandler(StartXPSupportMixin, MessageHandler):
    async def handle(self) -> None:
        await self.handle_my_xp_history(
            message=self.event,
            _=self.data["_"],
            user=self.data.get("user"),
            telegram_profile=self.data.get("telegram_profile"),
            state=self.data.get("state"),
        )
