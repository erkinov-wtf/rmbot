import re

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
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
from core.utils.constants import AccessRequestStatus, RoleSlug, TicketStatus
from gamification.models import XPTransaction
from ticket.models import Ticket

router = Router(name="start")
PHONE_PATTERN = re.compile(r"^\+?[1-9][0-9]{7,14}$")

MENU_BUTTON_ACTIVE_TICKETS = "🎟 Active Tickets"
MENU_BUTTON_UNDER_QC_TICKETS = "🧪 Under QC"
MENU_BUTTON_PAST_TICKETS = "✅ Past Tickets"
MENU_BUTTON_MY_XP = "⭐ My XP"
MENU_BUTTON_XP_HISTORY = "📜 XP Activity"
MENU_BUTTON_MY_STATUS = "📊 My Profile"
MENU_BUTTON_HELP = "❓ Help"
MENU_BUTTON_START_ACCESS = "📝 Start Access Request"
XP_HISTORY_CALLBACK_PREFIX = "xph"
XP_HISTORY_DEFAULT_LIMIT = 10
XP_HISTORY_MAX_LIMIT = 30


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


async def _has_inactive_linked_user(
    *,
    telegram_profile: TelegramProfile | None,
) -> bool:
    profile_user_id = telegram_profile.user_id if telegram_profile else None
    if profile_user_id and await run_sync(
        User.all_objects.filter(pk=profile_user_id, is_active=False).exists
    ):
        return True

    telegram_id = telegram_profile.telegram_id if telegram_profile else None
    if not telegram_id:
        return False

    return await run_sync(
        User.all_objects.filter(
            access_requests__telegram_id=telegram_id,
            access_requests__status=AccessRequestStatus.APPROVED,
            is_active=False,
        ).exists
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


def _normalize_xp_history_limit(limit: int) -> int:
    try:
        normalized_limit = int(limit)
    except (TypeError, ValueError):
        normalized_limit = XP_HISTORY_DEFAULT_LIMIT
    return min(max(1, normalized_limit), XP_HISTORY_MAX_LIMIT)


def _normalize_xp_history_offset(offset: int) -> int:
    try:
        normalized_offset = int(offset)
    except (TypeError, ValueError):
        return 0
    return max(0, normalized_offset)


def _role_label(*, role_slug: str, _) -> str:
    if role_slug == RoleSlug.TECHNICIAN:
        return _("Technician")
    if role_slug == RoleSlug.MASTER:
        return _("Master")
    if role_slug == RoleSlug.QC_INSPECTOR:
        return _("QC Inspector")
    if role_slug == RoleSlug.OPS_MANAGER:
        return _("Ops Manager")
    if role_slug == RoleSlug.SUPER_ADMIN:
        return _("Super Admin")
    return role_slug.replace("_", " ").replace("-", " ").title()


def _friendly_xp_description(*, entry: XPTransaction, _) -> str:
    description = str(getattr(entry, "description", "") or "").strip()
    description_map = {
        "Attendance punctuality XP": _("On-time attendance reward"),
        "Ticket completion base XP": _("Reward for completing a ticket"),
        "Ticket QC first-pass bonus XP": _("Quality check first-pass bonus"),
        "QC status update XP": _("Quality check update"),
        "Manual XP adjustment": _("Manual XP update"),
        "Weekly level-up coupon": _("Weekly level-up bonus"),
    }
    if description:
        return description_map.get(description, description)

    entry_type_display = getattr(entry, "get_entry_type_display", None)
    if callable(entry_type_display):
        resolved_display = str(entry_type_display() or "").strip()
        if resolved_display:
            return resolved_display

    raw_entry_type = str(getattr(entry, "entry_type", "") or "").strip()
    if raw_entry_type:
        return raw_entry_type.replace("_", " ").replace("-", " ").title()
    return _("XP update")


async def _xp_history_count_for_user(*, user_id: int) -> int:
    return int(await run_sync(XPTransaction.objects.filter(user_id=user_id).count))


async def _xp_history_for_user(
    *,
    user_id: int,
    limit: int = XP_HISTORY_DEFAULT_LIMIT,
    offset: int = 0,
) -> list[XPTransaction]:
    normalized_limit = _normalize_xp_history_limit(limit)
    normalized_offset = _normalize_xp_history_offset(offset)
    queryset = XPTransaction.objects.filter(user_id=user_id).order_by(
        "-created_at", "-id"
    )
    return await run_sync(
        list,
        queryset[normalized_offset : normalized_offset + normalized_limit],
    )


async def _build_active_status_text(
    *,
    user: User,
    _,
) -> str:
    role_slugs = await _active_role_slugs(user=user)
    resolved_roles = [_role_label(role_slug=role_slug, _=_) for role_slug in role_slugs]
    role_title = _("Roles") if len(resolved_roles) > 1 else _("Role")
    full_name = (
        " ".join(part for part in [user.first_name, user.last_name] if part) or "-"
    )
    lines = [
        _("Your access is active ✅"),
        f"{_('Name')}: {full_name}",
        (
            f"{_('Username')}: @{user.username}"
            if user.username
            else f"{_('Username')}: -"
        ),
        f"{_('Phone')}: {user.phone or '-'}",
        f"{_('Current level')}: {user.get_level_display()}",
        f"{role_title}: {', '.join(resolved_roles) if resolved_roles else _('No role assigned yet')}",
    ]
    total_xp, tx_count = await _xp_totals_for_user(user_id=user.id)
    lines.append(
        _("XP balance: %(xp)s points (%(updates)s updates).")
        % {"xp": total_xp, "updates": tx_count}
    )
    if RoleSlug.TECHNICIAN in role_slugs:
        status_counts = await _ticket_status_counts_for_technician(
            technician_id=user.id
        )
        active_ticket_count = await _active_ticket_count_for_technician(
            technician_id=user.id
        )
        lines.append(_("Open tickets: %(count)s") % {"count": active_ticket_count})
        lines.append(
            _("Waiting for quality check: %(count)s")
            % {"count": status_counts.get(TicketStatus.WAITING_QC, 0)}
        )
        lines.append(
            _("Completed tickets: %(count)s")
            % {"count": status_counts.get(TicketStatus.DONE, 0)}
        )
    return "\n".join(lines)


def _build_pending_status_text(*, pending, _) -> str:
    full_name = (
        " ".join(part for part in [pending.first_name, pending.last_name] if part)
        or "-"
    )
    lines = [
        _("Your access request is under review ⏳"),
        f"{_('Name')}: {full_name}",
        (
            f"{_('Username')}: @{pending.username}"
            if pending.username
            else f"{_('Username')}: -"
        ),
        f"{_('Phone')}: {pending.phone or '-'}",
        f"{_('Submitted at')}: {_format_status_datetime(pending.created_at)}",
        _("We will notify you here as soon as the review is complete."),
    ]
    return "\n".join(lines)


async def _build_xp_summary_text(*, user: User, _) -> str:
    total_xp, tx_count = await _xp_totals_for_user(user_id=user.id)
    recent_entries = await _xp_history_for_user(user_id=user.id, limit=5)

    lines = [
        _("Your XP summary"),
        f"{_('Total XP')}: {total_xp}",
        f"{_('Updates')}: {tx_count}",
    ]
    if not recent_entries:
        lines.append(_("No XP activity yet."))
        return "\n".join(lines)

    lines.append(_("Latest updates:"))
    for entry in recent_entries:
        amount = int(entry.amount or 0)
        sign = "+" if amount >= 0 else ""
        lines.append(
            f"• {_format_entry_created_at(entry.created_at)} | {sign}{amount} XP | "
            f"{_friendly_xp_description(entry=entry, _=_)}"
        )
    return "\n".join(lines)


def _build_xp_history_callback_data(*, limit: int, offset: int) -> str:
    return (
        f"{XP_HISTORY_CALLBACK_PREFIX}:"
        f"{_normalize_xp_history_limit(limit)}:"
        f"{_normalize_xp_history_offset(offset)}"
    )


def _parse_xp_history_callback_data(*, callback_data: str) -> tuple[int, int] | None:
    raw_parts = callback_data.split(":")
    if len(raw_parts) != 3:
        return None
    if raw_parts[0] != XP_HISTORY_CALLBACK_PREFIX:
        return None

    try:
        limit = int(raw_parts[1])
        offset = int(raw_parts[2])
    except ValueError:
        return None

    if limit < 1 or offset < 0:
        return None
    return _normalize_xp_history_limit(limit), _normalize_xp_history_offset(offset)


def _resolve_safe_history_offset(*, total_count: int, limit: int, offset: int) -> int:
    if total_count <= 0:
        return 0
    normalized_limit = _normalize_xp_history_limit(limit)
    normalized_offset = _normalize_xp_history_offset(offset)
    max_offset = ((total_count - 1) // normalized_limit) * normalized_limit
    return min(normalized_offset, max_offset)


def _build_xp_history_pagination_markup(
    *,
    total_count: int,
    limit: int,
    offset: int,
    _,
) -> InlineKeyboardMarkup | None:
    if total_count <= 0:
        return None

    normalized_limit = _normalize_xp_history_limit(limit)
    safe_offset = _resolve_safe_history_offset(
        total_count=total_count,
        limit=normalized_limit,
        offset=offset,
    )

    page = (safe_offset // normalized_limit) + 1
    page_count = ((total_count - 1) // normalized_limit) + 1
    navigation_row: list[InlineKeyboardButton] = []
    if safe_offset > 0:
        navigation_row.append(
            InlineKeyboardButton(
                text=_("⬅ Previous"),
                callback_data=_build_xp_history_callback_data(
                    limit=normalized_limit,
                    offset=max(0, safe_offset - normalized_limit),
                ),
            )
        )
    if safe_offset + normalized_limit < total_count:
        navigation_row.append(
            InlineKeyboardButton(
                text=_("Next ➡"),
                callback_data=_build_xp_history_callback_data(
                    limit=normalized_limit,
                    offset=safe_offset + normalized_limit,
                ),
            )
        )

    if not navigation_row:
        return None

    indicator_row = [
        InlineKeyboardButton(
            text=_("Page %(current)s/%(total)s")
            % {"current": page, "total": page_count},
            callback_data=_build_xp_history_callback_data(
                limit=normalized_limit,
                offset=safe_offset,
            ),
        )
    ]
    return InlineKeyboardMarkup(inline_keyboard=[navigation_row, indicator_row])


async def _build_xp_history_text(
    *,
    user: User,
    _,
    limit: int = XP_HISTORY_DEFAULT_LIMIT,
    offset: int = 0,
) -> tuple[str, int, int, int]:
    normalized_limit = _normalize_xp_history_limit(limit)
    total_count = await _xp_history_count_for_user(user_id=user.id)
    safe_offset = _resolve_safe_history_offset(
        total_count=total_count,
        limit=normalized_limit,
        offset=offset,
    )

    lines = [_("Your XP activity")]
    if total_count <= 0:
        lines.append(_("No XP activity yet."))
        return "\n".join(lines), total_count, normalized_limit, safe_offset

    entries = await _xp_history_for_user(
        user_id=user.id,
        limit=normalized_limit,
        offset=safe_offset,
    )
    start_item = safe_offset + 1
    end_item = safe_offset + len(entries)
    lines.append(
        _("Showing %(start)s-%(end)s of %(total)s updates.")
        % {"start": start_item, "end": end_item, "total": total_count}
    )

    for entry in entries:
        amount = int(entry.amount or 0)
        sign = "+" if amount >= 0 else ""
        lines.append(
            f"• {_format_entry_created_at(entry.created_at)} | {sign}{amount} XP | "
            f"{_friendly_xp_description(entry=entry, _=_)}"
        )
    return "\n".join(lines), total_count, normalized_limit, safe_offset


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
        _("You do not have access yet. Send /start or tap the button below."),
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
    limit: int = XP_HISTORY_DEFAULT_LIMIT,
    offset: int = 0,
) -> None:
    resolved_user = await _resolve_registered_user(
        user=user,
        telegram_profile=telegram_profile,
    )
    if resolved_user is None:
        await _reply_not_registered(message=message, _=_)
        return
    text, total_count, normalized_limit, safe_offset = await _build_xp_history_text(
        user=resolved_user,
        _=_,
        limit=limit,
        offset=offset,
    )
    await message.answer(
        text,
        reply_markup=_build_xp_history_pagination_markup(
            total_count=total_count,
            limit=normalized_limit,
            offset=safe_offset,
            _=_,
        ),
    )


async def _reply_not_registered_callback(
    *,
    query: CallbackQuery,
    _,
) -> None:
    await query.answer(
        _("You do not have access yet. Please send /start first."),
        show_alert=True,
    )
    if query.message is None:
        return
    await query.message.answer(
        _("Open access request from the menu below."),
        reply_markup=build_main_menu_keyboard(
            is_technician=False,
            include_start_access=True,
        ),
    )


async def _safe_edit_callback_message(
    *,
    query: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None,
) -> None:
    if query.message is None:
        return
    try:
        await query.message.edit_text(text=text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return
        raise


@router.callback_query(F.data.startswith(f"{XP_HISTORY_CALLBACK_PREFIX}:"))
async def xp_history_pagination_handler(
    query: CallbackQuery,
    _,
    user: User = None,
    telegram_profile: TelegramProfile = None,
):
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
            _("Your access request is already under review."),
            reply_markup=build_main_menu_keyboard(
                is_technician=False,
                include_start_access=False,
            ),
        )
        return

    if await _has_active_linked_user(user, profile):
        await state.clear()
        await message.answer(
            _("You are all set. Your account is already active."),
            reply_markup=await _main_menu_markup_for_user(user=user),
        )
        return

    if await _has_inactive_linked_user(telegram_profile=profile):
        await state.clear()
        await message.answer(
            _(
                "Your account already exists but is inactive. "
                "Please contact an administrator to reactivate it."
            ),
            reply_markup=build_main_menu_keyboard(
                is_technician=False,
                include_start_access=False,
            ),
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
            "/start - " + _("Start the bot and access setup"),
            "/my - " + _("Check my profile and access status"),
            "/queue - " + _("Open my active ticket list"),
            "/active - " + _("Open my active ticket list"),
            "/tech - " + _("Open technician ticket controls"),
            "/under_qc - " + _("Open tickets waiting for quality check"),
            "/past - " + _("Open my completed tickets"),
            "/xp - " + _("Show my XP summary"),
            "/xp_history - " + _("Show my XP activity with pages"),
            "/cancel - " + _("Cancel the current form"),
            "/help - " + _("Show this help message"),
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
            _("There is no form in progress right now."),
            reply_markup=await _main_menu_markup_for_user(
                user=user,
                include_start_access=not bool(user and user.is_active),
            ),
        )
        return

    await state.clear()
    await message.answer(
        _("Canceled. You can start a new request anytime."),
        reply_markup=await _main_menu_markup_for_user(
            user=user,
            include_start_access=not bool(user and user.is_active),
        ),
    )


@router.message(AccessRequestForm.first_name, F.text, ~F.text.startswith("/"))
async def request_first_name_handler(message: Message, state: FSMContext, _):
    first_name = (message.text or "").strip()
    if len(first_name) < 2:
        await message.answer(_("Please enter a valid first name (at least 2 letters)."))
        return
    await state.update_data(first_name=first_name)
    await state.set_state(AccessRequestForm.last_name)
    await message.answer(_("Please enter your last name."))


@router.message(AccessRequestForm.last_name, F.text, ~F.text.startswith("/"))
async def request_last_name_handler(message: Message, state: FSMContext, _):
    last_name = (message.text or "").strip()
    if len(last_name) < 2:
        await message.answer(_("Please enter a valid last name (at least 2 letters)."))
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
            translator(
                "Request submitted successfully. We will review it and message you here."
            ),
            reply_markup=pending_menu,
        )
        return
    await message.answer(
        translator("Your request is already under review."),
        reply_markup=pending_menu,
    )


@router.message(AccessRequestForm.phone, F.contact)
async def request_phone_contact_handler(message: Message, state: FSMContext, _):
    contact = message.contact
    if contact.user_id and contact.user_id != message.from_user.id:
        await message.answer(
            _("Please share your own phone number, not someone else's.")
        )
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
