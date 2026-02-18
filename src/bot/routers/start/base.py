from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup


class AccessRequestForm(StatesGroup):
    first_name = State()
    last_name = State()
    phone = State()


class StartStateMixin:
    @classmethod
    async def clear_state_if_active(cls, state: FSMContext | None) -> None:
        if state is None:
            return
        if await state.get_state():
            await state.clear()
