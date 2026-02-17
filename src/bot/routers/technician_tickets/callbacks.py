from aiogram import F, Router
from aiogram.handlers import CallbackQueryHandler
from aiogram.types import CallbackQuery

from account.models import User
from bot.services.technician_queue import TechnicianQueueService
from bot.services.technician_ticket_actions import TechnicianTicketActionService
from core.utils.asyncio import run_sync

router = Router(name="technician_tickets_callbacks")
LEGACY_MENU_CALLBACK_PREFIX = "ttm"


class TechnicianCallbackSupportMixin:
    @classmethod
    async def ensure_active_technician(
        cls,
        *,
        user: User | None,
        query: CallbackQuery,
        _,
    ) -> bool:
        if not user or not user.is_active:
            await TechnicianQueueService.notify_not_registered_callback(
                query=query, _=_
            )
            return False

        if not await TechnicianQueueService.is_technician(user):
            await query.answer(
                _("This action is available only for technicians."),
                show_alert=True,
            )
            return False

        return True


@router.callback_query(
    F.data.startswith(f"{TechnicianTicketActionService.QUEUE_CALLBACK_PREFIX}:")
)
class TechnicianQueueControlHandler(
    TechnicianCallbackSupportMixin, CallbackQueryHandler
):
    async def handle(self) -> None:
        query: CallbackQuery = self.event
        _ = self.data["_"]
        user: User | None = self.data.get("user")

        parsed = TechnicianTicketActionService.parse_queue_callback_data(
            callback_data=query.data or ""
        )
        if parsed is None:
            await query.answer(_("Unknown action."), show_alert=True)
            return

        if not await self.ensure_active_technician(user=user, query=query, _=_):
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

            heading = (
                _("🎛 Technician ticket controls.")
                if scope == TechnicianTicketActionService.VIEW_SCOPE_ACTIVE
                else _("🔎 Technician ticket details.")
            )
            text = TechnicianTicketActionService.render_state_message(
                state=state,
                heading=heading,
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
class TechnicianTicketActionHandler(
    TechnicianCallbackSupportMixin, CallbackQueryHandler
):
    async def handle(self) -> None:
        query: CallbackQuery = self.event
        _ = self.data["_"]
        user: User | None = self.data.get("user")

        parsed = TechnicianTicketActionService.parse_callback_data(
            callback_data=query.data or ""
        )
        if parsed is None:
            await query.answer(_("Unknown action."), show_alert=True)
            return

        if not await self.ensure_active_technician(user=user, query=query, _=_):
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
        message_markup = getattr(query.message, "reply_markup", None)
        context = TechnicianQueueService.queue_context_from_markup(
            markup=message_markup
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
class TechnicianLegacyMenuControlHandler(CallbackQueryHandler):
    async def handle(self) -> None:
        query: CallbackQuery = self.event
        _ = self.data["_"]
        await query.answer(
            _(
                "This old quick panel was removed. Use the bottom keyboard buttons for Stats, XP, and queue sections."
            ),
            show_alert=True,
        )
