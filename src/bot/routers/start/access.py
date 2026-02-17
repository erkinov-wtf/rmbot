import re
from html import escape
from typing import Any, cast

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.handlers import MessageHandler
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from account.models import TelegramProfile, User
from account.services import AccountService
from bot.routers.start.common import AccessRequestForm, StartStateMixin
from bot.services.menu import (
    MENU_BUTTON_START_ACCESS_VARIANTS,
    build_main_menu_keyboard,
    main_menu_markup_for_user,
)
from bot.services.start_support import _has_active_linked_user
from core.utils.asyncio import run_sync

router = Router(name="start_access")


class AccessRequestSupportMixin(StartStateMixin):
    PHONE_PATTERN = re.compile(r"^\+?[1-9][0-9]{7,14}$")
    PROGRESS_MESSAGE_ID_KEY = "access_progress_message_id"
    PHONE_PROMPT_MESSAGE_ID_KEY = "access_phone_prompt_message_id"
    TOTAL_ACCESS_REQUEST_FIELDS = 3

    @classmethod
    def normalize_phone(cls, raw: str) -> str | None:
        compact = raw.strip().replace(" ", "").replace("-", "")
        if not compact:
            return None
        if not cls.PHONE_PATTERN.fullmatch(compact):
            return None
        return compact if compact.startswith("+") else f"+{compact}"

    @classmethod
    def phone_keyboard(cls, _) -> ReplyKeyboardMarkup:
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

    @classmethod
    def clean_form_value(cls, value: Any) -> str | None:
        del cls
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @classmethod
    def progress_values_from_state_data(
        cls,
        state_data: dict[str, Any],
    ) -> tuple[str | None, str | None, str | None]:
        return (
            cls.clean_form_value(state_data.get("first_name")),
            cls.clean_form_value(state_data.get("last_name")),
            cls.clean_form_value(state_data.get("phone")),
        )

    @classmethod
    def _progress_field_line(
        cls,
        *,
        label: str,
        value: str | None,
        _,
    ) -> str:
        del cls
        if value:
            return _("✅ <b>%(label)s:</b> <code>%(value)s</code>") % {
                "label": escape(label),
                "value": escape(value),
            }
        return _("⬜ <b>%(label)s:</b> <i>%(placeholder)s</i>") % {
            "label": escape(label),
            "placeholder": escape(_("...")),
        }

    @classmethod
    def build_progress_card_text(
        cls,
        *,
        first_name: str | None,
        last_name: str | None,
        phone: str | None,
        next_step: str,
        saved_update: str | None,
        _,
    ) -> str:
        progress_done = sum(bool(value) for value in (first_name, last_name, phone))
        progress_bar = "🟩" * progress_done + "⬜" * (
            cls.TOTAL_ACCESS_REQUEST_FIELDS - progress_done
        )

        lines = [
            _("🧾 <b>Access request</b>"),
            _("📈 <b>Progress:</b> %(done)s/%(total)s %(bar)s")
            % {
                "done": progress_done,
                "total": cls.TOTAL_ACCESS_REQUEST_FIELDS,
                "bar": progress_bar,
            },
            "",
            cls._progress_field_line(label=_("First name"), value=first_name, _=_),
            cls._progress_field_line(label=_("Last name"), value=last_name, _=_),
            cls._progress_field_line(label=_("Phone"), value=phone, _=_),
            "",
            _("➡️ <b>Next step:</b> %(value)s") % {"value": escape(next_step)},
        ]
        if saved_update:
            lines.insert(
                1,
                _("💾 <b>Saved:</b> %(value)s") % {"value": escape(saved_update)},
            )
        return "\n".join(lines)

    @classmethod
    def _progress_message_id(cls, state_data: dict[str, Any]) -> int | None:
        raw = state_data.get(cls.PROGRESS_MESSAGE_ID_KEY)
        if isinstance(raw, int):
            return raw
        if isinstance(raw, str) and raw.isdigit():
            return int(raw)
        return None

    @classmethod
    def _phone_prompt_message_id(cls, state_data: dict[str, Any]) -> int | None:
        raw = state_data.get(cls.PHONE_PROMPT_MESSAGE_ID_KEY)
        if isinstance(raw, int):
            return raw
        if isinstance(raw, str) and raw.isdigit():
            return int(raw)
        return None

    @classmethod
    async def clear_progress_message_state(cls, *, state: FSMContext) -> None:
        await state.update_data(data={cls.PROGRESS_MESSAGE_ID_KEY: None})

    @classmethod
    async def clear_phone_prompt_message_state(cls, *, state: FSMContext) -> None:
        await state.update_data(data={cls.PHONE_PROMPT_MESSAGE_ID_KEY: None})

    @classmethod
    async def safe_delete_message(
        cls,
        *,
        message: Message,
        message_id: int | None,
    ) -> None:
        del cls
        if message_id is None:
            return

        bot = message.bot
        if bot is None:
            return

        safe_bot = cast(Bot, bot)
        try:
            await safe_bot.delete_message(
                chat_id=message.chat.id,
                message_id=message_id,
            )
        except (TelegramBadRequest, TelegramForbiddenError):
            return

    @classmethod
    async def consume_user_input_message(cls, *, message: Message) -> None:
        await cls.safe_delete_message(message=message, message_id=message.message_id)

    @classmethod
    async def delete_progress_message(
        cls,
        *,
        message: Message,
        state: FSMContext,
    ) -> None:
        state_data = await state.get_data()
        await cls.safe_delete_message(
            message=message,
            message_id=cls._progress_message_id(state_data),
        )
        await cls.clear_progress_message_state(state=state)

    @classmethod
    async def delete_phone_prompt_message(
        cls,
        *,
        message: Message,
        state: FSMContext,
    ) -> None:
        state_data = await state.get_data()
        await cls.safe_delete_message(
            message=message,
            message_id=cls._phone_prompt_message_id(state_data),
        )
        await cls.clear_phone_prompt_message_state(state=state)

    @classmethod
    async def send_phone_prompt_message(
        cls,
        *,
        message: Message,
        state: FSMContext,
        text: str,
        _,
    ) -> None:
        await cls.delete_phone_prompt_message(message=message, state=state)
        prompt_message = await message.answer(
            text,
            reply_markup=cls.phone_keyboard(_),
        )
        await state.update_data(
            data={cls.PHONE_PROMPT_MESSAGE_ID_KEY: prompt_message.message_id}
        )

    @classmethod
    async def _try_edit_progress_card(
        cls,
        *,
        message: Message,
        progress_message_id: int,
        text: str,
    ) -> bool:
        del cls
        bot = message.bot
        if bot is None:
            return False
        safe_bot = cast(Bot, bot)
        try:
            await safe_bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=progress_message_id,
                text=text,
            )
            return True
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                return True
            return False

    @classmethod
    async def show_progress_card(
        cls,
        *,
        message: Message,
        state: FSMContext,
        first_name: str | None,
        last_name: str | None,
        phone: str | None,
        next_step: str,
        _,
        saved_update: str | None = None,
        force_new_message: bool = False,
        replace_existing: bool = False,
    ) -> None:
        text = cls.build_progress_card_text(
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            next_step=next_step,
            saved_update=saved_update,
            _=_,
        )

        if not force_new_message:
            state_data = await state.get_data()
            progress_message_id = cls._progress_message_id(state_data)

            if replace_existing and progress_message_id is not None:
                await cls.safe_delete_message(
                    message=message,
                    message_id=progress_message_id,
                )
                await cls.clear_progress_message_state(state=state)
                progress_message_id = None

            if progress_message_id is not None:
                if await cls._try_edit_progress_card(
                    message=message,
                    progress_message_id=progress_message_id,
                    text=text,
                ):
                    return

        sent_message = await message.answer(
            text,
            reply_markup=ReplyKeyboardRemove() if force_new_message else None,
        )
        await state.update_data(
            data={cls.PROGRESS_MESSAGE_ID_KEY: sent_message.message_id}
        )

    @classmethod
    async def finalize_access_request(
        cls,
        *,
        message: Message,
        state: FSMContext,
        _,
        phone: str,
    ) -> None:
        from_user = message.from_user
        if from_user is None:
            return

        data = await state.get_data()
        first_name = cls.clean_form_value(data.get("first_name"))
        last_name = cls.clean_form_value(data.get("last_name"))
        if first_name is None or last_name is None:
            await cls.delete_progress_message(message=message, state=state)
            await cls.delete_phone_prompt_message(message=message, state=state)
            await state.clear()
            await message.answer(
                _(
                    "⚠️ <b>Your draft expired.</b>\nPlease send /start and fill the form again."
                ),
                reply_markup=ReplyKeyboardRemove(),
            )
            return

        await state.update_data(phone=phone)
        await cls.show_progress_card(
            message=message,
            state=state,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            saved_update=_("Phone number saved."),
            next_step=_("Submitting your request..."),
            replace_existing=True,
            _=_,
        )

        try:
            _access_request, created = await run_sync(
                AccountService.ensure_pending_access_request_from_bot,
                telegram_id=from_user.id,
                username=from_user.username,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
            )
        except ValueError as exc:
            await cls.show_progress_card(
                message=message,
                state=state,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                saved_update=_("Submission failed."),
                next_step=_("Please review your data and send your phone again."),
                _=_,
            )
            await cls.send_phone_prompt_message(
                message=message,
                state=state,
                text=_("❌ <b>Could not submit your request.</b>\nReason: %(reason)s")
                % {"reason": escape(_(str(exc)))},
                _=_,
            )
            return

        pending_menu = build_main_menu_keyboard(
            is_technician=False,
            include_start_access=False,
            _=_,
        )
        if created:
            await cls.delete_progress_message(message=message, state=state)
            await cls.delete_phone_prompt_message(message=message, state=state)
            await state.clear()
            await message.answer(
                _(
                    "✅ <b>Request submitted successfully.</b>\nWe will review it and message you here."
                ),
                reply_markup=pending_menu,
            )
            return

        await cls.delete_progress_message(message=message, state=state)
        await cls.delete_phone_prompt_message(message=message, state=state)
        await state.clear()
        await message.answer(
            _("ℹ️ <b>Your request is already under review.</b>"),
            reply_markup=pending_menu,
        )

    @classmethod
    async def handle_start_request(
        cls,
        *,
        message: Message,
        state: FSMContext,
        _,
        user: User | None,
        telegram_profile: TelegramProfile | None,
    ) -> None:
        from_user = message.from_user
        if from_user is None:
            return

        profile = telegram_profile or await run_sync(
            AccountService.upsert_telegram_profile,
            from_user,
        )

        pending = await run_sync(
            AccountService.get_pending_access_request,
            profile.telegram_id if profile else from_user.id,
        )
        if pending:
            await cls.delete_progress_message(message=message, state=state)
            await cls.delete_phone_prompt_message(message=message, state=state)
            await state.clear()
            await message.answer(
                _("ℹ️ <b>Your access request is already under review.</b>"),
                reply_markup=build_main_menu_keyboard(
                    is_technician=False,
                    include_start_access=False,
                    _=_,
                ),
            )
            return

        if await _has_active_linked_user(user, profile):
            await cls.delete_progress_message(message=message, state=state)
            await cls.delete_phone_prompt_message(message=message, state=state)
            await state.clear()
            await message.answer(
                _("✅ <b>You are all set.</b> Your account is already active."),
                reply_markup=await main_menu_markup_for_user(user=user, _=_),
            )
            return

        await cls.delete_progress_message(message=message, state=state)
        await cls.delete_phone_prompt_message(message=message, state=state)
        await state.clear()
        await state.set_state(AccessRequestForm.first_name)
        await cls.show_progress_card(
            message=message,
            state=state,
            first_name=None,
            last_name=None,
            phone=None,
            saved_update=_("Draft started."),
            next_step=_("Enter your first name."),
            force_new_message=True,
            _=_,
        )


@router.message(CommandStart())
@router.message(F.text.in_(MENU_BUTTON_START_ACCESS_VARIANTS))
class StartAccessHandler(AccessRequestSupportMixin, MessageHandler):
    async def handle(self) -> None:
        message: Message = self.event
        state: FSMContext = self.data["state"]
        _ = self.data["_"]
        user: User | None = self.data.get("user")
        telegram_profile: TelegramProfile | None = self.data.get("telegram_profile")

        await self.handle_start_request(
            message=message,
            state=state,
            _=_,
            user=user,
            telegram_profile=telegram_profile,
        )


@router.message(Command("cancel"))
class CancelHandler(AccessRequestSupportMixin, MessageHandler):
    async def handle(self) -> None:
        message: Message = self.event
        state: FSMContext = self.data["state"]
        _ = self.data["_"]
        user: User | None = self.data.get("user")

        current_state = await state.get_state()
        if not current_state:
            await message.answer(
                _("ℹ️ <b>No form in progress.</b>"),
                reply_markup=await main_menu_markup_for_user(
                    user=user,
                    include_start_access=not bool(user and user.is_active),
                    _=_,
                ),
            )
            return

        await self.consume_user_input_message(message=message)
        await self.delete_progress_message(message=message, state=state)
        await self.delete_phone_prompt_message(message=message, state=state)
        await state.clear()
        await message.answer(
            _("🛑 <b>Draft canceled.</b>\nYou can start a new request anytime."),
            reply_markup=await main_menu_markup_for_user(
                user=user,
                include_start_access=not bool(user and user.is_active),
                _=_,
            ),
        )


@router.message(AccessRequestForm.first_name, F.text, ~F.text.startswith("/"))
class AccessRequestFirstNameHandler(AccessRequestSupportMixin, MessageHandler):
    async def handle(self) -> None:
        message: Message = self.event
        state: FSMContext = self.data["state"]
        _ = self.data["_"]

        first_name = (message.text or "").strip()
        if len(first_name) < 2:
            await message.answer(
                _("⚠️ <b>First name is too short.</b>\nPlease enter at least 2 letters.")
            )
            return

        await state.update_data(first_name=first_name)
        await state.set_state(AccessRequestForm.last_name)
        state_data = await state.get_data()
        saved_first_name, saved_last_name, saved_phone = (
            self.progress_values_from_state_data(state_data)
        )
        await self.consume_user_input_message(message=message)
        await self.show_progress_card(
            message=message,
            state=state,
            first_name=saved_first_name,
            last_name=saved_last_name,
            phone=saved_phone,
            saved_update=_("First name saved."),
            next_step=_("Enter your last name."),
            replace_existing=True,
            _=_,
        )


@router.message(AccessRequestForm.last_name, F.text, ~F.text.startswith("/"))
class AccessRequestLastNameHandler(AccessRequestSupportMixin, MessageHandler):
    async def handle(self) -> None:
        message: Message = self.event
        state: FSMContext = self.data["state"]
        _ = self.data["_"]

        last_name = (message.text or "").strip()
        if len(last_name) < 2:
            await message.answer(
                _("⚠️ <b>Last name is too short.</b>\nPlease enter at least 2 letters.")
            )
            return

        await state.update_data(last_name=last_name)
        await state.set_state(AccessRequestForm.phone)
        state_data = await state.get_data()
        saved_first_name, saved_last_name, saved_phone = (
            self.progress_values_from_state_data(state_data)
        )
        await self.consume_user_input_message(message=message)
        await self.show_progress_card(
            message=message,
            state=state,
            first_name=saved_first_name,
            last_name=saved_last_name,
            phone=saved_phone,
            saved_update=_("Last name saved."),
            next_step=_("Share your phone number."),
            replace_existing=True,
            _=_,
        )
        await self.send_phone_prompt_message(
            message=message,
            state=state,
            text=_(
                "📱 <b>Phone number</b>\n"
                "Use the button below or type your number in international format "
                "(for example: <code>+998901234567</code>)."
            ),
            _=_,
        )


@router.message(AccessRequestForm.phone, F.contact)
class AccessRequestPhoneContactHandler(AccessRequestSupportMixin, MessageHandler):
    async def handle(self) -> None:
        message: Message = self.event
        state: FSMContext = self.data["state"]
        _ = self.data["_"]

        contact = message.contact
        from_user = message.from_user
        if contact is None or from_user is None:
            await message.answer(
                _("⚠️ <b>Please share a valid phone number.</b>"),
                reply_markup=self.phone_keyboard(_),
            )
            return

        if contact.user_id and contact.user_id != from_user.id:
            await message.answer(
                _("⚠️ <b>Please share your own phone number, not someone else's.</b>"),
                reply_markup=self.phone_keyboard(_),
            )
            return
        phone = self.normalize_phone(contact.phone_number or "")
        if not phone:
            await message.answer(
                _("⚠️ <b>Please share a valid phone number.</b>"),
                reply_markup=self.phone_keyboard(_),
            )
            return
        await self.consume_user_input_message(message=message)
        await self.delete_phone_prompt_message(message=message, state=state)
        await self.finalize_access_request(
            message=message,
            state=state,
            _=_,
            phone=phone,
        )


@router.message(AccessRequestForm.phone, F.text, ~F.text.startswith("/"))
class AccessRequestPhoneTextHandler(AccessRequestSupportMixin, MessageHandler):
    async def handle(self) -> None:
        message: Message = self.event
        state: FSMContext = self.data["state"]
        _ = self.data["_"]

        phone = self.normalize_phone(message.text or "")
        if not phone:
            await message.answer(
                _(
                    "⚠️ <b>Invalid phone number format.</b>\n"
                    "Please send it in international format, for example "
                    "<code>+998901234567</code>."
                ),
                reply_markup=self.phone_keyboard(_),
            )
            return
        await self.consume_user_input_message(message=message)
        await self.delete_phone_prompt_message(message=message, state=state)
        await self.finalize_access_request(
            message=message,
            state=state,
            _=_,
            phone=phone,
        )
