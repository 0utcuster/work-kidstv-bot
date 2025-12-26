import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from app.config import settings
from app.db.session import init_db
from app.bot.routers import user, admin
from app.bot.middlewares.antiflood import AntiFloodMiddleware
from app.services.reminders import Reminders

logging.basicConfig(level=logging.INFO)

async def main():
    await init_db()

    bot = Bot(settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(AntiFloodMiddleware())
    dp.callback_query.middleware(AntiFloodMiddleware())

    dp.include_router(user.router)
    dp.include_router(admin.router)

    Reminders.start_scheduler()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())