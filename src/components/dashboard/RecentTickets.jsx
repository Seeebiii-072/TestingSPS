import { Link } from 'react-router-dom';
import Badge from '../common/Badge';
import Card from '../common/Card';

const statusTones = {
  open: 'blue',
  in_progress: 'blue',
  waiting_approval: 'amber',
  waiting_user: 'amber',
  resolved: 'green',
  closed: 'gray',
};

function formatUpdatedAt(value) {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value));
}

export default function RecentTickets({ tickets }) {
  const recentTickets = [...tickets]
    .sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt))
    .slice(0, 6);

  return (
    <Card
      className="dashboard-panel recent-tickets"
      title="Recent Tickets"
      subtitle="Latest activity across email, web form, and AI chat."
      actions={
        <Link className="dashboard-text-link" to="/agent/queue">
          View queue
        </Link>
      }
    >
      <div className="recent-tickets__scroll">
        <table className="recent-tickets__table">
          <caption className="visually-hidden">Recent helpdesk tickets</caption>
          <thead>
            <tr>
              <th scope="col">Ticket ID</th>
              <th scope="col">Subject</th>
              <th scope="col">Source</th>
              <th scope="col">Status</th>
              <th scope="col">Priority</th>
              <th scope="col">Updated</th>
            </tr>
          </thead>
          <tbody>
            {recentTickets.map((ticket) => (
              <tr key={ticket.id}>
                <td>
                  <Link to={`/agent/tickets/${ticket.id}`}>{ticket.ticketNumber || ticket.id}</Link>
                </td>
                <td>
                  <strong>{ticket.subject}</strong>
                  <span>{ticket.assignedTeam}</span>
                </td>
                <td>
                  <Badge value={ticket.source} />
                </td>
                <td>
                  <Badge tone={statusTones[ticket.status]}>{ticket.statusLabel || ticket.status}</Badge>
                </td>
                <td>
                  <Badge value={ticket.priority.toLowerCase()} />
                </td>
                <td>{formatUpdatedAt(ticket.updatedAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
