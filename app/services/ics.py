import os
import datetime as dt
from uuid import uuid4

ICS_DIR = "./.ics_tmp"


def make_ics_file(ev: dict) -> str:
    os.makedirs(ICS_DIR, exist_ok=True)

    uid = f"{ev['id']}-{uuid4()}@tg-events-bot"
    dtstart = ev["starts_at"].strftime("%Y%m%dT%H%M%S")
    # по умолчанию длительность 2 часа
    dtend = (ev["starts_at"] + dt.timedelta(hours=2)).strftime("%Y%m%dT%H%M%S")

    title = _escape(ev["title"])
    location = _escape(ev.get("location", ""))
    description = _escape((ev.get("description", "") + ("\n" + ev["url"] if ev.get("url") else "")).strip())

    content = (
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        "PRODID:-//tg-events-bot//EN\n"
        "BEGIN:VEVENT\n"
        f"UID:{uid}\n"
        f"DTSTAMP:{dt.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}\n"
        f"DTSTART:{dtstart}\n"
        f"DTEND:{dtend}\n"
        f"SUMMARY:{title}\n"
        f"LOCATION:{location}\n"
        f"DESCRIPTION:{description}\n"
        "END:VEVENT\n"
        "END:VCALENDAR\n"
    )

    path = os.path.join(ICS_DIR, f"event_{ev['id']}_{uuid4().hex}.ics")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")