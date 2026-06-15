import Badge from '../common/Badge';
import TicketPriorityBadge from './TicketPriorityBadge';
import TicketStatusBadge from './TicketStatusBadge';

function riskTone(risk) {
  if (risk === 'High Risk') return 'red';
  if (risk === 'Elevated') return 'amber';
  return 'green';
}

export default function TicketCard({ onClick, ticket }) {
  return (
    <button
      className="ticket-card"
      type="button"
      aria-label={`Open ticket ${ticket.id}: ${ticket.subject}`}
      onClick={() => onClick(ticket)}
    >
      <span className="ticket-card__heading">
        <strong>{ticket.ticketNumber || ticket.id}</strong>
        <TicketStatusBadge status={ticket.status} />
      </span>
      <span className="ticket-card__subject">{ticket.subject}</span>
      <span className="ticket-card__requester">
        {ticket.requesterName} &middot; {ticket.assignedTeam}
      </span>
      <span className="ticket-card__badges">
        <Badge value={ticket.source} />
        <TicketPriorityBadge priority={ticket.priority} />
        <Badge tone={riskTone(ticket.risk)}>{ticket.risk}</Badge>
      </span>
      <span className="ticket-card__footer">
        <span>{ticket.category}</span>
        <strong>{ticket.sla}</strong>
      </span>
    </button>
  );
}
