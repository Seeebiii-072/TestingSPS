import Badge from '../common/Badge';
import Card from '../common/Card';

const channels = [
  {
    name: 'Email intake',
    code: 'EM',
    status: 'Operational',
    detail: 'Last message processed 2 min ago',
  },
  {
    name: 'Web form intake',
    code: 'WF',
    status: 'Operational',
    detail: 'Submissions routing normally',
  },
  {
    name: 'AI chat escalation',
    code: 'AI',
    status: 'Operational',
    detail: 'Escalation service available',
  },
  {
    name: 'Notification service',
    code: 'NS',
    status: 'Monitoring',
    detail: 'Delivery latency within target',
  },
];

export default function ChannelHealth() {
  return (
    <Card
      className="dashboard-panel channel-health"
      title="Channel Health"
      subtitle="Intake and notification service status."
      actions={<Badge tone="green">All available</Badge>}
    >
      <div className="channel-health__list">
        {channels.map((channel) => (
          <div className="channel-health__item" key={channel.name}>
            <span className="channel-health__icon" aria-hidden="true">
              {channel.code}
            </span>
            <span className="channel-health__content">
              <strong>{channel.name}</strong>
              <small>{channel.detail}</small>
            </span>
            <span
              className={`channel-health__status ${
                channel.status === 'Operational'
                  ? 'channel-health__status--operational'
                  : ''
              }`}
            >
              <i aria-hidden="true" />
              {channel.status}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}
