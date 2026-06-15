from fastapi import APIRouter, Header, HTTPException, status

from ai.config.constants import TicketSource
from ai.schemas.ticket import (
    AssignmentRequest,
    EscalationRequest,
    ReplyRequest,
    ResolveRequest,
    Ticket,
    TicketCreate,
    TicketUpdate,
)
from ai.services.ticket_service import (
    InvalidTicketActionError,
    TicketNotFoundError,
    TicketService,
)


router = APIRouter(prefix="/tickets", tags=["tickets"])


def _service_call(operation):
    try:
        return operation()
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidTicketActionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("", response_model=Ticket, status_code=status.HTTP_201_CREATED)
def create_ticket(request: TicketCreate) -> Ticket:
    return TicketService().create(request)


@router.get("/{ticket_id}", response_model=Ticket)
def get_ticket(ticket_id: str) -> Ticket:
    return _service_call(lambda: TicketService().get(ticket_id))


@router.patch("/{ticket_id}", response_model=Ticket)
def update_ticket(
    ticket_id: str,
    request: TicketUpdate,
    x_actor_id: str = Header(min_length=1, max_length=128),
) -> Ticket:
    return _service_call(
        lambda: TicketService().update(ticket_id, request, x_actor_id)
    )


@router.post("/{ticket_id}/assign", response_model=Ticket)
def assign_ticket(ticket_id: str, request: AssignmentRequest) -> Ticket:
    return _service_call(lambda: TicketService().assign(ticket_id, request))


@router.post("/{ticket_id}/escalate", response_model=Ticket)
def escalate_ticket(ticket_id: str, request: EscalationRequest) -> Ticket:
    return _service_call(lambda: TicketService().escalate(ticket_id, request))


@router.post("/{ticket_id}/resolve", response_model=Ticket)
def resolve_ticket(ticket_id: str, request: ResolveRequest) -> Ticket:
    return _service_call(lambda: TicketService().resolve(ticket_id, request))


@router.post("/{ticket_id}/replies/email", response_model=Ticket)
def email_reply(ticket_id: str, request: ReplyRequest) -> Ticket:
    return _service_call(
        lambda: TicketService().reply(ticket_id, request, TicketSource.EMAIL)
    )


@router.post("/{ticket_id}/replies/portal", response_model=Ticket)
def portal_reply(ticket_id: str, request: ReplyRequest) -> Ticket:
    return _service_call(
        lambda: TicketService().reply(ticket_id, request, TicketSource.PORTAL_FORM)
    )
