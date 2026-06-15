import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import AsyncState from '../../components/common/AsyncState';
import Badge from '../../components/common/Badge';
import Card from '../../components/common/Card';
import StatCard from '../../components/common/StatCard';
import TicketPriorityBadge from '../../components/tickets/TicketPriorityBadge';
import TicketStatusBadge from '../../components/tickets/TicketStatusBadge';
import { getTickets } from '../../services/ticketService.js';
import authService from '../../services/authService.js';

const quickActions = [
  {
    code: 'SR',
    title: 'Submit Request',
    description: 'Create a structured portal-form ticket.',
    to: '/requester/submit',
  },
  {
    code: 'AI',
    title: 'Start AI Chat',
    description: 'Get approved knowledge-base guidance.',
    to: '/requester/ai-chat',
  },
  {
    code: 'MT',
    title: 'View My Tickets',
    description: 'Track every request across all channels.',
    to: '/requester/tickets',
  },
];

export default function RequesterDashboard() {
  const [tickets, setTickets] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    setError('');
    setIsLoading(true);
    getTickets()
      .then(setTickets)
      .catch(() => setError('Your ticket summary could not be loaded from the backend.'))
      .finally(() => setIsLoading(false));
  }, [reloadKey]);

  if (error) return <AsyncState type="error" title="Requester dashboard unavailable" description={error} onAction={() => setReloadKey((value) => value + 1)} />;
  if (isLoading) return <AsyncState title="Loading requester dashboard" description="Preparing your ticket summary." />;

  const openTickets = tickets.filter(
    (ticket) => !['resolved', 'closed'].includes(ticket.status),
  );
  const resolvedTickets = tickets.filter((ticket) =>
    ['resolved', 'closed'].includes(ticket.status),
  );
  const waitingUser = tickets.filter((ticket) => ticket.status === 'waiting_user');
  const recentTickets = [...tickets]
    .sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt))
    .slice(0, 3);

  return (
    <section className="page requester-dashboard">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Requester portal</p>
          <h1>Welcome, {authService.getCurrentUser()?.email || 'Requester'}</h1>
          <p>
            Submit requests, get AI-guided help, and track every support channel
            from one workspace.
          </p>
        </div>
        <Badge tone="green">Portal available</Badge>
      </div>

      <div className="requester-dashboard-stats">
        <StatCard
          title="My open tickets"
          value={openTickets.length}
          icon="OT"
          trend="Active"
          description="Requests still in progress"
        />
        <StatCard
          title="Resolved tickets"
          value={resolvedTickets.length}
          icon="RT"
          trend="Complete"
          trendDirection="up"
          description="Requests resolved or closed"
        />
        <StatCard
          title="Waiting user response"
          value={waitingUser.length}
          icon="WU"
          trend={waitingUser.length ? 'Action needed' : 'Clear'}
          trendDirection={waitingUser.length ? 'warning' : 'up'}
          description="Tickets awaiting your update"
        />
      </div>

      <section className="requester-quick-actions" aria-label="Requester quick actions">
        {quickActions.map((action) => (
          <Link key={action.title} to={action.to}>
            <span aria-hidden="true">{action.code}</span>
            <div>
              <strong>{action.title}</strong>
              <p>{action.description}</p>
            </div>
          </Link>
        ))}
      </section>

      <Card
        className="requester-recent-card"
        title="Recent Tickets"
        subtitle="Your latest requests from email, portal form, and AI chat."
        actions={
          <Link className="dashboard-text-link" to="/requester/tickets">
            View all tickets
          </Link>
        }
      >
        <div className="requester-recent-list">
          {recentTickets.map((ticket) => (
            <Link key={ticket.id} to={`/agent/tickets/${ticket.id}`}>
              <span className="requester-recent-list__source">
                <Badge value={ticket.source} />
              </span>
              <span className="requester-recent-list__content">
                <strong>{ticket.subject}</strong>
                <small>{ticket.ticketNumber || ticket.id}</small>
              </span>
              <span className="requester-recent-list__badges">
                <TicketStatusBadge status={ticket.status} />
                <TicketPriorityBadge priority={ticket.priority} />
              </span>
            </Link>
          ))}
        </div>
      </Card>
    </section>
  );
}
