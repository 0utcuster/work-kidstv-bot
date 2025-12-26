import datetime as dt
from dataclasses import dataclass
from aiogram.types import InputMediaPhoto, InputMediaDocument
from sqlalchemy import select, func
from app.db.session import SessionLocal
from app.db.models import Event, EventMedia, EventReaction, User
from app.services.utils import parse_dt


@dataclass
class EventCard:
    caption: str
    poster_file_id: str | None
    poster_type: str | None
    media_group: list | None


PAGE_SIZE = 8


async def list_events(page: int = 1):
    async with SessionLocal() as s:
        total = (await s.execute(select(func.count()).select_from(Event).where(Event.status == "published"))).scalar_one()
        pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(1, min(page, pages))
        offset = (page - 1) * PAGE_SIZE

        res = await s.execute(
            select(Event).where(Event.status == "published").order_by(Event.starts_at.asc()).offset(offset).limit(PAGE_SIZE)
        )
        events = res.scalars().all()
        items = [(e.id, f"{e.title} · {e.starts_at.strftime('%d.%m %H:%M')}") for e in events]
        return items, page, pages


async def get_event_card(event_id: int) -> EventCard:
    async with SessionLocal() as s:
        ev = (await s.execute(select(Event).where(Event.id == event_id))).scalar_one_or_none()
        if not ev:
            return EventCard("Не найдено.", None, None, None)

        media = (await s.execute(select(EventMedia).where(EventMedia.event_id == event_id))).scalars().all()
        caption = _build_caption(ev)

        if len(media) >= 2 and all(m.media_type == "photo" for m in media):
            group = [InputMediaPhoto(media=m.file_id) for m in media[:10]]
            return EventCard(caption=caption, poster_file_id=None, poster_type=None, media_group=group)

        if len(media) == 1:
            m0 = media[0]
            return EventCard(caption=caption, poster_file_id=m0.file_id, poster_type=m0.media_type, media_group=None)

        return EventCard(caption=caption, poster_file_id=None, poster_type=None, media_group=None)


def _build_caption(ev: Event) -> str:
    lines = [
        f"<b>{ev.title}</b>",
        f"🕒 {ev.starts_at.strftime('%Y-%m-%d %H:%M')}",
        f"📍 {ev.location}",
    ]
    if ev.description:
        lines += ["", ev.description]
    if ev.url:
        lines += ["", f"🔗 {ev.url}"]
    return "\n".join(lines)


async def build_event_caption(event_id: int) -> str:
    async with SessionLocal() as s:
        ev = (await s.execute(select(Event).where(Event.id == event_id))).scalar_one_or_none()
        return _build_caption(ev) if ev else "Не найдено."


async def set_reaction(tg_user, event_id: int, reaction: str) -> None:
    async with SessionLocal() as s:
        u = (await s.execute(select(User).where(User.tg_id == tg_user.id))).scalar_one()
        existing = (await s.execute(select(EventReaction).where(EventReaction.event_id == event_id, EventReaction.user_id == u.id))).scalar_one_or_none()
        now = dt.datetime.utcnow()
        if existing:
            existing.reaction = reaction
            existing.reacted_at = now
        else:
            s.add(EventReaction(event_id=event_id, user_id=u.id, reaction=reaction, reacted_at=now))
        await s.commit()


async def list_my_interests(tg_id: int) -> list[str]:
    async with SessionLocal() as s:
        u = (await s.execute(select(User).where(User.tg_id == tg_id))).scalar_one_or_none()
        if not u:
            return []
        res = await s.execute(
            select(Event.title, Event.starts_at)
            .join(EventReaction, EventReaction.event_id == Event.id)
            .where(EventReaction.user_id == u.id, EventReaction.reaction == "interested")
            .order_by(Event.starts_at.asc())
        )
        rows = res.all()
        return [f"{t} · {d.strftime('%d.%m %H:%M')}" for t, d in rows]


async def reactions_report_text(event_id: int) -> str:
    async with SessionLocal() as s:
        ev = (await s.execute(select(Event).where(Event.id == event_id))).scalar_one_or_none()
        if not ev:
            return "Не найдено."

        res = await s.execute(
            select(User.tg_id, User.username, User.full_name, EventReaction.reaction, EventReaction.reacted_at)
            .join(EventReaction, EventReaction.user_id == User.id)
            .where(EventReaction.event_id == event_id)
            .order_by(EventReaction.reacted_at.desc())
        )
        rows = res.all()

        interested = []
        declined = []
        for tg_id, username, full_name, reaction, reacted_at in rows:
            link = f"https://t.me/{username}" if username else f"tg://user?id={tg_id}"
            who = f"<a href=\"{link}\">{(username or full_name or str(tg_id))}</a>"
            line = f"{who} ({reacted_at.strftime('%Y-%m-%d %H:%M')})"
            (interested if reaction == "interested" else declined).append(line)

        text = [f"<b>{ev.title}</b>"]
        text.append("")
        text.append(f"✅ Интересно: {len(interested)}")
        text += interested[:80] if interested else ["—"]
        text.append("")
        text.append(f"❌ Не интересно: {len(declined)}")
        text += declined[:80] if declined else ["—"]

        return "\n".join(text)


async def admin_list_published_events(limit: int = 50):
    async with SessionLocal() as s:
        res = await s.execute(select(Event.id, Event.title).where(Event.status == "published").order_by(Event.starts_at.asc()).limit(limit))
        return list(res.all())


async def get_event_for_ics(event_id: int) -> dict | None:
    async with SessionLocal() as s:
        ev = (await s.execute(select(Event).where(Event.id == event_id))).scalar_one_or_none()
        if not ev:
            return None
        return {
            "id": ev.id,
            "title": ev.title,
            "starts_at": ev.starts_at,
            "location": ev.location,
            "description": ev.description,
            "url": ev.url,
        }