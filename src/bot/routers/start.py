import re

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from django.db.models import Count, Sum
from django.utils import timezone

from account.models import TelegramProfile, User
from account.services import AccountService
from core.utils.asyncio import run_sync
from core.utils.constants import RoleSlug, TicketStatus
from gamification.models import XPTransaction
from ticket.models import Ticket

router = Router(name="start")
PHONE_PATTERN = re.compile(r"^\+?[1-9][0-9]{7,14}$")

MENU_BUTTON_ACTIVE_TICKETS = "🎟 Active Tickets"
MENU_BUTTON_UNDER_QC_TICKETS = "🧪 Under QC"
MENU_BUTTON_PAST_TICKETS = "✅ Past Tickets"
MENU_BUTTON_MY_XP = "⭐ My XP"
MENU_BUTTON_XP_HISTORY = "📜 XP History"
MENU_BUTTON_MY_STATUS = "📊 My Stats"
MENU_BUTTON_HELP = "❓ Help"
MENU_BUTTON_START_ACCESS = "📝 Start Access Request"


class AccessRequestForm(StatesGroup):
    first_name = State()
    last_name = State()
    phone = State()


def _normalize_phone(raw: str) -> str | None:
    compact = raw.strip().replace(" ", "").replace("-", "")
    if not compact:
        return None
    if not PHONE_PATTERN.fullmatch(compact):
        return None
    return compact if compact.startswith("+") else f"+{compact}"


def _phone_keyboard(_) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text=_("Share phone number"),
                    request_contact=True,
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
        selective=True,
    )


def build_main_menu_keyboard(
    *,
    is_technician: bool,
    include_start_access: bool = False,
) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = []
    if is_technician:
        rows.extend(
            [
                [
                    KeyboardButton(text=MENU_BUTTON_ACTIVE_TICKETS),
                    KeyboardButton(text=MENU_BUTTON_UNDER_QC_TICKETS),
                ],
                [
                    KeyboardButton(text=MENU_BUTTON_PAST_TICKETS),
                    KeyboardButton(text=MENU_BUTTON_MY_XP),
                ],
                [
                    KeyboardButton(text=MENU_BUTTON_XP_HISTORY),
                    KeyboardButton(text=MENU_BUTTON_MY_STATUS),
                ],
                [KeyboardButton(text=MENU_BUTTON_HELP)],
            ]
        )
    else:
        rows.append(
            [
                KeyboardButton(text=MENU_BUTTON_MY_STATUS),
                KeyboardButton(text=MENU_BUTTON_HELP),
            ]
        )
    if include_start_access:
        rows.append([KeyboardButton(text=MENU_BUTTON_START_ACCESS)])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        one_time_keyboard=False,
        selective=False,
    )


async def _ticket_status_counts_for_technician(*, technician_id: int) -> dict[str, int]:
    queryset = (
        Ticket.domain.filter(technician_id=technician_id)
        .values("status")
        .annotate(total=Count("id"))
    )
    rows = await run_sync(list, queryset)
    return {str(item["status"]): int(item["total"] or 0) for item in rows}


async def _is_technician_user(user: User | None) -> bool:
    if not user or not user.is_active:
        return False
    return await run_sync(
        user.roles.filter(slug=RoleSlug.TECHNICIAN, deleted_at__isnull=True).exists
    )


async def _main_menu_markup_for_user(
    *,
    user: User | None,
    include_start_access: bool = False,
) -> ReplyKeyboardMarkup:
    return build_main_menu_keyboard(
        is_technician=await _is_technician_user(user),
        include_start_access=include_start_access,
    )


async def _has_active_linked_user(
    user: User | None,
    telegram_profile: TelegramProfile | None,
) -> bool:
    if user and user.is_active:
        return True

    profile_user_id = telegram_profile.user_id if telegram_profile else None
    if not profile_user_id:
        return False

    return await run_sync(
        User.all_objects.filter(pk=profile_user_id, is_active=True).exists
    )


def _format_status_datetime(value) -> str:
    if value is None:
        return "-"
    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")


async def _resolve_active_user_for_status(
    *,
    user: User | None,
    telegram_profile: TelegramProfile | None,
) -> User | None:
    if user and user.is_active:
        return user

    profile_user_id = telegram_profile.user_id if telegram_profile else None
    if not profile_user_id:
        return None

    return await run_sync(
        User.all_objects.prefetch_related("roles")
        .filter(pk=profile_user_id, is_active=True)
        .first
    )


async def _active_role_slugs(*, user: User) -> list[str]:
    return await run_sync(
        list,
        user.roles.filter(deleted_at__isnull=True).values_list("slug", flat=True),
    )


async def _active_ticket_count_for_technician(*, technician_id: int) -> int:
    status_counts = await _ticket_status_counts_for_technician(
        technician_id=technician_id
    )
    return (
        status_counts.get(TicketStatus.ASSIGNED, 0)
        + status_counts.get(TicketStatus.REWORK, 0)
        + status_counts.get(TicketStatus.IN_PROGRESS, 0)
    )


async def _xp_totals_for_user(*, user_id: int) -> tuple[int, int]:
    aggregate = await run_sync(
        XPTransaction.objects.filter(user_id=user_id).aggregate,
        total_xp=Sum("amount"),
        tx_count=Count("id"),
    )
    return int(aggregate.get("total_xp") or 0), int(aggregate.get("tx_count") or 0)


def _format_entry_created_at(created_at) -> str:
    return timezone.localtime(created_at).strftime("%Y-%m-%d %H:%M")


async def _xp_history_for_user(*, user_id: int, limit: int = 10) -> list[XPTransaction]:
    queryset = XPTransaction.objects.filter(user_id=user_id).order_by(
        "-created_at", "-id"
    )
    return await run_sync(list, queryset[:limit])


async def _build_active_status_text(
    *,
    user: User,
    _,
) -> str:
    role_slugs = await _active_role_slugs(user=user)
    full_name = (
        " ".join(part for part in [user.first_name, user.last_name] if part) or "-"
    )
    lines = [
        _("Access status: active"),
        f"Name: {full_name}",
        f"Username: @{user.username}" if user.username else "Username: -",
        f"Phone: {user.phone or '-'}",
        f"Level: {user.get_level_display()}",
        f"Roles: {', '.join(role_slugs) if role_slugs else '-'}",
        f"Linked user ID: {user.id}",
    ]
    total_xp, tx_count = await _xp_totals_for_user(user_id=user.id)
    lines.append(f"Total XP: {total_xp} (transactions: {tx_count})")
    if RoleSlug.TECHNICIAN in role_slugs:
        status_counts = await _ticket_status_counts_for_technician(
            technician_id=user.id
        )
        active_ticket_count = await _active_ticket_count_for_technician(
            technician_id=user.id
        )
        lines.append(f"Active tickets in queue: {active_ticket_count}")
        lines.append(
            f"Waiting QC tickets: {status_counts.get(TicketStatus.WAITING_QC, 0)}"
        )
        lines.append(f"Done tickets: {status_counts.get(TicketStatus.DONE, 0)}")
    return "\n".join(lines)


def _build_pending_status_text(*, pending, _) -> str:
    full_name = (
        " ".join(part for part in [pending.first_name, pending.last_name] if part)
        or "-"
    )
    lines = [
        _("Access status: pending"),
        f"Name: {full_name}",
        f"Username: @{pending.username}" if pending.username else "Username: -",
        f"Phone: {pending.phone or '-'}",
        f"Requested at: {_format_status_datetime(pending.created_at)}",
        f"Request ID: {pending.id}",
    ]
    return "\n".join(lines)


async def _build_xp_summary_text(*, user: User, _) -> str:
    total_xp, tx_count = await _xp_totals_for_user(user_id=user.id)
    recent_entries = await _xp_history_for_user(user_id=user.id, limit=5)

    lines = [
        _("XP summary"),
        f"Total XP: {total_xp}",
        f"Transactions: {tx_count}",
    ]
    if not recent_entries:
        lines.append("No XP transactions yet.")
        return "\n".join(lines)

    lines.append("Recent transactions:")
    for entry in recent_entries:
        amount = int(entry.amount or 0)
        sign = "+" if amount >= 0 else ""
        lines.append(
            f"{_format_entry_created_at(entry.created_at)} | {sign}{amount} | {entry.entry_type}"
        )
    return "\n".join(lines)


async def _build_xp_history_text(*, user: User, _, limit: int = 15) -> str:
    entries = await _xp_history_for_user(user_id=user.id, limit=limit)
    lines = [_("XP transaction history")]

    if not entries:
        lines.append("No XP transactions yet.")
        return "\n".join(lines)

    for entry in entries:
        amount = int(entry.amount or 0)
        sign = "+" if amount >= 0 else ""
        lines.append(
            f"{_format_entry_created_at(entry.created_at)} | {sign}{amount} | {entry.entry_type} | {entry.reference}"
        )
    return "\n".join(lines)


async def _resolve_registered_user(
    *,
    user: User | None,
    telegram_profile: TelegramProfile | None,
) -> User | None:
    return await _resolve_active_user_for_status(
        user=user,
        telegram_profile=telegram_profile,
    )


async def _reply_not_registered(
    *,
    message: Message,
    _,
) -> None:
    await message.answer(
        _("You are not registered. Use /start to submit access request."),
        reply_markup=build_main_menu_keyboard(
            is_technician=False,
            include_start_access=True,
        ),
    )


async def _reply_xp_summary(
    *,
    message: Message,
    user: User | None,
    telegram_profile: TelegramProfile | None,
    _,
) -> None:
    resolved_user = await _resolve_registered_user(
        user=user,
        telegram_profile=telegram_profile,
    )
    if resolved_user is None:
        await _reply_not_registered(message=message, _=_)
        return
    await message.answer(
        await _build_xp_summary_text(user=resolved_user, _=_),
        reply_markup=await _main_menu_markup_for_user(user=resolved_user),
    )


async def _reply_xp_history(
    *,
    message: Message,
    user: User | None,
    telegram_profile: TelegramProfile | None,
    _,
) -> None:
    resolved_user = await _resolve_registered_user(
        user=user,
        telegram_profile=telegram_profile,
    )
    if resolved_user is None:
        await _reply_not_registered(message=message, _=_)
        return
    await message.answer(
        await _build_xp_history_text(user=resolved_user, _=_),
        reply_markup=await _main_menu_markup_for_user(user=resolved_user),
    )


@router.message(CommandStart())
async def start_handler(
    message: Message,
    state: FSMContext,
    _,
    user: User = None,
    telegram_profile: TelegramProfile = None,
):
    profile = telegram_profile or await run_sync(
        AccountService.upsert_telegram_profile, message.from_user
    )

    pending = await run_sync(
        AccountService.get_pending_access_request,
        profile.telegram_id if profile else message.from_user.id,
    )
    if pending:
        await state.clear()
        await message.answer(
            _("Your access request is already pending."),
            reply_markup=build_main_menu_keyboard(
                is_technician=False,
                include_start_access=False,
            ),
        )
        return

    if await _has_active_linked_user(user, profile):
        await state.clear()
        await message.answer(
            _("You are registered and linked."),
            reply_markup=await _main_menu_markup_for_user(user=user),
        )
        return

    await state.set_state(AccessRequestForm.first_name)
    await message.answer(
        _("Let's create your access request. Please enter your first name."),
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(Command("help"))
async def help_handler(message: Message, _, user: User = None):
    help_text = "\n".join(
        [
            _("Available commands:"),
            "/start - " + _("Start bot"),
            "/my - " + _("Show my access status"),
            "/queue - " + _("Show my ticket queue"),
            "/active - " + _("Show my ticket queue"),
            "/tech - " + _("Open technician ticket controls"),
            "/under_qc - " + _("Show my tickets waiting QC"),
            "/past - " + _("Show my past tickets"),
            "/xp - " + _("Show my XP summary"),
            "/xp_history - " + _("Show my XP transaction history"),
            "/cancel - " + _("Cancel current form"),
            "/help - " + _("Show help"),
        ]
    )
    await message.answer(
        help_text,
        reply_markup=await _main_menu_markup_for_user(
            user=user,
            include_start_access=not bool(user and user.is_active),
        ),
    )


@router.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext, _, user: User = None):
    current_state = await state.get_state()
    if not current_state:
        await message.answer(
            _("There is no active form right now."),
            reply_markup=await _main_menu_markup_for_user(
                user=user,
                include_start_access=not bool(user and user.is_active),
            ),
        )
        return

    await state.clear()
    await message.answer(
        _("Access request form was canceled."),
        reply_markup=await _main_menu_markup_for_user(
            user=user,
            include_start_access=not bool(user and user.is_active),
        ),
    )


@router.message(AccessRequestForm.first_name, F.text, ~F.text.startswith("/"))
async def request_first_name_handler(message: Message, state: FSMContext, _):
    first_name = (message.text or "").strip()
    if len(first_name) < 2:
        await message.answer(_("Please enter a valid first name."))
        return
    await state.update_data(first_name=first_name)
    await state.set_state(AccessRequestForm.last_name)
    await message.answer(_("Please enter your last name."))


@router.message(AccessRequestForm.last_name, F.text, ~F.text.startswith("/"))
async def request_last_name_handler(message: Message, state: FSMContext, _):
    last_name = (message.text or "").strip()
    if len(last_name) < 2:
        await message.answer(_("Please enter a valid last name."))
        return
    await state.update_data(last_name=last_name)
    await state.set_state(AccessRequestForm.phone)
    await message.answer(
        _("Please share your phone number or type it in international format."),
        reply_markup=_phone_keyboard(_),
    )


async def _finalize_access_request(
    message: Message, state: FSMContext, translator, phone: str
) -> None:
    data = await state.get_data()
    try:
        _access_request, created = await run_sync(
            AccountService.ensure_pending_access_request_from_bot,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=data["first_name"],
            last_name=data["last_name"],
            phone=phone,
        )
    except ValueError as exc:
        await message.answer(
            translator(str(exc)),
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    await state.clear()
    pending_menu = build_main_menu_keyboard(
        is_technician=False,
        include_start_access=False,
    )
    if created:
        await message.answer(
            translator("Access request submitted. We will review and notify you."),
            reply_markup=pending_menu,
        )
        return
    await message.answer(
        translator("Your access request is already pending."),
        reply_markup=pending_menu,
    )


@router.message(AccessRequestForm.phone, F.contact)
async def request_phone_contact_handler(message: Message, state: FSMContext, _):
    contact = message.contact
    if contact.user_id and contact.user_id != message.from_user.id:
        await message.answer(_("Please share your own phone number."))
        return
    phone = _normalize_phone(contact.phone_number or "")
    if not phone:
        await message.answer(_("Please share a valid phone number."))
        return
    await _finalize_access_request(message, state, _, phone)


@router.message(AccessRequestForm.phone, F.text, ~F.text.startswith("/"))
async def request_phone_text_handler(message: Message, state: FSMContext, _):
    phone = _normalize_phone(message.text or "")
    if not phone:
        await message.answer(
            _("Please send a valid phone number in international format.")
        )
        return
    await _finalize_access_request(message, state, _, phone)


@router.message(Command("my"))
async def my_handler(
    message: Message, _, user: User = None, telegram_profile: TelegramProfile = None
):
    pending = await run_sync(
        AccountService.get_pending_access_request, message.from_user.id
    )
    if pending:
        await message.answer(
            _build_pending_status_text(pending=pending, _=_),
            reply_markup=build_main_menu_keyboard(
                is_technician=False,
                include_start_access=False,
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
            reply_markup=await _main_menu_markup_for_user(user=resolved_user),
        )
        return

    await _reply_not_registered(message=message, _=_)


@router.message(Command("xp"))
async def my_xp_handler(
    message: Message,
    _,
    user: User = None,
    telegram_profile: TelegramProfile = None,
):
    await _reply_xp_summary(
        message=message,
        user=user,
        telegram_profile=telegram_profile,
        _=_,
    )


@router.message(Command("xp_history"))
async def my_xp_history_handler(
    message: Message,
    _,
    user: User = None,
    telegram_profile: TelegramProfile = None,
):
    await _reply_xp_history(
        message=message,
        user=user,
        telegram_profile=telegram_profile,
        _=_,
    )


@router.message(StateFilter(None), F.text == MENU_BUTTON_HELP)
async def help_button_handler(message: Message, _, user: User = None):
    await help_handler(message, _, user=user)


@router.message(StateFilter(None), F.text == MENU_BUTTON_MY_STATUS)
async def my_button_handler(
    message: Message,
    _,
    user: User = None,
    telegram_profile: TelegramProfile = None,
):
    await my_handler(
        message,
        _,
        user=user,
        telegram_profile=telegram_profile,
    )


@router.message(StateFilter(None), F.text == MENU_BUTTON_MY_XP)
async def my_xp_button_handler(
    message: Message,
    _,
    user: User = None,
    telegram_profile: TelegramProfile = None,
):
    await _reply_xp_summary(
        message=message,
        user=user,
        telegram_profile=telegram_profile,
        _=_,
    )


@router.message(StateFilter(None), F.text == MENU_BUTTON_XP_HISTORY)
async def my_xp_history_button_handler(
    message: Message,
    _,
    user: User = None,
    telegram_profile: TelegramProfile = None,
):
    await _reply_xp_history(
        message=message,
        user=user,
        telegram_profile=telegram_profile,
        _=_,
    )


@router.message(StateFilter(None), F.text == MENU_BUTTON_START_ACCESS)
async def start_button_handler(
    message: Message,
    state: FSMContext,
    _,
    user: User = None,
    telegram_profile: TelegramProfile = None,
):
    await start_handler(
        message,
        state,
        _,
        user=user,
        telegram_profile=telegram_profile,
    )
