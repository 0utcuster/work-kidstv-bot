from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.bot.callbacks import AdminMenuCb, AdminEventActionCb, AdminBroadcastActionCb, AdminBroadcastAudienceCb


def admin_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Мероприятия", callback_data=AdminMenuCb(section="events").pack())
    kb.button(text="📣 Рассылки", callback_data=AdminMenuCb(section="broadcasts").pack())
    kb.button(text="📊 Статистика", callback_data=AdminMenuCb(section="stats").pack())
    kb.adjust(1)
    return kb.as_markup()


def admin_events_kb(events):
    kb = InlineKeyboardBuilder()
    # events ожидается: [(id, title, status), ...]
    for event_id, title, status in events:
        kb.button(
            text=f"#{event_id} {title} [{status}]",
            callback_data=AdminEventActionCb(event_id=event_id, action="view").pack()
        )
    kb.button(text="➕ Добавить", callback_data="admin:event:add")
    kb.button(text="⬅️ Назад", callback_data="admin:back")
    kb.adjust(1)
    return kb.as_markup()


def admin_event_actions_kb(event_id: int, status: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="👀 Просмотр", callback_data=AdminEventActionCb(event_id=event_id, action="view").pack())
    kb.button(text="📎 Медиа", callback_data=AdminEventActionCb(event_id=event_id, action="media").pack())
    kb.button(text="📝 Редактировать поля", callback_data=AdminEventActionCb(event_id=event_id, action="edit").pack())
    kb.button(text="📄 Отчёт", callback_data=AdminEventActionCb(event_id=event_id, action="report").pack())

    if status != "published":
        kb.button(text="✅ Опубликовать", callback_data=AdminEventActionCb(event_id=event_id, action="publish").pack())
    if status != "archived":
        kb.button(text="📦 В архив", callback_data=AdminEventActionCb(event_id=event_id, action="archive").pack())

    kb.button(text="🗑 Удалить", callback_data=AdminEventActionCb(event_id=event_id, action="delete").pack())
    kb.button(text="⬅️ Назад к списку", callback_data=AdminMenuCb(section="events").pack())
    kb.adjust(1)
    return kb.as_markup()


def admin_event_media_kb(event_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить", callback_data=f"admin:media:add:{event_id}")
    kb.button(text="♻️ Заменить №", callback_data=f"admin:media:replace:{event_id}")
    kb.button(text="🗑 Удалить №", callback_data=f"admin:media:delete:{event_id}")
    kb.button(text="⬅️ Назад", callback_data=AdminEventActionCb(event_id=event_id, action="view").pack())
    kb.adjust(1)
    return kb.as_markup()


def admin_broadcasts_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Новая рассылка", callback_data=AdminBroadcastActionCb(action="new").pack())
    kb.button(text="📃 Список", callback_data=AdminBroadcastActionCb(action="list").pack())
    kb.button(text="⬅️ Назад", callback_data="admin:back")
    kb.adjust(1)
    return kb.as_markup()


def audience_kb(selected: str | None = None):
    kb = InlineKeyboardBuilder()
    for a in ["all", "subscribed", "active"]:
        prefix = "✅ " if selected == a else ""
        kb.button(text=f"{prefix}{a}", callback_data=AdminBroadcastAudienceCb(audience=a).pack())
    kb.button(text="➡️ Далее", callback_data="admin:aud:next")
    kb.adjust(1)
    return kb.as_markup()