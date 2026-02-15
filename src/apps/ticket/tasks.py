"""Ticket Celery task module."""

from celery import shared_task

from ticket.services_work_session import TicketWorkSessionService


@shared_task(name="ticket.tasks.enforce_daily_pause_limits")
def enforce_daily_pause_limits() -> int:
    """Auto-resume paused work sessions that exhausted today's pause budget."""
    return TicketWorkSessionService.auto_resume_paused_sessions_if_limit_reached()
