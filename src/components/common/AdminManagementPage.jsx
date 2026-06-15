import Badge from './Badge';
import Button from './Button';
import Card from './Card';

export default function AdminManagementPage({
  actionLabel,
  columns,
  description,
  eyebrow = 'System administration',
  rows,
  title,
}) {
  return (
    <section className="page admin-management-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        <Button disabled>{actionLabel}</Button>
      </div>

      <div className="future-integration-note">
        <span aria-hidden="true">API</span>
        <div>
          <strong>Future backend integration</strong>
          <p>
            This management screen currently uses static configuration records. Create,
            update, and delete actions will connect to secured backend APIs later.
          </p>
        </div>
      </div>

      <Card
        className="admin-management-card"
        title={`${title} management`}
        subtitle="Configuration records for frontend review."
        actions={<Badge tone="blue">{rows.length} records</Badge>}
      >
        <div className="admin-management-table-wrap">
          <table className="admin-management-table">
            <caption className="visually-hidden">{title} management records</caption>
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column.key} scope="col">{column.label}</th>
                ))}
                <th scope="col">Action</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  {columns.map((column) => (
                    <td key={column.key}>{row[column.key]}</td>
                  ))}
                  <td>
                    <Button variant="outline" disabled>
                      Manage
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </section>
  );
}
