import re

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from account.models import TelegramProfile, User
from account.services import AccountService
from core.utils.asyncio import run_sync

router = Router(name="start")
PHONE_PATTERN = re.compile(r"^\+?[1-9][0-9]{7,14}$")


class AccessRequestForm(StatesGroup):
    first_name = State()
    last_name = State()
    patronymic = State()
    phone = State()


def _normalize_phone(raw: str) -> str | None:
    compact = raw.strip().replace(" ", "").replace("-", "")
    if not compact:
        return None
    if not PHONE_PATTERN.fullmatch(compact):
        return None
    return compact if compact.startswith("+") else f"+{compact}"


def _phone_keyboard(_) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text=_("Share phone number"),
                    request_contact=True,
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
        selective=True,
    )


async def _has_active_linked_user(
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


@router.message(CommandStart())
async def start_handler(
    message: Message,
    state: FSMContext,
    _,
    user: User = None,
    telegram_profile: TelegramProfile = None,
):
    profile = telegram_profile or await run_sync(
        AccountService.upsert_telegram_profile, message.from_user
    )

    pending = await run_sync(
        AccountService.get_pending_access_request,
        profile.telegram_id if profile else message.from_user.id,
    )
    if pending:
        await state.clear()
        await message.answer(_("Your access request is already pending."))
        return

    if await _has_active_linked_user(user, profile):
        await state.clear()
        await message.answer(_("You are registered and linked."))
        return

    await state.set_state(AccessRequestForm.first_name)
    await message.answer(
        _("Let's create your access request. Please enter your first name."),
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(Command("help"))
async def help_handler(message: Message, _):
    help_text = "\n".join(
        [
            _("Available commands:"),
            "/start - " + _("Start bot"),
            "/my - " + _("Show my access status"),
            "/cancel - " + _("Cancel current form"),
            "/help - " + _("Show help"),
        ]
    )
    await message.answer(help_text)


@router.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext, _):
    current_state = await state.get_state()
    if not current_state:
        await message.answer(_("There is no active form right now."))
        return

    await state.clear()
    await message.answer(
        _("Access request form was canceled."),
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(AccessRequestForm.first_name, F.text, ~F.text.startswith("/"))
async def request_first_name_handler(message: Message, state: FSMContext, _):
    first_name = (message.text or "").strip()
    if len(first_name) < 2:
        await message.answer(_("Please enter a valid first name."))
        return
    await state.update_data(first_name=first_name)
    await state.set_state(AccessRequestForm.last_name)
    await message.answer(_("Please enter your last name."))


@router.message(AccessRequestForm.last_name, F.text, ~F.text.startswith("/"))
async def request_last_name_handler(message: Message, state: FSMContext, _):
    last_name = (message.text or "").strip()
    if len(last_name) < 2:
        await message.answer(_("Please enter a valid last name."))
        return
    await state.update_data(last_name=last_name)
    await state.set_state(AccessRequestForm.patronymic)
    await message.answer(_("Enter your patronymic or send '-' to skip."))


@router.message(AccessRequestForm.patronymic, F.text, ~F.text.startswith("/"))
async def request_patronymic_handler(message: Message, state: FSMContext, _):
    patronymic_raw = (message.text or "").strip()
    patronymic = None if patronymic_raw in {"-", "—"} else patronymic_raw
    await state.update_data(patronymic=patronymic)
    await state.set_state(AccessRequestForm.phone)
    await message.answer(
        _("Please share your phone number or type it in international format."),
        reply_markup=_phone_keyboard(_),
    )


async def _finalize_access_request(
    message: Message, state: FSMContext, translator, phone: str
) -> None:
    data = await state.get_data()
    try:
        _access_request, created = await run_sync(
            AccountService.ensure_pending_access_request_from_bot,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=data["first_name"],
            last_name=data["last_name"],
            patronymic=data.get("patronymic"),
            phone=phone,
        )
    except ValueError as exc:
        await message.answer(
            translator(str(exc)),
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    await state.clear()
    if created:
        await message.answer(
            translator("Access request submitted. We will review and notify you."),
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    await message.answer(
        translator("Your access request is already pending."),
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(AccessRequestForm.phone, F.contact)
async def request_phone_contact_handler(message: Message, state: FSMContext, _):
    contact = message.contact
    if contact.user_id and contact.user_id != message.from_user.id:
        await message.answer(_("Please share your own phone number."))
        return
    phone = _normalize_phone(contact.phone_number or "")
    if not phone:
        await message.answer(_("Please share a valid phone number."))
        return
    await _finalize_access_request(message, state, _, phone)


@router.message(AccessRequestForm.phone, F.text, ~F.text.startswith("/"))
async def request_phone_text_handler(message: Message, state: FSMContext, _):
    phone = _normalize_phone(message.text or "")
    if not phone:
        await message.answer(
            _("Please send a valid phone number in international format.")
        )
        return
    await _finalize_access_request(message, state, _, phone)


@router.message(Command("my"))
async def my_handler(
    message: Message, _, user: User = None, telegram_profile: TelegramProfile = None
):
    pending = await run_sync(
        AccountService.get_pending_access_request, message.from_user.id
    )
    if pending:
        await message.answer(_("Your access request is pending."))
        return

    if await _has_active_linked_user(user, telegram_profile):
        await message.answer(_("You are registered and linked."))
        return

    await message.answer(
        _("You are not registered. Use /start to submit access request.")
    )
