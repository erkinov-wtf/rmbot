from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from account.models import User
from core.utils.asyncio import run_sync
from core.utils.constants import RoleSlug
from ticket.services_technician_actions import TechnicianTicketActionService

router = Router(name="technician_tickets")


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


@router.message(Command("queue"))
async def technician_queue_handler(message: Message, _, user: User = None):
    if not user or not user.is_active:
        await message.answer(
            _("You are not registered. Use /start to submit access request.")
        )
        return

    if not await _is_technician(user):
        await message.answer(_("This command is available only for technicians."))
        return

    states = await run_sync(
        TechnicianTicketActionService.queue_states_for_technician,
        technician_id=user.id,
    )
    if not states:
        await message.answer(_("No active tickets assigned right now."))
        return

    for state in states:
        text = TechnicianTicketActionService.render_state_message(
            state=state,
            heading=_("Technician ticket queue."),
        )
        markup = TechnicianTicketActionService.build_action_keyboard(
            ticket_id=state.ticket_id,
            actions=state.actions,
        )
        await message.answer(text=text, reply_markup=markup)


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
        await query.answer(
            _("You are not registered. Use /start to submit access request."),
            show_alert=True,
        )
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
        heading=_("Ticket state updated."),
    )
    markup = TechnicianTicketActionService.build_action_keyboard(
        ticket_id=state.ticket_id,
        actions=state.actions,
    )
    await _safe_edit_message(query=query, text=text, reply_markup=markup)

    await query.answer(
        _(TechnicianTicketActionService.action_feedback(action=action)),
        show_alert=False,
    )
