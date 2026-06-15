import Badge from '../common/Badge';

const statusTones = {
  open: 'blue',
  in_progress: 'blue',
  waiting_approval: 'amber',
  waiting_user: 'amber',
  resolved: 'green',
  closed: 'gray',
};

export default function TicketStatusBadge({ status }) {
  const label = String(status || '').replaceAll('_', ' ');
  return <Badge tone={statusTones[status] || 'gray'}>{label}</Badge>;
}
