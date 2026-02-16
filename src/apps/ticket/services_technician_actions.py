from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core.utils.constants import TicketStatus, WorkSessionStatus
from ticket.models import Ticket, WorkSession


@dataclass(frozen=True)
class TechnicianTicketState:
    ticket_id: int
    serial_number: str
    ticket_status: str
    session_status: str | None
    actions: tuple[str, ...]


class TechnicianTicketActionService:
    """Technician-side ticket action helper for Telegram-driven workflows."""

    CALLBACK_PREFIX = "tt"

    ACTION_START = "start"
    ACTION_PAUSE = "pause"
    ACTION_RESUME = "resume"
    ACTION_STOP = "stop"
    ACTION_TO_WAITING_QC = "to_waiting_qc"
    ACTION_REFRESH = "refresh"

    _ACTION_ORDER = (
        ACTION_START,
        ACTION_PAUSE,
        ACTION_RESUME,
        ACTION_STOP,
        ACTION_TO_WAITING_QC,
    )
    _ACTION_LABELS = {
        ACTION_START: "Start",
        ACTION_PAUSE: "Pause",
        ACTION_RESUME: "Resume",
        ACTION_STOP: "Stop",
        ACTION_TO_WAITING_QC: "Move to QC",
        ACTION_REFRESH: "Refresh",
    }
    _ACTION_FEEDBACK = {
        ACTION_START: "Work started.",
        ACTION_PAUSE: "Work paused.",
        ACTION_RESUME: "Work resumed.",
        ACTION_STOP: "Work stopped.",
        ACTION_TO_WAITING_QC: "Ticket moved to waiting QC.",
        ACTION_REFRESH: "Ticket status refreshed.",
    }

    @classmethod
    def queue_states_for_technician(
        cls, *, technician_id: int
    ) -> list[TechnicianTicketState]:
        tickets = cls._queue_tickets_for_technician(technician_id=technician_id)
        return [
            cls.state_for_ticket(ticket=ticket, technician_id=technician_id)
            for ticket in tickets
        ]

    @classmethod
    def state_for_technician_and_ticket(
        cls, *, technician_id: int, ticket_id: int
    ) -> TechnicianTicketState:
        ticket = cls.get_ticket_for_technician(
            technician_id=technician_id,
            ticket_id=ticket_id,
        )
        if ticket is None:
            raise ValueError("Ticket is not found or is not assigned to you.")
        return cls.state_for_ticket(ticket=ticket, technician_id=technician_id)

    @classmethod
    def execute_for_technician(
        cls,
        *,
        technician_id: int,
        ticket_id: int,
        action: str,
    ) -> TechnicianTicketState:
        ticket = cls.get_ticket_for_technician(
            technician_id=technician_id,
            ticket_id=ticket_id,
        )
        if ticket is None:
            raise ValueError("Ticket is not found or is not assigned to you.")

        cls._execute_action(ticket=ticket, technician_id=technician_id, action=action)

        refreshed_ticket = cls.get_ticket_for_technician(
            technician_id=technician_id,
            ticket_id=ticket_id,
        )
        if refreshed_ticket is None:
            raise ValueError("Ticket is not found or is not assigned to you.")
        return cls.state_for_ticket(
            ticket=refreshed_ticket, technician_id=technician_id
        )

    @classmethod
    def state_for_ticket(
        cls, *, ticket: Ticket, technician_id: int
    ) -> TechnicianTicketState:
        if ticket.technician_id != technician_id:
            raise ValueError("Ticket is not assigned to this technician.")

        session_status = cls._latest_session_status(
            ticket=ticket,
            technician_id=technician_id,
        )
        actions = tuple(
            cls.available_actions(
                ticket=ticket,
                technician_id=technician_id,
                latest_session_status=session_status,
            )
        )
        return TechnicianTicketState(
            ticket_id=ticket.id,
            serial_number=cls._serial_number(ticket=ticket),
            ticket_status=str(ticket.status),
            session_status=session_status,
            actions=actions,
        )

    @classmethod
    def available_actions(
        cls,
        *,
        ticket: Ticket,
        technician_id: int,
        latest_session_status: str | None = None,
    ) -> list[str]:
        if ticket.technician_id != technician_id:
            return []

        if ticket.status in (TicketStatus.ASSIGNED, TicketStatus.REWORK):
            if WorkSession.domain.has_open_for_technician(technician_id=technician_id):
                return []
            return [cls.ACTION_START]

        if ticket.status != TicketStatus.IN_PROGRESS:
            return []

        session_status = latest_session_status or cls._latest_session_status(
            ticket=ticket,
            technician_id=technician_id,
        )
        if session_status == WorkSessionStatus.RUNNING:
            return [cls.ACTION_PAUSE, cls.ACTION_STOP]
        if session_status == WorkSessionStatus.PAUSED:
            return [cls.ACTION_RESUME, cls.ACTION_STOP]
        if session_status == WorkSessionStatus.STOPPED:
            return [cls.ACTION_TO_WAITING_QC]
        return []

    @classmethod
    def build_action_keyboard(
        cls,
        *,
        ticket_id: int,
        actions: Iterable[str],
        include_refresh: bool = True,
    ) -> InlineKeyboardMarkup | None:
        action_set = {
            action
            for action in actions
            if action in cls._ACTION_LABELS and action != cls.ACTION_REFRESH
        }
        ordered_actions = [
            action for action in cls._ACTION_ORDER if action in action_set
        ]
        if include_refresh and ordered_actions:
            ordered_actions.append(cls.ACTION_REFRESH)
        if not ordered_actions:
            return None

        inline_keyboard: list[list[InlineKeyboardButton]] = []
        row: list[InlineKeyboardButton] = []
        for action in ordered_actions:
            row.append(
                InlineKeyboardButton(
                    text=cls._ACTION_LABELS[action],
                    callback_data=cls.build_callback_data(
                        ticket_id=ticket_id,
                        action=action,
                    ),
                )
            )
            if len(row) == 2:
                inline_keyboard.append(row)
                row = []
        if row:
            inline_keyboard.append(row)
        return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    @classmethod
    def render_state_message(
        cls,
        *,
        state: TechnicianTicketState,
        heading: str | None = None,
    ) -> str:
        lines: list[str] = []
        if heading:
            lines.append(heading)
        lines.extend(
            [
                f"Ticket: #{state.ticket_id}",
                f"Serial number: {state.serial_number}",
                f"Status: {state.ticket_status}",
            ]
        )
        if state.session_status:
            lines.append(f"Work session: {state.session_status}")

        available_labels = [
            cls._ACTION_LABELS[action]
            for action in state.actions
            if action != cls.ACTION_REFRESH and action in cls._ACTION_LABELS
        ]
        if available_labels:
            lines.append(f"Available actions: {', '.join(available_labels)}")
        else:
            lines.append("No technician actions are available right now.")
        return "\n".join(lines)

    @classmethod
    def action_feedback(cls, *, action: str) -> str:
        return cls._ACTION_FEEDBACK.get(action, "Ticket state updated.")

    @classmethod
    def build_callback_data(cls, *, ticket_id: int, action: str) -> str:
        return f"{cls.CALLBACK_PREFIX}:{int(ticket_id)}:{action}"

    @classmethod
    def parse_callback_data(cls, *, callback_data: str) -> tuple[int, str] | None:
        parts = str(callback_data or "").split(":", 2)
        if len(parts) != 3 or parts[0] != cls.CALLBACK_PREFIX:
            return None

        ticket_id_raw, action = parts[1], parts[2]
        if action not in cls._ACTION_LABELS:
            return None

        try:
            ticket_id = int(ticket_id_raw)
        except (TypeError, ValueError):
            return None

        return ticket_id, action

    @classmethod
    def get_ticket_for_technician(
        cls, *, technician_id: int, ticket_id: int
    ) -> Ticket | None:
        return (
            Ticket.domain.select_related("inventory_item")
            .filter(pk=ticket_id, technician_id=technician_id)
            .first()
        )

    @classmethod
    def _queue_tickets_for_technician(cls, *, technician_id: int) -> list[Ticket]:
        return list(
            Ticket.domain.select_related("inventory_item")
            .filter(
                technician_id=technician_id,
                status__in=[
                    TicketStatus.ASSIGNED,
                    TicketStatus.REWORK,
                    TicketStatus.IN_PROGRESS,
                ],
            )
            .order_by("-created_at", "-id")
        )

    @classmethod
    def _latest_session_status(
        cls, *, ticket: Ticket, technician_id: int
    ) -> str | None:
        open_session = WorkSession.domain.get_open_for_ticket_and_technician(
            ticket=ticket,
            technician_id=technician_id,
        )
        if open_session is not None:
            return str(open_session.status)

        latest_session = WorkSession.domain.get_latest_for_ticket_and_technician(
            ticket=ticket,
            technician_id=technician_id,
        )
        if latest_session is None:
            return None
        return str(latest_session.status)

    @classmethod
    def _execute_action(
        cls,
        *,
        ticket: Ticket,
        technician_id: int,
        action: str,
    ) -> None:
        if action == cls.ACTION_REFRESH:
            return

        available_actions = cls.available_actions(
            ticket=ticket,
            technician_id=technician_id,
        )
        if action not in available_actions:
            raise ValueError("Action is not available for this ticket right now.")

        if action == cls.ACTION_START:
            from ticket.services_workflow import TicketWorkflowService

            TicketWorkflowService.start_ticket(
                ticket=ticket,
                actor_user_id=technician_id,
            )
            return

        if action == cls.ACTION_PAUSE:
            from ticket.services_work_session import TicketWorkSessionService

            TicketWorkSessionService.pause_work_session(
                ticket=ticket,
                actor_user_id=technician_id,
            )
            return

        if action == cls.ACTION_RESUME:
            from ticket.services_work_session import TicketWorkSessionService

            TicketWorkSessionService.resume_work_session(
                ticket=ticket,
                actor_user_id=technician_id,
            )
            return

        if action == cls.ACTION_STOP:
            from ticket.services_work_session import TicketWorkSessionService

            TicketWorkSessionService.stop_work_session(
                ticket=ticket,
                actor_user_id=technician_id,
            )
            return

        if action == cls.ACTION_TO_WAITING_QC:
            from ticket.services_workflow import TicketWorkflowService

            TicketWorkflowService.move_ticket_to_waiting_qc(
                ticket=ticket,
                actor_user_id=technician_id,
            )
            return

        raise ValueError("Unsupported action.")

    @staticmethod
    def _serial_number(*, ticket: Ticket) -> str:
        inventory_item = getattr(ticket, "inventory_item", None)
        return getattr(inventory_item, "serial_number", "") or "unknown"
