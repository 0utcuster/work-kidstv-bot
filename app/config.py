from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()


def _parse_int_list(v: str) -> list[int]:
    if not v:
        return []
    return [int(x.strip()) for x in v.split(",") if x.strip().isdigit()]


@dataclass(frozen=True)
class Settings:
    BOT_TOKEN: str
    ADMIN_IDS: list[int]
    TIMEZONE: str
    DATABASE_URL: str
    REMINDER_HOURS: int
    FLOOD_SECONDS: float
    FLOOD_BURST: int
    BROADCAST_RPS: int


settings = Settings(
    BOT_TOKEN=os.getenv("BOT_TOKEN", "").strip(),
    ADMIN_IDS=_parse_int_list(os.getenv("ADMIN_IDS", "")),
    TIMEZONE=os.getenv("TIMEZONE", "Europe/Amsterdam"),
    DATABASE_URL=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./bot.db"),
    REMINDER_HOURS=int(os.getenv("REMINDER_HOURS", "12")),
    FLOOD_SECONDS=float(os.getenv("FLOOD_SECONDS", "1.0")),
    FLOOD_BURST=int(os.getenv("FLOOD_BURST", "3")),
    BROADCAST_RPS=int(os.getenv("BROADCAST_RPS", "20")),
)

if not settings.BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is empty. Fill .env")