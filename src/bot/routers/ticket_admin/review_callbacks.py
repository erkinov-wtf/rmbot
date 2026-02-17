from typing import cast

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.handlers import CallbackQueryHandler
from aiogram.types import CallbackQuery

from account.models import User
from bot.permissions import TicketBotPermissionSet
from bot.services import ticket_admin_support
from core.utils.asyncio import run_sync

router = Router(name="ticket_admin_review_callbacks")


class TicketReviewCallbackSupportMixin:
    @classmethod
    async def resolve_review_permissions(
        cls,
        *,
        state: FSMContext,
        user: User | None,
        query: CallbackQuery,
        _,
    ) -> TicketBotPermissionSet | None:
        if not user or not user.is_active:
            await state.clear()
            await ticket_admin_support._notify_not_registered_callback(query=query, _=_)
            return None

        permissions = await ticket_admin_support._ticket_permissions(user=user)
        if not permissions.can_open_review_panel:
            await query.answer(
                _("⛔ Your roles do not allow ticket review actions."),
                show_alert=True,
            )
            return None

        return permissions


@router.callback_query(
    F.data.startswith(f"{ticket_admin_support.REVIEW_QUEUE_CALLBACK_PREFIX}:")
)
class TicketReviewQueueCallbackHandler(
    TicketReviewCallbackSupportMixin, CallbackQueryHandler
):
    async def handle(self) -> None:
        query: CallbackQuery = self.event
        state: FSMContext = self.data["state"]
        _ = self.data["_"]
        user: User | None = self.data.get("user")

        parsed = ticket_admin_support._parse_review_queue_callback(
            callback_data=query.data or ""
        )
        if parsed is None:
            await query.answer(_("⚠️ Unknown action."), show_alert=True)
            return

        permissions = await self.resolve_review_permissions(
            state=state,
            user=user,
            query=query,
            _=_,
        )
        if permissions is None:
            return

        action, ticket_id, page = parsed
        if action == ticket_admin_support.REVIEW_QUEUE_ACTION_REFRESH:
            await ticket_admin_support._show_review_queue(
                query=query,
                state=state,
                page=page,
                _=_,
            )
            await query.answer(_("🔄 Review queue refreshed."), show_alert=False)
            return

        if (
            action == ticket_admin_support.REVIEW_QUEUE_ACTION_OPEN
            and ticket_id is not None
        ):
            await state.set_state(ticket_admin_support.TicketReviewForm.flow)
            await state.update_data(
                review_ticket_id=ticket_id,
                review_page=ticket_admin_support._normalize_page(page=page),
            )
            await ticket_admin_support._show_review_ticket(
                query=query,
                ticket_id=ticket_id,
                page=ticket_admin_support._normalize_page(page=page),
                permissions=permissions,
                _=_,
            )
            await query.answer()
            return

        await query.answer(_("⚠️ Unknown action."), show_alert=True)


@router.callback_query(
    F.data.startswith(f"{ticket_admin_support.REVIEW_ACTION_CALLBACK_PREFIX}:")
)
class TicketReviewActionCallbackHandler(
    TicketReviewCallbackSupportMixin, CallbackQueryHandler
):
    async def handle(self) -> None:
        query: CallbackQuery = self.event
        state: FSMContext = self.data["state"]
        _ = self.data["_"]
        user: User | None = self.data.get("user")

        parsed = ticket_admin_support._parse_review_action_callback(
            callback_data=query.data or ""
        )
        if parsed is None:
            await query.answer(_("⚠️ Unknown action."), show_alert=True)
            return

        permissions = await self.resolve_review_permissions(
            state=state,
            user=user,
            query=query,
            _=_,
        )
        if permissions is None:
            return

        action, ticket_id, arg = parsed
        state_data = await state.get_data()
        review_page = ticket_admin_support._normalize_page(
            page=state_data.get("review_page") or 1
        )

        if action == "noop":
            await query.answer()
            return

        if action == ticket_admin_support.REVIEW_ACTION_BACK:
            await ticket_admin_support._show_review_ticket(
                query=query,
                ticket_id=ticket_id,
                page=review_page,
                permissions=permissions,
                _=_,
            )
            await query.answer()
            return

        if action == ticket_admin_support.REVIEW_ACTION_ASSIGN_OPEN:
            if not permissions.can_approve_and_assign:
                await query.answer(
                    _("⛔ Your roles do not allow approve-and-assign action."),
                    show_alert=True,
                )
                return
            ticket = await run_sync(
                ticket_admin_support._review_ticket, ticket_id=ticket_id
            )
            if ticket is None:
                await query.answer(_("⚠️ Ticket was not found."), show_alert=True)
                return
            if not ticket_admin_support._can_assign_ticket_status(status=ticket.status):
                await query.answer(
                    _("⚠️ Approve & assign is not available for this ticket status."),
                    show_alert=True,
                )
                return

            (
                technician_options,
                assign_page,
                assign_page_count,
                _assign_total_count,
            ) = await run_sync(
                ticket_admin_support._list_technician_options_page,
                page=1,
                per_page=ticket_admin_support.TECHNICIAN_OPTIONS_PER_PAGE,
            )
            if not technician_options:
                await query.answer(
                    _("⚠️ No technicians are available for assignment."),
                    show_alert=True,
                )
                return

            await state.set_state(ticket_admin_support.TicketReviewForm.flow)
            await state.update_data(assign_page=assign_page)
            await ticket_admin_support._safe_edit_message(
                query=query,
                text=_("👤 Select technician for ticket #%(ticket_id)s.")
                % {"ticket_id": ticket_id},
                reply_markup=ticket_admin_support._assign_keyboard(
                    ticket_id=ticket_id,
                    technician_options=technician_options,
                    page=assign_page,
                    page_count=assign_page_count,
                ),
            )
            await query.answer()
            return

        if action == ticket_admin_support.REVIEW_ACTION_ASSIGN_PAGE:
            if not permissions.can_approve_and_assign:
                await query.answer(
                    _("⛔ Your roles do not allow approve-and-assign action."),
                    show_alert=True,
                )
                return
            ticket = await run_sync(
                ticket_admin_support._review_ticket, ticket_id=ticket_id
            )
            if ticket is None:
                await query.answer(_("⚠️ Ticket was not found."), show_alert=True)
                return
            if not ticket_admin_support._can_assign_ticket_status(status=ticket.status):
                await query.answer(
                    _("⚠️ Approve & assign is not available for this ticket status."),
                    show_alert=True,
                )
                return

            try:
                assign_page = int(arg) if arg is not None else 1
            except (TypeError, ValueError):
                await query.answer(_("⚠️ Could not open this page."), show_alert=True)
                return

            (
                technician_options,
                safe_page,
                page_count,
                _assign_total_count,
            ) = await run_sync(
                ticket_admin_support._list_technician_options_page,
                page=assign_page,
                per_page=ticket_admin_support.TECHNICIAN_OPTIONS_PER_PAGE,
            )
            if not technician_options:
                await query.answer(
                    _("⚠️ No technicians are available for assignment."),
                    show_alert=True,
                )
                return

            await state.set_state(ticket_admin_support.TicketReviewForm.flow)
            await state.update_data(assign_page=safe_page)
            await ticket_admin_support._safe_edit_message(
                query=query,
                text=_("👤 Select technician for ticket #%(ticket_id)s.")
                % {"ticket_id": ticket_id},
                reply_markup=ticket_admin_support._assign_keyboard(
                    ticket_id=ticket_id,
                    technician_options=technician_options,
                    page=safe_page,
                    page_count=page_count,
                ),
            )
            await query.answer()
            return

        if action == ticket_admin_support.REVIEW_ACTION_ASSIGN_EXEC:
            if not permissions.can_approve_and_assign:
                await query.answer(
                    _("⛔ Your roles do not allow approve-and-assign action."),
                    show_alert=True,
                )
                return
            ticket = await run_sync(
                ticket_admin_support._review_ticket, ticket_id=ticket_id
            )
            if ticket is None:
                await query.answer(_("⚠️ Ticket was not found."), show_alert=True)
                return
            if not ticket_admin_support._can_assign_ticket_status(status=ticket.status):
                await query.answer(
                    _("⚠️ Approve & assign is not available for this ticket status."),
                    show_alert=True,
                )
                return

            if arg is None:
                await query.answer(
                    _("⚠️ Technician selection is invalid."), show_alert=True
                )
                return
            if user is None:
                await query.answer(_("⚠️ Unknown action."), show_alert=True)
                return
            actor_user_id = cast(User, user).id
            try:
                technician_id = int(arg)
            except (TypeError, ValueError):
                await query.answer(
                    _("⚠️ Technician selection is invalid."), show_alert=True
                )
                return

            try:
                ticket = await run_sync(
                    ticket_admin_support._approve_and_assign_ticket,
                    ticket_id=ticket_id,
                    technician_id=technician_id,
                    actor_user_id=actor_user_id,
                )
            except ValueError as exc:
                await query.answer(
                    _("❌ Approve & assign failed: %(reason)s")
                    % {"reason": _(str(exc))},
                    show_alert=True,
                )
                return

            await ticket_admin_support._safe_edit_message(
                query=query,
                text=ticket_admin_support._review_ticket_text(ticket=ticket, _=_),
                reply_markup=ticket_admin_support._review_ticket_keyboard(
                    ticket_id=ticket.id,
                    page=review_page,
                    permissions=permissions,
                    ticket_status=ticket.status,
                ),
            )
            await query.answer(_("✅ Ticket approved and assigned."), show_alert=False)
            return

        if action == ticket_admin_support.REVIEW_ACTION_MANUAL_OPEN:
            if not permissions.can_manual_metrics:
                await query.answer(
                    _("⛔ Your roles do not allow manual metrics override."),
                    show_alert=True,
                )
                return

            ticket = await run_sync(
                ticket_admin_support._review_ticket, ticket_id=ticket_id
            )
            if ticket is None:
                await query.answer(_("⚠️ Ticket was not found."), show_alert=True)
                return

            color = str(ticket.flag_color or "green").lower()
            if color not in ticket_admin_support.VALID_TICKET_COLORS:
                color = "green"
            xp_amount = max(0, int(ticket.xp_amount or 0))

            await state.set_state(ticket_admin_support.TicketReviewForm.flow)
            await state.update_data(
                manual_ticket_id=ticket_id,
                manual_flag_color=color,
                manual_xp_amount=xp_amount,
            )
            await ticket_admin_support._safe_edit_message(
                query=query,
                text=ticket_admin_support._manual_metrics_text(
                    ticket_id=ticket_id,
                    flag_color=color,
                    xp_amount=xp_amount,
                    _=_,
                ),
                reply_markup=ticket_admin_support._manual_metrics_keyboard(
                    ticket_id=ticket_id,
                    flag_color=color,
                    xp_amount=xp_amount,
                ),
            )
            await query.answer()
            return

        if action in {
            ticket_admin_support.REVIEW_ACTION_MANUAL_COLOR,
            ticket_admin_support.REVIEW_ACTION_MANUAL_XP,
            ticket_admin_support.REVIEW_ACTION_MANUAL_ADJ,
            ticket_admin_support.REVIEW_ACTION_MANUAL_SAVE,
        }:
            if not permissions.can_manual_metrics:
                await query.answer(
                    _("⛔ Your roles do not allow manual metrics override."),
                    show_alert=True,
                )
                return

            data = await state.get_data()
            manual_ticket_id = int(data.get("manual_ticket_id") or 0)
            flag_color = str(data.get("manual_flag_color") or "green").lower()
            xp_amount = max(0, int(data.get("manual_xp_amount") or 0))

            if manual_ticket_id != ticket_id:
                ticket = await run_sync(
                    ticket_admin_support._review_ticket, ticket_id=ticket_id
                )
                if ticket is None:
                    await query.answer(_("⚠️ Ticket was not found."), show_alert=True)
                    return
                flag_color = str(ticket.flag_color or "green").lower()
                xp_amount = max(0, int(ticket.xp_amount or 0))
                await state.update_data(
                    manual_ticket_id=ticket_id,
                    manual_flag_color=flag_color,
                    manual_xp_amount=xp_amount,
                )

            if action == ticket_admin_support.REVIEW_ACTION_MANUAL_COLOR:
                if arg is None:
                    await query.answer(_("⚠️ Invalid color option."), show_alert=True)
                    return
                next_color = str(arg).lower()
                if next_color not in ticket_admin_support.VALID_TICKET_COLORS:
                    await query.answer(_("⚠️ Invalid color option."), show_alert=True)
                    return
                flag_color = next_color
                await state.update_data(manual_flag_color=flag_color)

            elif action == ticket_admin_support.REVIEW_ACTION_MANUAL_XP:
                if arg is None:
                    await query.answer(_("⚠️ Invalid XP option."), show_alert=True)
                    return
                try:
                    xp_amount = int(arg)
                except (TypeError, ValueError):
                    await query.answer(_("⚠️ Invalid XP option."), show_alert=True)
                    return
                xp_amount = max(0, xp_amount)
                await state.update_data(manual_xp_amount=xp_amount)

            elif action == ticket_admin_support.REVIEW_ACTION_MANUAL_ADJ:
                if arg is None:
                    await query.answer(_("⚠️ Invalid XP adjustment."), show_alert=True)
                    return
                try:
                    delta = int(arg)
                except (TypeError, ValueError):
                    await query.answer(_("⚠️ Invalid XP adjustment."), show_alert=True)
                    return
                xp_amount = max(0, xp_amount + delta)
                await state.update_data(manual_xp_amount=xp_amount)

            elif action == ticket_admin_support.REVIEW_ACTION_MANUAL_SAVE:
                try:
                    ticket = await run_sync(
                        ticket_admin_support._set_ticket_manual_metrics,
                        ticket_id=ticket_id,
                        flag_color=flag_color,
                        xp_amount=xp_amount,
                    )
                except ValueError as exc:
                    await query.answer(
                        _("❌ Manual metrics update failed: %(reason)s")
                        % {"reason": _(str(exc))},
                        show_alert=True,
                    )
                    return

                await ticket_admin_support._safe_edit_message(
                    query=query,
                    text=ticket_admin_support._review_ticket_text(ticket=ticket, _=_),
                    reply_markup=ticket_admin_support._review_ticket_keyboard(
                        ticket_id=ticket.id,
                        page=review_page,
                        permissions=permissions,
                        ticket_status=ticket.status,
                    ),
                )
                await query.answer(_("✅ Manual metrics updated."), show_alert=False)
                return

            await ticket_admin_support._safe_edit_message(
                query=query,
                text=ticket_admin_support._manual_metrics_text(
                    ticket_id=ticket_id,
                    flag_color=flag_color,
                    xp_amount=xp_amount,
                    _=_,
                ),
                reply_markup=ticket_admin_support._manual_metrics_keyboard(
                    ticket_id=ticket_id,
                    flag_color=flag_color,
                    xp_amount=xp_amount,
                ),
            )
            await query.answer()
            return

        await query.answer(_("⚠️ Unknown action."), show_alert=True)
