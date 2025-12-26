import datetime as dt
from sqlalchemy import select, update
from app.db.session import SessionLocal
from app.db.models import Broadcast


async def create_broadcast(kind: str, event_id: int | None, text: str | None, media: tuple[str, str] | None, created_by_admin_tg_id: int) -> Broadcast:
    async with SessionLocal() as s:
        media_type = None
        media_file_id = None
        if media:
            media_type, media_file_id = media
        b = Broadcast(
            kind=kind,
            event_id=event_id,
            text=text,
            media_type=media_type,
            media_file_id=media_file_id,
            status="draft",
            created_by_admin_tg_id=created_by_admin_tg_id,
            created_at=dt.datetime.utcnow(),
        )
        s.add(b)
        await s.commit()
        await s.refresh(b)
        return b


async def get_broadcast(broadcast_id: int) -> Broadcast | None:
    async with SessionLocal() as s:
        res = await s.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
        return res.scalar_one_or_none()


async def list_broadcasts(limit: int = 20) -> list[Broadcast]:
    async with SessionLocal() as s:
        res = await s.execute(select(Broadcast).order_by(Broadcast.created_at.desc()).limit(limit))
        return list(res.scalars().all())


async def set_broadcast_status(broadcast_id: int, status: str, started_at=None, finished_at=None) -> None:
    async with SessionLocal() as s:
        vals = {"status": status}
        if started_at is not None:
            vals["started_at"] = started_at
        if finished_at is not None:
            vals["finished_at"] = finished_at
        await s.execute(update(Broadcast).where(Broadcast.id == broadcast_id).values(**vals))
        await s.commit()


async def set_broadcast_audience(broadcast_id: int, audience: str) -> None:
    async with SessionLocal() as s:
        await s.execute(update(Broadcast).where(Broadcast.id == broadcast_id).values(audience=audience))
        await s.commit()


async def set_broadcast_reminder_hours(broadcast_id: int, hours: int) -> None:
    async with SessionLocal() as s:
        await s.execute(update(Broadcast).where(Broadcast.id == broadcast_id).values(reminder_hours=hours))
        await s.commit()