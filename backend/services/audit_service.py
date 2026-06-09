import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from models.audit_log import AuditLog


async def write_audit_log(
    db: AsyncSession,
    *,
    action: str,
    channel: str,
    ticket_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    audit_entry = AuditLog(
        ticket_id=ticket_id,
        actor_id=actor_id,
        action=action,
        channel=channel,
        details=details,
        ip_address=ip_address,
    )
    db.add(audit_entry)
    return audit_entry
