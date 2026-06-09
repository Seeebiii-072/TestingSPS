from datetime import datetime, timedelta

from models.ticket import TicketPriority

SLA_HOURS: dict[TicketPriority, int] = {
    TicketPriority.CRITICAL: 4,
    TicketPriority.HIGH: 8,
    TicketPriority.MEDIUM: 24,
    TicketPriority.LOW: 72,
}


def compute_sla_due_at(created_at: datetime, priority: TicketPriority) -> datetime:
    return created_at + timedelta(hours=SLA_HOURS[priority])
