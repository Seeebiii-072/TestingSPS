import Badge from '../../components/common/Badge';
import Button from '../../components/common/Button';
import Card from '../../components/common/Card';

const roles = [
  { id: 'ROLE-01', name: 'Intern', value: 'intern', access: 'Requester self-service' },
  { id: 'ROLE-02', name: 'Employee', value: 'employee', access: 'Requester self-service' },
  { id: 'ROLE-03', name: 'Agent', value: 'agent', access: 'Ticket queue and updates' },
  { id: 'ROLE-04', name: 'Security Admin', value: 'security_admin', access: 'Approvals and security review' },
  { id: 'ROLE-05', name: 'Manager', value: 'manager', access: 'Reports and approvals' },
  { id: 'ROLE-06', name: 'Administrator', value: 'administrator', access: 'Full backend access' },
];

export default function Users() {
  return (
    <section className="page users-admin-page">
      <div className="page-heading">
        <div><p className="eyebrow">System administration</p><h1>Users</h1><p>Review backend-supported roles and access levels.</p></div>
        <Button disabled>Add User</Button>
      </div>
      <div className="future-integration-note"><span aria-hidden="true">API</span><div><strong>User management API pending</strong><p>The backend currently supports register/login, but not administrative user listing or provisioning.</p></div></div>
      <Card title="Role Model" subtitle="Backend roles available for authentication and route guards." actions={<Badge tone="blue">{roles.length} roles</Badge>}>
        <div className="admin-management-table-wrap">
          <table className="admin-management-table">
            <caption className="visually-hidden">Backend role model records</caption>
            <thead><tr><th scope="col">Role</th><th scope="col">Value</th><th scope="col">Access</th><th scope="col">Action</th></tr></thead>
            <tbody>{roles.map((role) => <tr key={role.id}><td><strong>{role.name}</strong></td><td>{role.value}</td><td>{role.access}</td><td><Button variant="outline" disabled>Manage</Button></td></tr>)}</tbody>
          </table>
        </div>
      </Card>
    </section>
  );
}
