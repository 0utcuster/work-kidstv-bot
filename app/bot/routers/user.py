from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, FSInputFile

from app.bot.keyboards.user_kb import main_menu_kb, events_list_kb, event_card_kb, settings_kb
from app.bot.callbacks import EventsListCb, EventViewCb, EventReactCb
from app.db.repos.users import upsert_user, set_subscribed, get_user_by_tg_id
from app.services.events import list_events, get_event_card, set_reaction, list_my_interests, get_event_for_ics
from app.services.ics import make_ics_file


router = Router()

# Память для "назад к списку" (в простом варианте)
_LAST_LIST_PAGE: dict[int, int] = {}


@router.message(CommandStart())
async def start(m: Message):
    await upsert_user(m.from_user)
    await m.answer("Привет! Я буду присылать афиши и собирать Ваш интерес.", reply_markup=main_menu_kb())


@router.message(F.text == "Грядущие мероприятия")
async def upcoming(m: Message):
    await upsert_user(m.from_user)
    page = 1
    items, page, pages = await list_events(page=page)
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
    event_id = callback_data.event_id
    card = await get_event_card(event_id)

    # Если альбом — отправляем media_group
    if card.media_group:
        await c.message.answer_media_group(media=card.media_group)
        await c.message.answer(card.caption, reply_markup=event_card_kb(event_id))
    else:
        if card.poster_file_id and card.poster_type == "photo":
            await c.message.answer_photo(photo=card.poster_file_id, caption=card.caption, reply_markup=event_card_kb(event_id))
        elif card.poster_file_id and card.poster_type == "document":
            await c.message.answer_document(document=card.poster_file_id, caption=card.caption, reply_markup=event_card_kb(event_id))
        else:
            await c.message.answer(card.caption, reply_markup=event_card_kb(event_id))

    await c.answer()


@router.callback_query(EventReactCb.filter())
async def react(c: CallbackQuery, callback_data: EventReactCb):
    await set_reaction(tg_user=c.from_user, event_id=callback_data.event_id, reaction=callback_data.reaction)
    await c.answer("Готово!")


@router.callback_query(F.data == "usr:back_to_list")
async def back_to_list(c: CallbackQuery):
    page = _LAST_LIST_PAGE.get(c.from_user.id, 1)
    items, page, pages = await list_events(page=page)
    await c.message.answer("Список мероприятий:", reply_markup=events_list_kb(items, page, pages))
    await c.answer()


@router.message(F.text == "Мои интересы")
async def my_interests(m: Message):
    items = await list_my_interests(m.from_user.id)
    if not items:
        return await m.answer("Пока пусто. Отметьте какое-нибудь мероприятие как «Интересно».", reply_markup=main_menu_kb())
    text = "Ваши «Интересно»:\n" + "\n".join([f"• {t}" for t in items[:40]])
    await m.answer(text, reply_markup=main_menu_kb())


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


@router.callback_query(F.data.startswith("usr:ics:"))
async def send_ics(c: CallbackQuery):
    event_id = int(c.data.split(":")[-1])
    ev = await get_event_for_ics(event_id)
    if not ev:
        return await c.answer("Не найдено.", show_alert=True)

    path = make_ics_file(ev)
    await c.message.answer_document(FSInputFile(path), caption="Файл для добавления в календарь (.ics)")
    await c.answer()