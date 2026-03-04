from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.handlers import CallbackQueryHandler
from aiogram.types import CallbackQuery

from account.models import User
from bot.services.error_text import translate_error_reason
from bot.services.technician_queue import TechnicianQueueService
from bot.services.technician_ticket_actions import TechnicianTicketActionService
from core.utils.constants import TicketStatus
from core.utils.asyncio import run_sync

router = Router(name="technician_tickets_callbacks")
LEGACY_MENU_CALLBACK_PREFIX = "ttm"
PART_SELECTION_STATE_KEY = "technician_part_selection"
PART_SELECTION_CONTEXT_STATE_KEY = "technician_part_selection_context"


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
                _("⛔ This action is available only for technicians."),
                show_alert=True,
            )
            return False

        return True

    @staticmethod
    def _ticket_storage_key(*, ticket_id: int) -> str:
        return str(int(ticket_id))

    @classmethod
    async def _selected_part_ids_for_ticket(
        cls, *, state: FSMContext, ticket_id: int
    ) -> set[int]:
        data = await state.get_data()
        raw_map = data.get(PART_SELECTION_STATE_KEY) or {}
        if not isinstance(raw_map, dict):
            return set()
        raw_list = raw_map.get(cls._ticket_storage_key(ticket_id=ticket_id), [])
        if not isinstance(raw_list, list):
            return set()
        selected: set[int] = set()
        for value in raw_list:
            try:
                selected.add(int(value))
            except (TypeError, ValueError):
                continue
        return selected

    @classmethod
    async def _store_selected_part_ids_for_ticket(
        cls,
        *,
        state: FSMContext,
        ticket_id: int,
        selected_part_ids: set[int],
    ) -> None:
        data = await state.get_data()
        raw_map = data.get(PART_SELECTION_STATE_KEY) or {}
        if not isinstance(raw_map, dict):
            raw_map = {}
        map_copy = dict(raw_map)
        map_copy[cls._ticket_storage_key(ticket_id=ticket_id)] = sorted(
            int(part_id) for part_id in selected_part_ids
        )
        await state.update_data(**{PART_SELECTION_STATE_KEY: map_copy})

    @classmethod
    async def _clear_selected_part_ids_for_ticket(
        cls, *, state: FSMContext, ticket_id: int
    ) -> None:
        data = await state.get_data()
        raw_map = data.get(PART_SELECTION_STATE_KEY) or {}
        if not isinstance(raw_map, dict):
            return
        key = cls._ticket_storage_key(ticket_id=ticket_id)
        if key not in raw_map:
            return
        map_copy = dict(raw_map)
        map_copy.pop(key, None)
        await state.update_data(**{PART_SELECTION_STATE_KEY: map_copy})

    @classmethod
    async def _store_ticket_queue_context(
        cls,
        *,
        state: FSMContext,
        ticket_id: int,
        scope: str,
        page: int,
    ) -> None:
        data = await state.get_data()
        raw_map = data.get(PART_SELECTION_CONTEXT_STATE_KEY) or {}
        if not isinstance(raw_map, dict):
            raw_map = {}
        map_copy = dict(raw_map)
        map_copy[cls._ticket_storage_key(ticket_id=ticket_id)] = {
            "scope": str(scope),
            "page": max(1, int(page or 1)),
        }
        await state.update_data(**{PART_SELECTION_CONTEXT_STATE_KEY: map_copy})

    @classmethod
    async def _ticket_queue_context(
        cls,
        *,
        state: FSMContext,
        ticket_id: int,
    ) -> tuple[str, int]:
        data = await state.get_data()
        raw_map = data.get(PART_SELECTION_CONTEXT_STATE_KEY) or {}
        if not isinstance(raw_map, dict):
            return TechnicianTicketActionService.VIEW_SCOPE_ACTIVE, 1
        key = cls._ticket_storage_key(ticket_id=ticket_id)
        raw_context = raw_map.get(key)
        if not isinstance(raw_context, dict):
            return TechnicianTicketActionService.VIEW_SCOPE_ACTIVE, 1
        scope = str(
            raw_context.get(
                "scope",
                TechnicianTicketActionService.VIEW_SCOPE_ACTIVE,
            )
        )
        if scope not in {
            TechnicianTicketActionService.VIEW_SCOPE_ACTIVE,
            TechnicianTicketActionService.VIEW_SCOPE_UNDER_QC,
            TechnicianTicketActionService.VIEW_SCOPE_PAST,
        }:
            scope = TechnicianTicketActionService.VIEW_SCOPE_ACTIVE
        try:
            page = max(1, int(raw_context.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        return scope, page

    @classmethod
    async def _clear_ticket_queue_context(
        cls, *, state: FSMContext, ticket_id: int
    ) -> None:
        data = await state.get_data()
        raw_map = data.get(PART_SELECTION_CONTEXT_STATE_KEY) or {}
        if not isinstance(raw_map, dict):
            return
        key = cls._ticket_storage_key(ticket_id=ticket_id)
        if key not in raw_map:
            return
        map_copy = dict(raw_map)
        map_copy.pop(key, None)
        await state.update_data(**{PART_SELECTION_CONTEXT_STATE_KEY: map_copy})

    @classmethod
    async def show_part_completion_panel(
        cls,
        *,
        query: CallbackQuery,
        state: FSMContext,
        technician_id: int,
        ticket_id: int,
        _,
        heading: str | None = None,
    ) -> bool:
        ticket = await run_sync(
            TechnicianTicketActionService.get_ticket_for_technician,
            technician_id=technician_id,
            ticket_id=ticket_id,
        )
        if ticket is None:
            return False

        ticket_state = await run_sync(
            TechnicianTicketActionService.state_for_technician_and_ticket,
            technician_id=technician_id,
            ticket_id=ticket_id,
        )
        pending_parts = await run_sync(
            TechnicianTicketActionService.pending_part_specs,
            ticket=ticket,
        )
        selected_part_ids = await cls._selected_part_ids_for_ticket(
            state=state,
            ticket_id=ticket_id,
        )
        valid_part_ids = {part.part_spec_id for part in pending_parts}
        selected_part_ids = {
            part_id for part_id in selected_part_ids if part_id in valid_part_ids
        }
        await cls._store_selected_part_ids_for_ticket(
            state=state,
            ticket_id=ticket_id,
            selected_part_ids=selected_part_ids,
        )

        text = TechnicianTicketActionService.render_part_completion_message(
            state=ticket_state,
            pending_parts=pending_parts,
            selected_part_spec_ids=selected_part_ids,
            heading=heading or _("🧩 <b>Select completed parts</b>"),
            _=_,
        )
        markup = TechnicianTicketActionService.build_part_completion_keyboard(
            ticket_id=ticket_id,
            pending_parts=pending_parts,
            selected_part_spec_ids=selected_part_ids,
            _=_,
        )
        context_scope, context_page = await cls._ticket_queue_context(
            state=state,
            ticket_id=ticket_id,
        )
        markup = TechnicianQueueService.with_queue_navigation(
            reply_markup=markup,
            _=_,
            scope=context_scope,
            page=context_page,
        )
        await TechnicianQueueService.safe_edit_message(
            query=query,
            text=text,
            reply_markup=markup,
        )
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
            await query.answer(_("⚠️ Unknown action."), show_alert=True)
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
            except Exception as exc:
                await query.answer(
                    translate_error_reason(reason=exc, _=_),
                    show_alert=True,
                )
                return

            heading = (
                _("🔧 Ticket sent to QC")
                if scope == TechnicianTicketActionService.VIEW_SCOPE_UNDER_QC
                else (
                    _("🎛 Technician ticket controls.")
                    if scope == TechnicianTicketActionService.VIEW_SCOPE_ACTIVE
                    else _("🔎 Technician ticket details.")
                )
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
                _("🎫 Ticket #%(ticket_id)s opened.") % {"ticket_id": state.ticket_id},
                show_alert=False,
            )
            return

        await query.answer(_("⚠️ Unknown action."), show_alert=True)


@router.callback_query(
    F.data.startswith(f"{TechnicianTicketActionService.CALLBACK_PREFIX}:")
)
class TechnicianTicketActionHandler(
    TechnicianCallbackSupportMixin, CallbackQueryHandler
):
    async def handle(self) -> None:
        query: CallbackQuery = self.event
        state: FSMContext = self.data["state"]
        _ = self.data["_"]
        user: User | None = self.data.get("user")

        parsed = TechnicianTicketActionService.parse_callback_data(
            callback_data=query.data or ""
        )
        if parsed is None:
            await query.answer(_("⚠️ Unknown action."), show_alert=True)
            return

        if not await self.ensure_active_technician(user=user, query=query, _=_):
            return

        ticket_id, action = parsed
        message_markup = getattr(query.message, "reply_markup", None)
        context = TechnicianQueueService.queue_context_from_markup(markup=message_markup)
        queue_scope = (
            context[0]
            if context is not None
            else TechnicianTicketActionService.VIEW_SCOPE_ACTIVE
        )
        queue_page = context[1] if context is not None else 1
        await self._store_ticket_queue_context(
            state=state,
            ticket_id=ticket_id,
            scope=queue_scope,
            page=queue_page,
        )
        try:
            ticket_state = await run_sync(
                TechnicianTicketActionService.execute_for_technician,
                technician_id=user.id,
                ticket_id=ticket_id,
                action=action,
            )
        except Exception as exc:
            await query.answer(
                translate_error_reason(reason=exc, _=_),
                show_alert=True,
            )
            return

        if action == TechnicianTicketActionService.ACTION_STOP:
            await self._clear_selected_part_ids_for_ticket(
                state=state,
                ticket_id=ticket_id,
            )
            panel_shown = await self.show_part_completion_panel(
                query=query,
                state=state,
                technician_id=user.id,
                ticket_id=ticket_id,
                _=_,
            )
            if panel_shown:
                await query.answer(
                    _("⏹ Session stopped. Select completed parts."),
                    show_alert=False,
                )
                return

        heading = (
            _("🔧 Ticket sent to QC")
            if ticket_state.ticket_status == TicketStatus.WAITING_QC
            else _("✅ Ticket state updated.")
        )
        text = TechnicianTicketActionService.render_state_message(
            state=ticket_state,
            heading=heading,
            _=_,
        )
        target_scope = TechnicianTicketActionService.scope_for_ticket_status(
            status=ticket_state.ticket_status
        )
        target_page = (
            context[1] if context is not None and context[0] == target_scope else 1
        )
        markup = TechnicianTicketActionService.build_action_keyboard(
            ticket_id=ticket_state.ticket_id,
            actions=ticket_state.actions,
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


@router.callback_query(
    F.data.startswith(f"{TechnicianTicketActionService.PARTS_CALLBACK_PREFIX}:")
)
class TechnicianTicketPartCompletionHandler(
    TechnicianCallbackSupportMixin, CallbackQueryHandler
):
    async def handle(self) -> None:
        query: CallbackQuery = self.event
        state: FSMContext = self.data["state"]
        _ = self.data["_"]
        user: User | None = self.data.get("user")

        parsed = TechnicianTicketActionService.parse_parts_callback_data(
            callback_data=query.data or ""
        )
        if parsed is None:
            await query.answer(_("⚠️ Unknown action."), show_alert=True)
            return
        if not await self.ensure_active_technician(user=user, query=query, _=_):
            return

        ticket_id, action, part_spec_id = parsed
        message_markup = getattr(query.message, "reply_markup", None)
        context = TechnicianQueueService.queue_context_from_markup(markup=message_markup)
        if context is not None:
            await self._store_ticket_queue_context(
                state=state,
                ticket_id=ticket_id,
                scope=context[0],
                page=context[1],
            )
        queue_scope, queue_page = await self._ticket_queue_context(
            state=state,
            ticket_id=ticket_id,
        )

        ticket = await run_sync(
            TechnicianTicketActionService.get_ticket_for_technician,
            technician_id=user.id,
            ticket_id=ticket_id,
        )
        if ticket is None:
            await self._clear_selected_part_ids_for_ticket(
                state=state,
                ticket_id=ticket_id,
            )
            await self._clear_ticket_queue_context(
                state=state,
                ticket_id=ticket_id,
            )
            text, markup = await TechnicianQueueService.queue_dashboard_payload(
                technician_id=user.id,
                scope=queue_scope,
                page=queue_page,
                _=_,
            )
            await TechnicianQueueService.safe_edit_message(
                query=query,
                text=text,
                reply_markup=markup,
            )
            await query.answer(_("ℹ️ Ticket is no longer in your queue."), show_alert=False)
            return

        pending_parts = await run_sync(
            TechnicianTicketActionService.pending_part_specs,
            ticket=ticket,
        )
        pending_part_ids = {part.part_spec_id for part in pending_parts}
        selected_part_ids = await self._selected_part_ids_for_ticket(
            state=state,
            ticket_id=ticket_id,
        )
        selected_part_ids = {
            selected_part_id
            for selected_part_id in selected_part_ids
            if selected_part_id in pending_part_ids
        }

        if action == TechnicianTicketActionService.PARTS_ACTION_TOGGLE:
            if part_spec_id is None or part_spec_id not in pending_part_ids:
                await query.answer(
                    _("⚠️ Invalid part selection."),
                    show_alert=True,
                )
                return
            if part_spec_id in selected_part_ids:
                selected_part_ids.remove(part_spec_id)
            else:
                selected_part_ids.add(part_spec_id)
            await self._store_selected_part_ids_for_ticket(
                state=state,
                ticket_id=ticket_id,
                selected_part_ids=selected_part_ids,
            )
            await self.show_part_completion_panel(
                query=query,
                state=state,
                technician_id=user.id,
                ticket_id=ticket_id,
                _=_,
            )
            await query.answer(show_alert=False)
            return

        if action == TechnicianTicketActionService.PARTS_ACTION_REFRESH:
            await self.show_part_completion_panel(
                query=query,
                state=state,
                technician_id=user.id,
                ticket_id=ticket_id,
                _=_,
            )
            await query.answer(_("🔄 Selection refreshed."), show_alert=False)
            return

        if action == TechnicianTicketActionService.PARTS_ACTION_CANCEL:
            await self._clear_selected_part_ids_for_ticket(
                state=state,
                ticket_id=ticket_id,
            )
            ticket_state = await run_sync(
                TechnicianTicketActionService.state_for_technician_and_ticket,
                technician_id=user.id,
                ticket_id=ticket_id,
            )
            text = TechnicianTicketActionService.render_state_message(
                state=ticket_state,
                heading=_("✅ Ticket state updated."),
                _=_,
            )
            markup = TechnicianTicketActionService.build_action_keyboard(
                ticket_id=ticket_state.ticket_id,
                actions=ticket_state.actions,
                _=_,
            )
            target_scope = TechnicianTicketActionService.scope_for_ticket_status(
                status=ticket_state.ticket_status
            )
            target_page = queue_page if queue_scope == target_scope else 1
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
            await query.answer(_("↩️ Returned to ticket controls."), show_alert=False)
            return

        if action == TechnicianTicketActionService.PARTS_ACTION_SUBMIT:
            if not selected_part_ids:
                await query.answer(
                    _("⚠️ Select at least one completed part."),
                    show_alert=True,
                )
                return
            part_payloads = [
                {"part_spec_id": int(part_spec_id), "note": ""}
                for part_spec_id in sorted(selected_part_ids)
            ]
            from ticket.services_workflow import TicketWorkflowService

            try:
                updated_ticket = await run_sync(
                    TicketWorkflowService.complete_ticket_parts,
                    ticket=ticket,
                    actor_user_id=user.id,
                    part_payloads=part_payloads,
                    transition_metadata={
                        "source": "telegram_bot",
                        "channel": "technician_part_selection",
                        "telegram_action": "submit_parts",
                    },
                )
            except Exception as exc:
                await query.answer(
                    translate_error_reason(reason=exc, _=_),
                    show_alert=True,
                )
                return

            await self._clear_selected_part_ids_for_ticket(
                state=state,
                ticket_id=ticket_id,
            )
            await self._clear_ticket_queue_context(
                state=state,
                ticket_id=ticket_id,
            )

            if updated_ticket.technician_id == user.id:
                ticket_state = await run_sync(
                    TechnicianTicketActionService.state_for_technician_and_ticket,
                    technician_id=user.id,
                    ticket_id=ticket_id,
                )
                heading = (
                    _("🔧 Ticket sent to QC")
                    if ticket_state.ticket_status == TicketStatus.WAITING_QC
                    else _("✅ Ticket state updated.")
                )
                text = TechnicianTicketActionService.render_state_message(
                    state=ticket_state,
                    heading=heading,
                    _=_,
                )
                markup = TechnicianTicketActionService.build_action_keyboard(
                    ticket_id=ticket_state.ticket_id,
                    actions=ticket_state.actions,
                    _=_,
                )
                target_scope = TechnicianTicketActionService.scope_for_ticket_status(
                    status=ticket_state.ticket_status
                )
                target_page = queue_page if queue_scope == target_scope else 1
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
            else:
                text, markup = await TechnicianQueueService.queue_dashboard_payload(
                    technician_id=user.id,
                    scope=queue_scope,
                    page=queue_page,
                    _=_,
                )
                await TechnicianQueueService.safe_edit_message(
                    query=query,
                    text=text,
                    reply_markup=markup,
                )
            await query.answer(_("✅ Parts completion submitted."), show_alert=False)
            return

        await query.answer(_("⚠️ Unknown action."), show_alert=True)


@router.callback_query(F.data.startswith(f"{LEGACY_MENU_CALLBACK_PREFIX}:"))
class TechnicianLegacyMenuControlHandler(CallbackQueryHandler):
    async def handle(self) -> None:
        query: CallbackQuery = self.event
        _ = self.data["_"]
        await query.answer(
            _(
                "ℹ️ This old quick panel was removed. Use the bottom keyboard buttons for Stats, XP, and queue sections."
            ),
            show_alert=True,
        )
