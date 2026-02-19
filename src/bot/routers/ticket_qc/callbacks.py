from aiogram import F, Router
from aiogram.handlers import CallbackQueryHandler
from aiogram.types import CallbackQuery

from account.models import User
from bot.routers.ticket_qc.base import QCTicketBaseMixin
from bot.services.error_text import translate_error_reason
from bot.services.ticket_qc_actions import TicketQCActionService
from bot.services.ticket_qc_queue import QCTicketQueueService
from core.utils.asyncio import run_sync
from ticket.services_workflow import TicketWorkflowService

router = Router(name="ticket_qc_callbacks")


@router.callback_query(F.data.startswith(f"{QCTicketQueueService.CALLBACK_PREFIX}:"))
class QCQueueCallbackHandler(QCTicketBaseMixin, CallbackQueryHandler):
    async def handle(self) -> None:
        query: CallbackQuery = self.event
        _ = self.data["_"]
        user: User | None = self.data.get("user")

        parsed = QCTicketQueueService.parse_queue_callback_data(
            callback_data=query.data or ""
        )
        if parsed is None:
            await query.answer(_("⚠️ Unknown action."), show_alert=True)
            return

        if not user or not user.is_active:
            await query.answer(
                _("🚫 No access yet. Send /start to request access."),
                show_alert=True,
            )
            return

        if not await self.can_qc_ticket_async(user=user):
            await query.answer(
                _("⛔ This action is available only for QC inspectors."),
                show_alert=True,
            )
            return

        action, ticket_id, page = parsed
        if action == QCTicketQueueService.QUEUE_ACTION_REFRESH:
            text, markup = await self.build_qc_queue_payload(
                qc_user_id=user.id,
                page=page,
                _=_,
            )
            await self.safe_edit_message(query=query, text=text, reply_markup=markup)
            await query.answer(_("🔄 QC checks refreshed."), show_alert=False)
            return

        if action == QCTicketQueueService.QUEUE_ACTION_OPEN and ticket_id is not None:
            ticket = await run_sync(
                QCTicketQueueService.get_assigned_ticket_for_qc_user,
                qc_user_id=user.id,
                ticket_id=ticket_id,
            )
            if ticket is None:
                await query.answer(
                    _("⚠️ Ticket is not assigned to you for QC."),
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
            await self.safe_edit_message(
                query=query,
                text=TicketQCActionService.render_ticket_message(
                    ticket=ticket,
                    heading=_("🧪 <b>QC Ticket Action Panel</b>"),
                    _=_,
                ),
                reply_markup=details_markup,
            )
            await query.answer(_("🧪 QC check opened."), show_alert=False)
            return

        await query.answer(_("⚠️ Unknown action."), show_alert=True)


@router.callback_query(F.data.startswith(f"{TicketQCActionService.CALLBACK_PREFIX}:"))
class QCTicketCallbackHandler(QCTicketBaseMixin, CallbackQueryHandler):
    async def handle(self) -> None:
        query: CallbackQuery = self.event
        _ = self.data["_"]
        user: User | None = self.data.get("user")

        parsed = TicketQCActionService.parse_callback_data(
            callback_data=query.data or ""
        )
        if parsed is None:
            await query.answer(_("⚠️ Unknown action."), show_alert=True)
            return

        if not user or not user.is_active:
            await query.answer(
                _("🚫 No access yet. Send /start to request access."),
                show_alert=True,
            )
            return

        if not await self.can_qc_ticket_async(user=user):
            await query.answer(
                _("⛔ This action is available only for QC inspectors."),
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

        if action in {
            TicketQCActionService.ACTION_PASS,
            TicketQCActionService.ACTION_FAIL,
        }:
            if not TicketQCActionService.can_apply_qc_decision(
                ticket_status=ticket.status
            ):
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
                        transition_metadata=TicketQCActionService.transition_metadata(
                            action=action
                        ),
                    )
                else:
                    await run_sync(
                        TicketWorkflowService.qc_fail_ticket,
                        ticket=ticket,
                        actor_user_id=user.id,
                        transition_metadata=TicketQCActionService.transition_metadata(
                            action=action
                        ),
                    )
            except ValueError as exc:
                await query.answer(
                    translate_error_reason(reason=exc, _=_),
                    show_alert=True,
                )
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
            markup=(
                getattr(query.message, "reply_markup", None) if query.message else None
            )
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

        await self.safe_edit_message(
            query=query,
            text=TicketQCActionService.render_ticket_message(
                ticket=refreshed_ticket,
                heading=_("🧪 <b>QC Ticket Action Panel</b>"),
                _=_,
            ),
            reply_markup=action_markup,
        )
        await query.answer(
            TicketQCActionService.action_feedback(action=action, _=_),
            show_alert=False,
        )
