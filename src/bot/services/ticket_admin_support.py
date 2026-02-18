from __future__ import annotations

from html import escape
from types import SimpleNamespace

from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from django.utils.translation import gettext, gettext_noop

from account.models import User
from api.v1.ticket.serializers import TicketSerializer
from bot.permissions import TicketBotPermissionSet, resolve_ticket_bot_permissions
from bot.services.menu import BotMenuService
from core.utils.asyncio import run_sync
from core.utils.constants import (
    RoleSlug,
    TicketColor,
    TicketStatus,
    TicketTransitionAction,
)
from inventory.models import InventoryItem
from ticket.models import Ticket
from ticket.services_workflow import TicketWorkflowService

CREATE_CALLBACK_PREFIX = "tc"
REVIEW_QUEUE_CALLBACK_PREFIX = "trq"
REVIEW_ACTION_CALLBACK_PREFIX = "tra"

ITEMS_PER_PAGE = 5
REVIEW_ITEMS_PER_PAGE = 5
TECHNICIAN_OPTIONS_PER_PAGE = 5

REVIEW_QUEUE_ACTION_OPEN = "open"
REVIEW_QUEUE_ACTION_REFRESH = "refresh"

REVIEW_ACTION_ASSIGN_OPEN = "assign"
REVIEW_ACTION_ASSIGN_EXEC = "at"
REVIEW_ACTION_ASSIGN_PAGE = "ap"
REVIEW_ACTION_MANUAL_OPEN = "manual"
REVIEW_ACTION_MANUAL_COLOR = "mc"
REVIEW_ACTION_MANUAL_XP = "mx"
REVIEW_ACTION_MANUAL_ADJ = "adj"
REVIEW_ACTION_MANUAL_SAVE = "ms"
REVIEW_ACTION_BACK = "bk"

VALID_TICKET_COLORS = {choice.value for choice in TicketColor}
MANUAL_XP_PRESETS = (0, 5, 10, 15, 20, 30, 40, 50)

TICKET_STATUS_LABELS = {
    TicketStatus.UNDER_REVIEW: gettext_noop("Under review"),
    TicketStatus.NEW: gettext_noop("New"),
    TicketStatus.ASSIGNED: gettext_noop("Assigned"),
    TicketStatus.IN_PROGRESS: gettext_noop("In progress"),
    TicketStatus.WAITING_QC: gettext_noop("Waiting QC"),
    TicketStatus.REWORK: gettext_noop("Rework"),
    TicketStatus.DONE: gettext_noop("Done"),
}
ASSIGNABLE_TICKET_STATUSES = {
    TicketStatus.UNDER_REVIEW,
    TicketStatus.NEW,
    TicketStatus.ASSIGNED,
    TicketStatus.REWORK,
}

ERROR_INVALID_INPUT = gettext_noop("Invalid input.")
ERROR_TICKET_NOT_FOUND = gettext_noop("⚠️ Ticket was not found.")
ERROR_TECHNICIAN_NOT_FOUND = gettext_noop("Technician user does not exist.")
ERROR_USER_NOT_TECHNICIAN = gettext_noop("Selected user does not have TECHNICIAN role.")


class TicketCreateForm(StatesGroup):
    flow = State()


class TicketReviewForm(StatesGroup):
    flow = State()


def _extract_error_message(detail, _=None) -> str:
    translator = _ or gettext
    if isinstance(detail, dict):
        first_key = next(iter(detail.keys()), None)
        if first_key is None:
            return translator(ERROR_INVALID_INPUT)
        message = _extract_error_message(detail[first_key], _=translator)
        if str(first_key) == "non_field_errors":
            return message
        return f"{first_key}: {message}"
    if isinstance(detail, list):
        if not detail:
            return translator(ERROR_INVALID_INPUT)
        return _extract_error_message(detail[0], _=translator)
    return str(detail)


def _user_label(*, user: User | None, fallback: str) -> str:
    if user is None:
        return fallback
    full_name = " ".join(
        part for part in [user.first_name, user.last_name] if part
    ).strip()
    if full_name and user.username:
        return f"{full_name} (@{user.username})"
    if full_name:
        return full_name
    if user.username:
        return f"@{user.username}"
    return fallback


def _status_label(*, status: str, _=None) -> str:
    translator = _ or gettext
    default_label = str(status).replace("_", " ").title()
    return translator(TICKET_STATUS_LABELS.get(status, default_label))


def _can_assign_ticket_status(*, status: str) -> bool:
    return str(status) in ASSIGNABLE_TICKET_STATUSES


def _normalize_page(*, page: int) -> int:
    try:
        normalized_page = int(page)
    except (TypeError, ValueError):
        return 1
    return max(1, normalized_page)


def _pagination_window(
    *, page: int, per_page: int, total_count: int
) -> tuple[int, int, int]:
    safe_per_page = max(1, int(per_page or 1))
    page_count = max(1, ((max(0, int(total_count or 0)) - 1) // safe_per_page) + 1)
    safe_page = min(_normalize_page(page=page), page_count)
    offset = (safe_page - 1) * safe_per_page
    return safe_page, page_count, offset


def _query_inventory_items_page(
    *,
    page: int,
    per_page: int = ITEMS_PER_PAGE,
) -> tuple[list[InventoryItem], int, int, int]:
    queryset = (
        InventoryItem.domain.get_queryset()
        .filter(is_active=True)
        .select_related("category")
        .order_by("serial_number", "id")
    )
    total_count = int(queryset.count())
    safe_page, page_count, offset = _pagination_window(
        page=page,
        per_page=per_page,
        total_count=total_count,
    )
    items = list(queryset[offset : offset + per_page])
    return items, safe_page, page_count, total_count


def _review_queue_tickets(
    *,
    page: int,
    per_page: int = REVIEW_ITEMS_PER_PAGE,
) -> tuple[list[Ticket], int, int, int]:
    queryset = Ticket.domain.select_related("inventory_item", "technician").order_by(
        "-created_at", "-id"
    )
    total_count = int(queryset.count())
    safe_page, page_count, offset = _pagination_window(
        page=page,
        per_page=per_page,
        total_count=total_count,
    )
    return (
        list(queryset[offset : offset + per_page]),
        safe_page,
        page_count,
        total_count,
    )


def _review_ticket(*, ticket_id: int) -> Ticket | None:
    return (
        Ticket.domain.select_related("inventory_item", "technician", "master")
        .filter(pk=ticket_id)
        .first()
    )


def _list_technician_options_page(
    *,
    page: int,
    per_page: int = TECHNICIAN_OPTIONS_PER_PAGE,
) -> tuple[list[tuple[int, str]], int, int, int]:
    queryset = (
        User.objects.filter(
            is_active=True,
            roles__slug=RoleSlug.TECHNICIAN,
            roles__deleted_at__isnull=True,
        )
        .order_by("first_name", "last_name", "username", "id")
        .distinct()
    )
    total_count = int(queryset.count())
    safe_page, page_count, offset = _pagination_window(
        page=page,
        per_page=per_page,
        total_count=total_count,
    )
    users = list(queryset[offset : offset + per_page])
    options = [
        (
            user.id,
            _user_label(
                user=user,
                fallback=gettext("User #%(user_id)s") % {"user_id": user.id},
            ),
        )
        for user in users
    ]
    return options, safe_page, page_count, total_count


def _create_ticket_from_payload(
    *,
    actor_user: User,
    serial_number: str,
    title: str | None = None,
    part_specs: list[dict[str, object]],
) -> Ticket:
    payload: dict[str, object] = {
        "serial_number": serial_number,
        "part_specs": part_specs,
    }
    if title:
        payload["title"] = title

    serializer = TicketSerializer(
        data=payload,
        context={"request": SimpleNamespace(user=actor_user)},
    )
    serializer.is_valid(raise_exception=True)
    ticket = serializer.save(master=actor_user)
    intake_metadata = serializer.get_intake_metadata()
    ticket.add_transition(
        from_status=None,
        to_status=ticket.status,
        action=TicketTransitionAction.CREATED,
        actor_user_id=actor_user.id,
        metadata={
            "total_duration": ticket.total_duration,
            "review_approved": bool(ticket.approved_at),
            "flag_color": ticket.flag_color,
            "xp_amount": ticket.xp_amount,
            "is_manual": ticket.is_manual,
            **intake_metadata,
        },
    )
    return Ticket.domain.select_related("inventory_item", "technician", "master").get(
        pk=ticket.pk
    )


def _approve_and_assign_ticket(
    *,
    ticket_id: int,
    technician_id: int,
    actor_user_id: int,
) -> Ticket:
    ticket = _review_ticket(ticket_id=ticket_id)
    if ticket is None:
        raise ValueError(ERROR_TICKET_NOT_FOUND)

    technician = User.objects.filter(pk=technician_id, is_active=True).first()
    if technician is None:
        raise ValueError(ERROR_TECHNICIAN_NOT_FOUND)
    if not technician.roles.filter(
        slug=RoleSlug.TECHNICIAN,
        deleted_at__isnull=True,
    ).exists():
        raise ValueError(ERROR_USER_NOT_TECHNICIAN)

    if not ticket.is_admin_reviewed and ticket.status in {
        TicketStatus.UNDER_REVIEW,
        TicketStatus.NEW,
    }:
        TicketWorkflowService.approve_ticket_review(
            ticket=ticket,
            actor_user_id=actor_user_id,
        )

    TicketWorkflowService.assign_ticket(
        ticket=ticket,
        technician_id=technician_id,
        actor_user_id=actor_user_id,
    )
    return Ticket.domain.select_related("inventory_item", "technician", "master").get(
        pk=ticket.pk
    )


def _set_ticket_manual_metrics(
    *, ticket_id: int, flag_color: str, xp_amount: int
) -> Ticket:
    ticket = _review_ticket(ticket_id=ticket_id)
    if ticket is None:
        raise ValueError(ERROR_TICKET_NOT_FOUND)

    TicketWorkflowService.set_manual_ticket_metrics(
        ticket=ticket,
        flag_color=flag_color,
        xp_amount=xp_amount,
    )
    return Ticket.domain.select_related("inventory_item", "technician", "master").get(
        pk=ticket.pk
    )


def _parse_create_callback(*, callback_data: str) -> tuple[str, list[str]] | None:
    parts = str(callback_data or "").split(":")
    if len(parts) < 2 or parts[0] != CREATE_CALLBACK_PREFIX:
        return None
    return parts[1], parts[2:]


def _parse_review_queue_callback(
    *,
    callback_data: str,
) -> tuple[str, int | None, int] | None:
    parts = str(callback_data or "").split(":")
    if len(parts) < 2 or parts[0] != REVIEW_QUEUE_CALLBACK_PREFIX:
        return None

    action = parts[1]
    if action == REVIEW_QUEUE_ACTION_REFRESH:
        if len(parts) >= 3:
            try:
                page = int(parts[2])
            except (TypeError, ValueError):
                return None
        else:
            page = 1
        return action, None, _normalize_page(page=page)
    if action == REVIEW_QUEUE_ACTION_OPEN and len(parts) >= 3:
        try:
            ticket_id = int(parts[2])
        except (TypeError, ValueError):
            return None
        if len(parts) >= 4:
            try:
                page = int(parts[3])
            except (TypeError, ValueError):
                return None
        else:
            page = 1
        return action, ticket_id, _normalize_page(page=page)
    return None


def _parse_review_action_callback(
    *, callback_data: str
) -> tuple[str, int, str | None] | None:
    parts = str(callback_data or "").split(":")
    if len(parts) < 3 or parts[0] != REVIEW_ACTION_CALLBACK_PREFIX:
        return None
    action = parts[1]
    try:
        ticket_id = int(parts[2])
    except (TypeError, ValueError):
        return None
    arg = parts[3] if len(parts) >= 4 else None
    return action, ticket_id, arg


async def _safe_edit_message(
    *, query: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup | None
) -> None:
    if query.message is None:
        return
    try:
        await query.message.edit_text(text=text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return
        raise


async def _ticket_permissions(*, user: User | None) -> TicketBotPermissionSet:
    return await run_sync(resolve_ticket_bot_permissions, user=user)


async def _notify_not_registered_message(*, message: Message, _) -> None:
    await message.answer(
        _("🚫 <b>No access yet.</b>\nSend <code>/start</code> to request access."),
        reply_markup=BotMenuService.build_main_menu_keyboard(
            is_technician=False,
            include_start_access=True,
            _=_,
        ),
    )


async def _notify_not_registered_callback(*, query: CallbackQuery, _) -> None:
    await query.answer(
        _("🚫 No access yet. Send /start to request access."),
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


def _create_items_text(
    *, page: int, page_count: int, items: list[InventoryItem], _
) -> str:
    lines = [
        _("🆕 <b>Ticket Intake</b>"),
        _("🧩 <b>Step 1/3:</b> Select an inventory item"),
        _("📄 <b>Page:</b> %(page)s/%(page_count)s")
        % {"page": page, "page_count": page_count},
    ]
    if not items:
        lines.append(_("ℹ️ No active inventory items found on this page."))
        return "\n".join(lines)

    lines.append(_("\n📦 <b>Available items</b>"))
    for item in items:
        lines.append(
            _("• <b>#%(item_id)s</b> • <code>%(serial)s</code> • %(status)s")
            % {
                "item_id": item.id,
                "serial": escape(item.serial_number),
                "status": escape(str(item.status)),
            }
        )
    lines.append(_("💡 Choose an item using the inline buttons."))
    return "\n".join(lines)


def _create_items_keyboard(
    *,
    page: int,
    page_count: int,
    items: list[InventoryItem],
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in items:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"#{item.id} · {item.serial_number}",
                    callback_data=f"{CREATE_CALLBACK_PREFIX}:item:{item.id}:{page}",
                )
            ]
        )

    prev_page = max(1, page - 1)
    next_page = min(page_count, page + 1)
    rows.append(
        [
            InlineKeyboardButton(
                text="<",
                callback_data=f"{CREATE_CALLBACK_PREFIX}:list:{prev_page}",
            ),
            InlineKeyboardButton(
                text=f"{page}/{page_count}",
                callback_data=f"{CREATE_CALLBACK_PREFIX}:list:{page}",
            ),
            InlineKeyboardButton(
                text=">",
                callback_data=f"{CREATE_CALLBACK_PREFIX}:list:{next_page}",
            ),
        ]
    )

    rows.append(
        [
            InlineKeyboardButton(
                text=gettext("❌ Cancel"),
                callback_data=f"{CREATE_CALLBACK_PREFIX}:cancel",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _parts_selection_text(
    *, serial_number: str, parts: list[dict], selected_ids: set[int], _
) -> str:
    lines = [
        _("🆕 <b>Ticket Intake</b>"),
        _("🧩 <b>Step 2/3:</b> Select parts"),
        _("🔢 <b>Serial number:</b> <code>%(serial)s</code>")
        % {"serial": escape(serial_number)},
    ]
    if not parts:
        lines.append(_("ℹ️ This inventory item has no parts configured."))
        return "\n".join(lines)

    lines.append(_("\n🧱 <b>Toggle parts to include in the ticket</b>"))
    for part in parts:
        marker = "✅" if int(part["id"]) in selected_ids else "☐"
        lines.append(f"{marker} <b>#{int(part['id'])}</b> {escape(str(part['name']))}")

    lines.append(
        _("\n📌 <b>Selected parts:</b> %(count)s") % {"count": len(selected_ids)}
    )
    return "\n".join(lines)


def _parts_selection_keyboard(
    *, parts: list[dict], selected_ids: set[int], item_page: int
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for part in parts:
        part_id = int(part["id"])
        marker = "✅" if part_id in selected_ids else "☐"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{marker} {part['name']}",
                    callback_data=f"{CREATE_CALLBACK_PREFIX}:tog:{part_id}",
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text=gettext("➡ Configure selected parts"),
                callback_data=f"{CREATE_CALLBACK_PREFIX}:go",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text=gettext("⬅ Back to items"),
                callback_data=f"{CREATE_CALLBACK_PREFIX}:list:{item_page}",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text=gettext("❌ Cancel"),
                callback_data=f"{CREATE_CALLBACK_PREFIX}:cancel",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _spec_editor_text(
    *,
    serial_number: str,
    current_index: int,
    total_parts: int,
    part_name: str,
    draft_color: str,
    draft_minutes: int,
    completed_count: int,
    _,
) -> str:
    return "\n".join(
        [
            _("🆕 <b>Ticket Intake</b>"),
            _("🧩 <b>Step 3/3:</b> Configure part metrics"),
            _("🔢 <b>Serial number:</b> <code>%(serial)s</code>")
            % {"serial": escape(serial_number)},
            _("🧱 <b>Part %(index)s/%(total)s:</b> %(name)s")
            % {
                "index": current_index + 1,
                "total": total_parts,
                "name": escape(part_name),
            },
            _("🎨 <b>Draft color:</b> %(color)s") % {"color": escape(draft_color)},
            _("⏱ <b>Draft minutes:</b> %(minutes)s") % {"minutes": draft_minutes},
            _("✅ <b>Configured parts:</b> %(count)s") % {"count": completed_count},
            _("💡 Use inline buttons only to configure values."),
        ]
    )


def _spec_editor_keyboard(
    *, draft_color: str, draft_minutes: int
) -> InlineKeyboardMarkup:
    color_row = [
        InlineKeyboardButton(
            text=(gettext("🟢 Green") if draft_color == "green" else gettext("Green")),
            callback_data=f"{CREATE_CALLBACK_PREFIX}:clr:green",
        ),
        InlineKeyboardButton(
            text=(
                gettext("🟡 Yellow") if draft_color == "yellow" else gettext("Yellow")
            ),
            callback_data=f"{CREATE_CALLBACK_PREFIX}:clr:yellow",
        ),
        InlineKeyboardButton(
            text=(gettext("🔴 Red") if draft_color == "red" else gettext("Red")),
            callback_data=f"{CREATE_CALLBACK_PREFIX}:clr:red",
        ),
    ]

    preset_row = [
        InlineKeyboardButton(
            text="10", callback_data=f"{CREATE_CALLBACK_PREFIX}:min:10"
        ),
        InlineKeyboardButton(
            text="20", callback_data=f"{CREATE_CALLBACK_PREFIX}:min:20"
        ),
        InlineKeyboardButton(
            text="30", callback_data=f"{CREATE_CALLBACK_PREFIX}:min:30"
        ),
        InlineKeyboardButton(
            text="45", callback_data=f"{CREATE_CALLBACK_PREFIX}:min:45"
        ),
    ]
    adjust_row = [
        InlineKeyboardButton(
            text="-5", callback_data=f"{CREATE_CALLBACK_PREFIX}:adj:-5"
        ),
        InlineKeyboardButton(
            text="-1", callback_data=f"{CREATE_CALLBACK_PREFIX}:adj:-1"
        ),
        InlineKeyboardButton(
            text=f"{draft_minutes}m", callback_data=f"{CREATE_CALLBACK_PREFIX}:noop"
        ),
        InlineKeyboardButton(
            text="+1", callback_data=f"{CREATE_CALLBACK_PREFIX}:adj:1"
        ),
        InlineKeyboardButton(
            text="+5", callback_data=f"{CREATE_CALLBACK_PREFIX}:adj:5"
        ),
    ]

    rows = [color_row, preset_row, adjust_row]
    rows.append(
        [
            InlineKeyboardButton(
                text=gettext("✅ Save part"),
                callback_data=f"{CREATE_CALLBACK_PREFIX}:save",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text=gettext("⬅ Back to parts"),
                callback_data=f"{CREATE_CALLBACK_PREFIX}:back",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text=gettext("❌ Cancel"),
                callback_data=f"{CREATE_CALLBACK_PREFIX}:cancel",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _summary_text(
    *, serial_number: str, specs: list[dict], parts_by_id: dict[int, str], _
) -> str:
    total_minutes = sum(int(spec["minutes"]) for spec in specs)
    lines = [
        _("🧾 <b>Ticket Intake Summary</b>"),
        _("🔢 <b>Serial number:</b> <code>%(serial)s</code>")
        % {"serial": escape(serial_number)},
        _("⏱ <b>Total minutes:</b> %(minutes)s") % {"minutes": total_minutes},
        _("🧱 <b>Part specs</b>"),
    ]
    for spec in specs:
        part_id = int(spec["part_id"])
        part_name = parts_by_id.get(
            part_id,
            gettext("Part #%(part_id)s") % {"part_id": part_id},
        )
        lines.append(
            _("• <b>%(part)s</b> • %(color)s • %(minutes)s min")
            % {
                "part": escape(part_name),
                "color": escape(str(spec["color"])),
                "minutes": int(spec["minutes"]),
            }
        )

    lines.append(_("💡 Create ticket using the button below."))
    return "\n".join(lines)


def _summary_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=gettext("✅ Create ticket"),
                    callback_data=f"{CREATE_CALLBACK_PREFIX}:create",
                )
            ],
            [
                InlineKeyboardButton(
                    text=gettext("⬅ Back to parts"),
                    callback_data=f"{CREATE_CALLBACK_PREFIX}:back",
                )
            ],
            [
                InlineKeyboardButton(
                    text=gettext("❌ Cancel"),
                    callback_data=f"{CREATE_CALLBACK_PREFIX}:cancel",
                )
            ],
        ]
    )


def _draft_for_part(*, part_id: int, part_specs: list[dict]) -> tuple[str, int]:
    existing = next((row for row in part_specs if int(row["part_id"]) == part_id), None)
    if existing is None:
        return "green", 10
    color = str(existing.get("color") or "green").lower()
    if color not in VALID_TICKET_COLORS:
        color = "green"
    minutes = max(1, int(existing.get("minutes") or 10))
    return color, minutes


def _review_queue_text(
    *,
    tickets: list[Ticket],
    page: int,
    page_count: int,
    total_count: int,
    _,
) -> str:
    lines = [_("🧾 <b>Ticket Review Queue</b>")]
    if not tickets:
        lines.append(
            _("📄 <b>Page:</b> %(page)s/%(page_count)s")
            % {"page": page, "page_count": page_count}
        )
        lines.append(_("ℹ️ No tickets found for review."))
        return "\n".join(lines)

    lines.append(_("📦 <b>Total tickets:</b> %(count)s") % {"count": total_count})
    lines.append(
        _("📄 <b>Page:</b> %(page)s/%(page_count)s")
        % {"page": page, "page_count": page_count}
    )
    for ticket in tickets:
        lines.append(
            _("• <b>#%(id)s</b> • <code>%(serial)s</code> • %(status)s")
            % {
                "id": ticket.id,
                "serial": escape(ticket.inventory_item.serial_number),
                "status": escape(_status_label(status=ticket.status, _=_)),
            }
        )
    lines.append(_("💡 Use inline buttons to open ticket details."))
    return "\n".join(lines)


def _review_queue_keyboard(
    *,
    tickets: list[Ticket],
    page: int,
    page_count: int,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for ticket in tickets:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🎫 #{ticket.id} · {ticket.inventory_item.serial_number}",
                    callback_data=(
                        f"{REVIEW_QUEUE_CALLBACK_PREFIX}:{REVIEW_QUEUE_ACTION_OPEN}:{ticket.id}:{page}"
                    ),
                )
            ]
        )

    prev_page = max(1, page - 1)
    next_page = min(page_count, page + 1)
    rows.append(
        [
            InlineKeyboardButton(
                text="<",
                callback_data=(
                    f"{REVIEW_QUEUE_CALLBACK_PREFIX}:{REVIEW_QUEUE_ACTION_REFRESH}:{prev_page}"
                ),
            ),
            InlineKeyboardButton(
                text=f"{page}/{page_count}",
                callback_data=(
                    f"{REVIEW_QUEUE_CALLBACK_PREFIX}:{REVIEW_QUEUE_ACTION_REFRESH}:{page}"
                ),
            ),
            InlineKeyboardButton(
                text=">",
                callback_data=(
                    f"{REVIEW_QUEUE_CALLBACK_PREFIX}:{REVIEW_QUEUE_ACTION_REFRESH}:{next_page}"
                ),
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _review_ticket_text(*, ticket: Ticket, _) -> str:
    title = ticket.title or _("No title")
    technician_label = _user_label(user=ticket.technician, fallback=_("Not assigned"))
    approved_label = _("Yes") if ticket.is_admin_reviewed else _("No")

    return "\n".join(
        [
            _("🎫 <b>Ticket #%(ticket_id)s</b>") % {"ticket_id": ticket.id},
            _("• <b>Serial:</b> <code>%(serial)s</code>")
            % {"serial": escape(ticket.inventory_item.serial_number)},
            _("• <b>Status:</b> %(status)s")
            % {"status": escape(_status_label(status=ticket.status, _=_))},
            _("• <b>Title:</b> %(title)s") % {"title": escape(title)},
            _("• <b>Technician:</b> %(technician)s")
            % {"technician": escape(technician_label)},
            _("• <b>Admin review approved:</b> %(approved)s")
            % {"approved": escape(approved_label)},
            _("• <b>Total minutes:</b> %(minutes)s")
            % {"minutes": int(ticket.total_duration or 0)},
            _("• <b>Flag / XP:</b> %(flag)s / %(xp)s")
            % {
                "flag": escape(str(ticket.flag_color)),
                "xp": int(ticket.xp_amount or 0),
            },
            _("• <b>Manual metrics mode:</b> %(manual)s")
            % {"manual": escape(_("Yes") if ticket.is_manual else _("No"))},
        ]
    )


def _review_ticket_keyboard(
    *,
    ticket_id: int,
    page: int,
    permissions: TicketBotPermissionSet,
    ticket_status: str | None = None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    can_assign_action = permissions.can_approve_and_assign and (
        ticket_status is None or _can_assign_ticket_status(status=ticket_status)
    )
    if can_assign_action:
        rows.append(
            [
                InlineKeyboardButton(
                    text=gettext("✅ Approve & Assign"),
                    callback_data=f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_ASSIGN_OPEN}:{ticket_id}",
                )
            ]
        )
    if permissions.can_manual_metrics:
        rows.append(
            [
                InlineKeyboardButton(
                    text=gettext("🛠 Manual Metrics"),
                    callback_data=f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_MANUAL_OPEN}:{ticket_id}",
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text=gettext("🔄 Refresh ticket"),
                callback_data=(
                    f"{REVIEW_QUEUE_CALLBACK_PREFIX}:{REVIEW_QUEUE_ACTION_OPEN}:{ticket_id}:{page}"
                ),
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text=gettext("⬅ Back to review queue"),
                callback_data=(
                    f"{REVIEW_QUEUE_CALLBACK_PREFIX}:{REVIEW_QUEUE_ACTION_REFRESH}:{page}"
                ),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _assign_keyboard(
    *,
    ticket_id: int,
    technician_options: list[tuple[int, str]],
    page: int,
    page_count: int,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for technician_id, label in technician_options:
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=(
                        f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_ASSIGN_EXEC}:{ticket_id}:{technician_id}"
                    ),
                )
            ]
        )

    prev_page = max(1, page - 1)
    next_page = min(page_count, page + 1)
    rows.append(
        [
            InlineKeyboardButton(
                text="<",
                callback_data=(
                    f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_ASSIGN_PAGE}:{ticket_id}:{prev_page}"
                ),
            ),
            InlineKeyboardButton(
                text=f"{page}/{page_count}",
                callback_data=(
                    f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_ASSIGN_PAGE}:{ticket_id}:{page}"
                ),
            ),
            InlineKeyboardButton(
                text=">",
                callback_data=(
                    f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_ASSIGN_PAGE}:{ticket_id}:{next_page}"
                ),
            ),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text=gettext("⬅ Back to ticket"),
                callback_data=f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_BACK}:{ticket_id}",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _manual_metrics_text(*, ticket_id: int, flag_color: str, xp_amount: int, _) -> str:
    return "\n".join(
        [
            _("🛠 <b>Manual Metrics Override</b>"),
            _("🎫 <b>Ticket:</b> #%(ticket_id)s") % {"ticket_id": ticket_id},
            _("🎨 <b>Flag color:</b> %(color)s") % {"color": escape(flag_color)},
            _("⭐ <b>XP amount:</b> %(xp)s") % {"xp": xp_amount},
            _("💡 Use inline buttons only to update values."),
        ]
    )


def _manual_metrics_keyboard(
    *, ticket_id: int, flag_color: str, xp_amount: int
) -> InlineKeyboardMarkup:
    color_row = [
        InlineKeyboardButton(
            text=(gettext("🟢 Green") if flag_color == "green" else gettext("Green")),
            callback_data=f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_MANUAL_COLOR}:{ticket_id}:green",
        ),
        InlineKeyboardButton(
            text=(
                gettext("🟡 Yellow") if flag_color == "yellow" else gettext("Yellow")
            ),
            callback_data=f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_MANUAL_COLOR}:{ticket_id}:yellow",
        ),
        InlineKeyboardButton(
            text=(gettext("🔴 Red") if flag_color == "red" else gettext("Red")),
            callback_data=f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_MANUAL_COLOR}:{ticket_id}:red",
        ),
    ]

    preset_row_a = [
        InlineKeyboardButton(
            text=str(value),
            callback_data=f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_MANUAL_XP}:{ticket_id}:{value}",
        )
        for value in MANUAL_XP_PRESETS[:4]
    ]
    preset_row_b = [
        InlineKeyboardButton(
            text=str(value),
            callback_data=f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_MANUAL_XP}:{ticket_id}:{value}",
        )
        for value in MANUAL_XP_PRESETS[4:]
    ]
    adjust_row = [
        InlineKeyboardButton(
            text="-5",
            callback_data=f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_MANUAL_ADJ}:{ticket_id}:-5",
        ),
        InlineKeyboardButton(
            text="-1",
            callback_data=f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_MANUAL_ADJ}:{ticket_id}:-1",
        ),
        InlineKeyboardButton(
            text=str(xp_amount),
            callback_data=f"{REVIEW_ACTION_CALLBACK_PREFIX}:noop:{ticket_id}",
        ),
        InlineKeyboardButton(
            text="+1",
            callback_data=f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_MANUAL_ADJ}:{ticket_id}:1",
        ),
        InlineKeyboardButton(
            text="+5",
            callback_data=f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_MANUAL_ADJ}:{ticket_id}:5",
        ),
    ]

    rows = [color_row, preset_row_a, preset_row_b, adjust_row]
    rows.append(
        [
            InlineKeyboardButton(
                text=gettext("✅ Save manual metrics"),
                callback_data=f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_MANUAL_SAVE}:{ticket_id}",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text=gettext("⬅ Back to ticket"),
                callback_data=f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_BACK}:{ticket_id}",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _show_create_items_page(
    *, query: CallbackQuery, state: FSMContext, page: int, _
) -> None:
    items, safe_page, page_count, _total_count = await run_sync(
        _query_inventory_items_page,
        page=page,
    )
    await state.set_state(TicketCreateForm.flow)
    await state.update_data(create_page=safe_page)
    await _safe_edit_message(
        query=query,
        text=_create_items_text(
            page=safe_page,
            page_count=page_count,
            items=items,
            _=_,
        ),
        reply_markup=_create_items_keyboard(
            page=safe_page,
            page_count=page_count,
            items=items,
        ),
    )


async def _show_review_queue(
    *, query: CallbackQuery, state: FSMContext, page: int, _
) -> None:
    tickets, safe_page, page_count, total_count = await run_sync(
        _review_queue_tickets,
        page=page,
        per_page=REVIEW_ITEMS_PER_PAGE,
    )
    await state.set_state(TicketReviewForm.flow)
    await state.update_data(review_page=safe_page)
    await _safe_edit_message(
        query=query,
        text=_review_queue_text(
            tickets=tickets,
            page=safe_page,
            page_count=page_count,
            total_count=total_count,
            _=_,
        ),
        reply_markup=_review_queue_keyboard(
            tickets=tickets,
            page=safe_page,
            page_count=page_count,
        ),
    )


async def _show_review_ticket(
    *,
    query: CallbackQuery,
    ticket_id: int,
    page: int,
    permissions: TicketBotPermissionSet,
    _,
) -> None:
    ticket = await run_sync(_review_ticket, ticket_id=ticket_id)
    if ticket is None:
        await query.answer(_(ERROR_TICKET_NOT_FOUND), show_alert=True)
        return

    await _safe_edit_message(
        query=query,
        text=_review_ticket_text(ticket=ticket, _=_),
        reply_markup=_review_ticket_keyboard(
            ticket_id=ticket.id,
            page=page,
            permissions=permissions,
            ticket_status=ticket.status,
        ),
    )
