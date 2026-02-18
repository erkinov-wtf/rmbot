from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from account.models import User
from bot.services.menu import BotMenuService
from bot.services.technician_ticket_actions import TechnicianTicketActionService
from core.utils.asyncio import run_sync
from core.utils.constants import RoleSlug


class TechnicianQueueService:
    @staticmethod
    async def is_technician(user: User) -> bool:
        return await run_sync(
            user.roles.filter(slug=RoleSlug.TECHNICIAN, deleted_at__isnull=True).exists
        )

    @staticmethod
    async def safe_edit_message(
        *,
        query: CallbackQuery,
        text: str,
        reply_markup,
    ) -> None:
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

    @staticmethod
    async def notify_not_registered_callback(
        *,
        query: CallbackQuery,
        _,
    ) -> None:
        await query.answer(
            _("🚫 No access yet. Send /start first."),
            show_alert=True,
        )
        if query.message is None:
            return
        await query.message.answer(
            _(
                "📝 <b>Open Access Request</b>\nUse <code>/start</code> or tap the button below."
            ),
            reply_markup=BotMenuService.build_main_menu_keyboard(
                is_technician=False,
                include_start_access=True,
                _=_,
            ),
        )

    @staticmethod
    def scope_back_text(*, scope: str, _) -> str:
        if scope == TechnicianTicketActionService.VIEW_SCOPE_UNDER_QC:
            return _("⬅ Back to waiting QC tickets")
        if scope == TechnicianTicketActionService.VIEW_SCOPE_PAST:
            return _("⬅ Back to past tickets")
        return _("⬅ Back to active tickets")

    @classmethod
    def with_queue_navigation(
        cls,
        *,
        reply_markup,
        scope: str,
        page: int,
        _,
    ) -> InlineKeyboardMarkup:
        nav_row = [
            InlineKeyboardButton(
                text=cls.scope_back_text(scope=scope, _=_),
                callback_data=TechnicianTicketActionService.build_queue_callback_data(
                    action=TechnicianTicketActionService.QUEUE_ACTION_REFRESH,
                    scope=scope,
                    page=page,
                ),
            )
        ]
        with_back = InlineKeyboardMarkup(
            inline_keyboard=[
                *(reply_markup.inline_keyboard if reply_markup else []),
                nav_row,
            ]
        )
        return with_back

    @staticmethod
    def scope_heading(*, scope: str, _) -> str:
        if scope == TechnicianTicketActionService.VIEW_SCOPE_UNDER_QC:
            return _("🧪 <b>Waiting QC Tickets</b>")
        if scope == TechnicianTicketActionService.VIEW_SCOPE_PAST:
            return _("✅ <b>Past Tickets</b>")
        return _("🎟 <b>Active Tickets</b>")

    @staticmethod
    def scope_refreshed_feedback(*, scope: str, _) -> str:
        if scope == TechnicianTicketActionService.VIEW_SCOPE_UNDER_QC:
            return _("🔄 Waiting QC list refreshed.")
        if scope == TechnicianTicketActionService.VIEW_SCOPE_PAST:
            return _("🔄 Past tickets list refreshed.")
        return _("🔄 Active tickets list refreshed.")

    @staticmethod
    def queue_context_from_markup(
        *,
        markup: InlineKeyboardMarkup | None,
    ) -> tuple[str, int] | None:
        if markup is None:
            return None

        for row in markup.inline_keyboard:
            for button in row:
                callback_data = getattr(button, "callback_data", None)
                if not callback_data:
                    continue
                parsed = TechnicianTicketActionService.parse_queue_callback_data(
                    callback_data=callback_data,
                )
                if parsed is None:
                    continue
                action, _ticket_id, scope, page = parsed
                if action == TechnicianTicketActionService.QUEUE_ACTION_REFRESH:
                    return scope, page
        return None

    @classmethod
    async def queue_dashboard_payload(
        cls,
        *,
        technician_id: int,
        scope: str,
        page: int = 1,
        _,
    ) -> tuple[str, InlineKeyboardMarkup | None]:
        states, safe_page, page_count, total_count = await run_sync(
            TechnicianTicketActionService.paginated_view_states_for_technician,
            technician_id=technician_id,
            scope=scope,
            page=page,
            per_page=TechnicianTicketActionService.QUEUE_PAGE_SIZE,
        )
        text = TechnicianTicketActionService.render_queue_summary(
            states=states,
            scope=scope,
            heading=cls.scope_heading(scope=scope, _=_),
            total_count=total_count,
            page=safe_page,
            page_count=page_count,
            _=_,
        )
        markup = TechnicianTicketActionService.build_queue_keyboard(
            states=states,
            scope=scope,
            page=safe_page,
            page_count=page_count,
            _=_,
        )
        return text, markup

    @classmethod
    async def technician_dashboard_handler(
        cls,
        *,
        message: Message,
        user: User | None,
        scope: str,
        _,
    ) -> None:
        if not user or not user.is_active:
            await message.answer(
                _(
                    "🚫 <b>No access yet.</b>\nSend <code>/start</code> to submit access request."
                ),
                reply_markup=BotMenuService.build_main_menu_keyboard(
                    is_technician=False,
                    include_start_access=True,
                    _=_,
                ),
            )
            return

        if not await cls.is_technician(user):
            await message.answer(
                _("⛔ <b>This command is available only for technicians.</b>"),
                reply_markup=BotMenuService.build_main_menu_keyboard(
                    is_technician=False,
                    include_start_access=False,
                    _=_,
                ),
            )
            return

        text, markup = await cls.queue_dashboard_payload(
            technician_id=user.id,
            scope=scope,
            page=1,
            _=_,
        )
        await message.answer(text=text, reply_markup=markup)
