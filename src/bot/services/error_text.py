from __future__ import annotations

from django.utils.translation import gettext as django_gettext
from django.utils.translation import gettext_noop

_ERROR_REASON_MAP: dict[str, str] = {
    "You are already registered and linked.": gettext_noop(
        "You are already registered and linked."
    ),
    "Your access request was already approved.": gettext_noop(
        "Your access request was already approved."
    ),
    "Phone number is already used by another account.": gettext_noop(
        "Phone number is already used by another account."
    ),
    "Technician already has an active work session. Stop current work session or move ticket to waiting QC before starting another ticket.": gettext_noop(
        "Technician already has an active work session. Stop current work session or move ticket to waiting QC before starting another ticket."
    ),
    "Work session must be stopped before moving ticket to waiting QC.": gettext_noop(
        "Work session must be stopped before moving ticket to waiting QC."
    ),
    "Daily pause limit is fully reached for today.": gettext_noop(
        "Daily pause limit is fully reached for today."
    ),
    "No active work session found for this ticket and technician.": gettext_noop(
        "No active work session found for this ticket and technician."
    ),
    "Ticket cannot be assigned in current status.": gettext_noop(
        "Ticket cannot be assigned in current status."
    ),
    "Ticket must pass admin review before assignment.": gettext_noop(
        "Ticket must pass admin review before assignment."
    ),
    "Ticket can be started only from ASSIGNED or REWORK.": gettext_noop(
        "Ticket can be started only from ASSIGNED or REWORK."
    ),
    "Ticket has no assigned technician.": gettext_noop(
        "Ticket has no assigned technician."
    ),
    "Only assigned technician can start this ticket.": gettext_noop(
        "Only assigned technician can start this ticket."
    ),
    "Ticket can be sent to QC only from IN_PROGRESS.": gettext_noop(
        "Ticket can be sent to QC only from IN_PROGRESS."
    ),
    "Only assigned technician can send ticket to QC.": gettext_noop(
        "Only assigned technician can send ticket to QC."
    ),
    "QC PASS allowed only from WAITING_QC.": gettext_noop(
        "QC PASS allowed only from WAITING_QC."
    ),
    "Ticket must have an assigned technician before QC PASS.": gettext_noop(
        "Ticket must have an assigned technician before QC PASS."
    ),
    "QC FAIL allowed only from WAITING_QC.": gettext_noop(
        "QC FAIL allowed only from WAITING_QC."
    ),
    "Work session can be paused only from RUNNING state.": gettext_noop(
        "Work session can be paused only from RUNNING state."
    ),
    "Work session can be resumed only from PAUSED state.": gettext_noop(
        "Work session can be resumed only from PAUSED state."
    ),
    "Work session can be stopped only from RUNNING or PAUSED state.": gettext_noop(
        "Work session can be stopped only from RUNNING or PAUSED state."
    ),
    "Ticket review can be approved only from UNDER_REVIEW or NEW status.": gettext_noop(
        "Ticket review can be approved only from UNDER_REVIEW or NEW status."
    ),
    "Target user was not found.": gettext_noop("Target user was not found."),
    "amount must not be 0.": gettext_noop("amount must not be 0."),
    "comment is required.": gettext_noop("comment is required."),
    "level is invalid.": gettext_noop("level is invalid."),
    "actor_user_id does not exist.": gettext_noop("actor_user_id does not exist."),
}


def translate_error_reason(*, reason: object, _) -> str:
    translator = _ or django_gettext
    raw_reason = str(reason or "").strip()
    if not raw_reason:
        return translator(gettext_noop("Unknown error."))
    normalized = " ".join(raw_reason.split())
    mapped = _ERROR_REASON_MAP.get(normalized, normalized)
    return translator(mapped)

