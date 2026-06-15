import { useEffect, useState } from 'react';
import ChannelHealth from '../../components/dashboard/ChannelHealth';
import AsyncState from '../../components/common/AsyncState';
import DashboardStats from '../../components/dashboard/DashboardStats';
import HighRiskPanel from '../../components/dashboard/HighRiskPanel';
import RecentTickets from '../../components/dashboard/RecentTickets';
import SLAOverview from '../../components/dashboard/SLAOverview';
import TicketSourceChart from '../../components/dashboard/TicketSourceChart';
import Badge from '../../components/common/Badge';
import { getReports } from '../../services/reportService.js';
import { getTickets } from '../../services/ticketService.js';

export default function AgentDashboard() {
  const [tickets, setTickets] = useState([]);
  const [reports, setReports] = useState(null);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let isMounted = true;
    setError('');

    Promise.all([getTickets(), getReports()]).then(([ticketData, reportData]) => {
      if (!isMounted) return;
      setTickets(ticketData);
      setReports(reportData);
    }).catch(() => {
      if (isMounted) setError('The operations data could not be loaded from the backend.');
    });

    return () => {
      isMounted = false;
    };
  }, [reloadKey]);

  if (error) return <AsyncState type="error" title="Dashboard unavailable" description={error} onAction={() => setReloadKey((value) => value + 1)} />;
  if (!reports) return <AsyncState title="Loading dashboard" description="Preparing operations metrics and ticket activity." />;

  return (
    <section className="page agent-dashboard">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Service operations</p>
          <h1>SecureDesk AI Dashboard</h1>
          <p>Unified helpdesk operations across email, web form, and AI chat.</p>
        </div>
        <Badge tone="green">Live systems operational</Badge>
      </div>

      <div className="dashboard-info-banner">
        <span className="dashboard-info-banner__icon" aria-hidden="true">
          i
        </span>
        <div>
          <strong>All channels feed one ticket system and one timeline.</strong>
          <p>
            Email, portal form, and AI chat requests share the same service
            workflow and reporting model.
          </p>
        </div>
      </div>

      <DashboardStats tickets={tickets} />
      <TicketSourceChart sources={reports.ticketsBySource} />

      <div className="dashboard-main-grid">
        <RecentTickets tickets={tickets} />
        <HighRiskPanel tickets={tickets} />
      </div>

      <div className="dashboard-secondary-grid">
        <SLAOverview
          compliance={reports.dashboardStats.slaCompliance}
          performance={reports.slaPerformance}
        />
        <ChannelHealth />
      </div>
    </section>
  );
}
