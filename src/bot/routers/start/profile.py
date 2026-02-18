from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.handlers import MessageHandler
from aiogram.types import Message

from account.models import TelegramProfile, User
from account.services import AccountService
from bot.routers.start.base import StartStateMixin
from bot.services.menu import (
    MENU_BUTTON_HELP_VARIANTS,
    MENU_BUTTON_MY_STATUS_VARIANTS,
    BotMenuService,
)
from bot.services.start_support import StartProfileService
from core.utils.asyncio import run_sync
from core.utils.constants import RoleSlug

router = Router(name="start_profile")


class StartProfileSupportMixin(StartStateMixin):
    @classmethod
    def _command_help_line(
        cls,
        *,
        command: str,
        icon: str,
        description: str,
    ) -> str:
        del cls
        return f"• {icon} <code>{escape(command)}</code> — {escape(description)}"

    @classmethod
    def build_help_text(
        cls,
        *,
        include_start_access: bool,
        has_pending_request: bool,
        is_active_user: bool,
        is_technician: bool,
        can_create_ticket: bool,
        can_open_review_panel: bool,
        can_qc_checks: bool,
        _,
    ) -> str:
        del can_create_ticket, can_open_review_panel, can_qc_checks
        status_value = _("access not registered")
        if has_pending_request:
            status_value = _("access request under review")
        elif is_active_user:
            status_value = _("access active")

        lines = [
            _("🆘 <b>Help</b>"),
            _("👤 <b>Status:</b> %(value)s") % {"value": escape(status_value)},
            "",
            _("📌 <b>Main Commands</b>"),
            cls._command_help_line(
                command="/my",
                icon="📊",
                description=_("View your profile and access status"),
            ),
            cls._command_help_line(
                command="/help",
                icon="❓",
                description=_("Show this help menu"),
            ),
        ]

        if include_start_access:
            lines.append(
                cls._command_help_line(
                    command="/start",
                    icon="📝",
                    description=_("Start access request"),
                )
            )
        elif has_pending_request:
            lines.append(
                cls._command_help_line(
                    command="/start",
                    icon="🔎",
                    description=_("Check your request status"),
                )
            )

        if is_technician:
            lines.extend(["", _("🛠 <b>Technician</b>")])
            lines.extend(
                [
                    cls._command_help_line(
                        command="/queue",
                        icon="🎟",
                        description=_("Open my active ticket list"),
                    ),
                    cls._command_help_line(
                        command="/active",
                        icon="📌",
                        description=_("Open my active ticket list"),
                    ),
                    cls._command_help_line(
                        command="/tech",
                        icon="🧑‍🔧",
                        description=_("Open technician ticket controls"),
                    ),
                    cls._command_help_line(
                        command="/under_qc",
                        icon="🧪",
                        description=_("Open tickets waiting for quality check"),
                    ),
                    cls._command_help_line(
                        command="/past",
                        icon="✅",
                        description=_("Open my completed tickets"),
                    ),
                    cls._command_help_line(
                        command="/xp",
                        icon="⭐",
                        description=_("Show my XP summary"),
                    ),
                    cls._command_help_line(
                        command="/xp_history",
                        icon="📜",
                        description=_("Show my XP activity with pages"),
                    ),
                ]
            )

        lines.extend(["", _("🧰 <b>Tools</b>")])
        lines.append(
            cls._command_help_line(
                command="/cancel",
                icon="✋",
                description=_("Cancel the current form"),
            )
        )
        lines.append(
            _(
                "ℹ️ Ticket intake/review/QC actions are now available in the Telegram Mini App."
            )
        )
        lines.append(_("💡 Use the buttons below for quick actions."))
        return "\n".join(lines)

    @classmethod
    async def handle_help(
        cls,
        *,
        message: Message,
        _,
        user: User | None,
        telegram_profile: TelegramProfile | None,
        state: FSMContext | None,
    ) -> None:
        await cls.clear_state_if_active(state)

        telegram_id = None
        if telegram_profile is not None:
            telegram_id = telegram_profile.telegram_id
        elif message.from_user is not None:
            telegram_id = message.from_user.id

        pending_request = None
        if telegram_id is not None:
            pending_request = await run_sync(
                AccountService.get_pending_access_request,
                telegram_id,
            )

        resolved_user = await StartProfileService.resolve_active_user_for_status(
            user=user,
            telegram_profile=telegram_profile,
        )
        is_technician = False
        if resolved_user is not None:
            is_technician = await run_sync(
                resolved_user.roles.filter(
                    slug=RoleSlug.TECHNICIAN,
                    deleted_at__isnull=True,
                ).exists
            )

        include_start_access = (
            not bool(resolved_user and resolved_user.is_active)
            and pending_request is None
        )

        await message.answer(
            cls.build_help_text(
                include_start_access=include_start_access,
                has_pending_request=pending_request is not None,
                is_active_user=bool(resolved_user and resolved_user.is_active),
                is_technician=is_technician,
                can_create_ticket=False,
                can_open_review_panel=False,
                can_qc_checks=False,
                _=_,
            ),
            reply_markup=await BotMenuService.main_menu_markup_for_user(
                user=resolved_user or user,
                include_start_access=include_start_access,
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
                StartProfileService.build_pending_status_text(pending=pending, _=_),
                reply_markup=BotMenuService.build_main_menu_keyboard(
                    is_technician=False,
                    include_start_access=False,
                    _=_,
                ),
            )
            return

        resolved_user = await StartProfileService.resolve_active_user_for_status(
            user=user,
            telegram_profile=telegram_profile,
        )
        if resolved_user:
            await message.answer(
                await StartProfileService.build_active_status_text(
                    user=resolved_user,
                    _=_,
                ),
                reply_markup=await BotMenuService.main_menu_markup_for_user(
                    user=resolved_user,
                    _=_,
                ),
            )
            return

        await StartProfileService.reply_not_registered(message=message, _=_)


@router.message(Command("help"))
@router.message(F.text.in_(MENU_BUTTON_HELP_VARIANTS))
class HelpHandler(StartProfileSupportMixin, MessageHandler):
    async def handle(self) -> None:
        await self.handle_help(
            message=self.event,
            _=self.data["_"],
            user=self.data.get("user"),
            telegram_profile=self.data.get("telegram_profile"),
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
