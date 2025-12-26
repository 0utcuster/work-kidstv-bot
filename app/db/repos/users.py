import datetime as dt

from aiogram.types import User as TgUser
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.db.models import User


async def upsert_user(tg_user: TgUser) -> User:
    """
    Создаёт/обновляет пользователя в БД.
    """
    async with SessionLocal() as s:
        res = await s.execute(select(User).where(User.tg_id == tg_user.id))
        u = res.scalar_one_or_none()

        if u:
            u.username = tg_user.username
            u.full_name = (tg_user.full_name or "").strip()
            u.last_seen_at = dt.datetime.utcnow() if hasattr(u, "last_seen_at") else None
            u.is_active = True if hasattr(u, "is_active") else True
            await s.commit()
            return u

        # ВАЖНО: ставим display_name пустым — чтобы needs_onboarding() сработал
        u = User(
            tg_id=tg_user.id,
            username=tg_user.username,
            full_name=(tg_user.full_name or "").strip(),
            display_name="",
            phone="",
            is_active=True,
            is_subscribed=True,
            created_at=dt.datetime.utcnow() if hasattr(User, "created_at") else None,
            last_seen_at=dt.datetime.utcnow() if hasattr(User, "last_seen_at") else None,
        )
        s.add(u)

        try:
            await s.commit()
        except IntegrityError:
            await s.rollback()
            u = (await s.execute(select(User).where(User.tg_id == tg_user.id))).scalar_one()
        return u


async def get_user_by_tg_id(tg_id: int) -> User | None:
    async with SessionLocal() as s:
        res = await s.execute(select(User).where(User.tg_id == tg_id))
        return res.scalar_one_or_none()


async def set_subscribed(tg_id: int, val: bool) -> None:
    """
    Для меню настроек пользователя.
    """
    async with SessionLocal() as s:
        await s.execute(
            update(User)
            .where(User.tg_id == tg_id)
            .values(is_subscribed=val)
        )
        await s.commit()


async def set_profile(tg_id: int, display_name: str, phone: str = "") -> None:
    """
    Онбординг: сохраняем имя + телефон (по желанию).
    """
    async with SessionLocal() as s:
        await s.execute(
            update(User)
            .where(User.tg_id == tg_id)
            .values(
                display_name=(display_name or "").strip(),
                phone=(phone or "").strip()
            )
        )
        await s.commit()


async def needs_onboarding(tg_id: int) -> bool:
    """
    True если пользователь ещё не ввёл имя (display_name пустой).
    """
    async with SessionLocal() as s:
        u = (await s.execute(select(User).where(User.tg_id == tg_id))).scalar_one_or_none()
        if not u:
            return True
        return not bool((getattr(u, "display_name", "") or "").strip())


async def set_user_active(tg_id: int, is_active: bool) -> None:
    """
    Для рассылок: если бот заблокирован/недоступен — выключаем пользователя.
    """
    async with SessionLocal() as s:
        await s.execute(
            update(User)
            .where(User.tg_id == tg_id)
            .values(is_active=is_active)
        )
        await s.commit()