import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from middleware.auth_middleware import require_roles
from models.user import User, UserRole
from schemas.ticket import ApprovalRequest, TicketDetailRead
from services.ticket_service import resolve_approval

router = APIRouter(prefix="/tickets", tags=["approvals"])

APPROVER_ROLES = {UserRole.SECURITY_ADMIN, UserRole.MANAGER, UserRole.ADMINISTRATOR}


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/{ticket_id}/approve", response_model=TicketDetailRead)
async def approve_ticket(
    ticket_id: uuid.UUID,
    payload: ApprovalRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(APPROVER_ROLES))],
):
    return await resolve_approval(db, ticket_id, payload, current_user, ip_address=_client_ip(request))
