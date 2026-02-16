from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from account.models import User
from bot.routers.start import (
    MENU_BUTTON_ACTIVE_TICKETS,
    MENU_BUTTON_PAST_TICKETS,
    MENU_BUTTON_UNDER_QC_TICKETS,
    build_main_menu_keyboard,
)
from core.utils.asyncio import run_sync
from core.utils.constants import RoleSlug
from ticket.services_technician_actions import TechnicianTicketActionService

router = Router(name="technician_tickets")
LEGACY_MENU_CALLBACK_PREFIX = "ttm"


async def _is_technician(user: User) -> bool:
    return await run_sync(
        user.roles.filter(slug=RoleSlug.TECHNICIAN, deleted_at__isnull=True).exists
    )


async def _safe_edit_message(
    *,
    query: CallbackQuery,
    text: str,
    reply_markup,
) -> None:
    if query.message is None:
        return

    try:
        await query.message.edit_text(text=text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return
        raise


async def _notify_not_registered_callback(
    *,
    query: CallbackQuery,
    _,
) -> None:
    await query.answer(
        _("You are not registered. Use /start to submit access request."),
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


def _scope_back_text(*, scope: str, _) -> str:
    if scope == TechnicianTicketActionService.VIEW_SCOPE_UNDER_QC:
        return _("⬅ Back to waiting QC tickets")
    if scope == TechnicianTicketActionService.VIEW_SCOPE_PAST:
        return _("⬅ Back to past tickets")
    return _("⬅ Back to active tickets")


def _with_queue_navigation(
    *,
    reply_markup,
    scope: str,
    _,
) -> InlineKeyboardMarkup:
    nav_row = [
        InlineKeyboardButton(
            text=_scope_back_text(scope=scope, _=_),
            callback_data=TechnicianTicketActionService.build_queue_callback_data(
                action=TechnicianTicketActionService.QUEUE_ACTION_REFRESH,
                scope=scope,
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


def _scope_heading(*, scope: str, _) -> str:
    if scope == TechnicianTicketActionService.VIEW_SCOPE_UNDER_QC:
        return _("🧪 Technician tickets waiting QC.")
    if scope == TechnicianTicketActionService.VIEW_SCOPE_PAST:
        return _("✅ Technician past tickets.")
    return _("🎟 Technician active ticket queue.")


def _scope_refreshed_feedback(*, scope: str, _) -> str:
    if scope == TechnicianTicketActionService.VIEW_SCOPE_UNDER_QC:
        return _("Waiting QC list refreshed.")
    if scope == TechnicianTicketActionService.VIEW_SCOPE_PAST:
        return _("Past tickets list refreshed.")
    return _("Active tickets list refreshed.")


async def _queue_dashboard_payload(
    *,
    technician_id: int,
    scope: str,
    _,
) -> tuple[str, InlineKeyboardMarkup | None]:
    states = await run_sync(
        TechnicianTicketActionService.view_states_for_technician,
        technician_id=technician_id,
        scope=scope,
    )
    text = TechnicianTicketActionService.render_queue_summary(
        states=states,
        scope=scope,
        heading=_scope_heading(scope=scope, _=_),
    )
    markup = TechnicianTicketActionService.build_queue_keyboard(
        states=states,
        scope=scope,
        include_refresh=True,
    )
    return text, markup


async def _technician_dashboard_handler(
    *,
    message: Message,
    user: User | None,
    scope: str,
    _,
) -> None:
    if not user or not user.is_active:
        await message.answer(
            _("You are not registered. Use /start to submit access request."),
            reply_markup=build_main_menu_keyboard(
                is_technician=False,
                include_start_access=True,
            ),
        )
        return

    if not await _is_technician(user):
        await message.answer(
            _("This command is available only for technicians."),
            reply_markup=build_main_menu_keyboard(
                is_technician=False,
                include_start_access=False,
            ),
        )
        return

    text, markup = await _queue_dashboard_payload(
        technician_id=user.id,
        scope=scope,
        _=_,
    )
    await message.answer(text=text, reply_markup=markup)


@router.message(Command("queue"))
@router.message(Command("active"))
@router.message(Command("tech"))
async def technician_queue_handler(message: Message, _, user: User = None):
    await _technician_dashboard_handler(
        message=message,
        user=user,
        scope=TechnicianTicketActionService.VIEW_SCOPE_ACTIVE,
        _=_,
    )


@router.message(Command("under_qc"))
async def technician_under_qc_handler(message: Message, _, user: User = None):
    await _technician_dashboard_handler(
        message=message,
        user=user,
        scope=TechnicianTicketActionService.VIEW_SCOPE_UNDER_QC,
        _=_,
    )


@router.message(Command("past"))
async def technician_past_handler(message: Message, _, user: User = None):
    await _technician_dashboard_handler(
        message=message,
        user=user,
        scope=TechnicianTicketActionService.VIEW_SCOPE_PAST,
        _=_,
    )


@router.message(
    StateFilter(None),
    F.text == MENU_BUTTON_ACTIVE_TICKETS,
)
async def technician_queue_menu_button_handler(message: Message, _, user: User = None):
    await _technician_dashboard_handler(
        message=message,
        user=user,
        scope=TechnicianTicketActionService.VIEW_SCOPE_ACTIVE,
        _=_,
    )


@router.message(
    StateFilter(None),
    F.text == MENU_BUTTON_UNDER_QC_TICKETS,
)
async def technician_under_qc_menu_button_handler(
    message: Message, _, user: User = None
):
    await _technician_dashboard_handler(
        message=message,
        user=user,
        scope=TechnicianTicketActionService.VIEW_SCOPE_UNDER_QC,
        _=_,
    )


@router.message(
    StateFilter(None),
    F.text == MENU_BUTTON_PAST_TICKETS,
)
async def technician_past_menu_button_handler(message: Message, _, user: User = None):
    await _technician_dashboard_handler(
        message=message,
        user=user,
        scope=TechnicianTicketActionService.VIEW_SCOPE_PAST,
        _=_,
    )


@router.callback_query(
    F.data.startswith(f"{TechnicianTicketActionService.QUEUE_CALLBACK_PREFIX}:")
)
async def technician_queue_control_handler(
    query: CallbackQuery,
    _,
    user: User = None,
):
    parsed = TechnicianTicketActionService.parse_queue_callback_data(
        callback_data=query.data or ""
    )
    if parsed is None:
        await query.answer(_("Unknown action."), show_alert=True)
        return

    if not user or not user.is_active:
        await _notify_not_registered_callback(query=query, _=_)
        return

    if not await _is_technician(user):
        await query.answer(
            _("This action is available only for technicians."),
            show_alert=True,
        )
        return

    action, ticket_id, scope = parsed
    if action == TechnicianTicketActionService.QUEUE_ACTION_REFRESH:
        text, markup = await _queue_dashboard_payload(
            technician_id=user.id,
            scope=scope,
            _=_,
        )
        await _safe_edit_message(
            query=query,
            text=text,
            reply_markup=markup,
        )
        await query.answer(
            _scope_refreshed_feedback(scope=scope, _=_),
            show_alert=False,
        )
        return

    if (
        action == TechnicianTicketActionService.QUEUE_ACTION_OPEN
        and ticket_id is not None
    ):
        try:
            state = await run_sync(
                TechnicianTicketActionService.state_for_technician_and_ticket,
                technician_id=user.id,
                ticket_id=ticket_id,
            )
        except ValueError as exc:
            await query.answer(_(str(exc)), show_alert=True)
            return

        text = TechnicianTicketActionService.render_state_message(
            state=state,
            heading=(
                _("🎛 Technician ticket controls.")
                if scope == TechnicianTicketActionService.VIEW_SCOPE_ACTIVE
                else _("🔎 Technician ticket details.")
            ),
        )
        markup = TechnicianTicketActionService.build_action_keyboard(
            ticket_id=state.ticket_id,
            actions=state.actions,
        )
        markup = _with_queue_navigation(
            reply_markup=markup,
            _=_,
            scope=scope,
        )
        await _safe_edit_message(query=query, text=text, reply_markup=markup)
        await query.answer(
            _("Ticket #{ticket_id} opened.").format(ticket_id=state.ticket_id),
            show_alert=False,
        )
        return

    await query.answer(_("Unknown action."), show_alert=True)


@router.callback_query(
    F.data.startswith(f"{TechnicianTicketActionService.CALLBACK_PREFIX}:")
)
async def technician_ticket_action_handler(
    query: CallbackQuery,
    _,
    user: User = None,
):
    parsed = TechnicianTicketActionService.parse_callback_data(
        callback_data=query.data or ""
    )
    if parsed is None:
        await query.answer(_("Unknown action."), show_alert=True)
        return

    if not user or not user.is_active:
        await _notify_not_registered_callback(query=query, _=_)
        return

    if not await _is_technician(user):
        await query.answer(
            _("This action is available only for technicians."),
            show_alert=True,
        )
        return

    ticket_id, action = parsed
    try:
        state = await run_sync(
            TechnicianTicketActionService.execute_for_technician,
            technician_id=user.id,
            ticket_id=ticket_id,
            action=action,
        )
    except ValueError as exc:
        await query.answer(_(str(exc)), show_alert=True)
        return

    text = TechnicianTicketActionService.render_state_message(
        state=state,
        heading=_("✅ Ticket state updated."),
    )
    target_scope = TechnicianTicketActionService.scope_for_ticket_status(
        status=state.ticket_status
    )
    markup = TechnicianTicketActionService.build_action_keyboard(
        ticket_id=state.ticket_id,
        actions=state.actions,
    )
    markup = _with_queue_navigation(
        reply_markup=markup,
        _=_,
        scope=target_scope,
    )
    await _safe_edit_message(query=query, text=text, reply_markup=markup)

    await query.answer(
        _(TechnicianTicketActionService.action_feedback(action=action)),
        show_alert=False,
    )


@router.callback_query(F.data.startswith(f"{LEGACY_MENU_CALLBACK_PREFIX}:"))
async def technician_legacy_menu_control_handler(query: CallbackQuery, _):
    await query.answer(
        _(
            "This old quick panel was removed. Use the bottom keyboard buttons for "
            "Stats, XP, and queue sections."
        ),
        show_alert=True,
    )
