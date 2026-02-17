from __future__ import annotations

from types import SimpleNamespace

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from account.models import User
from api.v1.ticket.permissions import TicketQCPermission
from bot.services.menu import (
    MENU_BUTTON_QC_CHECKS_VARIANTS,
    build_main_menu_keyboard,
    main_menu_markup_for_user,
)
from bot.services.ticket_qc_actions import TicketQCActionService
from bot.services.ticket_qc_queue import QCTicketQueueService
from core.utils.asyncio import run_sync
from ticket.services_workflow import TicketWorkflowService

router = Router(name="ticket_qc")


def _can_qc_ticket(*, user: User | None) -> bool:
    if user is None or not user.is_active:
        return False
    request = SimpleNamespace(user=user)
    return bool(TicketQCPermission().has_permission(request=request, view=None))


async def _can_qc_ticket_async(*, user: User | None) -> bool:
    return await run_sync(_can_qc_ticket, user=user)


async def _clear_state_if_active(state: FSMContext | None) -> None:
    if state is None:
        return
    if await state.get_state():
        await state.clear()


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


async def _build_qc_queue_payload(
    *,
    qc_user_id: int,
    page: int,
    _,
):
    items, safe_page, page_count, total_count = await run_sync(
        QCTicketQueueService.paginated_queue_for_qc_user,
        qc_user_id=qc_user_id,
        page=page,
        per_page=QCTicketQueueService.PAGE_SIZE,
    )
    text = QCTicketQueueService.render_queue_summary(
        items=items,
        total_count=total_count,
        page=safe_page,
        page_count=page_count,
        heading=_("🧪 My QC checks."),
        _=_,
    )
    markup = QCTicketQueueService.build_queue_keyboard(
        items=items,
        page=safe_page,
        page_count=page_count,
        _=_,
    )
    return text, markup


@router.message(Command("qc_checks"))
@router.message(Command("qc"))
async def qc_queue_handler(
    message: Message,
    _,
    user: User = None,
    state: FSMContext | None = None,
):
    await _clear_state_if_active(state)
    if not user or not user.is_active:
        await message.answer(
            _("You do not have access yet. Send /start to request access."),
            reply_markup=build_main_menu_keyboard(
                is_technician=False,
                include_start_access=True,
                _=_,
            ),
        )
        return
    if not await _can_qc_ticket_async(user=user):
        await message.answer(
            _("This action is available only for QC inspectors."),
            reply_markup=await main_menu_markup_for_user(user=user, _=_),
        )
        return
    text, markup = await _build_qc_queue_payload(qc_user_id=user.id, page=1, _=_)
    await message.answer(text=text, reply_markup=markup)


@router.message(F.text.in_(MENU_BUTTON_QC_CHECKS_VARIANTS))
async def qc_queue_button_handler(
    message: Message,
    _,
    user: User = None,
    state: FSMContext | None = None,
):
    await qc_queue_handler(message=message, _=_, user=user, state=state)


@router.callback_query(F.data.startswith(f"{QCTicketQueueService.CALLBACK_PREFIX}:"))
async def qc_queue_callback_handler(
    query: CallbackQuery,
    _,
    user: User = None,
):
    parsed = QCTicketQueueService.parse_queue_callback_data(
        callback_data=query.data or ""
    )
    if parsed is None:
        await query.answer(_("Unknown action."), show_alert=True)
        return

    if not user or not user.is_active:
        await query.answer(
            _("You do not have access yet. Send /start to request access."),
            show_alert=True,
        )
        return

    if not await _can_qc_ticket_async(user=user):
        await query.answer(
            _("This action is available only for QC inspectors."),
            show_alert=True,
        )
        return

    action, ticket_id, page = parsed
    if action == QCTicketQueueService.QUEUE_ACTION_REFRESH:
        text, markup = await _build_qc_queue_payload(qc_user_id=user.id, page=page, _=_)
        await _safe_edit_message(query=query, text=text, reply_markup=markup)
        await query.answer(_("QC checks refreshed."), show_alert=False)
        return

    if action == QCTicketQueueService.QUEUE_ACTION_OPEN and ticket_id is not None:
        ticket = await run_sync(
            QCTicketQueueService.get_assigned_ticket_for_qc_user,
            qc_user_id=user.id,
            ticket_id=ticket_id,
        )
        if ticket is None:
            await query.answer(
                _("Ticket is not assigned to you for QC."),
                show_alert=True,
            )
            return

        details_markup = QCTicketQueueService.with_back_navigation(
            reply_markup=TicketQCActionService.build_action_keyboard(
                ticket_id=ticket.id,
                ticket_status=ticket.status,
                _=_,
            ),
            page=page,
            _=_,
        )
        await _safe_edit_message(
            query=query,
            text=TicketQCActionService.render_ticket_message(
                ticket=ticket,
                heading=_("🧪 QC ticket action panel."),
                _=_,
            ),
            reply_markup=details_markup,
        )
        await query.answer(_("QC check opened."), show_alert=False)
        return

    await query.answer(_("Unknown action."), show_alert=True)


@router.callback_query(F.data.startswith(f"{TicketQCActionService.CALLBACK_PREFIX}:"))
async def qc_ticket_callback_handler(
    query: CallbackQuery,
    _,
    user: User = None,
):
    parsed = TicketQCActionService.parse_callback_data(callback_data=query.data or "")
    if parsed is None:
        await query.answer(_("Unknown action."), show_alert=True)
        return

    if not user or not user.is_active:
        await query.answer(
            _("You do not have access yet. Send /start to request access."),
            show_alert=True,
        )
        return

    if not await _can_qc_ticket_async(user=user):
        await query.answer(
            _("This action is available only for QC inspectors."),
            show_alert=True,
        )
        return

    ticket_id, action = parsed
    ticket = await run_sync(TicketQCActionService.get_ticket, ticket_id=ticket_id)
    if ticket is None:
        await query.answer(
            TicketQCActionService.ticket_not_found_error(_=_),
            show_alert=True,
        )
        return

    if action in {TicketQCActionService.ACTION_PASS, TicketQCActionService.ACTION_FAIL}:
        if not TicketQCActionService.can_apply_qc_decision(ticket_status=ticket.status):
            await query.answer(
                TicketQCActionService.status_validation_error(_=_),
                show_alert=True,
            )
            return
        try:
            if action == TicketQCActionService.ACTION_PASS:
                await run_sync(
                    TicketWorkflowService.qc_pass_ticket,
                    ticket=ticket,
                    actor_user_id=user.id,
                )
            else:
                await run_sync(
                    TicketWorkflowService.qc_fail_ticket,
                    ticket=ticket,
                    actor_user_id=user.id,
                )
        except ValueError as exc:
            await query.answer(_(str(exc)), show_alert=True)
            return

    refreshed_ticket = await run_sync(
        TicketQCActionService.get_ticket, ticket_id=ticket_id
    )
    if refreshed_ticket is None:
        await query.answer(
            TicketQCActionService.ticket_not_found_error(_=_),
            show_alert=True,
        )
        return

    queue_page = QCTicketQueueService.queue_page_from_markup(
        markup=query.message.reply_markup if query.message else None
    )
    action_markup = TicketQCActionService.build_action_keyboard(
        ticket_id=refreshed_ticket.id,
        ticket_status=refreshed_ticket.status,
        _=_,
    )
    if queue_page is not None:
        action_markup = QCTicketQueueService.with_back_navigation(
            reply_markup=action_markup,
            page=queue_page,
            _=_,
        )

    await _safe_edit_message(
        query=query,
        text=TicketQCActionService.render_ticket_message(
            ticket=refreshed_ticket,
            heading=_("🧪 QC ticket action panel."),
            _=_,
        ),
        reply_markup=action_markup,
    )
    await query.answer(
        TicketQCActionService.action_feedback(action=action, _=_),
        show_alert=False,
    )
