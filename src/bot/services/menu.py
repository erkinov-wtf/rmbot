from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from django.utils import translation
from django.utils.translation import gettext as django_gettext
from django.utils.translation import gettext_noop

from account.models import User
from bot.etc.i18n import SUPPORTED_BOT_LOCALES
from bot.permissions import resolve_ticket_bot_permissions
from core.utils.asyncio import run_sync
from core.utils.constants import RoleSlug

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


def _variants(button_text: str) -> frozenset[str]:
    variants = {button_text}
    for locale in sorted(SUPPORTED_BOT_LOCALES):
        with translation.override(locale):
            variants.add(django_gettext(button_text))
    return frozenset({value for value in variants if value})


MENU_BUTTON_ACTIVE_TICKETS_VARIANTS = _variants(MENU_BUTTON_ACTIVE_TICKETS)
MENU_BUTTON_UNDER_QC_TICKETS_VARIANTS = _variants(MENU_BUTTON_UNDER_QC_TICKETS)
MENU_BUTTON_PAST_TICKETS_VARIANTS = _variants(MENU_BUTTON_PAST_TICKETS)
MENU_BUTTON_MY_XP_VARIANTS = _variants(MENU_BUTTON_MY_XP)
MENU_BUTTON_XP_HISTORY_VARIANTS = _variants(MENU_BUTTON_XP_HISTORY)
MENU_BUTTON_MY_STATUS_VARIANTS = _variants(MENU_BUTTON_MY_STATUS)
MENU_BUTTON_QC_CHECKS_VARIANTS = _variants(MENU_BUTTON_QC_CHECKS)
MENU_BUTTON_CREATE_TICKET_VARIANTS = _variants(MENU_BUTTON_CREATE_TICKET)
MENU_BUTTON_REVIEW_TICKETS_VARIANTS = _variants(MENU_BUTTON_REVIEW_TICKETS)
MENU_BUTTON_HELP_VARIANTS = _variants(MENU_BUTTON_HELP)
MENU_BUTTON_START_ACCESS_VARIANTS = _variants(MENU_BUTTON_START_ACCESS)


def _label(*, text: str, _) -> str:
    if _ is None:
        return django_gettext(text)
    return _(text)


def build_main_menu_keyboard(
    *,
    is_technician: bool,
    can_create_ticket: bool = False,
    can_review_ticket: bool = False,
    can_qc_checks: bool = False,
    include_start_access: bool = False,
    _=None,
) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = []
    action_row: list[KeyboardButton] = []
    if can_create_ticket:
        action_row.append(
            KeyboardButton(text=_label(text=MENU_BUTTON_CREATE_TICKET, _=_))
        )
    if can_review_ticket:
        action_row.append(
            KeyboardButton(text=_label(text=MENU_BUTTON_REVIEW_TICKETS, _=_))
        )

    if is_technician:
        rows.extend(
            [
                [
                    KeyboardButton(
                        text=_label(text=MENU_BUTTON_ACTIVE_TICKETS, _=_),
                    ),
                    KeyboardButton(
                        text=_label(text=MENU_BUTTON_UNDER_QC_TICKETS, _=_),
                    ),
                ],
                [
                    KeyboardButton(
                        text=_label(text=MENU_BUTTON_PAST_TICKETS, _=_),
                    ),
                    KeyboardButton(text=_label(text=MENU_BUTTON_MY_XP, _=_)),
                ],
                [
                    KeyboardButton(
                        text=_label(text=MENU_BUTTON_XP_HISTORY, _=_),
                    ),
                    KeyboardButton(text=_label(text=MENU_BUTTON_MY_STATUS, _=_)),
                ],
            ]
        )
        if can_qc_checks:
            rows.append([KeyboardButton(text=_label(text=MENU_BUTTON_QC_CHECKS, _=_))])
        if action_row:
            rows.append(action_row)
        rows.append([KeyboardButton(text=_label(text=MENU_BUTTON_HELP, _=_))])
    else:
        if action_row:
            rows.append(action_row)
        if can_qc_checks:
            rows.append([KeyboardButton(text=_label(text=MENU_BUTTON_QC_CHECKS, _=_))])
        rows.append(
            [
                KeyboardButton(text=_label(text=MENU_BUTTON_MY_STATUS, _=_)),
                KeyboardButton(text=_label(text=MENU_BUTTON_HELP, _=_)),
            ]
        )
    if include_start_access:
        rows.append([KeyboardButton(text=_label(text=MENU_BUTTON_START_ACCESS, _=_))])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        one_time_keyboard=False,
        selective=False,
    )


async def _is_technician_user(user: User | None) -> bool:
    if not user or not user.is_active:
        return False
    return await run_sync(
        user.roles.filter(slug=RoleSlug.TECHNICIAN, deleted_at__isnull=True).exists
    )


async def main_menu_markup_for_user(
    *,
    user: User | None,
    include_start_access: bool = False,
    _=None,
) -> ReplyKeyboardMarkup:
    ticket_permissions = await run_sync(
        resolve_ticket_bot_permissions,
        user=user,
    )
    return build_main_menu_keyboard(
        is_technician=await _is_technician_user(user),
        can_create_ticket=ticket_permissions.can_create,
        can_review_ticket=ticket_permissions.can_open_review_panel,
        can_qc_checks=ticket_permissions.can_qc,
        include_start_access=include_start_access,
        _=_,
    )
