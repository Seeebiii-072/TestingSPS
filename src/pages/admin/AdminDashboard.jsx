import { Link } from 'react-router-dom';
import Badge from '../../components/common/Badge';
import StatCard from '../../components/common/StatCard';

const adminAreas = [
  { code: 'US', title: 'Users', description: 'Manage roles and access.', to: '/admin/users' },
  { code: 'KB', title: 'Knowledge Base', description: 'Manage approved support guidance.', to: '/admin/knowledge-base' },
  { code: 'CT', title: 'Categories', description: 'Configure request routing.', to: '/admin/categories' },
  { code: 'SL', title: 'SLA Settings', description: 'Configure service targets.', to: '/admin/sla-settings' },
  { code: 'EM', title: 'Email Settings', description: 'Prepare email channel integration.', to: '/admin/email-settings' },
];

export default function AdminDashboard() {
  return (
    <section className="page admin-dashboard-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">System administration</p>
          <h1>Admin Dashboard</h1>
          <p>Configure users, knowledge, routing, service targets, and communication channels.</p>
        </div>
        <Badge tone="blue">Configuration preview</Badge>
      </div>

      <div className="admin-stat-grid">
        <StatCard title="Supported roles" value="6" icon="US" trend="Ready" description="Backend role model configured" />
        <StatCard title="Knowledge articles" value="24" icon="KB" trend="+3" trendDirection="up" description="Approved helpdesk guidance" />
        <StatCard title="Ticket categories" value="6" icon="CT" trend="Configured" description="Routing categories available" />
        <StatCard title="SLA policies" value="4" icon="SL" trend="Active" description="Priority-based targets" />
      </div>

      <div className="admin-area-grid">
        {adminAreas.map((area) => (
          <Link key={area.title} to={area.to}>
            <span aria-hidden="true">{area.code}</span>
            <div><strong>{area.title}</strong><p>{area.description}</p></div>
          </Link>
        ))}
      </div>

      <div className="future-integration-note">
        <span aria-hidden="true">API</span>
        <div><strong>Admin API integration pending</strong><p>Administration changes are disabled until secured backend admin APIs are added.</p></div>
      </div>
    </section>
  );
}
