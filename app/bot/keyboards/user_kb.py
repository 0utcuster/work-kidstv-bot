from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.callbacks import EventsListCb, EventViewCb, EventReactCb, EventIcsCb, EventMoreMediaCb


BTN_UPCOMING = "📅 Ближайшие мероприятия"
BTN_INTERESTS = "⭐ Мои интересы"
BTN_SETTINGS = "⚙️ Настройки"


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_UPCOMING)],
            [KeyboardButton(text=BTN_INTERESTS)],
            [KeyboardButton(text=BTN_SETTINGS)],
        ],
        resize_keyboard=True,
    )


def events_list_kb(items: list[tuple[int, str]], page: int, pages: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()

    for event_id, title in items:
        kb.button(text=title, callback_data=EventViewCb(event_id=event_id).pack())

    nav = []
    if page > 1:
        nav.append(("⬅️", EventsListCb(page=page - 1).pack()))
    nav.append((f"{page}/{pages}", "noop"))
    if page < pages:
        nav.append(("➡️", EventsListCb(page=page + 1).pack()))

    for text, data in nav:
        kb.button(text=text, callback_data=data)

    kb.adjust(1)
    if pages > 1:
        kb.adjust(1, len(nav))

    return kb.as_markup()


def event_card_kb(event_id: int, has_more: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()

    kb.button(text="✅ Интересно", callback_data=EventReactCb(event_id=event_id, reaction="interested").pack())
    kb.button(text="❌ Не интересно", callback_data=EventReactCb(event_id=event_id, reaction="declined").pack())
    kb.button(text="📅 В календарь", callback_data=EventIcsCb(event_id=event_id).pack())

    if has_more:
        kb.button(text="🖼 Другие фото", callback_data=EventMoreMediaCb(event_id=event_id).pack())

    kb.adjust(2, 1, 1)
    return kb.as_markup()


def settings_kb(is_subscribed: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if is_subscribed:
        kb.button(text="🔕 Отписаться", callback_data="usr:unsub")
    else:
        kb.button(text="🔔 Подписаться", callback_data="usr:sub")
    kb.adjust(1)
    return kb.as_markup()