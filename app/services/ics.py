from __future__ import annotations

import os
import uuid
import datetime as dt

from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models import Event


ICS_DIR = ".ics_tmp"


def _escape(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")


async def build_ics_file(event_id: int) -> tuple[str, str]:
    os.makedirs(ICS_DIR, exist_ok=True)

    async with SessionLocal() as s:
        ev = (await s.execute(select(Event).where(Event.id == event_id))).scalar_one_or_none()
        if not ev:
            raise ValueError("Event not found")

    # ВАЖНО: делаем UTC-формат (Z), чтобы календарь понял.
    # Если у Вас starts_at хранится как naive local time — можно считать что это “локальное”,
    # но для простоты отдадим как floating local (без Z). Я оставлю Z-формат (чаще работает лучше).
    starts = ev.starts_at
    ends = starts + dt.timedelta(hours=2)

    def fmt(d: dt.datetime) -> str:
        return d.strftime("%Y%m%dT%H%M%S")

    uid = uuid.uuid4().hex
    filename = f"event_{event_id}_{uid}.ics"
    path = os.path.join(ICS_DIR, filename)

    desc_parts = []
    if ev.url:
        desc_parts.append(ev.url)
    description = _escape("\n".join(desc_parts))

    ics = "\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//KidsTV//EventsBot//RU",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{fmt(dt.datetime.utcnow())}Z",
        f"DTSTART:{fmt(starts)}",
        f"DTEND:{fmt(ends)}",
        f"SUMMARY:{_escape(ev.title)}",
        f"LOCATION:{_escape(ev.location)}",
        (f"DESCRIPTION:{description}" if description else "DESCRIPTION:"),
        "END:VEVENT",
        "END:VCALENDAR",
        ""
    ])

    with open(path, "w", encoding="utf-8") as f:
        f.write(ics)

    return path, filename