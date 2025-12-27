# app/db/repos/users.py
import datetime as dt

from aiogram.types import User as TgUser
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.db.models import User


async def upsert_user(tg_user: TgUser) -> User:
    """Создаёт/обновляет пользователя в БД."""
    async with SessionLocal() as s:
        u = (await s.execute(select(User).where(User.tg_id == tg_user.id))).scalar_one_or_none()

        if u:
            u.username = tg_user.username
            u.full_name = (tg_user.full_name or "").strip()
            u.last_seen_at = dt.datetime.utcnow()
            u.is_active = True
            await s.commit()
            return u

        # ВАЖНО: display_name/phone пустые -> онбординг обязателен
        u = User(
            tg_id=tg_user.id,
            username=tg_user.username,
            full_name=(tg_user.full_name or "").strip(),
            display_name="",
            phone="",
            is_active=True,
            is_subscribed=False,   # лучше так, подписку включает сам пользователь
            created_at=dt.datetime.utcnow(),
            last_seen_at=dt.datetime.utcnow(),
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
        return (await s.execute(select(User).where(User.tg_id == tg_id))).scalar_one_or_none()


async def set_subscribed(tg_id: int, val: bool) -> None:
    """Для меню настроек пользователя."""
    async with SessionLocal() as s:
        await s.execute(update(User).where(User.tg_id == tg_id).values(is_subscribed=val))
        await s.commit()


async def set_profile(tg_id: int, display_name: str, phone: str) -> None:
    """Онбординг: сохраняем имя + ОБЯЗАТЕЛЬНО телефон."""
    async with SessionLocal() as s:
        await s.execute(
            update(User)
            .where(User.tg_id == tg_id)
            .values(
                display_name=(display_name or "").strip(),
                phone=(phone or "").strip(),
            )
        )
        await s.commit()


async def needs_onboarding(tg_id: int) -> bool:
    """
    True если пользователь ещё не прошёл онбординг:
    нет имени ИЛИ нет телефона.
    """
    async with SessionLocal() as s:
        u = (await s.execute(select(User).where(User.tg_id == tg_id))).scalar_one_or_none()
        if not u:
            return True

        name_ok = bool((u.display_name or "").strip())
        phone_ok = bool((u.phone or "").strip())
        return not (name_ok and phone_ok)


async def set_user_active(tg_id: int, is_active: bool) -> None:
    """Для рассылок: если бот заблокирован/недоступен — выключаем пользователя."""
    async with SessionLocal() as s:
        await s.execute(update(User).where(User.tg_id == tg_id).values(is_active=is_active))
        await s.commit()