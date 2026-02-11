from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from account.models import TelegramProfile, User
from account.services import (
    ensure_pending_access_request,
    get_pending_access_request,
    upsert_telegram_profile,
)
from core.utils.asyncio import run_sync

router = Router(name="start")


@router.message(CommandStart())
async def start_handler(
    message: Message, _, user: User = None, telegram_profile: TelegramProfile = None
):
    profile = telegram_profile or await run_sync(
        upsert_telegram_profile, message.from_user
    )

    if user:
        await message.answer(_("You are registered and linked."))
        return

    access_request, created = await run_sync(
        ensure_pending_access_request,
        telegram_id=profile.telegram_id if profile else message.from_user.id,
        username=profile.username if profile else message.from_user.username,
        first_name=profile.first_name if profile else message.from_user.first_name,
        last_name=profile.last_name if profile else message.from_user.last_name,
    )
    if created:
        await message.answer(
            _("Access request submitted. We will review and notify you.")
        )
    else:
        await message.answer(_("Your access request is already pending."))


@router.message(Command("help"))
async def help_handler(message: Message, _):
    help_text = "\n".join(
        [
            _("Available commands:"),
            "/start - " + _("Start bot"),
            "/my - " + _("Show my access status"),
            "/help - " + _("Show help"),
        ]
    )
    await message.answer(help_text)


@router.message(Command("my"))
async def my_handler(
    message: Message, _, user: User = None, telegram_profile: TelegramProfile = None
):

    if user:
        await message.answer(_("You are registered and linked."))
        return

    pending = await run_sync(get_pending_access_request, message.from_user.id)
    if pending:
        await message.answer(_("Your access request is pending."))
        return

    await message.answer(
        _("You are not registered. Use /start to submit access request.")
    )
