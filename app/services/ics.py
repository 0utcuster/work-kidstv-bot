import datetime as dt
import os
import uuid

from aiogram.types import FSInputFile
from sqlalchemy import select

from app.db.session import SessionLocal
from app.db.models import Event


def _dt_to_ics_local(dtobj: dt.datetime) -> str:
    # “плавающее” локальное время без TZ — максимально совместимо
    return dtobj.strftime("%Y%m%dT%H%M%S")


async def build_ics_file(event_id: int) -> FSInputFile | None:
    async with SessionLocal() as s:
        ev = (await s.execute(select(Event).where(Event.id == event_id))).scalar_one_or_none()
        if not ev:
            return None

    uid = uuid.uuid4().hex
    dtstamp = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dtstart = _dt_to_ics_local(ev.starts_at)

    summary = (ev.title or "Мероприятие").replace("\n", " ").strip()
    location = (ev.location or "").replace("\n", " ").strip()
    description = (ev.description or "").replace("\n", "\\n").strip()
    url = (ev.url or "").strip()

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//KidsTV Bot//Events//RU",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART:{dtstart}",
        f"SUMMARY:{summary}",
    ]
    if location:
        lines.append(f"LOCATION:{location}")
    if description:
        lines.append(f"DESCRIPTION:{description}")
    if url:
        lines.append(f"URL:{url}")
    lines += ["END:VEVENT", "END:VCALENDAR", ""]

    os.makedirs(".ics_tmp", exist_ok=True)
    path = os.path.join(".ics_tmp", f"event_{event_id}_{uid}.ics")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\r\n".join(lines))

    return FSInputFile(path, filename=f"event_{event_id}.ics")