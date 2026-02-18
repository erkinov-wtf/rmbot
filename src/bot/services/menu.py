from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from django.utils import translation
from django.utils.translation import gettext as django_gettext
from django.utils.translation import gettext_noop

from account.models import User
from bot.etc.i18n import SUPPORTED_BOT_LOCALES, ensure_bot_locales_compiled
from core.utils.asyncio import run_sync
from core.utils.constants import RoleSlug

ensure_bot_locales_compiled()


class BotMenuService:
    MENU_BUTTON_ACTIVE_TICKETS = gettext_noop("🎟 Active Tickets")
    MENU_BUTTON_UNDER_QC_TICKETS = gettext_noop("🧪 Under QC")
    MENU_BUTTON_PAST_TICKETS = gettext_noop("✅ Past Tickets")
    MENU_BUTTON_MY_XP = gettext_noop("⭐ My XP")
    MENU_BUTTON_XP_HISTORY = gettext_noop("📜 XP Activity")
    MENU_BUTTON_MY_STATUS = gettext_noop("📊 My Profile")
    MENU_BUTTON_QC_CHECKS = gettext_noop("🧪 QC Checks")
    MENU_BUTTON_CREATE_TICKET = gettext_noop("🆕 Create Ticket")
    MENU_BUTTON_REVIEW_TICKETS = gettext_noop("🧾 Review Tickets")
    MENU_BUTTON_HELP = gettext_noop("❓ Help")
    MENU_BUTTON_START_ACCESS = gettext_noop("📝 Start Access Request")
    MENU_BUTTON_ACTIVE_TICKETS_VARIANTS: frozenset[str]
    MENU_BUTTON_UNDER_QC_TICKETS_VARIANTS: frozenset[str]
    MENU_BUTTON_PAST_TICKETS_VARIANTS: frozenset[str]
    MENU_BUTTON_MY_XP_VARIANTS: frozenset[str]
    MENU_BUTTON_XP_HISTORY_VARIANTS: frozenset[str]
    MENU_BUTTON_MY_STATUS_VARIANTS: frozenset[str]
    MENU_BUTTON_QC_CHECKS_VARIANTS: frozenset[str]
    MENU_BUTTON_CREATE_TICKET_VARIANTS: frozenset[str]
    MENU_BUTTON_REVIEW_TICKETS_VARIANTS: frozenset[str]
    MENU_BUTTON_HELP_VARIANTS: frozenset[str]
    MENU_BUTTON_START_ACCESS_VARIANTS: frozenset[str]

    @classmethod
    def _variants(cls, button_text: str) -> frozenset[str]:
        del cls
        variants = {button_text}
        for locale in sorted(SUPPORTED_BOT_LOCALES):
            with translation.override(locale):
                variants.add(django_gettext(button_text))
        return frozenset({value for value in variants if value})

    @staticmethod
    def _label(*, text: str, _) -> str:
        if _ is None:
            return django_gettext(text)
        return _(text)

    @classmethod
    def build_main_menu_keyboard(
        cls,
        *,
        is_technician: bool,
        can_create_ticket: bool = False,
        can_review_ticket: bool = False,
        can_qc_checks: bool = False,
        include_start_access: bool = False,
        _=None,
    ) -> ReplyKeyboardMarkup:
        del can_create_ticket, can_review_ticket, can_qc_checks
        rows: list[list[KeyboardButton]] = []

        if is_technician:
            rows.extend(
                [
                    [
                        KeyboardButton(
                            text=cls._label(text=cls.MENU_BUTTON_ACTIVE_TICKETS, _=_),
                        ),
                        KeyboardButton(
                            text=cls._label(
                                text=cls.MENU_BUTTON_UNDER_QC_TICKETS,
                                _=_,
                            ),
                        ),
                    ],
                    [
                        KeyboardButton(
                            text=cls._label(text=cls.MENU_BUTTON_PAST_TICKETS, _=_),
                        ),
                        KeyboardButton(
                            text=cls._label(text=cls.MENU_BUTTON_MY_XP, _=_)
                        ),
                    ],
                    [
                        KeyboardButton(
                            text=cls._label(text=cls.MENU_BUTTON_XP_HISTORY, _=_),
                        ),
                        KeyboardButton(
                            text=cls._label(text=cls.MENU_BUTTON_MY_STATUS, _=_)
                        ),
                    ],
                ]
            )
            rows.append(
                [KeyboardButton(text=cls._label(text=cls.MENU_BUTTON_HELP, _=_))]
            )
        else:
            rows.append(
                [
                    KeyboardButton(
                        text=cls._label(text=cls.MENU_BUTTON_MY_STATUS, _=_)
                    ),
                    KeyboardButton(text=cls._label(text=cls.MENU_BUTTON_HELP, _=_)),
                ]
            )
        if include_start_access:
            rows.append(
                [
                    KeyboardButton(
                        text=cls._label(text=cls.MENU_BUTTON_START_ACCESS, _=_)
                    )
                ]
            )

        return ReplyKeyboardMarkup(
            keyboard=rows,
            resize_keyboard=True,
            one_time_keyboard=False,
            selective=False,
        )

    @staticmethod
    async def _is_technician_user(user: User | None) -> bool:
        if not user or not user.is_active:
            return False
        return await run_sync(
            user.roles.filter(slug=RoleSlug.TECHNICIAN, deleted_at__isnull=True).exists
        )

    @classmethod
    async def main_menu_markup_for_user(
        cls,
        *,
        user: User | None,
        include_start_access: bool = False,
        _=None,
    ) -> ReplyKeyboardMarkup:
        return cls.build_main_menu_keyboard(
            is_technician=await cls._is_technician_user(user),
            include_start_access=include_start_access,
            _=_,
        )


BotMenuService.MENU_BUTTON_ACTIVE_TICKETS_VARIANTS = BotMenuService._variants(
    BotMenuService.MENU_BUTTON_ACTIVE_TICKETS
)
BotMenuService.MENU_BUTTON_UNDER_QC_TICKETS_VARIANTS = BotMenuService._variants(
    BotMenuService.MENU_BUTTON_UNDER_QC_TICKETS
)
BotMenuService.MENU_BUTTON_PAST_TICKETS_VARIANTS = BotMenuService._variants(
    BotMenuService.MENU_BUTTON_PAST_TICKETS
)
BotMenuService.MENU_BUTTON_MY_XP_VARIANTS = BotMenuService._variants(
    BotMenuService.MENU_BUTTON_MY_XP
)
BotMenuService.MENU_BUTTON_XP_HISTORY_VARIANTS = BotMenuService._variants(
    BotMenuService.MENU_BUTTON_XP_HISTORY
)
BotMenuService.MENU_BUTTON_MY_STATUS_VARIANTS = BotMenuService._variants(
    BotMenuService.MENU_BUTTON_MY_STATUS
)
BotMenuService.MENU_BUTTON_QC_CHECKS_VARIANTS = BotMenuService._variants(
    BotMenuService.MENU_BUTTON_QC_CHECKS
)
BotMenuService.MENU_BUTTON_CREATE_TICKET_VARIANTS = BotMenuService._variants(
    BotMenuService.MENU_BUTTON_CREATE_TICKET
)
BotMenuService.MENU_BUTTON_REVIEW_TICKETS_VARIANTS = BotMenuService._variants(
    BotMenuService.MENU_BUTTON_REVIEW_TICKETS
)
BotMenuService.MENU_BUTTON_HELP_VARIANTS = BotMenuService._variants(
    BotMenuService.MENU_BUTTON_HELP
)
BotMenuService.MENU_BUTTON_START_ACCESS_VARIANTS = BotMenuService._variants(
    BotMenuService.MENU_BUTTON_START_ACCESS
)

MENU_BUTTON_ACTIVE_TICKETS = BotMenuService.MENU_BUTTON_ACTIVE_TICKETS
MENU_BUTTON_UNDER_QC_TICKETS = BotMenuService.MENU_BUTTON_UNDER_QC_TICKETS
MENU_BUTTON_PAST_TICKETS = BotMenuService.MENU_BUTTON_PAST_TICKETS
MENU_BUTTON_MY_XP = BotMenuService.MENU_BUTTON_MY_XP
MENU_BUTTON_XP_HISTORY = BotMenuService.MENU_BUTTON_XP_HISTORY
MENU_BUTTON_MY_STATUS = BotMenuService.MENU_BUTTON_MY_STATUS
MENU_BUTTON_QC_CHECKS = BotMenuService.MENU_BUTTON_QC_CHECKS
MENU_BUTTON_CREATE_TICKET = BotMenuService.MENU_BUTTON_CREATE_TICKET
MENU_BUTTON_REVIEW_TICKETS = BotMenuService.MENU_BUTTON_REVIEW_TICKETS
MENU_BUTTON_HELP = BotMenuService.MENU_BUTTON_HELP
MENU_BUTTON_START_ACCESS = BotMenuService.MENU_BUTTON_START_ACCESS

MENU_BUTTON_ACTIVE_TICKETS_VARIANTS = BotMenuService.MENU_BUTTON_ACTIVE_TICKETS_VARIANTS
MENU_BUTTON_UNDER_QC_TICKETS_VARIANTS = (
    BotMenuService.MENU_BUTTON_UNDER_QC_TICKETS_VARIANTS
)
MENU_BUTTON_PAST_TICKETS_VARIANTS = BotMenuService.MENU_BUTTON_PAST_TICKETS_VARIANTS
MENU_BUTTON_MY_XP_VARIANTS = BotMenuService.MENU_BUTTON_MY_XP_VARIANTS
MENU_BUTTON_XP_HISTORY_VARIANTS = BotMenuService.MENU_BUTTON_XP_HISTORY_VARIANTS
MENU_BUTTON_MY_STATUS_VARIANTS = BotMenuService.MENU_BUTTON_MY_STATUS_VARIANTS
MENU_BUTTON_QC_CHECKS_VARIANTS = BotMenuService.MENU_BUTTON_QC_CHECKS_VARIANTS
MENU_BUTTON_CREATE_TICKET_VARIANTS = BotMenuService.MENU_BUTTON_CREATE_TICKET_VARIANTS
MENU_BUTTON_REVIEW_TICKETS_VARIANTS = BotMenuService.MENU_BUTTON_REVIEW_TICKETS_VARIANTS
MENU_BUTTON_HELP_VARIANTS = BotMenuService.MENU_BUTTON_HELP_VARIANTS
MENU_BUTTON_START_ACCESS_VARIANTS = BotMenuService.MENU_BUTTON_START_ACCESS_VARIANTS
