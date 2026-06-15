import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import AsyncState from '../../components/common/AsyncState';
import Badge from '../../components/common/Badge';
import Card from '../../components/common/Card';
import StatCard from '../../components/common/StatCard';
import TicketPriorityBadge from '../../components/tickets/TicketPriorityBadge';
import TicketStatusBadge from '../../components/tickets/TicketStatusBadge';
import { getTickets } from '../../services/ticketService.js';

export default function SecurityDashboard() {
  const [tickets, setTickets] = useState([]);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    getTickets()
      .then(setTickets)
      .catch(() => setError('Security tickets could not be loaded from the backend.'))
      .finally(() => setIsLoading(false));
  }, []);

  if (error) return <AsyncState type="error" title="Security dashboard unavailable" description={error} />;
  if (isLoading) return <AsyncState title="Loading security dashboard" description="Fetching security workload from the backend." />;

  const highRisk = tickets.filter((ticket) => ticket.riskLevel === 'high');
  const incidents = tickets.filter((ticket) => ticket.category === 'cybersecurity');
  const approvals = tickets.filter((ticket) => ticket.status === 'waiting_approval');
  const phishingReports = incidents.filter((ticket) => /phish/i.test(`${ticket.subject} ${ticket.description || ''}`)).length;

  return (
    <section className="page security-dashboard-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Security operations</p>
          <h1>Security Dashboard</h1>
          <p>Monitor high-risk tickets, incidents, phishing reports, and approval activity.</p>
        </div>
        <Badge tone="red">Human review active</Badge>
      </div>

      <div className="security-stat-grid">
        <StatCard title="High-risk queue" value={highRisk.length} icon="HR" trend="Review" trendDirection="warning" description="Security and access tickets" />
        <StatCard title="Security incidents" value={incidents.length} icon="SI" trend="Active" description="Cybersecurity category tickets" />
        <StatCard title="Phishing reports" value={phishingReports} icon="PH" trend="Live" trendDirection="warning" description="Suspected phishing reports" />
        <StatCard title="Waiting approval" value={approvals.length} icon="AP" trend="Human action" trendDirection="warning" description="Sensitive requests awaiting review" />
      </div>

      <div className="security-dashboard-grid">
        <Card
          className="security-queue-card"
          title="High-Risk Queue"
          subtitle="Tickets requiring security operations review."
          actions={
            <Link className="dashboard-text-link" to="/security/approvals">
              Review approvals
            </Link>
          }
        >
          <div className="security-ticket-list">
            {highRisk.map((ticket) => (
              <Link key={ticket.id} to={`/agent/tickets/${ticket.id}`}>
                <span className="security-ticket-list__icon" aria-hidden="true">!</span>
                <span className="security-ticket-list__content">
                  <strong>{ticket.subject}</strong>
                  <small>{ticket.ticketNumber || ticket.id} - {ticket.requesterName}</small>
                </span>
                <span className="security-ticket-list__badges">
                  <TicketStatusBadge status={ticket.status} />
                  <TicketPriorityBadge priority={ticket.priority} />
                </span>
              </Link>
            ))}
          </div>
        </Card>

        <Card title="Approval Statistics" subtitle="Current high-risk review queue.">
          <div className="approval-stat-list">
            <div><span>Waiting Approval</span><strong>{approvals.length}</strong></div>
            <div><span>Approved/In Progress</span><strong>{highRisk.filter((ticket) => ticket.status === 'in_progress').length}</strong></div>
            <div><span>Closed</span><strong>{highRisk.filter((ticket) => ticket.status === 'closed').length}</strong></div>
            <div><span>Waiting User</span><strong>{highRisk.filter((ticket) => ticket.status === 'waiting_user').length}</strong></div>
          </div>
        </Card>
      </div>
    </section>
  );
}
