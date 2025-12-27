import asyncio
import datetime as dt

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramBadRequest

from sqlalchemy import select, update, func

from app.config import settings
from app.db.session import SessionLocal
from app.db.models import Broadcast, User, Event, EventMedia, BroadcastRecipient, EventReaction
from app.db.repos.broadcasts import get_broadcast, set_broadcast_status
from app.db.repos.users import set_user_active
from app.db.repos.audit import audit_log
from app.services.reminders import Reminders
from app.services.events import _build_caption
from app.bot.keyboards.user_kb import event_card_kb
from app.services.events import list_event_media


AUDIENCE_EXPLAIN = {
    "all": "Все активные пользователи бота (is_active=True).",
    "active": "То же самое, что all (оставлено на будущее для доп. фильтров).",
    "subscribed": "Только подписанные на рассылки (is_subscribed=True).",
    "ever_interested": "Пользователи, которые когда-либо нажимали «Интересно» на любых мероприятиях.",
    "no_response": "Только для рассылки по событию: активные, кто ещё НЕ реагировал на это событие.",
}


class BroadcastService:
    @staticmethod
    async def run_broadcast(broadcast_id: int, bot: Bot):
        b = await get_broadcast(broadcast_id)
        if not b:
            return

        await set_broadcast_status(broadcast_id, "running", started_at=dt.datetime.utcnow())
        await audit_log(b.created_by_admin_tg_id, "broadcast_run", f"broadcast_id={broadcast_id}")

        recipients = await BroadcastService._select_recipients(b)
        total = len(recipients)

        # записываем recipients в таблицу
        async with SessionLocal() as s:
            for uid in recipients:
                s.add(BroadcastRecipient(broadcast_id=broadcast_id, user_id=uid, status="pending"))
            await s.commit()

        sent_ok = 0
        failed = 0
        delay = 1.0 / max(1, settings.BROADCAST_RPS)

        for user_id in recipients:
            ok = await BroadcastService._send_to_user(bot, b, user_id)
            if ok:
                sent_ok += 1
            else:
                failed += 1
            await asyncio.sleep(delay)

        await set_broadcast_status(broadcast_id, "done", finished_at=dt.datetime.utcnow())

        # итог админу: сколько отправлено
        try:
            expl = AUDIENCE_EXPLAIN.get(b.audience, b.audience)
            await bot.send_message(
                b.created_by_admin_tg_id,
                (
                    f"✅ <b>Рассылка завершена</b>\n"
                    f"• broadcast_id: {b.id}\n"
                    f"• kind: {b.kind}\n"
                    f"• audience: {b.audience} — {expl}\n"
                    f"• всего получателей: {total}\n"
                    f"• отправлено: {sent_ok}\n"
                    f"• ошибок: {failed}"
                ),
                disable_web_page_preview=True,
            )
        except Exception:
            pass

        # планируем напоминание тем, кто не ответил (только для kind=event)
        if b.kind == "event" and b.event_id:
            run_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=b.reminder_hours)
            job_id = f"rem_{broadcast_id}"
            Reminders.schedule(job_id, run_at, BroadcastService._run_reminder, broadcast_id, bot)

    @staticmethod
    async def _send_to_user(bot: Bot, b: Broadcast, user_id: int) -> bool:
        async with SessionLocal() as s:
            u = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
            tg_id = u.tg_id

        try:
            if b.kind == "event" and b.event_id:
                await BroadcastService._send_event(bot, tg_id, b.event_id)
            else:
                await BroadcastService._send_custom(bot, tg_id, b.text or "", b.media_type, b.media_file_id)

            async with SessionLocal() as s:
                await s.execute(
                    update(BroadcastRecipient)
                    .where(BroadcastRecipient.broadcast_id == b.id, BroadcastRecipient.user_id == user_id)
                    .values(status="sent", sent_at=dt.datetime.utcnow(), error=None)
                )
                await s.commit()
            return True

        except TelegramForbiddenError:
            await set_user_active(tg_id, False)
            async with SessionLocal() as s:
                await s.execute(
                    update(BroadcastRecipient)
                    .where(BroadcastRecipient.broadcast_id == b.id, BroadcastRecipient.user_id == user_id)
                    .values(status="failed", error="forbidden")
                )
                await s.commit()
            return False

        except TelegramRetryAfter as e:
            await asyncio.sleep(int(e.retry_after) + 1)
            return await BroadcastService._send_to_user(bot, b, user_id)

        except TelegramBadRequest as e:
            async with SessionLocal() as s:
                await s.execute(
                    update(BroadcastRecipient)
                    .where(BroadcastRecipient.broadcast_id == b.id, BroadcastRecipient.user_id == user_id)
                    .values(status="failed", error=str(e))
                )
                await s.commit()
            return False

        except Exception as e:
            async with SessionLocal() as s:
                await s.execute(
                    update(BroadcastRecipient)
                    .where(BroadcastRecipient.broadcast_id == b.id, BroadcastRecipient.user_id == user_id)
                    .values(status="failed", error=repr(e))
                )
                await s.commit()
            return False

    @staticmethod
    async def _send_event(bot: Bot, tg_id: int, event_id: int):
        async with SessionLocal() as s:
            ev = (await s.execute(select(Event).where(Event.id == event_id))).scalar_one_or_none()
        if not ev:
            return await bot.send_message(tg_id, "Мероприятие не найдено.")

        caption = _build_caption(ev)

        media = await list_event_media(event_id)
        has_more = len(media) >= 2
        kb = event_card_kb(event_id, has_more=has_more)

        # ВАЖНО: “одно сообщение” с кнопками (иначе альбом без клавиатуры)
        if media:
            m0 = media[0]
            if m0.media_type == "photo":
                return await bot.send_photo(tg_id, photo=m0.file_id, caption=caption, reply_markup=kb)
            if m0.media_type == "document":
                return await bot.send_document(tg_id, document=m0.file_id, caption=caption, reply_markup=kb)

        return await bot.send_message(tg_id, caption, reply_markup=kb)

    @staticmethod
    async def _send_custom(bot: Bot, tg_id: int, text: str, media_type: str | None, media_file_id: str | None):
        if media_type and media_file_id:
            if media_type == "photo":
                return await bot.send_photo(tg_id, photo=media_file_id, caption=text)
            return await bot.send_document(tg_id, document=media_file_id, caption=text)
        return await bot.send_message(tg_id, text)

    @staticmethod
    async def _select_recipients(b: Broadcast) -> list[int]:
        async with SessionLocal() as s:
            base = select(User.id).where(User.is_active == True)

            if b.audience == "subscribed":
                base = base.where(User.is_subscribed == True)
            elif b.audience in {"active", "all"}:
                pass
            elif b.audience == "ever_interested":
                base = base.join(EventReaction, EventReaction.user_id == User.id).where(EventReaction.reaction == "interested")
            elif b.audience == "no_response" and b.kind == "event" and b.event_id:
                reacted = select(EventReaction.user_id).where(EventReaction.event_id == b.event_id)
                base = base.where(User.id.not_in(reacted))

            res = await s.execute(base.distinct())
            return [r[0] for r in res.all()]

    @staticmethod
    async def count_recipients(kind: str, audience: str, event_id: int | None) -> int:
        # для превью в админке: сколько пользователей попадёт
        async with SessionLocal() as s:
            q = select(func.count(func.distinct(User.id))).where(User.is_active == True)

            if audience == "subscribed":
                q = q.where(User.is_subscribed == True)
            elif audience in {"active", "all"}:
                pass
            elif audience == "ever_interested":
                q = q.join(EventReaction, EventReaction.user_id == User.id).where(EventReaction.reaction == "interested")
            elif audience == "no_response" and kind == "event" and event_id:
                reacted = select(EventReaction.user_id).where(EventReaction.event_id == event_id)
                q = q.where(User.id.not_in(reacted))

            return int((await s.execute(q)).scalar_one())

    @staticmethod
    async def _run_reminder(broadcast_id: int, bot: Bot):
        async with SessionLocal() as s:
            b = (await s.execute(select(Broadcast).where(Broadcast.id == broadcast_id))).scalar_one_or_none()
            if not b or b.kind != "event" or not b.event_id:
                return
            event_id = b.event_id

            sent_users = select(BroadcastRecipient.user_id).where(
                BroadcastRecipient.broadcast_id == broadcast_id, BroadcastRecipient.status == "sent"
            )
            reacted = select(EventReaction.user_id).where(EventReaction.event_id == event_id)

            targets = (await s.execute(
                select(User.id, User.tg_id).where(
                    User.id.in_(sent_users),
                    User.id.not_in(reacted),
                    User.is_active == True
                )
            )).all()

        text = "Напоминание: если Вам интересно мероприятие, нажмите «✅ Интересно» в карточке события."

        for _, tg_id in targets:
            try:
                await bot.send_message(tg_id, text)
                await BroadcastService._send_event(bot, tg_id, event_id)
            except Exception:
                continue