import AdminManagementPage from '../../components/common/AdminManagementPage';

const rows = [
  { id: 'MAIL-01', setting: 'Support mailbox', value: 'support@sps.example', status: 'Pending integration', direction: 'Inbound' },
  { id: 'MAIL-02', setting: 'Requester notifications', value: 'notifications@sps.example', status: 'Pending integration', direction: 'Outbound' },
  { id: 'MAIL-03', setting: 'Security escalation mailbox', value: 'security@sps.example', status: 'Pending integration', direction: 'Inbound' },
];

export default function EmailSettings() {
  return <AdminManagementPage title="Email Settings" description="Prepare inbound ticket intake and outbound requester notification settings." actionLabel="Add Mailbox" rows={rows} columns={[{ key: 'setting', label: 'Setting' }, { key: 'value', label: 'Address' }, { key: 'direction', label: 'Direction' }, { key: 'status', label: 'Status' }]} />;
}
