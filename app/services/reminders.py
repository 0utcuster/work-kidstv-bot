import datetime as dt
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

from app.config import settings

_scheduler: AsyncIOScheduler | None = None


class Reminders:
    @staticmethod
    def start_scheduler():
        global _scheduler
        if _scheduler:
            return
        _scheduler = AsyncIOScheduler(timezone=settings.TIMEZONE)
        _scheduler.start()

    @staticmethod
    def schedule(job_id: str, run_at: dt.datetime, func, *args, **kwargs):
        if not _scheduler:
            Reminders.start_scheduler()
        _scheduler.add_job(func, trigger=DateTrigger(run_date=run_at), id=job_id, replace_existing=True, args=args, kwargs=kwargs)