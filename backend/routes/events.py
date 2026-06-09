import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from middleware.auth_middleware import require_min_role
from models.user import User, UserRole
from schemas.ticket import TimelineEventCreate, TimelineEventRead
from services.ticket_service import add_timeline_event

router = APIRouter(prefix="/tickets", tags=["events"])


@router.post("/{ticket_id}/events", response_model=TimelineEventRead, status_code=status.HTTP_201_CREATED)
async def create_event(
    ticket_id: uuid.UUID,
    payload: TimelineEventCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_min_role(UserRole.AGENT))],
):
    return await add_timeline_event(db, ticket_id, payload, current_user)
