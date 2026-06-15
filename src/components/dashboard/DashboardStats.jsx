import StatCard from '../common/StatCard';

function isOpen(ticket) {
  return !['resolved', 'closed'].includes(ticket.status);
}

function isSlaAtRisk(ticket) {
  return (
    isOpen(ticket) &&
    (ticket.sla.includes('minutes') || ticket.sla.includes('1 hour'))
  );
}

export default function DashboardStats({ tickets }) {
  const stats = [
    {
      title: 'Total Tickets',
      value: tickets.length,
      icon: 'TT',
      trend: '+6%',
      trendDirection: 'up',
      description: 'Across all helpdesk channels',
    },
    {
      title: 'Open Tickets',
      value: tickets.filter(isOpen).length,
      icon: 'OT',
      trend: 'Active',
      description: 'Requiring service desk action',
    },
    {
      title: 'Waiting Approval',
      value: tickets.filter((ticket) => ticket.status === 'waiting_approval').length,
      icon: 'WA',
      trend: 'Review',
      trendDirection: 'warning',
      description: 'Pending manager or security review',
    },
    {
      title: 'SLA At Risk',
      value: tickets.filter(isSlaAtRisk).length,
      icon: 'SL',
      trend: 'Urgent',
      trendDirection: 'warning',
      description: 'Within one hour of response target',
    },
    {
      title: 'Resolved Today',
      value: tickets.filter(
        (ticket) =>
          ['resolved', 'closed'].includes(ticket.status) &&
          ticket.updatedAt.startsWith('2026-06-09'),
      ).length,
      icon: 'RT',
      trend: 'Today',
      trendDirection: 'up',
      description: 'Completed during the current shift',
    },
  ];

  return (
    <div className="dashboard-stat-grid" aria-label="Helpdesk dashboard statistics">
      {stats.map((stat) => (
        <StatCard key={stat.title} {...stat} />
      ))}
    </div>
  );
}
