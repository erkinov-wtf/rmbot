from __future__ import annotations

from html import escape

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from django.db.models import Count, Sum
from django.utils import timezone

from account.models import TelegramProfile, User
from bot.services.menu import BotMenuService
from core.utils.asyncio import run_sync
from core.utils.constants import RoleSlug, TicketStatus
from gamification.models import XPTransaction
from ticket.models import Ticket


class StartProfileService:
    @staticmethod
    async def ticket_status_counts_for_technician(
        *, technician_id: int
    ) -> dict[str, int]:
        queryset = (
            Ticket.domain.filter(technician_id=technician_id)
            .values("status")
            .annotate(total=Count("id"))
        )
        rows = await run_sync(list, queryset)
        return {str(item["status"]): int(item["total"] or 0) for item in rows}

    @staticmethod
    async def has_active_linked_user(
        user: User | None,
        telegram_profile: TelegramProfile | None,
    ) -> bool:
        if user and user.is_active:
            return True

        profile_user_id = telegram_profile.user_id if telegram_profile else None
        if not profile_user_id:
            return False

        return await run_sync(
            User.all_objects.filter(pk=profile_user_id, is_active=True).exists
        )

    @staticmethod
    def format_status_datetime(value) -> str:
        if value is None:
            return "-"
        return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")

    @staticmethod
    async def resolve_active_user_for_status(
        *,
        user: User | None,
        telegram_profile: TelegramProfile | None,
    ) -> User | None:
        if user and user.is_active:
            return user

        profile_user_id = telegram_profile.user_id if telegram_profile else None
        if not profile_user_id:
            return None

        return await run_sync(
            User.all_objects.prefetch_related("roles")
            .filter(pk=profile_user_id, is_active=True)
            .first
        )

    @staticmethod
    async def active_role_slugs(*, user: User) -> list[str]:
        return await run_sync(
            list,
            user.roles.filter(deleted_at__isnull=True).values_list("slug", flat=True),
        )

    @classmethod
    async def active_ticket_count_for_technician(cls, *, technician_id: int) -> int:
        status_counts = await cls.ticket_status_counts_for_technician(
            technician_id=technician_id
        )
        return (
            status_counts.get(TicketStatus.ASSIGNED, 0)
            + status_counts.get(TicketStatus.REWORK, 0)
            + status_counts.get(TicketStatus.IN_PROGRESS, 0)
        )

    @staticmethod
    async def xp_totals_for_user(*, user_id: int) -> tuple[int, int]:
        aggregate = await run_sync(
            XPTransaction.objects.filter(user_id=user_id).aggregate,
            total_xp=Sum("amount"),
            tx_count=Count("id"),
        )
        return int(aggregate.get("total_xp") or 0), int(aggregate.get("tx_count") or 0)

    @staticmethod
    def role_label(*, role_slug: str, _) -> str:
        try:
            return str(RoleSlug(role_slug).label)
        except ValueError:
            pass
        return role_slug.replace("_", " ").replace("-", " ").title()

    @classmethod
    async def build_active_status_text(
        cls,
        *,
        user: User,
        _,
    ) -> str:
        role_slugs = await cls.active_role_slugs(user=user)
        resolved_roles = [
            cls.role_label(role_slug=role_slug, _=_) for role_slug in role_slugs
        ]
        role_title = _("Roles") if len(resolved_roles) > 1 else _("Role")
        full_name = (
            " ".join(part for part in [user.first_name, user.last_name] if part) or "-"
        )
        role_value = (
            ", ".join(resolved_roles) if resolved_roles else _("No role assigned yet")
        )
        username_value = f"@{user.username}" if user.username else "-"
        lines = [
            _("👤 <b>My Profile</b>"),
            _("🟢 <b>Access:</b> active"),
            "",
            _("🧾 <b>Identity</b>"),
            _("• <b>Name:</b> %(value)s") % {"value": escape(full_name)},
            _("• <b>Username:</b> %(value)s") % {"value": escape(username_value)},
            _("• <b>Phone:</b> <code>%(value)s</code>")
            % {"value": escape(user.phone or "-")},
            "",
            _("🏅 <b>Work Profile</b>"),
            _("• <b>Level:</b> %(value)s")
            % {"value": escape(user.get_level_display())},
            _("• <b>%(label)s:</b> %(value)s")
            % {
                "label": escape(role_title),
                "value": escape(role_value),
            },
        ]
        total_xp, tx_count = await cls.xp_totals_for_user(user_id=user.id)
        lines.append(
            _("• <b>XP:</b> %(xp)s points (%(updates)s updates)")
            % {"xp": total_xp, "updates": tx_count}
        )
        if RoleSlug.TECHNICIAN in role_slugs:
            status_counts = await cls.ticket_status_counts_for_technician(
                technician_id=user.id
            )
            active_ticket_count = await cls.active_ticket_count_for_technician(
                technician_id=user.id
            )
            lines.extend(["", _("🛠 <b>Technician Stats</b>")])
            lines.append(
                _("• <b>Open tickets:</b> %(count)s") % {"count": active_ticket_count}
            )
            lines.append(
                _("• <b>Waiting for quality check:</b> %(count)s")
                % {"count": status_counts.get(TicketStatus.WAITING_QC, 0)}
            )
            lines.append(
                _("• <b>Completed tickets:</b> %(count)s")
                % {"count": status_counts.get(TicketStatus.DONE, 0)}
            )
        return "\n".join(lines)

    @classmethod
    def build_pending_status_text(cls, *, pending, _) -> str:
        del cls
        full_name = (
            " ".join(part for part in [pending.first_name, pending.last_name] if part)
            or "-"
        )
        lines = [
            _("📨 <b>Access Request</b>"),
            _("🟡 <b>Status:</b> under review"),
            _("• <b>Name:</b> %(value)s") % {"value": escape(full_name)},
            _("• <b>Phone:</b> <code>%(value)s</code>")
            % {"value": escape(pending.phone or "-")},
            _("• <b>Submitted:</b> %(value)s")
            % {
                "value": escape(
                    StartProfileService.format_status_datetime(pending.created_at)
                )
            },
            _("ℹ️ We will notify you here after review."),
        ]
        return "\n".join(lines)

    @classmethod
    async def resolve_registered_user(
        cls,
        *,
        user: User | None,
        telegram_profile: TelegramProfile | None,
    ) -> User | None:
        return await cls.resolve_active_user_for_status(
            user=user,
            telegram_profile=telegram_profile,
        )

    @staticmethod
    async def reply_not_registered(
        *,
        message: Message,
        _,
    ) -> None:
        await message.answer(
            _(
                "🚫 <b>No access yet</b>\nSend <code>/start</code> or tap the button below."
            ),
            reply_markup=BotMenuService.build_main_menu_keyboard(
                is_technician=False,
                include_start_access=True,
                _=_,
            ),
        )

    @staticmethod
    async def reply_not_registered_callback(
        *,
        query: CallbackQuery,
        _,
    ) -> None:
        await query.answer(
            _("🚫 No access yet. Send /start first."),
            show_alert=True,
        )
        if query.message is None:
            return
        await query.message.answer(
            _(
                "📝 <b>Open Access Request</b>\nUse <code>/start</code> or tap the button below."
            ),
            reply_markup=BotMenuService.build_main_menu_keyboard(
                is_technician=False,
                include_start_access=True,
                _=_,
            ),
        )

    @staticmethod
    async def safe_edit_callback_message(
        *,
        query: CallbackQuery,
        text: str,
        reply_markup: InlineKeyboardMarkup | None,
    ) -> None:
        message = query.message
        edit_text = getattr(message, "edit_text", None)
        if edit_text is None:
            return
        try:
            await edit_text(text=text, reply_markup=reply_markup)
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                return
            raise


class StartXPService:
    CALLBACK_PREFIX = "xph"
    DEFAULT_LIMIT = 5
    MAX_LIMIT = 30

    @staticmethod
    def format_entry_created_at(created_at) -> str:
        return timezone.localtime(created_at).strftime("%Y-%m-%d %H:%M")

    @classmethod
    def normalize_limit(cls, limit: int) -> int:
        try:
            normalized_limit = int(limit)
        except (TypeError, ValueError):
            normalized_limit = cls.DEFAULT_LIMIT
        return min(max(1, normalized_limit), cls.MAX_LIMIT)

    @staticmethod
    def normalize_offset(offset: int) -> int:
        try:
            normalized_offset = int(offset)
        except (TypeError, ValueError):
            return 0
        return max(0, normalized_offset)

    @staticmethod
    def friendly_xp_description(*, entry: XPTransaction, _) -> str:
        description = str(getattr(entry, "description", "") or "").strip()
        description_map = {
            "Attendance punctuality XP": _("On-time attendance reward"),
            "Ticket completion base XP": _("Reward for completing a ticket"),
            "Ticket QC first-pass bonus XP": _("Quality check first-pass bonus"),
            "QC status update XP": _("Quality check update"),
            "Manual XP adjustment": _("Manual XP update"),
            "Weekly level-up coupon": _("Weekly level-up bonus"),
        }
        if description:
            return description_map.get(description, description)

        entry_type_display = getattr(entry, "get_entry_type_display", None)
        if callable(entry_type_display):
            resolved_display = str(entry_type_display() or "").strip()
            if resolved_display:
                return resolved_display

        raw_entry_type = str(getattr(entry, "entry_type", "") or "").strip()
        if raw_entry_type:
            return raw_entry_type.replace("_", " ").replace("-", " ").title()
        return _("XP update")

    @staticmethod
    async def xp_history_count_for_user(*, user_id: int) -> int:
        return int(await run_sync(XPTransaction.objects.filter(user_id=user_id).count))

    @classmethod
    async def xp_history_for_user(
        cls,
        *,
        user_id: int,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> list[XPTransaction]:
        normalized_limit = cls.normalize_limit(limit)
        normalized_offset = cls.normalize_offset(offset)
        queryset = XPTransaction.objects.filter(user_id=user_id).order_by(
            "-created_at", "-id"
        )
        return await run_sync(
            list,
            queryset[normalized_offset : normalized_offset + normalized_limit],
        )

    @classmethod
    async def build_summary_text(cls, *, user: User, _) -> str:
        total_xp, tx_count = await StartProfileService.xp_totals_for_user(
            user_id=user.id
        )
        recent_entries = await cls.xp_history_for_user(user_id=user.id, limit=5)

        lines = [
            _("⭐ <b>XP Summary</b>"),
            _("• <b>Total XP:</b> %(value)s") % {"value": total_xp},
            _("• <b>Updates:</b> %(value)s") % {"value": tx_count},
        ]
        if not recent_entries:
            lines.append(_("ℹ️ No XP activity yet."))
            return "\n".join(lines)

        lines.extend(["", _("🕒 <b>Latest updates</b>")])
        for entry in recent_entries:
            amount = int(entry.amount or 0)
            sign = "+" if amount >= 0 else ""
            timestamp = cls.format_entry_created_at(entry.created_at)
            description = cls.friendly_xp_description(entry=entry, _=_)
            lines.append(
                _("• <code>%(time)s</code> — <b>%(amount)s XP</b> — %(description)s")
                % {
                    "time": escape(timestamp),
                    "amount": escape(f"{sign}{amount}"),
                    "description": escape(description),
                }
            )
        return "\n".join(lines)

    @classmethod
    def build_history_callback_data(cls, *, limit: int, offset: int) -> str:
        return f"{cls.CALLBACK_PREFIX}:{cls.normalize_limit(limit)}:{cls.normalize_offset(offset)}"

    @classmethod
    def parse_history_callback_data(
        cls,
        *,
        callback_data: str,
    ) -> tuple[int, int] | None:
        raw_parts = callback_data.split(":")
        if len(raw_parts) != 3:
            return None
        if raw_parts[0] != cls.CALLBACK_PREFIX:
            return None

        try:
            limit = int(raw_parts[1])
            offset = int(raw_parts[2])
        except ValueError:
            return None

        if limit < 1 or offset < 0:
            return None
        return cls.normalize_limit(limit), cls.normalize_offset(offset)

    @classmethod
    def resolve_safe_history_offset(
        cls,
        *,
        total_count: int,
        limit: int,
        offset: int,
    ) -> int:
        if total_count <= 0:
            return 0
        normalized_limit = cls.normalize_limit(limit)
        normalized_offset = cls.normalize_offset(offset)
        max_offset = ((total_count - 1) // normalized_limit) * normalized_limit
        return min(normalized_offset, max_offset)

    @classmethod
    def build_history_pagination_markup(
        cls,
        *,
        total_count: int,
        limit: int,
        offset: int,
        _,
    ) -> InlineKeyboardMarkup | None:
        del _
        if total_count <= 0:
            return None

        normalized_limit = cls.normalize_limit(limit)
        safe_offset = cls.resolve_safe_history_offset(
            total_count=total_count,
            limit=normalized_limit,
            offset=offset,
        )

        page = (safe_offset // normalized_limit) + 1
        page_count = ((total_count - 1) // normalized_limit) + 1
        max_offset = ((total_count - 1) // normalized_limit) * normalized_limit
        prev_offset = max(0, safe_offset - normalized_limit)
        next_offset = min(max_offset, safe_offset + normalized_limit)

        navigation_row = [
            InlineKeyboardButton(
                text="<",
                callback_data=cls.build_history_callback_data(
                    limit=normalized_limit,
                    offset=prev_offset,
                ),
            ),
            InlineKeyboardButton(
                text=f"{page}/{page_count}",
                callback_data=cls.build_history_callback_data(
                    limit=normalized_limit,
                    offset=safe_offset,
                ),
            ),
            InlineKeyboardButton(
                text=">",
                callback_data=cls.build_history_callback_data(
                    limit=normalized_limit,
                    offset=next_offset,
                ),
            ),
        ]
        return InlineKeyboardMarkup(inline_keyboard=[navigation_row])

    @classmethod
    async def build_history_text(
        cls,
        *,
        user: User,
        _,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> tuple[str, int, int, int]:
        normalized_limit = cls.normalize_limit(limit)
        total_count = await cls.xp_history_count_for_user(user_id=user.id)
        safe_offset = cls.resolve_safe_history_offset(
            total_count=total_count,
            limit=normalized_limit,
            offset=offset,
        )

        lines = [_("📜 <b>XP Activity</b>")]
        if total_count <= 0:
            lines.append(_("ℹ️ No XP activity yet."))
            return "\n".join(lines), total_count, normalized_limit, safe_offset

        entries = await cls.xp_history_for_user(
            user_id=user.id,
            limit=normalized_limit,
            offset=safe_offset,
        )
        start_item = safe_offset + 1
        end_item = safe_offset + len(entries)
        lines.append(
            _("• <b>Showing:</b> %(start)s-%(end)s / %(total)s")
            % {"start": start_item, "end": end_item, "total": total_count}
        )

        for entry in entries:
            amount = int(entry.amount or 0)
            sign = "+" if amount >= 0 else ""
            timestamp = cls.format_entry_created_at(entry.created_at)
            description = cls.friendly_xp_description(entry=entry, _=_)
            lines.append(
                _("• <code>%(time)s</code> — <b>%(amount)s XP</b> — %(description)s")
                % {
                    "time": escape(timestamp),
                    "amount": escape(f"{sign}{amount}"),
                    "description": escape(description),
                }
            )
        return "\n".join(lines), total_count, normalized_limit, safe_offset

    @classmethod
    async def reply_xp_summary(
        cls,
        *,
        message: Message,
        user: User | None,
        telegram_profile: TelegramProfile | None,
        _,
    ) -> None:
        resolved_user = await StartProfileService.resolve_registered_user(
            user=user,
            telegram_profile=telegram_profile,
        )
        if resolved_user is None:
            await StartProfileService.reply_not_registered(message=message, _=_)
            return
        await message.answer(
            await cls.build_summary_text(user=resolved_user, _=_),
            reply_markup=await BotMenuService.main_menu_markup_for_user(
                user=resolved_user,
                _=_,
            ),
        )

    @classmethod
    async def reply_xp_history(
        cls,
        *,
        message: Message,
        user: User | None,
        telegram_profile: TelegramProfile | None,
        _,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> None:
        resolved_user = await StartProfileService.resolve_registered_user(
            user=user,
            telegram_profile=telegram_profile,
        )
        if resolved_user is None:
            await StartProfileService.reply_not_registered(message=message, _=_)
            return

        text, total_count, normalized_limit, safe_offset = await cls.build_history_text(
            user=resolved_user,
            _=_,
            limit=limit,
            offset=offset,
        )
        await message.answer(
            text,
            reply_markup=cls.build_history_pagination_markup(
                total_count=total_count,
                limit=normalized_limit,
                offset=safe_offset,
                _=_,
            ),
        )


XP_HISTORY_CALLBACK_PREFIX = StartXPService.CALLBACK_PREFIX
XP_HISTORY_DEFAULT_LIMIT = StartXPService.DEFAULT_LIMIT
XP_HISTORY_MAX_LIMIT = StartXPService.MAX_LIMIT
