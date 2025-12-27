from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InputMediaPhoto, InputMediaDocument
)
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import settings
from app.bot.states import UserOnboarding
from app.bot.keyboards.user_kb import (
    main_menu_kb, events_list_kb, event_card_kb, settings_kb,
    BTN_UPCOMING, BTN_INTERESTS, BTN_SETTINGS
)
from app.bot.callbacks import EventsListCb, EventViewCb, EventReactCb, EventIcsCb, EventMoreMediaCb
from app.db.repos.users import upsert_user, set_subscribed, get_user_by_tg_id, set_profile, needs_onboarding
from app.services.events import (
    list_events, get_event_card, set_reaction, list_my_interests,
    list_event_media, build_caption_short_no_desc
)
from app.services.ics import build_ics_file

from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models import Event


router = Router()
_LAST_LIST_PAGE: dict[int, int] = {}

SIGNUP_URL = "https://t.me/NikNadenka?text=%D0%97%D0%B4%D1%80%D0%B0%D0%B2%D1%81%D1%82%D0%B2%D1%83%D0%B9%D1%82%D0%B5%2C%20%D0%9D%D0%B0%D0%B4%D0%B5%D0%B6%D0%B4%D0%B0%21%20%D0%A5%D0%BE%D1%87%D1%83%20%D0%B7%D0%B0%D0%BF%D0%B8%D1%81%D0%B0%D1%82%D1%8C%D1%81%D1%8F%20%D0%BD%D0%B0%20%D1%83%D1%87%D0%B0%D1%81%D1%82%D0%B8%D0%B5%20%D0%B2%20%D0%BC%D0%B5%D1%80%D0%BE%D0%BF%D1%80%D0%B8%D1%8F%D1%82%D0%B8%D1%8F%D1%85%20%D0%B8%20%D1%83%D1%82%D0%BE%D1%87%D0%BD%D0%B8%D1%82%D1%8C%20%D1%83%D1%81%D0%BB%D0%BE%D0%B2%D0%B8%D1%8F"


def signup_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Записаться", url=SIGNUP_URL)
    kb.adjust(1)
    return kb.as_markup()


def phone_request_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить телефон", request_contact=True)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def user_link_html(tg_id: int, username: str | None, display_name: str) -> str:
    name = (display_name or "").strip() or "Пользователь"
    if username:
        return f"<a href='https://t.me/{username}'>{name}</a>"
    return f"<a href='tg://user?id={tg_id}'>{name}</a>"


@router.message(CommandStart())
async def start(m: Message, state: FSMContext):
    await upsert_user(m.from_user)

    if await needs_onboarding(m.from_user.id):
        await state.clear()
        await state.set_state(UserOnboarding.name)
        return await m.answer(
            "Привет! Как к Вам обращаться? Напишите Ваше имя.",
            reply_markup=ReplyKeyboardRemove()
        )

    await m.answer("Привет! Выберите действие:", reply_markup=main_menu_kb())


@router.message(UserOnboarding.name)
async def onboarding_name(m: Message, state: FSMContext):
    name = (m.text or "").strip()
    if len(name) < 2:
        return await m.answer("Имя слишком короткое. Напишите, пожалуйста, ещё раз.")

    await state.update_data(display_name=name)
    await state.set_state(UserOnboarding.phone)

    await m.answer(
        "Теперь отправьте, пожалуйста, Ваш номер телефона.\n"
        "Это нужно, чтобы мы могли связаться с Вами по мероприятию.",
        reply_markup=phone_request_kb()
    )


@router.message(UserOnboarding.phone, F.contact)
async def onboarding_phone_contact(m: Message, state: FSMContext):
    data = await state.get_data()
    display_name = data["display_name"]
    phone = m.contact.phone_number or ""

    if not phone:
        return await m.answer("Не получилось прочитать номер. Нажмите кнопку «📱 Отправить телефон» ещё раз.")

    await set_profile(m.from_user.id, display_name=display_name, phone=phone)
    await state.clear()

    await m.answer(f"Спасибо, {display_name}! Показываю ближайшие мероприятия 📅", reply_markup=main_menu_kb())
    items, page, pages = await list_events(page=1)
    _LAST_LIST_PAGE[m.from_user.id] = page
    await m.answer("Выберите мероприятие:", reply_markup=events_list_kb(items, page, pages))


@router.message(UserOnboarding.phone)
async def onboarding_phone_text_block(m: Message, state: FSMContext):
    await m.answer(
        "Пожалуйста, отправьте телефон кнопкой «📱 Отправить телефон».\n"
        "Telegram передаст номер корректно только через кнопку.",
        reply_markup=phone_request_kb()
    )


@router.message(F.text == BTN_UPCOMING)
async def upcoming(m: Message):
    await upsert_user(m.from_user)
    items, page, pages = await list_events(page=1)
    _LAST_LIST_PAGE[m.from_user.id] = page
    await m.answer("Выберите мероприятие:", reply_markup=events_list_kb(items, page, pages))


@router.callback_query(F.data == "noop")
async def noop(c: CallbackQuery):
    await c.answer()


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
    media = await list_event_media(event_id)
    has_more = len(media) >= 2

    kb = event_card_kb(event_id, has_more=has_more)

    if media:
        m0 = media[0]
        if m0.media_type == "photo":
            await c.message.answer_photo(photo=m0.file_id, caption=card.caption, reply_markup=kb)
        elif m0.media_type == "document":
            await c.message.answer_document(document=m0.file_id, caption=card.caption, reply_markup=kb)
        else:
            await c.message.answer(card.caption, reply_markup=kb)
    else:
        await c.message.answer(card.caption, reply_markup=kb)

    await c.answer()


@router.callback_query(EventMoreMediaCb.filter())
async def show_more_media(c: CallbackQuery, callback_data: EventMoreMediaCb):
    event_id = callback_data.event_id
    media = await list_event_media(event_id)
    if len(media) <= 1:
        return await c.answer("Больше афиш нет.", show_alert=True)

    tail = media[1:11]

    photos = [m for m in tail if m.media_type == "photo"]
    docs = [m for m in tail if m.media_type == "document"]

    if len(photos) >= 2:
        group = [InputMediaPhoto(media=m.file_id) for m in photos[:10]]
        await c.message.answer_media_group(media=group)
    elif len(photos) == 1:
        await c.message.answer_photo(photo=photos[0].file_id)

    if len(docs) >= 2:
        group = [InputMediaDocument(media=m.file_id) for m in docs[:10]]
        await c.message.answer_media_group(media=group)
    elif len(docs) == 1:
        await c.message.answer_document(document=docs[0].file_id)

    await c.answer()


@router.callback_query(EventIcsCb.filter())
async def send_ics(c: CallbackQuery, callback_data: EventIcsCb):
    ics = await build_ics_file(callback_data.event_id)
    if not ics:
        return await c.answer("Мероприятие не найдено.", show_alert=True)

    await c.message.answer_document(ics, caption="Файл для добавления в календарь 📅")
    await c.answer("Готово!")


@router.callback_query(EventReactCb.filter())
async def react(c: CallbackQuery, callback_data: EventReactCb):
    await set_reaction(
        tg_user=c.from_user,
        event_id=callback_data.event_id,
        reaction=callback_data.reaction
    )

    if callback_data.reaction == "interested":
        info_text = (
            "Условия участия и запись:\n"
            "📲 8-905-214-6666, Надежда\n"
            "💬 Telegram: @NikNadenka"
        )
        await c.message.answer(
            info_text,
            reply_markup=signup_kb(),
            disable_web_page_preview=True
        )

        u = await get_user_by_tg_id(c.from_user.id)
        display_name = ((u.display_name if u else "") or (c.from_user.full_name or "")).strip()
        phone = (u.phone if u else "") or ""
        who = user_link_html(c.from_user.id, c.from_user.username, display_name)
        phone_part = f"\n📞 {phone}" if phone else ""

        async with SessionLocal() as s:
            ev = (await s.execute(select(Event).where(Event.id == callback_data.event_id))).scalar_one_or_none()

        event_short = build_caption_short_no_desc(ev) if ev else "Мероприятие не найдено."

        notify_text = (
            "🔥 <b>Новый отклик: «Интересно»</b>\n"
            f"{who}{phone_part}\n\n"
            f"{event_short}"
        )

        for admin_id in settings.ADMIN_IDS:
            try:
                await c.bot.send_message(admin_id, notify_text, disable_web_page_preview=True)
            except Exception:
                pass

    await c.answer("Готово!")


@router.message(F.text == BTN_SETTINGS)
async def settings_menu(m: Message):
    u = await get_user_by_tg_id(m.from_user.id)
    await m.answer("⚙️ Настройки:", reply_markup=settings_kb(is_subscribed=bool(u and u.is_subscribed)))


@router.callback_query(F.data == "usr:sub")
async def sub(c: CallbackQuery):
    await set_subscribed(c.from_user.id, True)
    await c.message.edit_text("Вы подписались на рассылки 🔔", reply_markup=settings_kb(True))
    await c.answer()


@router.callback_query(F.data == "usr:unsub")
async def unsub(c: CallbackQuery):
    await set_subscribed(c.from_user.id, False)
    await c.message.edit_text("Вы отписались от рассылок 🔕", reply_markup=settings_kb(False))
    await c.answer()


@router.message(F.text.in_({BTN_INTERESTS, "Мои интересы", "⭐ Мои интересы"}))
async def my_interests(m: Message):
    items = await list_my_interests(m.from_user.id)
    if not items:
        return await m.answer(
            "Пока нет отмеченных мероприятий.\n"
            f"Нажмите «{BTN_UPCOMING}» и выберите то, что интересно 🙂"
        )
    await m.answer("⭐ Ваши интересы:\n" + "\n".join([f"• {x}" for x in items]))