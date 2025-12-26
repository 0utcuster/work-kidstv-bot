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
                msg = await BroadcastService._send_event(bot, tg_id, b.event_id)
            else:
                msg = await BroadcastService._send_custom(bot, tg_id, b.text or "", b.media_type, b.media_file_id)

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
            media = (await s.execute(select(EventMedia).where(EventMedia.event_id == event_id))).scalars().all()

        if not ev:
            return await bot.send_message(tg_id, "Мероприятие не найдено.")
        caption = _build_caption(ev)

        # альбом фото
        if len(media) >= 2 and all(m.media_type == "photo" for m in media):
            from aiogram.types import InputMediaPhoto
            group = [InputMediaPhoto(media=m.file_id) for m in media[:10]]
            await bot.send_media_group(tg_id, media=group)
            return await bot.send_message(tg_id, caption)

        if len(media) == 1:
            m0 = media[0]
            if m0.media_type == "photo":
                return await bot.send_photo(tg_id, photo=m0.file_id, caption=caption)
            return await bot.send_document(tg_id, document=m0.file_id, caption=caption)

        return await bot.send_message(tg_id, caption)

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
            elif b.audience == "active":
                pass
            elif b.audience == "all":
                pass
            elif b.audience == "ever_interested":
                base = base.join(EventReaction, EventReaction.user_id == User.id).where(EventReaction.reaction == "interested")
            elif b.audience == "no_response" and b.kind == "event" and b.event_id:
                # пользователи без реакции на это событие
                reacted = select(EventReaction.user_id).where(EventReaction.event_id == b.event_id)
                base = base.where(User.id.not_in(reacted))

            res = await s.execute(base.distinct())
            return [r[0] for r in res.all()]

    @staticmethod
    async def _run_reminder(broadcast_id: int, bot: Bot):
        # Напомнить тем, кто не отреагировал на event рассылку
        async with SessionLocal() as s:
            b = (await s.execute(select(Broadcast).where(Broadcast.id == broadcast_id))).scalar_one_or_none()
            if not b or b.kind != "event" or not b.event_id:
                return
            event_id = b.event_id

            # кому отправляли и кто не ответил
            sent_users = select(BroadcastRecipient.user_id).where(BroadcastRecipient.broadcast_id == broadcast_id, BroadcastRecipient.status == "sent")
            reacted = select(EventReaction.user_id).where(EventReaction.event_id == event_id)
            targets = (await s.execute(select(User.id, User.tg_id).where(User.id.in_(sent_users), User.id.not_in(reacted), User.is_active == True))).all()

        text = "Напоминание: если Вам интересно мероприятие, нажмите «✅ Интересно» в карточке события."

        # отправляем напоминание и сразу снова кидаем карточку события (без кнопок в этой версии, упрощённо)
        for user_id, tg_id in targets:
            try:
                await bot.send_message(tg_id, text)
                await BroadcastService._send_event(bot, tg_id, event_id)
            except Exception:
                continue