import { Link } from 'react-router-dom';
import Badge from '../common/Badge';
import Card from '../common/Card';

export default function HighRiskPanel({ tickets }) {
  const highRiskTickets = tickets.filter((ticket) => ticket.riskLevel === 'high' || ticket.risk === 'High Risk');

  return (
    <Card
      className="dashboard-panel high-risk-panel"
      title="High Risk Review"
      subtitle="Access and security tickets requiring attention."
      actions={<Badge tone="red">{highRiskTickets.length} require review</Badge>}
    >
      <div className="high-risk-list">
        {highRiskTickets.map((ticket) => (
          <Link
            className="high-risk-item"
            key={ticket.id}
            to={`/agent/tickets/${ticket.id}`}
          >
            <span className="high-risk-item__icon" aria-hidden="true">
              !
            </span>
            <span className="high-risk-item__content">
              <strong>{ticket.subject}</strong>
              <small>
                {ticket.ticketNumber || ticket.id} &middot; {ticket.requesterName}
              </small>
            </span>
            <span className="high-risk-item__badges">
              <Badge tone="red">High Risk</Badge>
              <Badge tone="amber">{ticket.statusLabel || ticket.status}</Badge>
            </span>
          </Link>
        ))}
      </div>
    </Card>
  );
}
