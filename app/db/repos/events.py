# app/db/repos/events.py
from sqlalchemy import select, update, delete
from app.db.session import SessionLocal
from app.db.models import Event, EventMedia
from app.services.utils import parse_dt


async def admin_list_events(limit: int = 50):
    """
    Возвращаем кортежи (id, title, status),
    потому что admin_events_kb распаковывает:
      for event_id, title, status in events:
    """
    async with SessionLocal() as s:
        res = await s.execute(
            select(Event.id, Event.title, Event.status)
            .order_by(Event.created_at.desc())
            .limit(limit)
        )
        return list(res.all())


async def get_event(event_id: int) -> Event | None:
    async with SessionLocal() as s:
        res = await s.execute(select(Event).where(Event.id == event_id))
        return res.scalar_one_or_none()


async def create_event(
    title: str,
    starts_at: str,
    location: str,
    description: str,
    url: str,
    created_by_admin_tg_id: int,
) -> Event:
    async with SessionLocal() as s:
        ev = Event(
            title=title,
            starts_at=parse_dt(starts_at),
            location=location,
            description=description,
            url=url,
            status="draft",
            created_by_admin_tg_id=created_by_admin_tg_id,
        )
        s.add(ev)
        await s.commit()
        await s.refresh(ev)
        return ev


async def update_event_field(event_id: int, field: str, value: str) -> None:
    values = {field: value}
    if field == "starts_at":
        values[field] = parse_dt(value)

    async with SessionLocal() as s:
        await s.execute(
            update(Event)
            .where(Event.id == event_id)
            .values(**values)
        )
        await s.commit()


async def set_event_status(event_id: int, status: str) -> None:
    async with SessionLocal() as s:
        await s.execute(
            update(Event)
            .where(Event.id == event_id)
            .values(status=status)
        )
        await s.commit()


async def delete_event(event_id: int) -> None:
    async with SessionLocal() as s:
        await s.execute(delete(EventMedia).where(EventMedia.event_id == event_id))
        await s.execute(delete(Event).where(Event.id == event_id))
        await s.commit()


async def set_event_media(event_id: int, media: list[tuple[str, str]]) -> None:
    """
    Полная замена медиа.
    media: [("photo", file_id), ("document", file_id), ...]
    """
    async with SessionLocal() as s:
        await s.execute(delete(EventMedia).where(EventMedia.event_id == event_id))
        for media_type, file_id in media:
            s.add(EventMedia(event_id=event_id, media_type=media_type, file_id=file_id))
        await s.commit()


# ====== NEW: управление медиа поштучно ======

async def list_event_media(event_id: int):
    async with SessionLocal() as s:
        res = await s.execute(
            select(EventMedia.id, EventMedia.media_type, EventMedia.file_id)
            .where(EventMedia.event_id == event_id)
            .order_by(EventMedia.id.asc())
        )
        return list(res.all())  # [(id, type, file_id), ...]


async def append_event_media(event_id: int, media: list[tuple[str, str]]) -> None:
    async with SessionLocal() as s:
        for media_type, file_id in media:
            s.add(EventMedia(event_id=event_id, media_type=media_type, file_id=file_id))
        await s.commit()


async def replace_event_media_by_index(event_id: int, index_1based: int, media_type: str, file_id: str) -> bool:
    async with SessionLocal() as s:
        rows = (await s.execute(
            select(EventMedia)
            .where(EventMedia.event_id == event_id)
            .order_by(EventMedia.id.asc())
        )).scalars().all()

        if index_1based < 1 or index_1based > len(rows):
            return False

        item = rows[index_1based - 1]
        item.media_type = media_type
        item.file_id = file_id
        await s.commit()
        return True


async def delete_event_media_by_index(event_id: int, index_1based: int) -> bool:
    async with SessionLocal() as s:
        ids = (await s.execute(
            select(EventMedia.id)
            .where(EventMedia.event_id == event_id)
            .order_by(EventMedia.id.asc())
        )).scalars().all()

        if index_1based < 1 or index_1based > len(ids):
            return False

        media_id = ids[index_1based - 1]
        await s.execute(delete(EventMedia).where(EventMedia.id == media_id))
        await s.commit()
        return True