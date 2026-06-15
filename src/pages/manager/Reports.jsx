import { useEffect, useState } from 'react';
import AsyncState from '../../components/common/AsyncState';
import Badge from '../../components/common/Badge';
import Card from '../../components/common/Card';
import { getSummary } from '../../services/reportService.js';

function BarChart({ data, maxValue }) {
  return (
    <div className="report-bar-chart">
      {data.map((item) => (
        <div className="report-bar-chart__row" key={item.label}>
          <div><span>{item.label}</span><strong>{item.value}</strong></div>
          <div className="report-bar-chart__track">
            <span style={{ width: `${(item.value / maxValue) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function Reports() {
  const [reports, setReports] = useState(null);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    setError('');
    getSummary().then(setReports).catch(() => setError('The report data could not be loaded from the backend.'));
  }, [reloadKey]);

  if (error) return <AsyncState type="error" title="Reports unavailable" description={error} onAction={() => setReloadKey((value) => value + 1)} />;
  if (!reports) return <AsyncState title="Loading reports" description="Preparing channel, SLA, risk, and audit data." />;

  return (
    <section className="page reports-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Service management</p>
          <h1>Reports</h1>
          <p>Review helpdesk channel volume, SLA health, risk, resolution, and audit activity.</p>
        </div>
        <Badge tone="blue">Live reporting data</Badge>
      </div>

      <div className="reports-grid">
        <Card title="Tickets by Source" subtitle="Unified intake channel volume.">
          <BarChart data={reports.ticketsBySource} maxValue={5} />
        </Card>
        <Card title="Tickets by Category" subtitle="Current request distribution.">
          <BarChart data={reports.ticketsByCategory} maxValue={3} />
        </Card>
        <Card title="SLA Performance" subtitle="Weekly target compliance.">
          <div className="report-sla-chart">
            {reports.slaPerformance.map((item) => (
              <div key={item.period}>
                <span>{item.period}</span>
                <div><i style={{ height: `${item.met}%` }} /></div>
                <strong>{item.met}%</strong>
              </div>
            ))}
          </div>
        </Card>
        <Card title="Resolved vs Open Tickets" subtitle="Current ticket state summary.">
          <div className="report-donut-placeholder">
            <div style={{ '--open-percent': `${(reports.dashboardStats.openTickets / reports.dashboardStats.totalTickets) * 100}%` }}>
              <strong>{reports.dashboardStats.totalTickets}</strong>
              <span>Total tickets</span>
            </div>
            <ul>
              {reports.resolvedVsOpen.map((item) => (
                <li key={item.label}><span>{item.label}</span><strong>{item.value}</strong></li>
              ))}
            </ul>
          </div>
        </Card>
        <Card
          className="report-wide-card"
          title="High-Risk Access Requests This Month"
          subtitle="Requests and incidents requiring security review."
          actions={<Badge tone="red">{reports.highRiskAccessRequests.length} active</Badge>}
        >
          <div className="report-risk-table-wrap">
            <table className="report-risk-table">
              <caption className="visually-hidden">High-risk access requests this month</caption>
              <thead><tr><th scope="col">Ticket</th><th scope="col">Subject</th><th scope="col">Requester</th><th scope="col">Status</th><th scope="col">Age</th></tr></thead>
              <tbody>
                {reports.highRiskAccessRequests.map((item) => (
                  <tr key={item.ticketId}>
                    <td>{item.ticketId}</td><td>{item.subject}</td><td>{item.requesterName}</td>
                    <td><Badge tone="amber">{item.status}</Badge></td><td>{item.ageHours} hours</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <Card
          className="report-wide-card"
          title="Audit Summary"
          subtitle="Controls and audit-readiness overview."
        >
          <div className="audit-summary-grid">
            <div><span>Timeline events captured</span><strong>48</strong><small>Across all source channels</small></div>
            <div><span>Sensitive actions human-approved</span><strong>100%</strong><small>No AI approvals permitted</small></div>
            <div><span>Ticket changes attributed</span><strong>100%</strong><small>Actor and timestamp recorded</small></div>
            <div><span>Retention policy status</span><strong>Ready</strong><small>Future backend configuration</small></div>
          </div>
        </Card>
      </div>
    </section>
  );
}
