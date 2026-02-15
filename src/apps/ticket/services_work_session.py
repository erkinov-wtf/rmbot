from django.db import transaction

from ticket.models import Ticket, WorkSession, WorkSessionTransition


class TicketWorkSessionService:
    """Session lifecycle manager for technician work time accounting."""

    @classmethod
    @transaction.atomic
    def pause_work_session(cls, ticket: Ticket, actor_user_id: int) -> WorkSession:
        session = cls._get_open_session_for_ticket(
            ticket=ticket, actor_user_id=actor_user_id
        )
        session.pause(actor_user_id=actor_user_id)
        return session

    @classmethod
    @transaction.atomic
    def resume_work_session(cls, ticket: Ticket, actor_user_id: int) -> WorkSession:
        session = cls._get_open_session_for_ticket(
            ticket=ticket, actor_user_id=actor_user_id
        )
        session.resume(actor_user_id=actor_user_id)
        return session

    @classmethod
    @transaction.atomic
    def stop_work_session(cls, ticket: Ticket, actor_user_id: int) -> WorkSession:
        session = cls._get_open_session_for_ticket(
            ticket=ticket, actor_user_id=actor_user_id
        )
        session.stop(actor_user_id=actor_user_id)
        return session

    @staticmethod
    def get_ticket_work_session_history(ticket: Ticket):
        return WorkSessionTransition.domain.history_for_ticket(ticket=ticket)

    @staticmethod
    def _get_open_session_for_ticket(ticket: Ticket, actor_user_id: int) -> WorkSession:
        session = WorkSession.domain.get_open_for_ticket_and_technician(
            ticket=ticket,
            technician_id=actor_user_id,
        )
        if not session:
            raise ValueError(
                "No active work session found for this ticket and technician."
            )
        return session
