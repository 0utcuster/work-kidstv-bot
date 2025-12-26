from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.callbacks import EventsListCb, EventViewCb, EventReactCb


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Грядущие мероприятия")],
            [KeyboardButton(text="Мои интересы"), KeyboardButton(text="Настройки")],
        ],
        resize_keyboard=True
    )


def settings_kb(is_subscribed: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if is_subscribed:
        b.button(text="🔕 Отписаться от рассылок", callback_data="usr:unsub")
    else:
        b.button(text="🔔 Подписаться на рассылки", callback_data="usr:sub")
    return b.as_markup()


def events_list_kb(items: list[tuple[int, str]], page: int, pages: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for event_id, title in items:
        b.button(text=title[:40], callback_data=EventViewCb(event_id=event_id).pack())

    nav = InlineKeyboardBuilder()
    if page > 1:
        nav.button(text="⬅️", callback_data=EventsListCb(page=page - 1).pack())
    nav.button(text=f"{page}/{pages}", callback_data="noop")
    if page < pages:
        nav.button(text="➡️", callback_data=EventsListCb(page=page + 1).pack())

    b.adjust(1)
    nav.adjust(3)
    return InlineKeyboardMarkup(inline_keyboard=b.export()) if pages == 1 else InlineKeyboardMarkup(
        inline_keyboard=b.export() + nav.export()
    )


def event_card_kb(event_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Интересно", callback_data=EventReactCb(event_id=event_id, reaction="interested").pack())
    b.button(text="❌ Не интересно", callback_data=EventReactCb(event_id=event_id, reaction="declined").pack())
    b.button(text="📅 В календарь", callback_data=f"usr:ics:{event_id}")
    b.button(text="⬅️ Назад к списку", callback_data="usr:back_to_list")
    b.adjust(2, 2)
    return b.as_markup()