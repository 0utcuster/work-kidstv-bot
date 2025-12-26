import datetime as dt
from aiogram.types import User as TgUser
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.db.models import User


async def upsert_user(tg_user: TgUser) -> User:
    async with SessionLocal() as s:
        q = select(User).where(User.tg_id == tg_user.id)
        res = await s.execute(q)
        u = res.scalar_one_or_none()

        if u:
            u.username = tg_user.username
            u.full_name = (tg_user.full_name or "").strip()
            u.last_seen_at = dt.datetime.utcnow()
            await s.commit()
            return u

        u = User(
            tg_id=tg_user.id,
            username=tg_user.username,
            full_name=(tg_user.full_name or "").strip(),
            is_active=True,
            is_subscribed=True,
        )
        s.add(u)
        try:
            await s.commit()
        except IntegrityError:
            await s.rollback()
            res2 = await s.execute(select(User).where(User.tg_id == tg_user.id))
            return res2.scalar_one()
        return u


async def get_user_by_tg_id(tg_id: int) -> User | None:
    async with SessionLocal() as s:
        res = await s.execute(select(User).where(User.tg_id == tg_id))
        return res.scalar_one_or_none()


async def set_subscribed(tg_id: int, val: bool) -> None:
    async with SessionLocal() as s:
        await s.execute(update(User).where(User.tg_id == tg_id).values(is_subscribed=val))
        await s.commit()


async def set_user_active(tg_id: int, val: bool) -> None:
    async with SessionLocal() as s:
        await s.execute(update(User).where(User.tg_id == tg_id).values(is_active=val))
        await s.commit()