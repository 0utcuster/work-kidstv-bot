from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.callbacks import AdminMenuCb, AdminEventActionCb, AdminBroadcastActionCb, AdminBroadcastAudienceCb


def admin_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Мероприятия", callback_data=AdminMenuCb(section="events").pack())
    b.button(text="Рассылки", callback_data=AdminMenuCb(section="broadcasts").pack())
    b.button(text="Статистика", callback_data=AdminMenuCb(section="stats").pack())
    b.adjust(1)
    return b.as_markup()


def admin_events_kb(events: list[tuple[int, str, str]]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="➕ Добавить мероприятие", callback_data="admin:event:add")
    for event_id, title, status in events:
        b.button(text=f"{title[:28]} [{status}]", callback_data=AdminEventActionCb(event_id=event_id, action="view").pack())
    b.adjust(1)
    return b.as_markup()


def admin_event_actions_kb(event_id: int, status: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="👁 Просмотр", callback_data=AdminEventActionCb(event_id=event_id, action="view").pack())
    b.button(text="📊 Отчёт (кто ответил)", callback_data=AdminEventActionCb(event_id=event_id, action="report").pack())
    b.button(text="✏️ Редактировать", callback_data=AdminEventActionCb(event_id=event_id, action="edit").pack())

    if status != "published":
        b.button(text="✅ Опубликовать", callback_data=AdminEventActionCb(event_id=event_id, action="publish").pack())
    if status != "archived":
        b.button(text="🗄 В архив", callback_data=AdminEventActionCb(event_id=event_id, action="archive").pack())

    b.button(text="🗑 Удалить", callback_data=AdminEventActionCb(event_id=event_id, action="delete").pack())
    b.button(text="⬅️ Назад", callback_data=AdminMenuCb(section="events").pack())
    b.adjust(2, 2, 1, 1)
    return b.as_markup()


def admin_broadcasts_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="➕ Создать рассылку", callback_data=AdminBroadcastActionCb(action="new").pack())
    b.button(text="📃 Список рассылок", callback_data=AdminBroadcastActionCb(action="list").pack())
    b.button(text="⬅️ Назад", callback_data="admin:back")
    b.adjust(1)
    return b.as_markup()


def audience_kb(selected: str | None = None) -> InlineKeyboardMarkup:
    options = [
        ("all", "Всем"),
        ("subscribed", "Только подписанным"),
        ("active", "Только активным"),
        ("no_response", "Тем, кто не отвечал"),
        ("ever_interested", "Тем, кто когда-либо интересовался"),
    ]
    b = InlineKeyboardBuilder()
    for key, label in options:
        mark = " ✅" if selected == key else ""
        b.button(text=label + mark, callback_data=AdminBroadcastAudienceCb(audience=key).pack())
    b.button(text="Далее", callback_data="admin:aud:next")
    b.adjust(1)
    return b.as_markup()