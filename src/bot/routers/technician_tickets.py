from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from account.models import User
from bot.services.menu import (
    MENU_BUTTON_ACTIVE_TICKETS_VARIANTS,
    MENU_BUTTON_PAST_TICKETS_VARIANTS,
    MENU_BUTTON_UNDER_QC_TICKETS_VARIANTS,
)
from bot.services.technician_queue import TechnicianQueueService
from bot.services.technician_ticket_actions import TechnicianTicketActionService
from core.utils.asyncio import run_sync

router = Router(name="technician_tickets")
LEGACY_MENU_CALLBACK_PREFIX = "ttm"


async def _clear_state_if_active(state: FSMContext | None) -> None:
    if state is None:
        return
    if await state.get_state():
        await state.clear()


@router.message(Command("queue"))
@router.message(Command("active"))
@router.message(Command("tech"))
async def technician_queue_handler(
    message: Message,
    _,
    user: User = None,
    state: FSMContext | None = None,
):
    await _clear_state_if_active(state)
    await TechnicianQueueService.technician_dashboard_handler(
        message=message,
        user=user,
        scope=TechnicianTicketActionService.VIEW_SCOPE_ACTIVE,
        _=_,
    )


@router.message(Command("under_qc"))
async def technician_under_qc_handler(
    message: Message,
    _,
    user: User = None,
    state: FSMContext | None = None,
):
    await _clear_state_if_active(state)
    await TechnicianQueueService.technician_dashboard_handler(
        message=message,
        user=user,
        scope=TechnicianTicketActionService.VIEW_SCOPE_UNDER_QC,
        _=_,
    )


@router.message(Command("past"))
async def technician_past_handler(
    message: Message,
    _,
    user: User = None,
    state: FSMContext | None = None,
):
    await _clear_state_if_active(state)
    await TechnicianQueueService.technician_dashboard_handler(
        message=message,
        user=user,
        scope=TechnicianTicketActionService.VIEW_SCOPE_PAST,
        _=_,
    )


@router.message(F.text.in_(MENU_BUTTON_ACTIVE_TICKETS_VARIANTS))
async def technician_queue_menu_button_handler(
    message: Message,
    _,
    user: User = None,
    state: FSMContext | None = None,
):
    await _clear_state_if_active(state)
    await TechnicianQueueService.technician_dashboard_handler(
        message=message,
        user=user,
        scope=TechnicianTicketActionService.VIEW_SCOPE_ACTIVE,
        _=_,
    )


@router.message(F.text.in_(MENU_BUTTON_UNDER_QC_TICKETS_VARIANTS))
async def technician_under_qc_menu_button_handler(
    message: Message,
    _,
    user: User = None,
    state: FSMContext | None = None,
):
    await _clear_state_if_active(state)
    await TechnicianQueueService.technician_dashboard_handler(
        message=message,
        user=user,
        scope=TechnicianTicketActionService.VIEW_SCOPE_UNDER_QC,
        _=_,
    )


@router.message(F.text.in_(MENU_BUTTON_PAST_TICKETS_VARIANTS))
async def technician_past_menu_button_handler(
    message: Message,
    _,
    user: User = None,
    state: FSMContext | None = None,
):
    await _clear_state_if_active(state)
    await TechnicianQueueService.technician_dashboard_handler(
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
        await TechnicianQueueService.notify_not_registered_callback(query=query, _=_)
        return

    if not await TechnicianQueueService.is_technician(user):
        await query.answer(
            _("This action is available only for technicians."),
            show_alert=True,
        )
        return

    action, ticket_id, scope, page = parsed
    if action == TechnicianTicketActionService.QUEUE_ACTION_REFRESH:
        text, markup = await TechnicianQueueService.queue_dashboard_payload(
            technician_id=user.id,
            scope=scope,
            page=page,
            _=_,
        )
        await TechnicianQueueService.safe_edit_message(
            query=query,
            text=text,
            reply_markup=markup,
        )
        await query.answer(
            TechnicianQueueService.scope_refreshed_feedback(scope=scope, _=_),
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
            _=_,
        )
        markup = TechnicianTicketActionService.build_action_keyboard(
            ticket_id=state.ticket_id,
            actions=state.actions,
            _=_,
        )
        markup = TechnicianQueueService.with_queue_navigation(
            reply_markup=markup,
            _=_,
            scope=scope,
            page=page,
        )
        await TechnicianQueueService.safe_edit_message(
            query=query,
            text=text,
            reply_markup=markup,
        )
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
        await TechnicianQueueService.notify_not_registered_callback(query=query, _=_)
        return

    if not await TechnicianQueueService.is_technician(user):
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
        _=_,
    )
    target_scope = TechnicianTicketActionService.scope_for_ticket_status(
        status=state.ticket_status
    )
    context = TechnicianQueueService.queue_context_from_markup(
        markup=(query.message.reply_markup if query.message else None),
    )
    target_page = (
        context[1] if context is not None and context[0] == target_scope else 1
    )
    markup = TechnicianTicketActionService.build_action_keyboard(
        ticket_id=state.ticket_id,
        actions=state.actions,
        _=_,
    )
    markup = TechnicianQueueService.with_queue_navigation(
        reply_markup=markup,
        _=_,
        scope=target_scope,
        page=target_page,
    )
    await TechnicianQueueService.safe_edit_message(
        query=query,
        text=text,
        reply_markup=markup,
    )

    await query.answer(
        TechnicianTicketActionService.action_feedback(action=action, _=_),
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
