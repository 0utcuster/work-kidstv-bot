import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.config import settings


class AntiFloodMiddleware(BaseMiddleware):
    def __init__(self):
        self._bucket: dict[int, list[float]] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any]
    ) -> Any:
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        uid = user.id
        now = time.monotonic()

        times = self._bucket.get(uid, [])
        times = [t for t in times if now - t <= settings.FLOOD_SECONDS]
        times.append(now)
        self._bucket[uid] = times

        if len(times) > settings.FLOOD_BURST:
            # тихо игнорируем, чтобы не раздражать
            return None

        return await handler(event, data)