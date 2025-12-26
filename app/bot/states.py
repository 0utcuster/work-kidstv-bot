# app/bot/states.py
from aiogram.fsm.state import StatesGroup, State


class AdminCreateEvent(StatesGroup):
    title = State()
    starts_at = State()
    location = State()
    description = State()
    url = State()
    media = State()
    confirm = State()


class AdminEditEvent(StatesGroup):
    choosing_field = State()
    title = State()
    starts_at = State()
    location = State()
    description = State()
    url = State()

    # медиа-режим
    media_menu = State()
    media_add = State()
    media_replace_choose = State()
    media_replace_wait = State()
    media_delete_choose = State()


class AdminCreateBroadcast(StatesGroup):
    kind = State()
    pick_event = State()
    custom_text = State()
    custom_media = State()
    audience = State()
    reminder_hours = State()
    confirm = State()


# Онбординг пользователя
class UserOnboarding(StatesGroup):
    name = State()
    phone = State()


# Подтверждения опасных действий (слово-подтверждение)
class AdminDangerConfirm(StatesGroup):
    delete_event = State()
    delete_broadcast = State()
    run_broadcast = State()
    purge_event_media = State()