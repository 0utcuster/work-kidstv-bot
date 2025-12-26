import datetime as dt
from sqlalchemy import select, update, delete
from app.db.session import SessionLocal
from app.db.models import Event, EventMedia
from app.services.utils import parse_dt


async def admin_list_events(limit: int = 50):
    async with SessionLocal() as s:
        res = await s.execute(select(Event).order_by(Event.starts_at.asc()).limit(limit))
        events = res.scalars().all()
        return [(e.id, e.title, e.status) for e in events]


async def get_event(event_id: int) -> Event | None:
    async with SessionLocal() as s:
        res = await s.execute(select(Event).where(Event.id == event_id))
        return res.scalar_one_or_none()


async def create_event(title: str, starts_at: str, location: str, description: str, url: str, created_by_admin_tg_id: int) -> Event:
    async with SessionLocal() as s:
        ev = Event(
            title=title,
            starts_at=parse_dt(starts_at),
            location=location,
            description=description,
            url=url,
            status="draft",
            created_by_admin_tg_id=created_by_admin_tg_id,
            created_at=dt.datetime.utcnow(),
            updated_at=dt.datetime.utcnow(),
        )
        s.add(ev)
        await s.commit()
        await s.refresh(ev)
        return ev


async def update_event_field(event_id: int, field: str, value: str) -> None:
    vals = {field: value, "updated_at": dt.datetime.utcnow()}
    if field == "starts_at":
        vals["starts_at"] = parse_dt(value)
        vals.pop("starts_at", None)
        vals["starts_at"] = parse_dt(value)
        vals.pop(field, None)
    async with SessionLocal() as s:
        if field == "starts_at":
            await s.execute(update(Event).where(Event.id == event_id).values(starts_at=parse_dt(value), updated_at=dt.datetime.utcnow()))
        else:
            await s.execute(update(Event).where(Event.id == event_id).values(**vals))
        await s.commit()


async def set_event_status(event_id: int, status: str) -> None:
    async with SessionLocal() as s:
        await s.execute(update(Event).where(Event.id == event_id).values(status=status, updated_at=dt.datetime.utcnow()))
        await s.commit()


async def delete_event(event_id: int) -> None:
    async with SessionLocal() as s:
        await s.execute(delete(Event).where(Event.id == event_id))
        await s.commit()


async def set_event_media(event_id: int, media: list[tuple[str, str]]) -> None:
    async with SessionLocal() as s:
        await s.execute(delete(EventMedia).where(EventMedia.event_id == event_id))
        for media_type, file_id in media:
            s.add(EventMedia(event_id=event_id, media_type=media_type, file_id=file_id))
        await s.commit()