from __future__ import annotations

import logging
from collections.abc import Iterable
from html import escape
from typing import TYPE_CHECKING, Callable

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from asgiref.sync import async_to_sync, sync_to_async
from django.conf import settings
from django.db import transaction
from django.utils import translation
from django.utils.translation import gettext_noop

from account.models import AccessRequest, TelegramProfile, User
from bot.etc.i18n import normalize_bot_locale
from bot.services.technician_ticket_actions import TechnicianTicketActionService
from bot.services.ticket_qc_actions import TicketQCActionService
from core.utils.constants import RoleSlug, TicketStatus

if TYPE_CHECKING:
    from ticket.models import Ticket

logger = logging.getLogger(__name__)

Translator = Callable[[str], str]
LocalizedMessage = str | Callable[[Translator], str]
LocalizedReplyMarkup = (
    InlineKeyboardMarkup | Callable[[Translator], InlineKeyboardMarkup | None] | None
)


class UserNotificationService:
    """Best-effort user-facing Telegram notifications for domain events."""

    @classmethod
    def notify_access_request_decision(
        cls, *, access_request: AccessRequest, approved: bool
    ) -> None:
        greeting_name = cls._safe_text(access_request.first_name or "there")

        def message_builder(_: Translator) -> str:
            if approved:
                return "\n".join(
                    [
                        _("✅ <b>Access Request Approved</b>"),
                        _("Hi, <b>%(name)s</b>.") % {"name": greeting_name},
                        _("You can now use <b>Rent Market</b>."),
                    ]
                )
            return "\n".join(
                [
                    _("❌ <b>Access Request Rejected</b>"),
                    _("Hi, <b>%(name)s</b>.") % {"name": greeting_name},
                    _("You can submit a new request using <code>/start</code>."),
                ]
            )

        cls._notify_telegram_ids(
            event_key="access_request_decision",
            telegram_ids=[access_request.telegram_id],
            message=message_builder,
        )

    @classmethod
    def notify_ticket_assigned(
        cls, *, ticket: Ticket, actor_user_id: int | None
    ) -> None:
        if not ticket.technician_id:
            return

        def master_message_builder(_: Translator) -> str:
            return "\n".join(
                [
                    _("📌 <b>Ticket Assigned</b>"),
                    _("🎫 <b>Ticket:</b> #%(ticket_id)s") % {"ticket_id": ticket.id},
                    _("🔢 <b>Serial:</b> <code>%(value)s</code>")
                    % {"value": cls._safe_text(cls._serial_number(ticket=ticket, _=_))},
                    _("👤 <b>Technician:</b> %(value)s")
                    % {
                        "value": cls._safe_text(
                            cls._display_name_by_user_id(ticket.technician_id, _=_)
                        )
                    },
                    _("🛠 <b>Assigned by:</b> %(value)s")
                    % {
                        "value": cls._safe_text(
                            cls._display_name_by_user_id(actor_user_id, _=_)
                        )
                    },
                    _("📍 <b>Status:</b> <code>%(value)s</code>")
                    % {
                        "value": cls._safe_text(
                            cls._ticket_status_label(ticket.status, _=_)
                        )
                    },
                ]
            )

        cls._notify_users(
            event_key="ticket_assigned_master",
            user_ids=[ticket.master_id],
            message=master_message_builder,
            exclude_user_ids=[actor_user_id],
        )

        technician_state = None
        try:
            technician_state = TechnicianTicketActionService.state_for_ticket(
                ticket=ticket,
                technician_id=ticket.technician_id,
            )
        except Exception:
            logger.exception(
                (
                    "Failed to build technician state for assigned ticket "
                    "notification: ticket_id=%s technician_id=%s"
                ),
                ticket.id,
                ticket.technician_id,
            )

        def technician_message_builder(_: Translator) -> str:
            assignment_meta_line = _("🛠 <b>Assigned by:</b> %(value)s") % {
                "value": cls._safe_text(
                    cls._display_name_by_user_id(actor_user_id, _=_)
                )
            }
            if technician_state is None:
                return "\n".join(
                    [
                        _("🆕 <b>New ticket assigned to you</b>"),
                        _("🎫 <b>Ticket:</b> #%(ticket_id)s")
                        % {"ticket_id": ticket.id},
                        _("🔢 <b>Serial:</b> <code>%(value)s</code>")
                        % {
                            "value": cls._safe_text(
                                cls._serial_number(ticket=ticket, _=_)
                            )
                        },
                        assignment_meta_line,
                    ]
                )
            return "\n".join(
                [
                    TechnicianTicketActionService.render_state_message(
                        state=technician_state,
                        heading=_("🆕 <b>New ticket assigned to you</b>"),
                        _=_,
                    ),
                    assignment_meta_line,
                ]
            )

        def technician_markup_builder(_: Translator) -> InlineKeyboardMarkup | None:
            if technician_state is None:
                return None
            return TechnicianTicketActionService.build_action_keyboard(
                ticket_id=ticket.id,
                actions=technician_state.actions,
                _=_,
            )

        cls._notify_users(
            event_key="ticket_assigned_technician",
            user_ids=[ticket.technician_id],
            message=technician_message_builder,
            reply_markup=technician_markup_builder,
        )

    @classmethod
    def notify_ticket_started(
        cls, *, ticket: Ticket, actor_user_id: int | None
    ) -> None:
        if not ticket.technician_id:
            return

        def message_builder(_: Translator) -> str:
            return "\n".join(
                [
                    _("▶️ <b>Ticket Work Started</b>"),
                    _("🎫 <b>Ticket:</b> #%(ticket_id)s") % {"ticket_id": ticket.id},
                    _("🔢 <b>Serial:</b> <code>%(value)s</code>")
                    % {"value": cls._safe_text(cls._serial_number(ticket=ticket, _=_))},
                    _("👤 <b>Technician:</b> %(value)s")
                    % {
                        "value": cls._safe_text(
                            cls._display_name_by_user_id(ticket.technician_id, _=_)
                        )
                    },
                    _("🛠 <b>Started by:</b> %(value)s")
                    % {
                        "value": cls._safe_text(
                            cls._display_name_by_user_id(actor_user_id, _=_)
                        )
                    },
                    _("📍 <b>Status:</b> <code>%(value)s</code>")
                    % {
                        "value": cls._safe_text(
                            cls._ticket_status_label(ticket.status, _=_)
                        )
                    },
                ]
            )

        cls._notify_users(
            event_key="ticket_started_technician",
            user_ids=[ticket.technician_id],
            message=message_builder,
            exclude_user_ids=[actor_user_id],
        )

    @classmethod
    def notify_ticket_waiting_qc(
        cls, *, ticket: Ticket, actor_user_id: int | None
    ) -> None:
        qc_user_ids = cls._user_ids_for_role_slugs(
            [RoleSlug.QC_INSPECTOR, RoleSlug.SUPER_ADMIN]
        )

        def qc_message_builder(_: Translator) -> str:
            return "\n".join(
                [
                    _("🧪 <b>Ticket Waiting For QC</b>"),
                    _("🎫 <b>Ticket:</b> #%(ticket_id)s") % {"ticket_id": ticket.id},
                    _("🔢 <b>Serial:</b> <code>%(value)s</code>")
                    % {"value": cls._safe_text(cls._serial_number(ticket=ticket, _=_))},
                    _("👤 <b>Technician:</b> %(value)s")
                    % {
                        "value": cls._safe_text(
                            cls._display_name_by_user_id(ticket.technician_id, _=_)
                        )
                    },
                    _("🛠 <b>Moved by:</b> %(value)s")
                    % {
                        "value": cls._safe_text(
                            cls._display_name_by_user_id(actor_user_id, _=_)
                        )
                    },
                    _("📍 <b>Status:</b> <code>%(value)s</code>")
                    % {
                        "value": cls._safe_text(
                            cls._ticket_status_label(ticket.status, _=_)
                        )
                    },
                    _("👇 <b>Action:</b> choose a QC decision using buttons below."),
                ]
            )

        def qc_markup_builder(_: Translator) -> InlineKeyboardMarkup | None:
            return TicketQCActionService.build_action_keyboard(
                ticket_id=ticket.id,
                ticket_status=ticket.status,
                _=_,
            )

        cls._notify_users(
            event_key="ticket_waiting_qc_reviewers",
            user_ids=qc_user_ids,
            message=qc_message_builder,
            exclude_user_ids=[actor_user_id],
            reply_markup=qc_markup_builder,
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
        def message_builder(_: Translator) -> str:
            xp_summary = (
                _("⭐ <b>XP awarded:</b> base=%(base)s")
                % {"base": cls._safe_text(base_xp)}
            )
            if first_pass_bonus > 0:
                xp_summary = (
                    _("⭐ <b>XP awarded:</b> base=%(base)s, first-pass bonus=%(bonus)s")
                    % {
                        "base": cls._safe_text(base_xp),
                        "bonus": cls._safe_text(first_pass_bonus),
                    }
                )

            return "\n".join(
                [
                    _("✅ <b>Ticket Passed QC</b>"),
                    _("🎫 <b>Ticket:</b> #%(ticket_id)s") % {"ticket_id": ticket.id},
                    _("🔢 <b>Serial:</b> <code>%(value)s</code>")
                    % {"value": cls._safe_text(cls._serial_number(ticket=ticket, _=_))},
                    _("👤 <b>Technician:</b> %(value)s")
                    % {
                        "value": cls._safe_text(
                            cls._display_name_by_user_id(ticket.technician_id, _=_)
                        )
                    },
                    _("🧪 <b>QC by:</b> %(value)s")
                    % {
                        "value": cls._safe_text(
                            cls._display_name_by_user_id(actor_user_id, _=_)
                        )
                    },
                    _("📍 <b>Status:</b> <code>%(value)s</code>")
                    % {
                        "value": cls._safe_text(
                            cls._ticket_status_label(ticket.status, _=_)
                        )
                    },
                    xp_summary,
                ]
            )

        cls._notify_users(
            event_key="ticket_qc_pass",
            user_ids=[ticket.technician_id],
            message=message_builder,
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
        def technician_message_builder(_: Translator) -> str:
            return "\n".join(
                [
                    TechnicianTicketActionService.render_state_message(
                        state=technician_state,
                        heading=_("❌ <b>Returned from QC</b>"),
                        _=_,
                    ),
                    _("🧪 <b>QC by:</b> %(value)s")
                    % {
                        "value": cls._safe_text(
                            cls._display_name_by_user_id(actor_user_id, _=_)
                        )
                    },
                ]
            )

        def technician_markup_builder(_: Translator) -> InlineKeyboardMarkup | None:
            return TechnicianTicketActionService.build_action_keyboard(
                ticket_id=ticket.id,
                actions=technician_state.actions,
                _=_,
            )

        cls._notify_users(
            event_key="ticket_qc_fail_technician",
            user_ids=[ticket.technician_id],
            message=technician_message_builder,
            reply_markup=technician_markup_builder,
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

        def message_builder(_: Translator) -> str:
            return "\n".join(
                [
                    _("⭐ <b>XP Adjustment Applied</b>"),
                    _("📈 <b>Amount:</b> <code>%(value)s</code>")
                    % {"value": cls._safe_text(signed_amount)},
                    _("👤 <b>By:</b> %(value)s")
                    % {
                        "value": cls._safe_text(
                            cls._display_name_by_user_id(actor_user_id, _=_)
                        )
                    },
                    _("💬 <b>Comment:</b> %(value)s")
                    % {"value": cls._safe_text(comment or "-")},
                ]
            )

        cls._notify_users(
            event_key="manual_xp_adjustment",
            user_ids=[target_user_id],
            message=message_builder,
        )

    @classmethod
    def notify_manual_level_update(
        cls,
        *,
        target_user_id: int,
        actor_user_id: int | None,
        previous_level: int,
        new_level: int,
        warning_active_before: bool,
        warning_active_after: bool,
        note: str,
    ) -> None:
        def message_builder(_: Translator) -> str:
            warning_label = cls._manual_warning_label(
                warning_active_before=warning_active_before,
                warning_active_after=warning_active_after,
                _=_,
            )
            level_label = cls._manual_level_label(
                previous_level=previous_level,
                new_level=new_level,
                _=_,
            )
            return "\n".join(
                [
                    _("🎚 <b>Level Update Applied</b>"),
                    _("📊 <b>Level:</b> <code>L%(previous)s → L%(new)s</code> (%(label)s)")
                    % {
                        "previous": previous_level,
                        "new": new_level,
                        "label": cls._safe_text(level_label),
                    },
                    _("⚠️ <b>Warning week:</b> %(value)s")
                    % {"value": cls._safe_text(warning_label)},
                    _("👤 <b>By:</b> %(value)s")
                    % {
                        "value": cls._safe_text(
                            cls._display_name_by_user_id(actor_user_id, _=_)
                        )
                    },
                    _("💬 <b>Comment:</b> %(value)s")
                    % {"value": cls._safe_text(note or "-")},
                ]
            )

        cls._notify_users(
            event_key="manual_level_update",
            user_ids=[target_user_id],
            message=message_builder,
        )

    @classmethod
    def _notify_users(
        cls,
        *,
        event_key: str,
        user_ids: Iterable[int | None],
        message: LocalizedMessage,
        exclude_user_ids: Iterable[int | None] | None = None,
        reply_markup: LocalizedReplyMarkup = None,
    ) -> None:
        recipient_user_ids = cls._normalize_user_ids(
            user_ids=user_ids, exclude_user_ids=exclude_user_ids
        )
        if not recipient_user_ids:
            return

        telegram_ids = cls._telegram_ids_for_user_ids(recipient_user_ids)
        if not telegram_ids:
            logger.info(
                "Skip %s notification: no telegram ids resolved for users=%s.",
                event_key,
                recipient_user_ids,
            )
            return
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
        message: LocalizedMessage,
        reply_markup: LocalizedReplyMarkup = None,
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
        message: LocalizedMessage,
        reply_markup: LocalizedReplyMarkup,
    ) -> None:
        try:
            locale_by_telegram_id = cls._locale_map_for_telegram_ids(
                telegram_ids=telegram_ids
            )
            async_to_sync(cls._send_telegram_messages)(
                event_key=event_key,
                bot_token=bot_token,
                telegram_ids=telegram_ids,
                locale_by_telegram_id=locale_by_telegram_id,
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
        locale_by_telegram_id: dict[int, str],
        message: LocalizedMessage,
        reply_markup: LocalizedReplyMarkup,
    ) -> None:
        bot = Bot(token=bot_token)
        try:
            for telegram_id in telegram_ids:
                try:
                    locale = locale_by_telegram_id.get(
                        int(telegram_id),
                        normalize_bot_locale(locale=None),
                    )
                    resolved_message, resolved_reply_markup = await sync_to_async(
                        cls._resolve_localized_payload,
                        thread_sensitive=True,
                    )(
                        locale=locale,
                        message=message,
                        reply_markup=reply_markup,
                    )
                    await bot.send_message(
                        chat_id=telegram_id,
                        text=resolved_message,
                        reply_markup=resolved_reply_markup,
                        parse_mode=getattr(settings, "BOT_PARSE_MODE", "HTML"),
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
    def _resolve_localized_payload(
        *,
        locale: str,
        message: LocalizedMessage,
        reply_markup: LocalizedReplyMarkup,
    ) -> tuple[str, InlineKeyboardMarkup | None]:
        with translation.override(locale):
            translator = translation.gettext
            resolved_message = message(translator) if callable(message) else message
            resolved_reply_markup = (
                reply_markup(translator) if callable(reply_markup) else reply_markup
            )
        return str(resolved_message), resolved_reply_markup

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

        profile_rows = list(
            TelegramProfile.objects.filter(user_id__in=resolved).values_list(
                "user_id",
                "telegram_id",
            )
        )
        telegram_ids = {
            int(telegram_id) for _, telegram_id in profile_rows if telegram_id
        }
        covered_user_ids = {int(user_id) for user_id, _ in profile_rows if user_id}

        missing_user_ids = [
            user_id for user_id in resolved if user_id not in covered_user_ids
        ]
        if not missing_user_ids:
            return sorted(telegram_ids)

        fallback_rows = AccessRequest.all_objects.filter(
            user_id__in=missing_user_ids,
        ).exclude(telegram_id__isnull=True)
        matched_user_ids: set[int] = set()
        for row in fallback_rows.values("user_id", "telegram_id").order_by(
            "user_id",
            "-resolved_at",
            "-created_at",
            "-id",
        ):
            user_id = row.get("user_id")
            if not user_id:
                continue
            normalized_user_id = int(user_id)
            if normalized_user_id in matched_user_ids:
                continue
            telegram_id = row.get("telegram_id")
            if telegram_id:
                telegram_ids.add(int(telegram_id))
                matched_user_ids.add(normalized_user_id)

        return sorted(telegram_ids)

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

    @classmethod
    def _display_name_by_user_id(cls, user_id: int | None, _=None) -> str:
        translator = _ or translation.gettext
        if not user_id:
            return translator(gettext_noop("Unknown user"))
        user = (
            User.objects.filter(pk=user_id)
            .only("id", "first_name", "last_name", "username")
            .first()
        )
        if not user:
            return translator(gettext_noop("user#%(user_id)s")) % {"user_id": user_id}
        full_name = " ".join(
            part for part in [user.first_name, user.last_name] if part
        ).strip()
        if full_name:
            return full_name
        return user.username or translator(gettext_noop("user#%(user_id)s")) % {
            "user_id": user.id
        }

    @classmethod
    def _serial_number(cls, *, ticket: Ticket, _=None) -> str:
        translator = _ or translation.gettext
        inventory_item = getattr(ticket, "inventory_item", None)
        return getattr(inventory_item, "serial_number", "") or translator(
            gettext_noop("unknown")
        )

    @staticmethod
    def _ticket_status_label(status: str, _=None) -> str:
        translator = _ or translation.gettext
        labels = {
            TicketStatus.UNDER_REVIEW: gettext_noop("Under review"),
            TicketStatus.NEW: gettext_noop("New"),
            TicketStatus.ASSIGNED: gettext_noop("Assigned"),
            TicketStatus.IN_PROGRESS: gettext_noop("In progress"),
            TicketStatus.WAITING_QC: gettext_noop("Waiting QC"),
            TicketStatus.REWORK: gettext_noop("Rework"),
            TicketStatus.DONE: gettext_noop("Done"),
        }
        return translator(labels.get(status, str(status)))

    @staticmethod
    def _safe_text(value: object) -> str:
        return escape(str(value if value is not None else "-"), quote=False)

    @staticmethod
    def _manual_warning_label(
        *,
        warning_active_before: bool,
        warning_active_after: bool,
        _=None,
    ) -> str:
        translator = _ or translation.gettext
        if not warning_active_before and warning_active_after:
            return translator(gettext_noop("added"))
        if warning_active_before and not warning_active_after:
            return translator(gettext_noop("removed"))
        return (
            translator(gettext_noop("active"))
            if warning_active_after
            else translator(gettext_noop("not active"))
        )

    @staticmethod
    def _manual_level_label(*, previous_level: int, new_level: int, _=None) -> str:
        translator = _ or translation.gettext
        if new_level > previous_level:
            return translator(gettext_noop("level up"))
        if new_level < previous_level:
            return translator(gettext_noop("level down"))
        return translator(gettext_noop("unchanged"))

    @staticmethod
    def _locale_map_for_telegram_ids(*, telegram_ids: list[int]) -> dict[int, str]:
        resolved_ids = [int(telegram_id) for telegram_id in telegram_ids if telegram_id]
        if not resolved_ids:
            return {}

        rows = TelegramProfile.objects.filter(telegram_id__in=resolved_ids).values_list(
            "telegram_id",
            "language_code",
        )
        locale_by_telegram_id = {
            int(telegram_id): normalize_bot_locale(locale=language_code)
            for telegram_id, language_code in rows
        }
        fallback_locale = normalize_bot_locale(locale=None)
        for telegram_id in resolved_ids:
            locale_by_telegram_id.setdefault(telegram_id, fallback_locale)
        return locale_by_telegram_id
