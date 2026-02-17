from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from django.db.models import Count, Sum
from django.utils import timezone

from account.models import TelegramProfile, User
from bot.services.menu import build_main_menu_keyboard, main_menu_markup_for_user
from core.utils.asyncio import run_sync
from core.utils.constants import RoleSlug, TicketStatus
from gamification.models import XPTransaction
from ticket.models import Ticket

XP_HISTORY_CALLBACK_PREFIX = "xph"
XP_HISTORY_DEFAULT_LIMIT = 5
XP_HISTORY_MAX_LIMIT = 30


async def _ticket_status_counts_for_technician(*, technician_id: int) -> dict[str, int]:
    queryset = (
        Ticket.domain.filter(technician_id=technician_id)
        .values("status")
        .annotate(total=Count("id"))
    )
    rows = await run_sync(list, queryset)
    return {str(item["status"]): int(item["total"] or 0) for item in rows}


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
    try:
        return str(RoleSlug(role_slug).label)
    except ValueError:
        pass
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
    max_offset = ((total_count - 1) // normalized_limit) * normalized_limit
    prev_offset = max(0, safe_offset - normalized_limit)
    next_offset = min(max_offset, safe_offset + normalized_limit)

    navigation_row = [
        InlineKeyboardButton(
            text="<",
            callback_data=_build_xp_history_callback_data(
                limit=normalized_limit,
                offset=prev_offset,
            ),
        ),
        InlineKeyboardButton(
            text=f"{page}/{page_count}",
            callback_data=_build_xp_history_callback_data(
                limit=normalized_limit,
                offset=safe_offset,
            ),
        ),
        InlineKeyboardButton(
            text=">",
            callback_data=_build_xp_history_callback_data(
                limit=normalized_limit,
                offset=next_offset,
            ),
        ),
    ]
    return InlineKeyboardMarkup(inline_keyboard=[navigation_row])


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
            _=_,
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
        reply_markup=await main_menu_markup_for_user(user=resolved_user, _=_),
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
            _=_,
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
