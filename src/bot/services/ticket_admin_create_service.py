from __future__ import annotations

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from account.models import User
from bot.services import ticket_admin_support as legacy
from inventory.models import InventoryItem
from ticket.models import Ticket


class TicketAdminCreateService:
    CALLBACK_PREFIX = legacy.CREATE_CALLBACK_PREFIX
    ITEMS_PER_PAGE = legacy.ITEMS_PER_PAGE

    @staticmethod
    def parse_callback(*, callback_data: str) -> tuple[str, list[str]] | None:
        return legacy._parse_create_callback(callback_data=callback_data)

    @staticmethod
    def query_inventory_items_page(
        *,
        page: int,
        per_page: int = ITEMS_PER_PAGE,
    ) -> tuple[list[InventoryItem], int, int, int]:
        return legacy._query_inventory_items_page(page=page, per_page=per_page)

    @staticmethod
    def create_items_text(
        *, page: int, page_count: int, items: list[InventoryItem], _
    ) -> str:
        return legacy._create_items_text(
            page=page,
            page_count=page_count,
            items=items,
            _=_,
        )

    @staticmethod
    def create_items_keyboard(
        *, page: int, page_count: int, items: list[InventoryItem]
    ):
        return legacy._create_items_keyboard(
            page=page,
            page_count=page_count,
            items=items,
        )

    @staticmethod
    def parts_selection_text(
        *,
        serial_number: str,
        parts: list[dict],
        selected_ids: set[int],
        _,
    ) -> str:
        return legacy._parts_selection_text(
            serial_number=serial_number,
            parts=parts,
            selected_ids=selected_ids,
            _=_,
        )

    @staticmethod
    def parts_selection_keyboard(
        *, parts: list[dict], selected_ids: set[int], item_page: int
    ):
        return legacy._parts_selection_keyboard(
            parts=parts,
            selected_ids=selected_ids,
            item_page=item_page,
        )

    @staticmethod
    def spec_editor_text(
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
        return legacy._spec_editor_text(
            serial_number=serial_number,
            current_index=current_index,
            total_parts=total_parts,
            part_name=part_name,
            draft_color=draft_color,
            draft_minutes=draft_minutes,
            completed_count=completed_count,
            _=_,
        )

    @staticmethod
    def spec_editor_keyboard(*, draft_color: str, draft_minutes: int):
        return legacy._spec_editor_keyboard(
            draft_color=draft_color,
            draft_minutes=draft_minutes,
        )

    @staticmethod
    def summary_text(
        *, serial_number: str, specs: list[dict], parts_by_id: dict[int, str], _
    ) -> str:
        return legacy._summary_text(
            serial_number=serial_number,
            specs=specs,
            parts_by_id=parts_by_id,
            _=_,
        )

    @staticmethod
    def summary_keyboard():
        return legacy._summary_keyboard()

    @staticmethod
    def draft_for_part(*, part_id: int, part_specs: list[dict]) -> tuple[str, int]:
        return legacy._draft_for_part(part_id=part_id, part_specs=part_specs)

    @staticmethod
    def create_ticket_from_payload(
        *,
        actor_user: User,
        serial_number: str,
        title: str | None = None,
        part_specs: list[dict[str, object]],
    ) -> Ticket:
        return legacy._create_ticket_from_payload(
            actor_user=actor_user,
            serial_number=serial_number,
            title=title,
            part_specs=part_specs,
        )

    @staticmethod
    async def show_items_page(
        *,
        query: CallbackQuery,
        state: FSMContext,
        page: int,
        _,
    ) -> None:
        await legacy._show_create_items_page(
            query=query,
            state=state,
            page=page,
            _=_,
        )
