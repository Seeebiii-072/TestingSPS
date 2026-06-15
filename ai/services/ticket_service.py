from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from ai.config.constants import (
    SLAStatus,
    TicketSource,
    TicketStatus,
    TimelineEventType,
)
from ai.schemas.ticket import (
    AssignmentRequest,
    EscalationRequest,
    ReplyRequest,
    ResolveRequest,
    Ticket,
    TicketCreate,
    TicketUpdate,
    TimelineEvent,
)


class TicketNotFoundError(LookupError):
    pass


class InvalidTicketActionError(ValueError):
    pass


class TicketRepository:
    def __init__(self) -> None:
        self._tickets: dict[str, Ticket] = {}
        self._year_counters: dict[int, int] = {}
        self._lock = RLock()

    def create(self, request: TicketCreate) -> Ticket:
        with self._lock:
            now = datetime.now(timezone.utc)
            year = now.year
            sequence = self._year_counters.get(year, 0) + 1
            self._year_counters[year] = sequence
            ticket_id = f"SPS-{year}-{sequence:03d}"
            snapshot_event = {
                TicketSource.EMAIL: TimelineEventType.EMAIL_EVENT,
                TicketSource.PORTAL_FORM: TimelineEventType.FORM_SUBMISSION,
                TicketSource.CHAT: TimelineEventType.CHAT_MESSAGE,
            }[request.source]
            ticket = Ticket(
                ticket_id=ticket_id,
                source=request.source,
                requester=request.requester,
                subject=request.subject,
                description=request.description,
                category=request.category,
                priority=request.priority,
                risk=request.risk,
                team=request.team,
                status=TicketStatus.OPEN,
                sla=request.sla,
                ai_summary=request.ai_summary,
                created_at=now,
                updated_at=now,
                timeline=[
                    self._event(
                        TimelineEventType.TICKET_CREATED,
                        body="Ticket created.",
                        visible=True,
                    ),
                    self._event(
                        snapshot_event,
                        body=request.source_snapshot.content,
                        visible=True,
                        details=request.source_snapshot.model_dump(mode="json"),
                    ),
                ],
            )
            self._tickets[ticket_id] = ticket
            return deepcopy(ticket)

    def get(self, ticket_id: str) -> Ticket:
        with self._lock:
            try:
                return deepcopy(self._tickets[ticket_id])
            except KeyError as exc:
                raise TicketNotFoundError(f"Ticket {ticket_id} was not found.") from exc

    def mutate(
        self,
        ticket_id: str,
        operation: Callable[[Ticket], None],
    ) -> Ticket:
        with self._lock:
            try:
                ticket = deepcopy(self._tickets[ticket_id])
            except KeyError as exc:
                raise TicketNotFoundError(
                    f"Ticket {ticket_id} was not found."
                ) from exc
            operation(ticket)
            ticket.updated_at = datetime.now(timezone.utc)
            self._tickets[ticket_id] = deepcopy(ticket)
            return deepcopy(ticket)

    def clear(self) -> None:
        with self._lock:
            self._tickets.clear()
            self._year_counters.clear()

    @staticmethod
    def _event(
        event_type: TimelineEventType,
        *,
        actor_id: str | None = None,
        body: str | None = None,
        visible: bool = False,
        details: dict | None = None,
    ) -> TimelineEvent:
        return TimelineEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            created_at=datetime.now(timezone.utc),
            actor_id=actor_id,
            body=body,
            visible_to_requester=visible,
            details=details or {},
        )


class TicketService:
    def __init__(self, repository: TicketRepository | None = None) -> None:
        self._repository = repository or ticket_repository

    def create(self, request: TicketCreate) -> Ticket:
        return self._repository.create(request)

    def get(self, ticket_id: str) -> Ticket:
        return self._repository.get(ticket_id)

    def update(self, ticket_id: str, request: TicketUpdate, actor_id: str) -> Ticket:
        changes = request.model_dump(exclude_unset=True)

        def operation(ticket: Ticket) -> None:
            for field, value in changes.items():
                setattr(ticket, field, value)
            if "ai_summary" in changes:
                ticket.timeline.append(
                    self._event(
                        TimelineEventType.AI_SUMMARY_EDITED,
                        actor_id=actor_id,
                        body="AI summary edited by agent.",
                    )
                )

        return self._repository.mutate(ticket_id, operation)

    def assign(self, ticket_id: str, request: AssignmentRequest) -> Ticket:
        def operation(ticket: Ticket) -> None:
            if ticket.status in {TicketStatus.RESOLVED, TicketStatus.CLOSED}:
                raise InvalidTicketActionError(
                    "Resolved or closed tickets cannot be assigned."
                )
            event_type = (
                TimelineEventType.REASSIGNMENT
                if ticket.assigned_agent_id
                else TimelineEventType.ASSIGNMENT
            )
            previous_agent = ticket.assigned_agent_id
            ticket.assigned_agent_id = request.agent_id
            ticket.status = TicketStatus.ASSIGNED
            ticket.timeline.append(
                self._event(
                    event_type,
                    actor_id=request.actor_id,
                    body=request.note,
                    details={
                        "previous_agent_id": previous_agent,
                        "agent_id": request.agent_id,
                    },
                )
            )
            self._status_event(ticket, request.actor_id, TicketStatus.ASSIGNED)

        return self._repository.mutate(ticket_id, operation)

    def escalate(self, ticket_id: str, request: EscalationRequest) -> Ticket:
        def operation(ticket: Ticket) -> None:
            if ticket.status in {TicketStatus.RESOLVED, TicketStatus.CLOSED}:
                raise InvalidTicketActionError(
                    "Resolved or closed tickets cannot be escalated."
                )
            ticket.status = TicketStatus.ESCALATED
            ticket.escalation_note = request.note
            if request.team is not None:
                ticket.team = request.team
            ticket.timeline.append(
                self._event(
                    TimelineEventType.ESCALATION,
                    actor_id=request.actor_id,
                    body=request.note,
                    details={"team": ticket.team.value},
                )
            )
            self._status_event(ticket, request.actor_id, TicketStatus.ESCALATED)

        return self._repository.mutate(ticket_id, operation)

    def resolve(self, ticket_id: str, request: ResolveRequest) -> Ticket:
        def operation(ticket: Ticket) -> None:
            if ticket.status == TicketStatus.CLOSED:
                raise InvalidTicketActionError("Closed tickets cannot be resolved.")
            now = datetime.now(timezone.utc)
            ticket.status = TicketStatus.RESOLVED
            ticket.sla.resolved_at = now
            ticket.sla.status = (
                SLAStatus.MET
                if ticket.sla.resolution_due_at is None
                or now <= ticket.sla.resolution_due_at
                else SLAStatus.BREACHED
            )
            ticket.timeline.append(
                self._event(
                    TimelineEventType.COMMENT,
                    actor_id=request.actor_id,
                    body=request.resolution,
                    visible=True,
                    details={"kind": "resolution"},
                )
            )
            self._status_event(ticket, request.actor_id, TicketStatus.RESOLVED)

        return self._repository.mutate(ticket_id, operation)

    def reply(
        self,
        ticket_id: str,
        request: ReplyRequest,
        channel: TicketSource,
    ) -> Ticket:
        if channel not in {TicketSource.EMAIL, TicketSource.PORTAL_FORM}:
            raise InvalidTicketActionError("Replies must use email or portal.")
        event_type = (
            TimelineEventType.EMAIL_REPLY
            if channel == TicketSource.EMAIL
            else TimelineEventType.PORTAL_REPLY
        )

        def operation(ticket: Ticket) -> None:
            if ticket.status == TicketStatus.CLOSED:
                raise InvalidTicketActionError(
                    "Closed tickets cannot receive replies."
                )
            ticket.timeline.append(
                self._event(
                    event_type,
                    actor_id=request.actor_id,
                    body=request.message,
                    visible=True,
                )
            )
            if ticket.sla.responded_at is None:
                ticket.sla.responded_at = datetime.now(timezone.utc)
            if ticket.status == TicketStatus.OPEN:
                ticket.status = TicketStatus.IN_PROGRESS
                self._status_event(
                    ticket,
                    request.actor_id,
                    TicketStatus.IN_PROGRESS,
                )

        return self._repository.mutate(ticket_id, operation)

    @staticmethod
    def _event(
        event_type: TimelineEventType,
        *,
        actor_id: str | None = None,
        body: str | None = None,
        visible: bool = False,
        details: dict | None = None,
    ) -> TimelineEvent:
        return TicketRepository._event(
            event_type,
            actor_id=actor_id,
            body=body,
            visible=visible,
            details=details,
        )

    def _status_event(
        self,
        ticket: Ticket,
        actor_id: str,
        status: TicketStatus,
    ) -> None:
        ticket.timeline.append(
            self._event(
                TimelineEventType.STATUS_CHANGE,
                actor_id=actor_id,
                body=f"Status changed to {status.value}.",
                visible=True,
                details={"status": status.value},
            )
        )


ticket_repository = TicketRepository()
