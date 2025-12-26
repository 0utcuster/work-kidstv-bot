# app/bot/routers/admin.py

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.config import settings
from app.bot.callbacks import (
    AdminMenuCb, AdminEventActionCb, AdminBroadcastActionCb,
    AdminBroadcastAudienceCb
)
from app.bot.keyboards.admin_kb import (
    admin_menu_kb, admin_events_kb, admin_event_actions_kb,
    admin_broadcasts_menu_kb, audience_kb
)
from app.bot.states import AdminCreateEvent, AdminEditEvent, AdminCreateBroadcast, AdminDangerConfirm

from app.db.repos.events import (
    admin_list_events, get_event, set_event_status, delete_event,
    create_event, update_event_field, set_event_media
)
from app.db.repos.audit import audit_log
from app.services.events import (
    build_event_caption, reactions_report_text, admin_list_published_events
)
from app.services.broadcast import BroadcastService
from app.db.repos.broadcasts import (
    create_broadcast, list_broadcasts, set_broadcast_audience, set_broadcast_reminder_hours
)

from app.db.repos.events import (
    list_event_media, append_event_media,
    replace_event_media_by_index, delete_event_media_by_index
)
from app.bot.keyboards.admin_kb import admin_event_media_kb

router = Router()

MAX_MEDIA = 10  # Telegram media_group максимум 10
DELETE_CONFIRM_WORD = "УДАЛИТЬ"


def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


async def smart_edit(c: CallbackQuery, text: str, reply_markup=None, disable_web_page_preview: bool = True):
    """
    Пытаемся редактировать текущее сообщение (чтобы админка была "одним экраном").
    Если редактирование невозможно — отправляем новое.
    """
    try:
        await c.message.edit_text(text, reply_markup=reply_markup, disable_web_page_preview=disable_web_page_preview)
    except Exception:
        await c.message.answer(text, reply_markup=reply_markup, disable_web_page_preview=disable_web_page_preview)


@router.message(Command("admin"))
async def admin_entry(m: Message):
    if not is_admin(m.from_user.id):
        return await m.answer("Нет доступа.")
    await m.answer("Админ-панель:", reply_markup=admin_menu_kb())


@router.callback_query(AdminMenuCb.filter())
async def admin_menu(c: CallbackQuery, callback_data: AdminMenuCb):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа.", show_alert=True)

    if callback_data.section == "events":
        events = await admin_list_events()
        await smart_edit(c, "Мероприятия:", reply_markup=admin_events_kb(events))
    elif callback_data.section == "broadcasts":
        await smart_edit(c, "Рассылки:", reply_markup=admin_broadcasts_menu_kb())
    elif callback_data.section == "stats":
        bcs = await list_broadcasts(limit=10)
        text = "Последние рассылки:\n" + "\n".join([f"• #{b.id} {b.status} {b.kind}" for b in bcs]) if bcs else "Пока нет рассылок."
        await smart_edit(c, text, reply_markup=admin_menu_kb())

    await c.answer()


@router.callback_query(F.data == "admin:back")
async def admin_back(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа.", show_alert=True)
    await smart_edit(c, "Админ-панель:", reply_markup=admin_menu_kb())
    await c.answer()


@router.callback_query(F.data == "admin:event:add")
async def add_event_start(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа.", show_alert=True)
    await state.clear()
    await state.set_state(AdminCreateEvent.title)
    await smart_edit(c, "Название мероприятия:")
    await c.answer()


@router.message(AdminCreateEvent.title)
async def add_event_title(m: Message, state: FSMContext):
    await state.update_data(title=m.text.strip())
    await state.set_state(AdminCreateEvent.starts_at)
    await m.answer("Дата и время начала: YYYY-MM-DD HH:MM (например 2026-01-11 13:30) или YYYY-MM-DD (будет 12:00).")


@router.message(AdminCreateEvent.starts_at)
async def add_event_starts(m: Message, state: FSMContext):
    await state.update_data(starts_at=m.text.strip())
    await state.set_state(AdminCreateEvent.location)
    await m.answer("Локация (адрес/город/площадка):")


@router.message(AdminCreateEvent.location)
async def add_event_loc(m: Message, state: FSMContext):
    await state.update_data(location=m.text.strip())
    await state.set_state(AdminCreateEvent.description)
    await m.answer("Описание (можно кратко):")


@router.message(AdminCreateEvent.description)
async def add_event_desc(m: Message, state: FSMContext):
    await state.update_data(description=m.text.strip())
    await state.set_state(AdminCreateEvent.url)
    await m.answer("Ссылка (или напишите 'нет'):")


@router.message(AdminCreateEvent.url)
async def add_event_url(m: Message, state: FSMContext):
    url = m.text.strip()
    if url.lower() == "нет":
        url = ""
    await state.update_data(url=url)
    await state.update_data(media=[])  # важно: инициализируем массив медиа
    await state.set_state(AdminCreateEvent.media)
    await m.answer("Пришлите афиши (фото/документ). Можно несколько. Когда закончите — напишите <b>готово</b>. Чтобы пропустить — <b>нет</b>.")


@router.message(AdminCreateEvent.media, F.text.casefold() == "нет")
async def add_event_media_skip(m: Message, state: FSMContext):
    await state.update_data(media=[])
    await state.set_state(AdminCreateEvent.confirm)
    data = await state.get_data()
    await m.answer("Подтвердите создание: 'да' или 'нет'.\n" + build_event_caption_preview(data))


@router.message(AdminCreateEvent.media, F.text.casefold() == "готово")
async def add_event_media_done(m: Message, state: FSMContext):
    data = await state.get_data()
    media = (data.get("media") or [])[:MAX_MEDIA]
    await state.update_data(media=media)
    await state.set_state(AdminCreateEvent.confirm)
    data = await state.get_data()
    await m.answer(
        f"Принято медиа: {len(data.get('media', []))}\n"
        "Подтвердите создание: 'да' или 'нет'.\n" + build_event_caption_preview(data)
    )


@router.message(AdminCreateEvent.media, F.photo)
async def add_event_media_photo(m: Message, state: FSMContext):
    data = await state.get_data()
    media = data.get("media") or []
    if len(media) >= MAX_MEDIA:
        return await m.answer(f"Достигнут лимит {MAX_MEDIA} медиа. Напишите <b>готово</b>.")

    media.append(("photo", m.photo[-1].file_id))
    await state.update_data(media=media)
    await m.answer(
        f"Добавлено фото ({len(media)}/{MAX_MEDIA}). "
        "Пришлите ещё или напишите <b>готово</b>. "
        "Чтобы пропустить — <b>нет</b>."
    )


@router.message(AdminCreateEvent.media, F.document)
async def add_event_media_doc(m: Message, state: FSMContext):
    data = await state.get_data()
    media = data.get("media") or []
    if len(media) >= MAX_MEDIA:
        return await m.answer(f"Достигнут лимит {MAX_MEDIA} медиа. Напишите <b>готово</b>.")

    media.append(("document", m.document.file_id))
    await state.update_data(media=media)
    await m.answer(
        f"Добавлен документ ({len(media)}/{MAX_MEDIA}). "
        "Пришлите ещё или напишите <b>готово</b>. "
        "Чтобы пропустить — <b>нет</b>."
    )


@router.message(AdminCreateEvent.confirm)
async def add_event_confirm(m: Message, state: FSMContext):
    if m.text.strip().lower() != "да":
        await state.clear()
        return await m.answer("Отменено.", reply_markup=admin_menu_kb())

    data = await state.get_data()
    ev = await create_event(
        title=data["title"],
        starts_at=data["starts_at"],
        location=data["location"],
        description=data["description"],
        url=data.get("url", ""),
        created_by_admin_tg_id=m.from_user.id,
    )

    media = data.get("media", [])
    if media:
        await set_event_media(ev.id, media)

    await audit_log(m.from_user.id, "event_create", f"event_id={ev.id}")
    await state.clear()

    await m.answer(f"Создано мероприятие #{ev.id} (статус draft).", reply_markup=admin_menu_kb())


def build_event_caption_preview(data: dict) -> str:
    title = data.get("title", "")
    starts_at = data.get("starts_at", "")
    location = data.get("location", "")
    description = data.get("description", "")
    url = data.get("url", "")
    media_count = len(data.get("media") or [])

    lines = [
        f"<b>{title}</b>",
        f"🕒 {starts_at}",
    ]
    if location:
        lines.append(f"📍 {location}")
    lines.append(f"🖼 Медиа: {media_count}")
    if description:
        lines += ["", description]
    if url:
        lines += ["", f"🔗 {url}"]
    return "\n".join(lines)


@router.callback_query(AdminEventActionCb.filter())
async def event_actions(c: CallbackQuery, callback_data: AdminEventActionCb, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа.", show_alert=True)

    ev = await get_event(callback_data.event_id)
    if not ev:
        return await c.answer("Не найдено.", show_alert=True)

    action = callback_data.action

    if action == "view":
        cap = await build_event_caption(ev.id)
        await smart_edit(c, cap, reply_markup=admin_event_actions_kb(ev.id, ev.status))

    elif action == "publish":
        await set_event_status(ev.id, "published")
        await audit_log(c.from_user.id, "event_publish", f"event_id={ev.id}")
        cap = await build_event_caption(ev.id)
        await smart_edit(c, "Опубликовано.\n\n" + cap, reply_markup=admin_event_actions_kb(ev.id, "published"))

    elif action == "archive":
        await set_event_status(ev.id, "archived")
        await audit_log(c.from_user.id, "event_archive", f"event_id={ev.id}")
        cap = await build_event_caption(ev.id)
        await smart_edit(c, "В архиве.\n\n" + cap, reply_markup=admin_event_actions_kb(ev.id, "archived"))


    elif action == "media":
        await state.clear()
        await state.set_state(AdminEditEvent.media_menu)
        await state.update_data(event_id=ev.id)
        text = await _admin_media_text(ev.id)
        await smart_edit(c, text, reply_markup=admin_event_media_kb(ev.id))

    elif action == "delete":
        # было: сразу удаление. стало: подтверждение словом
        await state.clear()
        await state.set_state(AdminDangerConfirm.delete_event)
        await state.update_data(event_id=ev.id)
        await c.message.answer(
            f"Критическое действие.\n"
            f"Чтобы удалить мероприятие #{ev.id}, введите слово: <b>{DELETE_CONFIRM_WORD}</b>\n"
            "Чтобы отменить — напишите что угодно другое."
        )

    elif action == "report":
        text = await reactions_report_text(ev.id)
        # отчёт может быть длинным — лучше отдельным сообщением
        await c.message.answer(text, disable_web_page_preview=True)

    elif action == "edit":
        await state.clear()
        await state.set_state(AdminEditEvent.choosing_field)
        await state.update_data(event_id=ev.id)
        await c.message.answer("Что редактируем? Напишите: title / starts_at / location / description / url")

    await c.answer()


@router.message(AdminDangerConfirm.delete_event)
async def danger_delete_confirm(m: Message, state: FSMContext):
    """
    Подтверждение удаления словом УДАЛИТЬ.
    """
    data = await state.get_data()
    event_id = data.get("event_id")
    txt = (m.text or "").strip()

    if txt != DELETE_CONFIRM_WORD:
        await state.clear()
        return await m.answer("Отменено.", reply_markup=admin_menu_kb())

    if event_id:
        await delete_event(event_id)
        await audit_log(m.from_user.id, "event_delete", f"event_id={event_id}")

    await state.clear()
    await m.answer("Удалено.", reply_markup=admin_menu_kb())


@router.message(AdminEditEvent.choosing_field)
async def edit_choose(m: Message, state: FSMContext):
    field = m.text.strip()
    if field not in {"title", "starts_at", "location", "description", "url"}:
        return await m.answer("Нужно одно из: title / starts_at / location / description / url")

    await state.update_data(field=field)
    await state.set_state(getattr(AdminEditEvent, field))
    await m.answer(f"Введите новое значение для {field}:")


@router.message(AdminEditEvent.title)
@router.message(AdminEditEvent.starts_at)
@router.message(AdminEditEvent.location)
@router.message(AdminEditEvent.description)
@router.message(AdminEditEvent.url)
async def edit_apply(m: Message, state: FSMContext):
    data = await state.get_data()
    event_id = data["event_id"]
    field = data["field"]
    await update_event_field(event_id, field, m.text.strip())
    await audit_log(m.from_user.id, "event_edit", f"event_id={event_id} field={field}")
    await state.clear()
    await m.answer("Обновлено.", reply_markup=admin_menu_kb())


@router.callback_query(AdminBroadcastActionCb.filter())
async def broadcasts(c: CallbackQuery, callback_data: AdminBroadcastActionCb, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа.", show_alert=True)

    if callback_data.action == "new":
        await state.clear()
        await state.set_state(AdminCreateBroadcast.kind)
        await smart_edit(c, "Тип рассылки: напишите 'event' (по мероприятию) или 'custom' (произвольная).")

    elif callback_data.action == "list":
        bcs = await list_broadcasts(limit=20)
        if not bcs:
            await smart_edit(c, "Пока нет рассылок.", reply_markup=admin_broadcasts_menu_kb())
        else:
            text = "Рассылки:\n" + "\n".join([f"• #{b.id} {b.status} {b.kind} audience={b.audience}" for b in bcs])
            await smart_edit(c, text, reply_markup=admin_broadcasts_menu_kb())

    await c.answer()


@router.message(AdminCreateBroadcast.kind)
async def bc_kind(m: Message, state: FSMContext):
    kind = m.text.strip().lower()
    if kind not in {"event", "custom"}:
        return await m.answer("Нужно 'event' или 'custom'.")

    await state.update_data(kind=kind)

    if kind == "event":
        await state.set_state(AdminCreateBroadcast.pick_event)
        events = await admin_list_published_events(limit=20)
        if not events:
            await state.clear()
            return await m.answer("Нет опубликованных мероприятий. Сначала опубликуйте.", reply_markup=admin_menu_kb())
        text = "Выберите event_id из списка (просто отправьте число):\n" + "\n".join([f"• {eid}: {title}" for eid, title in events])
        await m.answer(text)
    else:
        await state.set_state(AdminCreateBroadcast.custom_text)
        await m.answer("Введите текст рассылки:")


@router.message(AdminCreateBroadcast.pick_event)
async def bc_pick_event(m: Message, state: FSMContext):
    if not m.text.strip().isdigit():
        return await m.answer("Нужно число event_id.")
    await state.update_data(event_id=int(m.text.strip()))
    await state.set_state(AdminCreateBroadcast.audience)
    await m.answer("Выберите аудиторию:", reply_markup=audience_kb())


@router.message(AdminCreateBroadcast.custom_text)
async def bc_custom_text(m: Message, state: FSMContext):
    await state.update_data(text=m.html_text)
    await state.set_state(AdminCreateBroadcast.custom_media)
    await m.answer("Пришлите медиа (фото/документ) или напишите 'нет'.")


@router.message(AdminCreateBroadcast.custom_media, F.text.casefold() == "нет")
async def bc_custom_media_skip(m: Message, state: FSMContext):
    await state.update_data(media=None)
    await state.set_state(AdminCreateBroadcast.audience)
    await m.answer("Выберите аудиторию:", reply_markup=audience_kb())


@router.message(AdminCreateBroadcast.custom_media, F.photo)
async def bc_custom_media_photo(m: Message, state: FSMContext):
    await state.update_data(media=("photo", m.photo[-1].file_id))
    await state.set_state(AdminCreateBroadcast.audience)
    await m.answer("Выберите аудиторию:", reply_markup=audience_kb())


@router.message(AdminCreateBroadcast.custom_media, F.document)
async def bc_custom_media_doc(m: Message, state: FSMContext):
    await state.update_data(media=("document", m.document.file_id))
    await state.set_state(AdminCreateBroadcast.audience)
    await m.answer("Выберите аудиторию:", reply_markup=audience_kb())


@router.callback_query(AdminBroadcastAudienceCb.filter())
async def bc_audience_select(c: CallbackQuery, callback_data: AdminBroadcastAudienceCb, state: FSMContext):
    await state.update_data(audience=callback_data.audience)
    await c.message.edit_reply_markup(reply_markup=audience_kb(selected=callback_data.audience))
    await c.answer()


@router.callback_query(F.data == "admin:aud:next")
async def bc_audience_next(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("audience"):
        return await c.answer("Сначала выберите аудиторию.", show_alert=True)

    await state.set_state(AdminCreateBroadcast.reminder_hours)
    await c.message.answer(f"Напоминание тем, кто не ответил: через сколько часов? (число). По умолчанию {settings.REMINDER_HOURS}")
    await c.answer()


@router.message(AdminCreateBroadcast.reminder_hours)
async def bc_reminder_hours(m: Message, state: FSMContext):
    txt = m.text.strip()
    hours = settings.REMINDER_HOURS
    if txt.isdigit():
        hours = int(txt)
    await state.update_data(reminder_hours=hours)
    await state.set_state(AdminCreateBroadcast.confirm)

    data = await state.get_data()
    summary = (
        "Подтвердите рассылку.\n"
        f"kind={data['kind']}\n"
        f"audience={data['audience']}\n"
        f"reminder_hours={data['reminder_hours']}\n"
        "Напишите 'да' или 'нет'."
    )
    await m.answer(summary)


@router.message(AdminCreateBroadcast.confirm)
async def bc_confirm(m: Message, state: FSMContext):
    if m.text.strip().lower() != "да":
        await state.clear()
        return await m.answer("Отменено.", reply_markup=admin_menu_kb())

    data = await state.get_data()
    kind = data["kind"]
    audience = data["audience"]
    reminder_hours = data["reminder_hours"]

    if kind == "event":
        b = await create_broadcast(
            kind="event",
            event_id=data["event_id"],
            text=None,
            media=None,
            created_by_admin_tg_id=m.from_user.id
        )
    else:
        b = await create_broadcast(
            kind="custom",
            event_id=None,
            text=data["text"],
            media=data.get("media"),
            created_by_admin_tg_id=m.from_user.id
        )

    await set_broadcast_audience(b.id, audience)
    await set_broadcast_reminder_hours(b.id, reminder_hours)
    await audit_log(m.from_user.id, "broadcast_create", f"broadcast_id={b.id} kind={kind} audience={audience}")

    await state.clear()

    await m.answer(f"Создана рассылка #{b.id}. Запускаю...", reply_markup=admin_menu_kb())
    await BroadcastService.run_broadcast(broadcast_id=b.id, bot=m.bot)


    MAX_MEDIA = 10


async def _admin_media_text(event_id: int) -> str:
    media = await list_event_media(event_id)
    if not media:
        return "Медиа пока нет.\n\nВыберите действие:"
    lines = ["Медиа в мероприятии:"]
    for i, (_id, mtype, _fid) in enumerate(media, start=1):
        lines.append(f"{i}) {mtype}")
    lines.append("")
    lines.append("Выберите действие:")
    return "\n".join(lines)


@router.callback_query(F.data.startswith("admin:media:add:"))
async def admin_media_add_start(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа.", show_alert=True)

    event_id = int(c.data.split(":")[-1])
    await state.set_state(AdminEditEvent.media_add)
    await state.update_data(event_id=event_id, media_buf=[])
    await smart_edit(
        c,
        "Пришлите фото/документы (можно несколько). Когда закончите — напишите <b>готово</b>.\n"
        f"Лимит на мероприятие: {MAX_MEDIA}.",
        reply_markup=admin_event_media_kb(event_id),
    )
    await c.answer()


@router.message(AdminEditEvent.media_add, F.photo)
async def admin_media_add_photo(m: Message, state: FSMContext):
    data = await state.get_data()
    event_id = data["event_id"]
    buf = data.get("media_buf") or []

    # проверяем общий лимит
    existing = await list_event_media(event_id)
    if len(existing) + len(buf) >= MAX_MEDIA:
        return await m.answer(f"Лимит {MAX_MEDIA} достигнут. Напишите <b>готово</b>.")

    buf.append(("photo", m.photo[-1].file_id))
    await state.update_data(media_buf=buf)
    await m.answer(f"Добавлено ({len(buf)}). Ещё или <b>готово</b>.")


@router.message(AdminEditEvent.media_add, F.document)
async def admin_media_add_doc(m: Message, state: FSMContext):
    data = await state.get_data()
    event_id = data["event_id"]
    buf = data.get("media_buf") or []

    existing = await list_event_media(event_id)
    if len(existing) + len(buf) >= MAX_MEDIA:
        return await m.answer(f"Лимит {MAX_MEDIA} достигнут. Напишите <b>готово</b>.")

    buf.append(("document", m.document.file_id))
    await state.update_data(media_buf=buf)
    await m.answer(f"Добавлено ({len(buf)}). Ещё или <b>готово</b>.")


@router.message(AdminEditEvent.media_add, F.text.casefold() == "готово")
async def admin_media_add_done(m: Message, state: FSMContext):
    data = await state.get_data()
    event_id = data["event_id"]
    buf = data.get("media_buf") or []
    if buf:
        await append_event_media(event_id, buf)

    await state.set_state(AdminEditEvent.media_menu)
    await m.answer("Готово. Медиа обновлено.")
    # показываем меню медиа как “один экран”
    fake_cb = type("X", (), {"message": m, "from_user": m.from_user, "answer": m.answer})  # не нужен
    await m.answer(await _admin_media_text(event_id), reply_markup=admin_event_media_kb(event_id))


@router.callback_query(F.data.startswith("admin:media:replace:"))
async def admin_media_replace_choose(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа.", show_alert=True)

    event_id = int(c.data.split(":")[-1])
    await state.set_state(AdminEditEvent.media_replace_choose)
    await state.update_data(event_id=event_id)
    await smart_edit(c, "Введите номер медиа для замены (1,2,3...):", reply_markup=admin_event_media_kb(event_id))
    await c.answer()


@router.message(AdminEditEvent.media_replace_choose)
async def admin_media_replace_choose_num(m: Message, state: FSMContext):
    txt = (m.text or "").strip()
    if not txt.isdigit():
        return await m.answer("Нужно число (номер медиа).")

    idx = int(txt)
    data = await state.get_data()
    event_id = data["event_id"]

    media = await list_event_media(event_id)
    if idx < 1 or idx > len(media):
        return await m.answer(f"Неверный номер. Сейчас медиа: 1..{len(media)}")

    await state.set_state(AdminEditEvent.media_replace_wait)
    await state.update_data(replace_idx=idx)
    await m.answer("Ок. Теперь пришлите новое фото/документ для замены.")


@router.message(AdminEditEvent.media_replace_wait, F.photo)
async def admin_media_replace_photo(m: Message, state: FSMContext):
    data = await state.get_data()
    event_id = data["event_id"]
    idx = data["replace_idx"]

    ok = await replace_event_media_by_index(event_id, idx, "photo", m.photo[-1].file_id)
    await state.set_state(AdminEditEvent.media_menu)

    if not ok:
        return await m.answer("Не получилось заменить (номер не найден).")

    await m.answer("Заменено ✅")
    await m.answer(await _admin_media_text(event_id), reply_markup=admin_event_media_kb(event_id))


@router.message(AdminEditEvent.media_replace_wait, F.document)
async def admin_media_replace_doc(m: Message, state: FSMContext):
    data = await state.get_data()
    event_id = data["event_id"]
    idx = data["replace_idx"]

    ok = await replace_event_media_by_index(event_id, idx, "document", m.document.file_id)
    await state.set_state(AdminEditEvent.media_menu)

    if not ok:
        return await m.answer("Не получилось заменить (номер не найден).")

    await m.answer("Заменено ✅")
    await m.answer(await _admin_media_text(event_id), reply_markup=admin_event_media_kb(event_id))


@router.callback_query(F.data.startswith("admin:media:delete:"))
async def admin_media_delete_choose(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        return await c.answer("Нет доступа.", show_alert=True)

    event_id = int(c.data.split(":")[-1])
    await state.set_state(AdminEditEvent.media_delete_choose)
    await state.update_data(event_id=event_id)
    await smart_edit(c, "Введите номер медиа для удаления (1,2,3...):", reply_markup=admin_event_media_kb(event_id))
    await c.answer()


@router.message(AdminEditEvent.media_delete_choose)
async def admin_media_delete_apply(m: Message, state: FSMContext):
    txt = (m.text or "").strip()
    if not txt.isdigit():
        return await m.answer("Нужно число (номер медиа).")

    idx = int(txt)
    data = await state.get_data()
    event_id = data["event_id"]

    ok = await delete_event_media_by_index(event_id, idx)
    await state.set_state(AdminEditEvent.media_menu)

    if not ok:
        media = await list_event_media(event_id)
        return await m.answer(f"Неверный номер. Сейчас медиа: 1..{len(media)}")

    await m.answer("Удалено ✅")
    await m.answer(await _admin_media_text(event_id), reply_markup=admin_event_media_kb(event_id))