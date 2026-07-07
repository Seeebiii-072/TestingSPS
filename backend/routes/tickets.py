import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from middleware.auth_middleware import get_current_user, get_optional_current_user, require_min_role
from models.ticket import TicketCategory, TicketSource, TicketStatus, TicketTeam
from models.user import User, UserRole
from schemas.ticket import TicketCreate, TicketDetailRead, TicketEscalation, TicketRead, TicketUpdate
from services import ticket_service

router = APIRouter(prefix="/tickets", tags=["tickets"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("", response_model=TicketDetailRead, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    payload: TicketCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_current_user)],
):
    return await ticket_service.create_ticket(db, payload, current_user, ip_address=_client_ip(request))


@router.get("", response_model=list[TicketRead])
async def list_tickets(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    status_filter: Annotated[TicketStatus | None, Query(alias="status")] = None,
    category: TicketCategory | None = None,
    team: TicketTeam | None = None,
    source: TicketSource | None = None,
    assigned_to_me: bool = False,
    requester_email: str | None = None,
):
    return await ticket_service.list_tickets(
        db,
        current_user,
        status_filter=status_filter,
        category=category,
        team=team,
        source=source,
        assigned_to_me=assigned_to_me,
        requester_email=requester_email,
    )


@router.get("/public/{ticket_number}", response_model=TicketDetailRead)
async def get_ticket_by_number(
    ticket_number: str,
    email: Annotated[str, Query(description="Requester email to verify ownership")],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Public endpoint to look up a ticket by ticket_number + requester email.
    No authentication required — used by the email link "View Ticket" button
    so that recipients can track their ticket status without logging in.
    """
    ticket = await ticket_service.get_ticket_by_number_and_email(db, ticket_number, email)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


@router.get("/{ticket_id}", response_model=TicketDetailRead)
async def get_ticket(
    ticket_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    ticket = await ticket_service.get_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    if not ticket_service.user_can_view_ticket(current_user, ticket):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return ticket


@router.patch("/{ticket_id}", response_model=TicketDetailRead)
async def update_ticket(
    ticket_id: uuid.UUID,
    payload: TicketUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_min_role(UserRole.AGENT))],
):
    return await ticket_service.update_ticket(db, ticket_id, payload, current_user, ip_address=_client_ip(request))


@router.post("/{ticket_id}/escalate", response_model=TicketDetailRead)
async def escalate_ticket(
    ticket_id: uuid.UUID,
    payload: TicketEscalation,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_min_role(UserRole.AGENT))],
):
    ticket = await ticket_service.get_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    if not ticket_service.user_can_view_ticket(current_user, ticket):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    return await ticket_service.escalate_ticket(
        db,
        ticket_id,
        payload.team,
        payload.note,
        current_user,
        ip_address=_client_ip(request),
    )
