import Badge from '../common/Badge';
import TicketCard from './TicketCard';
import TicketPriorityBadge from './TicketPriorityBadge';
import TicketStatusBadge from './TicketStatusBadge';

function riskTone(risk) {
  if (risk === 'High Risk') return 'red';
  if (risk === 'Elevated') return 'amber';
  return 'green';
}

function formatUpdatedAt(value) {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value));
}

export default function TicketTable({ onSelectTicket, tickets }) {
  if (!tickets.length) {
    return (
      <div className="ticket-table-empty">
        <strong>No tickets match these filters.</strong>
        <span>Adjust the queue filters to see more tickets.</span>
      </div>
    );
  }

  return (
    <>
      <div className="ticket-table-wrap">
        <table className="ticket-table">
          <caption className="visually-hidden">
            Unified helpdesk ticket queue
          </caption>
          <thead>
            <tr>
              <th scope="col">Ticket ID</th>
              <th scope="col">Subject</th>
              <th scope="col">Requester</th>
              <th scope="col">Source</th>
              <th scope="col">Category</th>
              <th scope="col">Priority</th>
              <th scope="col">Risk</th>
              <th scope="col">Status</th>
              <th scope="col">Assigned Team</th>
              <th scope="col">SLA</th>
              <th scope="col">Updated</th>
            </tr>
          </thead>
          <tbody>
            {tickets.map((ticket) => (
              <tr
                key={ticket.id}
                role="link"
                tabIndex="0"
                aria-label={`Open ticket ${ticket.id}: ${ticket.subject}`}
                onClick={() => onSelectTicket(ticket)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    onSelectTicket(ticket);
                  }
                }}
              >
                <td>
                  <strong>{ticket.ticketNumber || ticket.id}</strong>
                </td>
                <td>
                  <strong>{ticket.subject}</strong>
                  <span>{ticket.requesterEmail}</span>
                </td>
                <td>{ticket.requesterName}</td>
                <td>
                  <Badge value={ticket.source} />
                </td>
                <td>{ticket.category}</td>
                <td>
                  <TicketPriorityBadge priority={ticket.priority} />
                </td>
                <td>
                  <Badge tone={riskTone(ticket.risk)}>{ticket.risk}</Badge>
                </td>
                <td>
                  <TicketStatusBadge status={ticket.status} />
                </td>
                <td>{ticket.assignedTeam}</td>
                <td>
                  <span className={ticket.sla.includes('minutes') || ticket.sla.includes('breached') ? 'ticket-sla-at-risk' : ''}>
                    {ticket.sla}
                  </span>
                </td>
                <td>{formatUpdatedAt(ticket.updatedAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="ticket-card-list">
        {tickets.map((ticket) => (
          <TicketCard key={ticket.id} onClick={onSelectTicket} ticket={ticket} />
        ))}
      </div>
    </>
  );
}
