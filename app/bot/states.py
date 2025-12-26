from aiogram.fsm.state import StatesGroup, State


class AdminCreateEvent(StatesGroup):
    title = State()
    starts_at = State()       # "YYYY-MM-DD HH:MM"
    location = State()
    description = State()
    url = State()
    media = State()           # album or single
    confirm = State()


class AdminEditEvent(StatesGroup):
    choosing_field = State()
    title = State()
    starts_at = State()
    location = State()
    description = State()
    url = State()


class AdminCreateBroadcast(StatesGroup):
    kind = State()            # "event" or "custom"
    pick_event = State()
    custom_text = State()
    custom_media = State()
    audience = State()
    reminder_hours = State()
    confirm = State()