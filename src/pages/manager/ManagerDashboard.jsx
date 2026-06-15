import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import AsyncState from '../../components/common/AsyncState';
import Badge from '../../components/common/Badge';
import Card from '../../components/common/Card';
import StatCard from '../../components/common/StatCard';
import { getSummary } from '../../services/reportService.js';

export default function ManagerDashboard() {
  const [reports, setReports] = useState(null);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    setError('');
    getSummary().then(setReports).catch(() => setError('The management data could not be loaded from the backend.'));
  }, [reloadKey]);

  if (error) return <AsyncState type="error" title="Management dashboard unavailable" description={error} onAction={() => setReloadKey((value) => value + 1)} />;
  if (!reports) return <AsyncState title="Loading management dashboard" description="Preparing service-management metrics." />;

  return (
    <section className="page manager-dashboard-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Service management</p>
          <h1>Manager Dashboard</h1>
          <p>Monitor service performance, workload, risk, and operational priorities.</p>
        </div>
        <Badge tone="green">Live data current</Badge>
      </div>

      <div className="manager-stat-grid">
        <StatCard title="Total tickets" value={reports.dashboardStats.totalTickets} icon="TT" trend="+6%" trendDirection="up" description="Current reporting period" />
        <StatCard title="Open workload" value={reports.dashboardStats.openTickets} icon="OW" trend="Active" description="Requires team action" />
        <StatCard title="SLA compliance" value={`${reports.dashboardStats.slaCompliance}%`} icon="SL" trend="+1.2%" trendDirection="up" description="Across all service teams" />
        <StatCard title="High-risk requests" value={reports.dashboardStats.highRiskRequests} icon="HR" trend="Review" trendDirection="warning" description="Security review required" />
      </div>

      <div className="manager-dashboard-grid">
        <Card title="Operational Priorities" subtitle="Current focus areas for service leadership.">
          <div className="manager-priority-list">
            <div><span>1</span><div><strong>Protect critical SLA response windows</strong><p>Three tickets are inside one-hour response targets.</p></div></div>
            <div><span>2</span><div><strong>Complete sensitive access reviews</strong><p>Human approval remains required for privileged access.</p></div></div>
            <div><span>3</span><div><strong>Balance intake across channels</strong><p>Web form volume is currently the largest source.</p></div></div>
          </div>
        </Card>
        <Card title="Management Actions" subtitle="Open detailed service views.">
          <div className="manager-action-links">
            <Link to="/manager/reports"><span>RP</span><div><strong>Open Reports</strong><p>Review service trends and audit data.</p></div></Link>
            <Link to="/security/approvals"><span>AP</span><div><strong>Review Approvals</strong><p>Inspect sensitive access requests.</p></div></Link>
            <Link to="/agent/queue"><span>TQ</span><div><strong>View Ticket Queue</strong><p>Review current operational workload.</p></div></Link>
          </div>
        </Card>
      </div>
    </section>
  );
}
