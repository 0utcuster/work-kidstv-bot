from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, CallbackQuery,
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InputMediaPhoto,
)
from aiogram.fsm.context import FSMContext

from app.config import settings
from app.bot.states import UserOnboarding
from app.bot.keyboards.user_kb import (
    main_menu_kb, events_list_kb, event_card_kb, settings_kb
)
from app.bot.callbacks import EventsListCb, EventViewCb, EventReactCb, EventIcsCb
from app.db.repos.users import (
    upsert_user, set_subscribed, get_user_by_tg_id, set_profile, needs_onboarding
)
from app.services.events import (
    list_events, get_event_card, set_reaction,
    build_event_caption, list_my_interests, build_event_caption_brief
)
from app.services.ics import build_ics_file  # см. ниже файл app/services/ics.py

router = Router()
_LAST_LIST_PAGE: dict[int, int] = {}


def phone_request_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить телефон", request_contact=True)],
            [KeyboardButton(text="Пропустить")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def user_link_html(tg_id: int, username: str | None, display_name: str) -> str:
    name = (display_name or "").strip() or "Пользователь"
    if username:
        return f"<a href='https://t.me/{username}'>{name}</a>"
    return f"<a href='tg://user?id={tg_id}'>{name}</a>"


async def send_event_with_buttons(c: CallbackQuery, event_id: int):
    """
    Без дубля:
    - если несколько фото: 1 фото + подпись + кнопки (одно сообщение),
      остальные фото:
        - если >=2: альбомом
        - если =1: отдельным фото без подписи (иначе Telegram не даст media_group)
    """
    card = await get_event_card(event_id)
    kb = event_card_kb(event_id)
    chat_id = c.message.chat.id

    if card.media_group:
        first = card.media_group[0]
        rest = card.media_group[1:]

        # 1) первое фото как одно “главное” сообщение
        await c.bot.send_photo(
            chat_id=chat_id,
            photo=first.media,
            caption=card.caption,
            reply_markup=kb,
        )

        # 2) остальные фото без подписи/кнопок
        if len(rest) >= 2:
            clean = [InputMediaPhoto(media=m.media) for m in rest[:9]]
            await c.bot.send_media_group(chat_id=chat_id, media=clean)
        elif len(rest) == 1:
            await c.bot.send_photo(chat_id=chat_id, photo=rest[0].media)

        return

    # Одно медиа (photo/document)
    if card.poster_file_id:
        if card.poster_type == "photo":
            await c.bot.send_photo(
                chat_id=chat_id,
                photo=card.poster_file_id,
                caption=card.caption,
                reply_markup=kb,
            )
            return
        if card.poster_type == "document":
            await c.bot.send_document(
                chat_id=chat_id,
                document=card.poster_file_id,
                caption=card.caption,
                reply_markup=kb,
            )
            return

    # Нет медиа
    await c.message.answer(card.caption, reply_markup=kb)


@router.message(CommandStart())
async def start(m: Message, state: FSMContext):
    await upsert_user(m.from_user)

    if await needs_onboarding(m.from_user.id):
        await state.clear()
        await state.set_state(UserOnboarding.name)
        return await m.answer(
            "Привет! Как к Вам обращаться? Напишите Ваше имя.",
            reply_markup=ReplyKeyboardRemove(),
        )

    await m.answer("Привет! Выберите действие:", reply_markup=main_menu_kb())


@router.message(UserOnboarding.name)
async def onboarding_name(m: Message, state: FSMContext):
    name = (m.text or "").strip()
    if len(name) < 2:
        return await m.answer("Имя слишком короткое. Напишите, пожалуйста, ещё раз.")

    await state.update_data(display_name=name)
    await state.set_state(UserOnboarding.phone)
    await m.answer("Хотите — отправьте номер телефона (по желанию).", reply_markup=phone_request_kb())


@router.message(UserOnboarding.phone, F.contact)
async def onboarding_phone_contact(m: Message, state: FSMContext):
    data = await state.get_data()
    display_name = data["display_name"]
    phone = m.contact.phone_number or ""

    await set_profile(m.from_user.id, display_name=display_name, phone=phone)
    await state.clear()

    await m.answer(f"Спасибо, {display_name}! Сразу покажу грядущие мероприятия.", reply_markup=main_menu_kb())
    items, page, pages = await list_events(page=1)
    _LAST_LIST_PAGE[m.from_user.id] = page
    await m.answer("Выберите мероприятие:", reply_markup=events_list_kb(items, page, pages))


@router.message(UserOnboarding.phone, F.text.casefold() == "пропустить")
async def onboarding_phone_skip(m: Message, state: FSMContext):
    data = await state.get_data()
    display_name = data["display_name"]

    await set_profile(m.from_user.id, display_name=display_name, phone="")
    await state.clear()

    await m.answer(f"Спасибо, {display_name}! Сразу покажу грядущие мероприятия.", reply_markup=main_menu_kb())
    items, page, pages = await list_events(page=1)
    _LAST_LIST_PAGE[m.from_user.id] = page
    await m.answer("Выберите мероприятие:", reply_markup=events_list_kb(items, page, pages))


@router.message(F.text == "Грядущие мероприятия")
async def upcoming(m: Message):
    await upsert_user(m.from_user)
    items, page, pages = await list_events(page=1)
    _LAST_LIST_PAGE[m.from_user.id] = page
    await m.answer("Выберите мероприятие:", reply_markup=events_list_kb(items, page, pages))


@router.callback_query(EventsListCb.filter())
async def list_page(c: CallbackQuery, callback_data: EventsListCb):
    page = callback_data.page
    items, page, pages = await list_events(page=page)
    _LAST_LIST_PAGE[c.from_user.id] = page
    await c.message.edit_reply_markup(reply_markup=events_list_kb(items, page, pages))
    await c.answer()


@router.callback_query(EventViewCb.filter())
async def view_event(c: CallbackQuery, callback_data: EventViewCb):
    await send_event_with_buttons(c, callback_data.event_id)
    await c.answer()


@router.callback_query(EventIcsCb.filter())
async def add_to_calendar(c: CallbackQuery, callback_data: EventIcsCb):
    # генерим .ics и отправляем пользователю
    try:
        path, filename = await build_ics_file(callback_data.event_id)
        await c.message.answer_document(
            document=path,
            caption="📅 Добавьте в календарь (файл .ics)."
        )
        await c.answer("Готово!")
    except Exception:
        await c.answer("Не удалось сформировать .ics", show_alert=True)


@router.callback_query(EventReactCb.filter())
async def react(c: CallbackQuery, callback_data: EventReactCb):
    await set_reaction(
        tg_user=c.from_user,
        event_id=callback_data.event_id,
        reaction=callback_data.reaction,
    )

    if callback_data.reaction == "interested":
        # уведомление админу БЕЗ описания
        u = await get_user_by_tg_id(c.from_user.id)
        display_name = ((u.display_name if u else "") or (c.from_user.full_name or "")).strip()
        phone = (u.phone if u else "") or ""
        who = user_link_html(c.from_user.id, c.from_user.username, display_name)
        phone_part = f"\n📞 {phone}" if phone else ""

        event_text = await build_event_caption_brief(callback_data.event_id)

        notify_text = (
            "🔥 <b>Новый отклик: «Интересно»</b>\n"
            f"{who}{phone_part}\n\n"
            f"{event_text}"
        )

        for admin_id in settings.ADMIN_IDS:
            try:
                await c.bot.send_message(admin_id, notify_text, disable_web_page_preview=True)
            except Exception:
                pass

    await c.answer("Готово!")


@router.message(F.text == "Настройки")
async def settings_menu(m: Message):
    u = await get_user_by_tg_id(m.from_user.id)
    await m.answer("Настройки:", reply_markup=settings_kb(is_subscribed=bool(u and u.is_subscribed)))


@router.callback_query(F.data == "usr:sub")
async def sub(c: CallbackQuery):
    await set_subscribed(c.from_user.id, True)
    await c.message.edit_text("Вы подписались на рассылки.", reply_markup=settings_kb(True))
    await c.answer()


@router.callback_query(F.data == "usr:unsub")
async def unsub(c: CallbackQuery):
    await set_subscribed(c.from_user.id, False)
    await c.message.edit_text("Вы отписались от рассылок.", reply_markup=settings_kb(False))
    await c.answer()


@router.message(F.text.in_({"Мои интересы", "⭐ Мои интересы"}))
async def my_interests(m: Message):
    items = await list_my_interests(m.from_user.id)
    if not items:
        return await m.answer(
            "Пока нет отмеченных мероприятий.\n"
            "Нажмите «Грядущие мероприятия» и выберите то, что интересно 🙂"
        )
    await m.answer("Ваши интересы:\n" + "\n".join([f"• {x}" for x in items]))