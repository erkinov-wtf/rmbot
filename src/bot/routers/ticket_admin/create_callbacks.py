from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.handlers import CallbackQueryHandler
from aiogram.types import CallbackQuery, Message
from rest_framework import serializers as drf_serializers

from account.models import User
from bot.services import ticket_admin_support
from bot.services.menu import main_menu_markup_for_user
from core.utils.asyncio import run_sync
from inventory.models import InventoryItem, InventoryItemPart
from ticket.models import Ticket

router = Router(name="ticket_admin_create_callbacks")


class TicketCreateCallbackSupportMixin:
    @classmethod
    def source_message(cls, query: CallbackQuery) -> Message | None:
        message = query.message
        return message if isinstance(message, Message) else None

    @classmethod
    async def ensure_create_access_for_callback(
        cls,
        *,
        state: FSMContext,
        user: User | None,
        query: CallbackQuery,
        _,
    ) -> bool:
        if not user or not user.is_active:
            await state.clear()
            await ticket_admin_support._notify_not_registered_callback(query=query, _=_)
            return False

        permissions = await ticket_admin_support._ticket_permissions(user=user)
        if not permissions.can_create:
            await state.clear()
            await query.answer(
                _("⛔ Your roles do not allow ticket intake."), show_alert=True
            )
            return False

        return True


@router.callback_query(
    F.data.startswith(f"{ticket_admin_support.CREATE_CALLBACK_PREFIX}:")
)
class TicketCreateCallbackHandler(
    TicketCreateCallbackSupportMixin, CallbackQueryHandler
):
    async def handle(self) -> None:
        query: CallbackQuery = self.event
        state: FSMContext = self.data["state"]
        _ = self.data["_"]
        user: User | None = self.data.get("user")

        parsed = ticket_admin_support._parse_create_callback(
            callback_data=query.data or ""
        )
        if parsed is None:
            await query.answer(_("⚠️ Unknown action."), show_alert=True)
            return

        if not await self.ensure_create_access_for_callback(
            state=state,
            user=user,
            query=query,
            _=_,
        ):
            return

        action, args = parsed
        if await self.handle_pre_parts_actions(
            query=query,
            state=state,
            action=action,
            args=args,
            user=user,
            _=_,
        ):
            return

        data = await state.get_data()
        serial_number = str(data.get("serial_number") or "")
        parts = list(data.get("available_parts") or [])
        selected_ids = {int(value) for value in data.get("selected_part_ids", [])}
        item_page = int(data.get("create_page") or 1)

        if not serial_number or not parts:
            await query.answer(
                _("⚠️ Ticket intake session expired. Start again."), show_alert=True
            )
            return

        if await self.handle_parts_selection_actions(
            query=query,
            state=state,
            action=action,
            args=args,
            serial_number=serial_number,
            parts=parts,
            selected_ids=selected_ids,
            item_page=item_page,
            _=_,
        ):
            return

        if action in {"clr", "min", "adj", "save", "create"}:
            await self.handle_spec_and_create_actions(
                query=query,
                state=state,
                action=action,
                args=args,
                serial_number=serial_number,
                parts=parts,
                user=user,
                _=_,
            )
            return

        await query.answer(_("⚠️ Unknown action."), show_alert=True)

    @classmethod
    async def handle_pre_parts_actions(
        cls,
        *,
        query: CallbackQuery,
        state: FSMContext,
        action: str,
        args: list[str],
        user: User,
        _,
    ) -> bool:
        if action == "noop":
            await query.answer()
            return True

        if action == "cancel":
            await state.clear()
            source_message = cls.source_message(query)
            if source_message is not None:
                await source_message.answer(
                    _("🛑 Ticket intake canceled."),
                    reply_markup=await main_menu_markup_for_user(user=user, _=_),
                )
            await query.answer()
            return True

        if action == "list":
            try:
                page = int(args[0]) if args else 1
            except (TypeError, ValueError):
                await query.answer(_("⚠️ Could not open this page."), show_alert=True)
                return True
            await ticket_admin_support._show_create_items_page(
                query=query,
                state=state,
                page=page,
                _=_,
            )
            await query.answer()
            return True

        if action == "item":
            if len(args) < 2:
                await query.answer(_("⚠️ Invalid item selection."), show_alert=True)
                return True
            try:
                item_id = int(args[0])
                page = int(args[1])
            except (TypeError, ValueError):
                await query.answer(_("⚠️ Invalid item selection."), show_alert=True)
                return True

            inventory_item = await run_sync(
                lambda _item_id: InventoryItem.domain.get_queryset()
                .filter(pk=_item_id, is_active=True)
                .first(),
                item_id,
            )
            if inventory_item is None:
                await query.answer(
                    _("⚠️ Inventory item was not found."), show_alert=True
                )
                return True

            has_active_ticket = await run_sync(
                Ticket.domain.has_active_for_inventory_item,
                inventory_item=inventory_item,
            )
            if has_active_ticket:
                await query.answer(
                    _("⚠️ An active ticket already exists for this inventory item."),
                    show_alert=True,
                )
                return True

            parts_queryset = (
                InventoryItemPart.domain.get_queryset()
                .filter(inventory_item_id=inventory_item.id)
                .order_by("id")
                .values("id", "name")
            )
            parts = await run_sync(list, parts_queryset)
            if not parts:
                await query.answer(
                    _("⚠️ This inventory item has no parts configured."),
                    show_alert=True,
                )
                return True

            await state.set_state(ticket_admin_support.TicketCreateForm.flow)
            await state.update_data(
                create_page=ticket_admin_support._normalize_page(page=page),
                inventory_item_id=inventory_item.id,
                serial_number=inventory_item.serial_number,
                available_parts=parts,
                selected_part_ids=[],
                part_order=[],
                part_specs=[],
                current_part_index=0,
                draft_color="green",
                draft_minutes=10,
                create_mode="parts",
            )

            await ticket_admin_support._safe_edit_message(
                query=query,
                text=ticket_admin_support._parts_selection_text(
                    serial_number=inventory_item.serial_number,
                    parts=parts,
                    selected_ids=set(),
                    _=_,
                ),
                reply_markup=ticket_admin_support._parts_selection_keyboard(
                    parts=parts,
                    selected_ids=set(),
                    item_page=ticket_admin_support._normalize_page(page=page),
                ),
            )
            await query.answer()
            return True

        return False

    @classmethod
    async def handle_parts_selection_actions(
        cls,
        *,
        query: CallbackQuery,
        state: FSMContext,
        action: str,
        args: list[str],
        serial_number: str,
        parts: list[dict],
        selected_ids: set[int],
        item_page: int,
        _,
    ) -> bool:
        if action == "tog":
            if not args:
                await query.answer(_("⚠️ Invalid part selection."), show_alert=True)
                return True
            try:
                part_id = int(args[0])
            except (TypeError, ValueError):
                await query.answer(_("⚠️ Invalid part selection."), show_alert=True)
                return True

            all_part_ids = {int(part["id"]) for part in parts}
            if part_id not in all_part_ids:
                await query.answer(_("⚠️ Invalid part selection."), show_alert=True)
                return True

            if part_id in selected_ids:
                selected_ids.remove(part_id)
            else:
                selected_ids.add(part_id)

            await state.update_data(
                selected_part_ids=sorted(selected_ids), create_mode="parts"
            )
            await ticket_admin_support._safe_edit_message(
                query=query,
                text=ticket_admin_support._parts_selection_text(
                    serial_number=serial_number,
                    parts=parts,
                    selected_ids=selected_ids,
                    _=_,
                ),
                reply_markup=ticket_admin_support._parts_selection_keyboard(
                    parts=parts,
                    selected_ids=selected_ids,
                    item_page=item_page,
                ),
            )
            await query.answer()
            return True

        if action == "go":
            if not selected_ids:
                await query.answer(
                    _("⚠️ Select at least one part first."), show_alert=True
                )
                return True

            part_order = [
                int(part["id"]) for part in parts if int(part["id"]) in selected_ids
            ]
            data = await state.get_data()
            part_specs = list(data.get("part_specs") or [])
            draft_color, draft_minutes = ticket_admin_support._draft_for_part(
                part_id=part_order[0],
                part_specs=part_specs,
            )

            await state.update_data(
                part_order=part_order,
                current_part_index=0,
                draft_color=draft_color,
                draft_minutes=draft_minutes,
                create_mode="spec",
            )
            current_part_name = next(
                (
                    str(part["name"])
                    for part in parts
                    if int(part["id"]) == part_order[0]
                ),
                f"Part #{part_order[0]}",
            )
            await ticket_admin_support._safe_edit_message(
                query=query,
                text=ticket_admin_support._spec_editor_text(
                    serial_number=serial_number,
                    current_index=0,
                    total_parts=len(part_order),
                    part_name=current_part_name,
                    draft_color=draft_color,
                    draft_minutes=draft_minutes,
                    completed_count=len(part_specs),
                    _=_,
                ),
                reply_markup=ticket_admin_support._spec_editor_keyboard(
                    draft_color=draft_color,
                    draft_minutes=draft_minutes,
                ),
            )
            await query.answer()
            return True

        if action == "back":
            await state.update_data(create_mode="parts")
            await ticket_admin_support._safe_edit_message(
                query=query,
                text=ticket_admin_support._parts_selection_text(
                    serial_number=serial_number,
                    parts=parts,
                    selected_ids=selected_ids,
                    _=_,
                ),
                reply_markup=ticket_admin_support._parts_selection_keyboard(
                    parts=parts,
                    selected_ids=selected_ids,
                    item_page=item_page,
                ),
            )
            await query.answer()
            return True

        return False

    @classmethod
    async def handle_spec_and_create_actions(
        cls,
        *,
        query: CallbackQuery,
        state: FSMContext,
        action: str,
        args: list[str],
        serial_number: str,
        parts: list[dict],
        user: User,
        _,
    ) -> None:
        data = await state.get_data()
        part_order = [int(value) for value in data.get("part_order", [])]
        part_specs = list(data.get("part_specs") or [])
        current_index = int(data.get("current_part_index") or 0)
        draft_color = str(data.get("draft_color") or "green").lower()
        draft_minutes = max(1, int(data.get("draft_minutes") or 10))

        if action != "create" and not part_order:
            await query.answer(
                _("⚠️ Part configuration session expired."), show_alert=True
            )
            return

        if action == "clr":
            if not args:
                await query.answer(_("⚠️ Invalid color option."), show_alert=True)
                return
            color = str(args[0]).lower()
            if color not in ticket_admin_support.VALID_TICKET_COLORS:
                await query.answer(_("⚠️ Invalid color option."), show_alert=True)
                return
            draft_color = color
            await state.update_data(draft_color=draft_color)

        elif action == "min":
            if not args:
                await query.answer(_("⚠️ Invalid minutes option."), show_alert=True)
                return
            try:
                draft_minutes = int(args[0])
            except (TypeError, ValueError):
                await query.answer(_("⚠️ Invalid minutes option."), show_alert=True)
                return
            draft_minutes = max(1, draft_minutes)
            await state.update_data(draft_minutes=draft_minutes)

        elif action == "adj":
            if not args:
                await query.answer(_("⚠️ Invalid minutes adjustment."), show_alert=True)
                return
            try:
                delta = int(args[0])
            except (TypeError, ValueError):
                await query.answer(_("⚠️ Invalid minutes adjustment."), show_alert=True)
                return
            draft_minutes = max(1, draft_minutes + delta)
            await state.update_data(draft_minutes=draft_minutes)

        elif action == "save":
            if current_index >= len(part_order):
                await query.answer(
                    _("⚠️ Part configuration session expired."), show_alert=True
                )
                return

            part_id = part_order[current_index]
            existing_idx = next(
                (
                    index
                    for index, row in enumerate(part_specs)
                    if int(row["part_id"]) == part_id
                ),
                None,
            )
            spec_payload = {
                "part_id": part_id,
                "color": draft_color,
                "minutes": draft_minutes,
                "comment": "",
            }
            if existing_idx is None:
                part_specs.append(spec_payload)
            else:
                part_specs[existing_idx] = spec_payload

            current_index += 1
            if current_index < len(part_order):
                next_part_id = part_order[current_index]
                draft_color, draft_minutes = ticket_admin_support._draft_for_part(
                    part_id=next_part_id,
                    part_specs=part_specs,
                )
                next_part_name = next(
                    (
                        str(part["name"])
                        for part in parts
                        if int(part["id"]) == next_part_id
                    ),
                    f"Part #{next_part_id}",
                )
                await state.update_data(
                    part_specs=part_specs,
                    current_part_index=current_index,
                    draft_color=draft_color,
                    draft_minutes=draft_minutes,
                    create_mode="spec",
                )
                await ticket_admin_support._safe_edit_message(
                    query=query,
                    text=ticket_admin_support._spec_editor_text(
                        serial_number=serial_number,
                        current_index=current_index,
                        total_parts=len(part_order),
                        part_name=next_part_name,
                        draft_color=draft_color,
                        draft_minutes=draft_minutes,
                        completed_count=len(part_specs),
                        _=_,
                    ),
                    reply_markup=ticket_admin_support._spec_editor_keyboard(
                        draft_color=draft_color,
                        draft_minutes=draft_minutes,
                    ),
                )
                await query.answer(_("✅ Part saved."))
                return

            parts_by_id = {int(part["id"]): str(part["name"]) for part in parts}
            ordered_specs = [
                next(row for row in part_specs if int(row["part_id"]) == part_id)
                for part_id in part_order
            ]
            await state.update_data(
                part_specs=ordered_specs,
                current_part_index=current_index,
                create_mode="summary",
            )
            await ticket_admin_support._safe_edit_message(
                query=query,
                text=ticket_admin_support._summary_text(
                    serial_number=serial_number,
                    specs=ordered_specs,
                    parts_by_id=parts_by_id,
                    _=_,
                ),
                reply_markup=ticket_admin_support._summary_keyboard(),
            )
            await query.answer(_("✅ All part specs configured."))
            return

        elif action == "create":
            create_mode = str(data.get("create_mode") or "")
            if create_mode != "summary":
                await query.answer(_("⚠️ Configure parts first."), show_alert=True)
                return

            part_specs = list(data.get("part_specs") or [])
            if not part_specs:
                await query.answer(
                    _("⚠️ No part specs were configured."), show_alert=True
                )
                return

            try:
                ticket = await run_sync(
                    ticket_admin_support._create_ticket_from_payload,
                    actor_user=user,
                    serial_number=serial_number,
                    part_specs=part_specs,
                )
            except drf_serializers.ValidationError as exc:
                error_message = ticket_admin_support._extract_error_message(
                    exc.detail,
                    _=_,
                )
                await query.answer(
                    _("❌ Ticket create failed: %(reason)s")
                    % {"reason": error_message},
                    show_alert=True,
                )
                return
            except ValueError as exc:
                await query.answer(
                    _("❌ Ticket create failed: %(reason)s") % {"reason": _(str(exc))},
                    show_alert=True,
                )
                return

            await state.clear()
            await ticket_admin_support._safe_edit_message(
                query=query,
                text=(
                    _("✅ <b>Ticket created successfully.</b>\n")
                    + _("• <b>Ticket:</b> #%(ticket_id)s\n") % {"ticket_id": ticket.id}
                    + _("• <b>Serial:</b> <code>%(serial)s</code>\n")
                    % {"serial": ticket.inventory_item.serial_number}
                    + _("• <b>Status:</b> %(status)s\n")
                    % {
                        "status": ticket_admin_support._status_label(
                            status=ticket.status, _=_
                        )
                    }
                    + _("• <b>Total minutes:</b> %(minutes)s\n")
                    % {"minutes": int(ticket.total_duration or 0)}
                    + _("• <b>Flag / XP:</b> %(flag)s / %(xp)s")
                    % {
                        "flag": ticket.flag_color,
                        "xp": int(ticket.xp_amount or 0),
                    }
                ),
                reply_markup=None,
            )
            source_message = cls.source_message(query)
            if source_message is not None:
                await source_message.answer(
                    _("✅ Ticket intake flow completed."),
                    reply_markup=await main_menu_markup_for_user(user=user, _=_),
                )
            await query.answer()
            return

        if current_index >= len(part_order):
            await query.answer(
                _("⚠️ Part configuration session expired."), show_alert=True
            )
            return

        current_part_id = part_order[current_index]
        current_part_name = next(
            (str(part["name"]) for part in parts if int(part["id"]) == current_part_id),
            f"Part #{current_part_id}",
        )
        await ticket_admin_support._safe_edit_message(
            query=query,
            text=ticket_admin_support._spec_editor_text(
                serial_number=serial_number,
                current_index=current_index,
                total_parts=len(part_order),
                part_name=current_part_name,
                draft_color=draft_color,
                draft_minutes=draft_minutes,
                completed_count=len(part_specs),
                _=_,
            ),
            reply_markup=ticket_admin_support._spec_editor_keyboard(
                draft_color=draft_color,
                draft_minutes=draft_minutes,
            ),
        )
        await query.answer()
