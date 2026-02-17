from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from asgiref.sync import async_to_sync
from django.conf import settings
from django.db import transaction

from account.models import TelegramProfile, User
from bot.services.technician_ticket_actions import TechnicianTicketActionService
from bot.services.ticket_qc_actions import TicketQCActionService
from core.utils.constants import RoleSlug

if TYPE_CHECKING:
    from account.models import AccessRequest
    from ticket.models import Ticket

logger = logging.getLogger(__name__)


class UserNotificationService:
    """Best-effort user-facing Telegram notifications for domain events."""

    @classmethod
    def notify_access_request_decision(
        cls, *, access_request: AccessRequest, approved: bool
    ) -> None:
        greeting = (
            f"Hello, {access_request.first_name}."
            if access_request.first_name
            else "Hello."
        )
        if approved:
            message = f"{greeting}\nYour access request has been approved. You can now use Rent Market."
        else:
            message = f"{greeting}\nYour access request has been denied. You can submit a new request using /start."

        cls._notify_telegram_ids(
            event_key="access_request_decision",
            telegram_ids=[access_request.telegram_id],
            message=message,
        )

    @classmethod
    def notify_ticket_assigned(
        cls, *, ticket: Ticket, actor_user_id: int | None
    ) -> None:
        if not ticket.technician_id:
            return

        master_message = "\n".join(
            [
                "Ticket assigned.",
                f"Ticket: #{ticket.id}",
                f"Serial number: {cls._serial_number(ticket)}",
                f"Technician: {cls._display_name_by_user_id(ticket.technician_id)}",
                f"Assigned by: {cls._display_name_by_user_id(actor_user_id)}",
                f"Status: {ticket.status}",
            ]
        )
        cls._notify_users(
            event_key="ticket_assigned_master",
            user_ids=[ticket.master_id],
            message=master_message,
            exclude_user_ids=[actor_user_id],
        )

        technician_state = TechnicianTicketActionService.state_for_ticket(
            ticket=ticket,
            technician_id=ticket.technician_id,
        )
        technician_message = "\n".join(
            [
                TechnicianTicketActionService.render_state_message(
                    state=technician_state,
                    heading="New ticket assigned to you.",
                ),
                f"Assigned by: {cls._display_name_by_user_id(actor_user_id)}",
            ]
        )
        technician_markup = TechnicianTicketActionService.build_action_keyboard(
            ticket_id=ticket.id,
            actions=technician_state.actions,
        )
        cls._notify_users(
            event_key="ticket_assigned_technician",
            user_ids=[ticket.technician_id],
            message=technician_message,
            reply_markup=technician_markup,
        )

    @classmethod
    def notify_ticket_started(
        cls, *, ticket: Ticket, actor_user_id: int | None
    ) -> None:
        if not ticket.technician_id:
            return

        message = "\n".join(
            [
                "Ticket work started.",
                f"Ticket: #{ticket.id}",
                f"Serial number: {cls._serial_number(ticket)}",
                f"Technician: {cls._display_name_by_user_id(ticket.technician_id)}",
                f"Started by: {cls._display_name_by_user_id(actor_user_id)}",
                f"Status: {ticket.status}",
            ]
        )
        cls._notify_users(
            event_key="ticket_started_technician",
            user_ids=[ticket.technician_id],
            message=message,
            exclude_user_ids=[actor_user_id],
        )

    @classmethod
    def notify_ticket_waiting_qc(
        cls, *, ticket: Ticket, actor_user_id: int | None
    ) -> None:
        qc_user_ids = cls._user_ids_for_role_slugs(
            [RoleSlug.QC_INSPECTOR, RoleSlug.SUPER_ADMIN]
        )
        qc_message = "\n".join(
            [
                "Ticket is waiting for QC.",
                f"Ticket: #{ticket.id}",
                f"Serial number: {cls._serial_number(ticket)}",
                f"Technician: {cls._display_name_by_user_id(ticket.technician_id)}",
                f"Moved by: {cls._display_name_by_user_id(actor_user_id)}",
                f"Status: {ticket.status}",
                "Action: choose QC decision from the buttons below.",
            ]
        )
        cls._notify_users(
            event_key="ticket_waiting_qc_reviewers",
            user_ids=qc_user_ids,
            message=qc_message,
            exclude_user_ids=[actor_user_id],
            reply_markup=TicketQCActionService.build_action_keyboard(
                ticket_id=ticket.id,
                ticket_status=ticket.status,
            ),
        )

    @classmethod
    def notify_ticket_qc_pass(
        cls,
        *,
        ticket: Ticket,
        actor_user_id: int | None,
        base_xp: int,
        first_pass_bonus: int,
    ) -> None:
        xp_summary = f"XP awarded: base={base_xp}"
        if first_pass_bonus > 0:
            xp_summary += f", first_pass_bonus={first_pass_bonus}"

        message = "\n".join(
            [
                "Ticket passed QC.",
                f"Ticket: #{ticket.id}",
                f"Serial number: {cls._serial_number(ticket)}",
                f"Technician: {cls._display_name_by_user_id(ticket.technician_id)}",
                f"QC by: {cls._display_name_by_user_id(actor_user_id)}",
                f"Status: {ticket.status}",
                xp_summary,
            ]
        )
        cls._notify_users(
            event_key="ticket_qc_pass",
            user_ids=[ticket.technician_id],
            message=message,
            exclude_user_ids=[actor_user_id],
        )

    @classmethod
    def notify_ticket_qc_fail(
        cls, *, ticket: Ticket, actor_user_id: int | None
    ) -> None:
        if not ticket.technician_id:
            return

        technician_state = TechnicianTicketActionService.state_for_ticket(
            ticket=ticket,
            technician_id=ticket.technician_id,
        )
        technician_message = "\n".join(
            [
                TechnicianTicketActionService.render_state_message(
                    state=technician_state,
                    heading="Ticket returned from QC. Continue rework.",
                ),
                f"QC by: {cls._display_name_by_user_id(actor_user_id)}",
            ]
        )
        technician_markup = TechnicianTicketActionService.build_action_keyboard(
            ticket_id=ticket.id,
            actions=technician_state.actions,
        )
        cls._notify_users(
            event_key="ticket_qc_fail_technician",
            user_ids=[ticket.technician_id],
            message=technician_message,
            reply_markup=technician_markup,
        )

    @classmethod
    def notify_manual_xp_adjustment(
        cls,
        *,
        target_user_id: int,
        actor_user_id: int | None,
        amount: int,
        comment: str,
    ) -> None:
        signed_amount = f"+{amount}" if amount > 0 else str(amount)
        message = "\n".join(
            [
                "Your XP was adjusted by admin.",
                f"Amount: {signed_amount}",
                f"By: {cls._display_name_by_user_id(actor_user_id)}",
                f"Comment: {comment}",
            ]
        )
        cls._notify_users(
            event_key="manual_xp_adjustment",
            user_ids=[target_user_id],
            message=message,
        )

    @classmethod
    def _notify_users(
        cls,
        *,
        event_key: str,
        user_ids: Iterable[int | None],
        message: str,
        exclude_user_ids: Iterable[int | None] | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> None:
        recipient_user_ids = cls._normalize_user_ids(
            user_ids=user_ids, exclude_user_ids=exclude_user_ids
        )
        if not recipient_user_ids:
            return

        telegram_ids = cls._telegram_ids_for_user_ids(recipient_user_ids)
        cls._notify_telegram_ids(
            event_key=event_key,
            telegram_ids=telegram_ids,
            message=message,
            reply_markup=reply_markup,
        )

    @classmethod
    def _notify_telegram_ids(
        cls,
        *,
        event_key: str,
        telegram_ids: Iterable[int],
        message: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> None:
        recipient_ids = sorted({int(tg_id) for tg_id in telegram_ids if tg_id})
        if not recipient_ids:
            return

        if getattr(settings, "IS_TEST_RUN", False):
            return

        bot_token = str(getattr(settings, "BOT_TOKEN", "")).strip()
        if not bot_token:
            logger.info("Skip %s notification: BOT_TOKEN is not configured.", event_key)
            return

        transaction.on_commit(
            lambda: cls._dispatch_telegram_messages(
                event_key=event_key,
                bot_token=bot_token,
                telegram_ids=recipient_ids,
                message=message,
                reply_markup=reply_markup,
            )
        )

    @classmethod
    def _dispatch_telegram_messages(
        cls,
        *,
        event_key: str,
        bot_token: str,
        telegram_ids: list[int],
        message: str,
        reply_markup: InlineKeyboardMarkup | None,
    ) -> None:
        try:
            async_to_sync(cls._send_telegram_messages)(
                event_key=event_key,
                bot_token=bot_token,
                telegram_ids=telegram_ids,
                message=message,
                reply_markup=reply_markup,
            )
        except Exception:
            logger.exception("Failed to dispatch %s notification.", event_key)

    @staticmethod
    async def _send_telegram_messages(
        *,
        event_key: str,
        bot_token: str,
        telegram_ids: list[int],
        message: str,
        reply_markup: InlineKeyboardMarkup | None,
    ) -> None:
        bot = Bot(token=bot_token)
        try:
            for telegram_id in telegram_ids:
                try:
                    await bot.send_message(
                        chat_id=telegram_id,
                        text=message,
                        reply_markup=reply_markup,
                    )
                except Exception:
                    logger.exception(
                        "Failed to send %s notification to telegram_id=%s.",
                        event_key,
                        telegram_id,
                    )
        finally:
            await bot.session.close()

    @staticmethod
    def _normalize_user_ids(
        *,
        user_ids: Iterable[int | None],
        exclude_user_ids: Iterable[int | None] | None,
    ) -> list[int]:
        excluded = {int(user_id) for user_id in (exclude_user_ids or []) if user_id}
        unique_ids = {int(user_id) for user_id in user_ids if user_id}
        resolved = unique_ids - excluded
        if not resolved:
            return []

        return list(
            User.objects.filter(id__in=resolved, is_active=True)
            .values_list("id", flat=True)
            .distinct()
        )

    @staticmethod
    def _telegram_ids_for_user_ids(user_ids: Iterable[int]) -> list[int]:
        resolved = [int(user_id) for user_id in user_ids if user_id]
        if not resolved:
            return []

        return list(
            TelegramProfile.objects.filter(user_id__in=resolved)
            .values_list("telegram_id", flat=True)
            .distinct()
        )

    @staticmethod
    def _user_ids_for_role_slugs(role_slugs: Iterable[str]) -> list[int]:
        normalized = [
            str(slug).strip()
            for slug in role_slugs
            if slug is not None and str(slug).strip()
        ]
        if not normalized:
            return []
        return list(
            User.objects.filter(roles__slug__in=normalized, is_active=True)
            .values_list("id", flat=True)
            .distinct()
        )

    @staticmethod
    def _display_name_by_user_id(user_id: int | None) -> str:
        if not user_id:
            return "Unknown user"
        user = (
            User.objects.filter(pk=user_id)
            .only("id", "first_name", "last_name", "username")
            .first()
        )
        if not user:
            return f"user#{user_id}"
        full_name = " ".join(
            part for part in [user.first_name, user.last_name] if part
        ).strip()
        if full_name:
            return full_name
        return user.username or f"user#{user.id}"

    @staticmethod
    def _serial_number(ticket: Ticket) -> str:
        inventory_item = getattr(ticket, "inventory_item", None)
        return getattr(inventory_item, "serial_number", "") or "unknown"
