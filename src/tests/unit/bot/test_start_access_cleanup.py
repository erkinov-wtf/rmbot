import asyncio
from types import SimpleNamespace

from bot.routers.start.access import AccessRequestSupportMixin


class _DummyBot:
    def __init__(self) -> None:
        self.deleted: list[tuple[int, int]] = []

    async def delete_message(self, *, chat_id: int, message_id: int) -> None:
        self.deleted.append((chat_id, message_id))


class _DummyState:
    def __init__(self, data: dict[str, object] | None = None) -> None:
        self.data = dict(data or {})

    async def get_data(self) -> dict[str, object]:
        return dict(self.data)

    async def update_data(self, data=None, **kwargs) -> dict[str, object]:
        if data:
            self.data.update(data)
        if kwargs:
            self.data.update(kwargs)
        return dict(self.data)


class _DummyMessage:
    def __init__(
        self,
        *,
        bot: _DummyBot,
        chat_id: int,
        message_id: int,
    ) -> None:
        self.bot = bot
        self.chat = SimpleNamespace(id=chat_id)
        self.message_id = message_id
        self.answers: list[dict[str, object]] = []

    async def answer(self, text: str, reply_markup=None):
        sent_message_id = 100 + len(self.answers)
        self.answers.append(
            {
                "text": text,
                "reply_markup": reply_markup,
                "message_id": sent_message_id,
            }
        )
        return SimpleNamespace(message_id=sent_message_id)


def test_delete_progress_message_removes_bot_progress_card_and_clears_state_key():
    bot = _DummyBot()
    state = _DummyState({AccessRequestSupportMixin.PROGRESS_MESSAGE_ID_KEY: 42})
    message = _DummyMessage(bot=bot, chat_id=5001, message_id=701)

    asyncio.run(
        AccessRequestSupportMixin.delete_progress_message(message=message, state=state)
    )

    assert bot.deleted == [(5001, 42)]
    assert state.data[AccessRequestSupportMixin.PROGRESS_MESSAGE_ID_KEY] is None


def test_consume_user_input_message_deletes_the_consumed_message():
    bot = _DummyBot()
    message = _DummyMessage(bot=bot, chat_id=5002, message_id=702)

    asyncio.run(AccessRequestSupportMixin.consume_user_input_message(message=message))

    assert bot.deleted == [(5002, 702)]


def test_show_progress_card_replace_existing_deletes_previous_progress_message():
    bot = _DummyBot()
    state = _DummyState({AccessRequestSupportMixin.PROGRESS_MESSAGE_ID_KEY: 88})
    message = _DummyMessage(bot=bot, chat_id=5003, message_id=703)

    asyncio.run(
        AccessRequestSupportMixin.show_progress_card(
            message=message,
            state=state,
            first_name="A",
            last_name=None,
            phone=None,
            next_step="Enter last name",
            saved_update="First name saved",
            replace_existing=True,
            _=lambda value: value,
        )
    )

    assert bot.deleted == [(5003, 88)]
    assert state.data[AccessRequestSupportMixin.PROGRESS_MESSAGE_ID_KEY] == 100
    assert len(message.answers) == 1


def test_delete_phone_prompt_message_removes_prompt_and_clears_state_key():
    bot = _DummyBot()
    state = _DummyState({AccessRequestSupportMixin.PHONE_PROMPT_MESSAGE_ID_KEY: 54})
    message = _DummyMessage(bot=bot, chat_id=5004, message_id=704)

    asyncio.run(
        AccessRequestSupportMixin.delete_phone_prompt_message(
            message=message, state=state
        )
    )

    assert bot.deleted == [(5004, 54)]
    assert state.data[AccessRequestSupportMixin.PHONE_PROMPT_MESSAGE_ID_KEY] is None


def test_send_phone_prompt_message_replaces_existing_prompt():
    bot = _DummyBot()
    state = _DummyState({AccessRequestSupportMixin.PHONE_PROMPT_MESSAGE_ID_KEY: 67})
    message = _DummyMessage(bot=bot, chat_id=5005, message_id=705)

    asyncio.run(
        AccessRequestSupportMixin.send_phone_prompt_message(
            message=message,
            state=state,
            text="Phone prompt",
            _=lambda value: value,
        )
    )

    assert bot.deleted == [(5005, 67)]
    assert state.data[AccessRequestSupportMixin.PHONE_PROMPT_MESSAGE_ID_KEY] == 100
    assert len(message.answers) == 1
