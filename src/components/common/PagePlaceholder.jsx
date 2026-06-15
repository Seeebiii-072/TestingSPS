import Badge from './Badge';
import Button from './Button';
import Card from './Card';
import EmptyState from './EmptyState';
import StatCard from './StatCard';

export default function PagePlaceholder({ description, eyebrow, title }) {
  return (
    <section className="page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        <Badge tone="blue">Frontend foundation</Badge>
      </div>

      <div className="stat-grid" aria-label="Dashboard statistics">
        <StatCard
          title="Open tickets"
          value="24"
          icon="OT"
          trend="+8%"
          trendDirection="up"
          description="Active workload"
        />
        <StatCard
          title="SLA compliance"
          value="96.4%"
          icon="SL"
          trend="+1.2%"
          trendDirection="up"
          description="Rolling 30-day result"
        />
        <StatCard
          title="Pending approvals"
          value="7"
          icon="PA"
          trend="2 urgent"
          trendDirection="warning"
          description="Security workflow"
        />
      </div>

      <Card
        title={`${title} workspace`}
        subtitle="Reusable components and content are ready for feature implementation."
        actions={
          <div className="badge-row">
            <Badge value="portal_form" />
            <Badge value="open" />
            <Badge value="medium" />
          </div>
        }
      >
        <EmptyState
          title="This module is prepared for the next build step"
          description="Feature-specific components, records, and workflows can be added here without changing the common application layout."
          action={
            <Button variant="outline" disabled>
            Future action
            </Button>
          }
        />
      </Card>
    </section>
  );
}
