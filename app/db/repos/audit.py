from app.db.session import SessionLocal
from app.db.models import AuditLog


async def audit_log(admin_tg_id: int, action: str, details: str = "") -> None:
    async with SessionLocal() as s:
        s.add(AuditLog(admin_tg_id=admin_tg_id, action=action, details=details))
        await s.commit()