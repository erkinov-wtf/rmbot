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
from bot.services.menu import (
    MENU_BUTTON_HELP_VARIANTS,
    MENU_BUTTON_MY_STATUS_VARIANTS,
    MENU_BUTTON_MY_XP_VARIANTS,
    MENU_BUTTON_START_ACCESS_VARIANTS,
    MENU_BUTTON_XP_HISTORY_VARIANTS,
    build_main_menu_keyboard,
    main_menu_markup_for_user,
)
from bot.services.start_support import (
    XP_HISTORY_CALLBACK_PREFIX,
    _build_active_status_text,
    _build_pending_status_text,
    _build_xp_history_pagination_markup,
    _build_xp_history_text,
    _has_active_linked_user,
    _parse_xp_history_callback_data,
    _reply_not_registered,
    _reply_not_registered_callback,
    _reply_xp_history,
    _reply_xp_summary,
    _resolve_active_user_for_status,
    _resolve_registered_user,
    _safe_edit_callback_message,
)
from core.utils.asyncio import run_sync

router = Router(name="start")
PHONE_PATTERN = re.compile(r"^\+?[1-9][0-9]{7,14}$")


class AccessRequestForm(StatesGroup):
    first_name = State()
    last_name = State()
    phone = State()


async def _clear_state_if_active(state: FSMContext | None) -> None:
    if state is None:
        return
    if await state.get_state():
        await state.clear()


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


@router.callback_query(F.data.startswith(f"{XP_HISTORY_CALLBACK_PREFIX}:"))
async def xp_history_pagination_handler(
    query,
    _,
    user: User = None,
    telegram_profile: TelegramProfile = None,
):
    parsed = _parse_xp_history_callback_data(callback_data=query.data or "")
    if parsed is None:
        await query.answer(_("Could not open this page."), show_alert=True)
        return
    limit, offset = parsed
    resolved_user = await _resolve_registered_user(
        user=user,
        telegram_profile=telegram_profile,
    )
    if resolved_user is None:
        await _reply_not_registered_callback(query=query, _=_)
        return

    text, total_count, normalized_limit, safe_offset = await _build_xp_history_text(
        user=resolved_user,
        _=_,
        limit=limit,
        offset=offset,
    )
    await _safe_edit_callback_message(
        query=query,
        text=text,
        reply_markup=_build_xp_history_pagination_markup(
            total_count=total_count,
            limit=normalized_limit,
            offset=safe_offset,
            _=_,
        ),
    )
    await query.answer()


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
        await message.answer(
            _("Your access request is already under review."),
            reply_markup=build_main_menu_keyboard(
                is_technician=False,
                include_start_access=False,
                _=_,
            ),
        )
        return

    if await _has_active_linked_user(user, profile):
        await state.clear()
        await message.answer(
            _("You are all set. Your account is already active."),
            reply_markup=await main_menu_markup_for_user(user=user, _=_),
        )
        return

    await state.set_state(AccessRequestForm.first_name)
    await message.answer(
        _("Let's create your access request. Please enter your first name."),
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(Command("help"))
async def help_handler(
    message: Message,
    _,
    user: User = None,
    state: FSMContext | None = None,
):
    await _clear_state_if_active(state)
    help_text = "\n".join(
        [
            _("Available commands:"),
            "/start - " + _("Start the bot and access setup"),
            "/my - " + _("Check my profile and access status"),
            "/ticket_create - " + _("Start ticket intake flow"),
            "/ticket_review - " + _("Open ticket review queue"),
            "/queue - " + _("Open my active ticket list"),
            "/active - " + _("Open my active ticket list"),
            "/tech - " + _("Open technician ticket controls"),
            "/under_qc - " + _("Open tickets waiting for quality check"),
            "/past - " + _("Open my completed tickets"),
            "/qc_checks - " + _("Open my assigned QC checks"),
            "/xp - " + _("Show my XP summary"),
            "/xp_history - " + _("Show my XP activity with pages"),
            "/cancel - " + _("Cancel the current form"),
            "/help - " + _("Show this help message"),
        ]
    )
    await message.answer(
        help_text,
        reply_markup=await main_menu_markup_for_user(
            user=user,
            include_start_access=not bool(user and user.is_active),
            _=_,
        ),
    )


@router.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext, _, user: User = None):
    current_state = await state.get_state()
    if not current_state:
        await message.answer(
            _("There is no form in progress right now."),
            reply_markup=await main_menu_markup_for_user(
                user=user,
                include_start_access=not bool(user and user.is_active),
                _=_,
            ),
        )
        return

    await state.clear()
    await message.answer(
        _("Canceled. You can start a new request anytime."),
        reply_markup=await main_menu_markup_for_user(
            user=user,
            include_start_access=not bool(user and user.is_active),
            _=_,
        ),
    )


@router.message(AccessRequestForm.first_name, F.text, ~F.text.startswith("/"))
async def request_first_name_handler(message: Message, state: FSMContext, _):
    first_name = (message.text or "").strip()
    if len(first_name) < 2:
        await message.answer(_("Please enter a valid first name (at least 2 letters)."))
        return
    await state.update_data(first_name=first_name)
    await state.set_state(AccessRequestForm.last_name)
    await message.answer(_("Please enter your last name."))


@router.message(AccessRequestForm.last_name, F.text, ~F.text.startswith("/"))
async def request_last_name_handler(message: Message, state: FSMContext, _):
    last_name = (message.text or "").strip()
    if len(last_name) < 2:
        await message.answer(_("Please enter a valid last name (at least 2 letters)."))
        return
    await state.update_data(last_name=last_name)
    await state.set_state(AccessRequestForm.phone)
    await message.answer(
        _("Please share your phone number or type it in international format."),
        reply_markup=_phone_keyboard(_),
    )


async def _finalize_access_request(
    message: Message,
    state: FSMContext,
    _,
    phone: str,
) -> None:
    data = await state.get_data()
    try:
        _access_request, created = await run_sync(
            AccountService.ensure_pending_access_request_from_bot,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=data["first_name"],
            last_name=data["last_name"],
            phone=phone,
        )
    except ValueError as exc:
        await message.answer(
            _(str(exc)),
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    await state.clear()
    pending_menu = build_main_menu_keyboard(
        is_technician=False,
        include_start_access=False,
        _=_,
    )
    if created:
        await message.answer(
            _(
                "Request submitted successfully. We will review it and message you here."
            ),
            reply_markup=pending_menu,
        )
        return
    await message.answer(
        _("Your request is already under review."),
        reply_markup=pending_menu,
    )


@router.message(AccessRequestForm.phone, F.contact)
async def request_phone_contact_handler(message: Message, state: FSMContext, _):
    contact = message.contact
    if contact.user_id and contact.user_id != message.from_user.id:
        await message.answer(
            _("Please share your own phone number, not someone else's.")
        )
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
    message: Message,
    _,
    user: User = None,
    telegram_profile: TelegramProfile = None,
    state: FSMContext | None = None,
):
    await _clear_state_if_active(state)
    pending = await run_sync(
        AccountService.get_pending_access_request, message.from_user.id
    )
    if pending:
        await message.answer(
            _build_pending_status_text(pending=pending, _=_),
            reply_markup=build_main_menu_keyboard(
                is_technician=False,
                include_start_access=False,
                _=_,
            ),
        )
        return

    resolved_user = await _resolve_active_user_for_status(
        user=user,
        telegram_profile=telegram_profile,
    )
    if resolved_user:
        await message.answer(
            await _build_active_status_text(user=resolved_user, _=_),
            reply_markup=await main_menu_markup_for_user(user=resolved_user, _=_),
        )
        return

    await _reply_not_registered(message=message, _=_)


@router.message(Command("xp"))
async def my_xp_handler(
    message: Message,
    _,
    user: User = None,
    telegram_profile: TelegramProfile = None,
    state: FSMContext | None = None,
):
    await _clear_state_if_active(state)
    await _reply_xp_summary(
        message=message,
        user=user,
        telegram_profile=telegram_profile,
        _=_,
    )


@router.message(Command("xp_history"))
async def my_xp_history_handler(
    message: Message,
    _,
    user: User = None,
    telegram_profile: TelegramProfile = None,
    state: FSMContext | None = None,
):
    await _clear_state_if_active(state)
    await _reply_xp_history(
        message=message,
        user=user,
        telegram_profile=telegram_profile,
        _=_,
    )


@router.message(F.text.in_(MENU_BUTTON_HELP_VARIANTS))
async def help_button_handler(
    message: Message,
    _,
    user: User = None,
    state: FSMContext | None = None,
):
    await help_handler(message, _, user=user, state=state)


@router.message(F.text.in_(MENU_BUTTON_MY_STATUS_VARIANTS))
async def my_button_handler(
    message: Message,
    _,
    user: User = None,
    telegram_profile: TelegramProfile = None,
    state: FSMContext | None = None,
):
    await my_handler(
        message,
        _,
        user=user,
        telegram_profile=telegram_profile,
        state=state,
    )


@router.message(F.text.in_(MENU_BUTTON_MY_XP_VARIANTS))
async def my_xp_button_handler(
    message: Message,
    _,
    user: User = None,
    telegram_profile: TelegramProfile = None,
    state: FSMContext | None = None,
):
    await my_xp_handler(
        message,
        _,
        user=user,
        telegram_profile=telegram_profile,
        state=state,
    )


@router.message(F.text.in_(MENU_BUTTON_XP_HISTORY_VARIANTS))
async def my_xp_history_button_handler(
    message: Message,
    _,
    user: User = None,
    telegram_profile: TelegramProfile = None,
    state: FSMContext | None = None,
):
    await my_xp_history_handler(
        message,
        _,
        user=user,
        telegram_profile=telegram_profile,
        state=state,
    )


@router.message(F.text.in_(MENU_BUTTON_START_ACCESS_VARIANTS))
async def start_button_handler(
    message: Message,
    state: FSMContext,
    _,
    user: User = None,
    telegram_profile: TelegramProfile = None,
):
    await start_handler(
        message,
        state,
        _,
        user=user,
        telegram_profile=telegram_profile,
    )
