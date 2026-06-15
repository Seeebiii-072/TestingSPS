import { useEffect, useState } from 'react';
import AsyncState from '../../components/common/AsyncState';
import Badge from '../../components/common/Badge';
import Button from '../../components/common/Button';
import { approveTicket, getTickets, updateTicket } from '../../services/ticketService.js';

export default function ApprovalRequests() {
  const [approvals, setApprovals] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);
    setError('');

    getTickets({ status: 'waiting_approval' }).then((tickets) => {
      if (!isMounted) return;
      setApprovals(tickets);
      setIsLoading(false);
    }).catch(() => {
      if (!isMounted) return;
      setError('Approval requests could not be loaded from the backend.');
      setIsLoading(false);
    });

    return () => {
      isMounted = false;
    };
  }, [reloadKey]);

  const decide = async (ticketId, decision) => {
    await approveTicket(ticketId, decision, `${decision} by security reviewer`);
    setReloadKey((value) => value + 1);
  };

  const requestMoreInfo = async (ticketId) => {
    await updateTicket(ticketId, { status: 'waiting_user' });
    setReloadKey((value) => value + 1);
  };

  if (error) return <AsyncState type="error" title="Approvals unavailable" description={error} onAction={() => setReloadKey((value) => value + 1)} />;
  if (isLoading) return <AsyncState title="Loading approval requests" description="Fetching high-risk tickets from the backend." />;

  return (
    <section className="page approval-requests-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Security operations</p>
          <h1>Approval Requests</h1>
          <p>Review high-risk identity and access requests requiring human authorization.</p>
        </div>
        <Badge tone="red">{approvals.length} sensitive requests</Badge>
      </div>

      <div className="human-approval-banner">
        <span aria-hidden="true">!</span>
        <div>
          <strong>AI never approves sensitive access. Human approval is required.</strong>
          <p>AI classification supports review but cannot authorize, reject, or provision access.</p>
        </div>
      </div>

      <div className="approval-card-list">
        {approvals.map((ticket) => (
          <article className="approval-card" key={ticket.id}>
            <div className="approval-card__header">
              <div>
                <span>{ticket.ticketNumber || ticket.id}</span>
                <h2>{ticket.subject}</h2>
              </div>
              <Badge tone="amber">{ticket.statusLabel || ticket.status}</Badge>
            </div>

            <dl className="approval-card__details">
              <div>
                <dt>Requester</dt>
                <dd>
                  <strong>{ticket.requesterName}</strong>
                  <span>{ticket.requesterEmail}</span>
                </dd>
              </div>
              <div>
                <dt>Requested access</dt>
                <dd>{ticket.subject}</dd>
              </div>
              <div>
                <dt>Risk reason</dt>
                <dd>High-risk identity/access ticket requires human approval before work can continue.</dd>
              </div>
              <div>
                <dt>AI classification note</dt>
                <dd>{ticket.aiSummary}</dd>
              </div>
            </dl>

            <div className="approval-card__footer">
              <div className="approval-card__risk">
                <Badge tone="red">{ticket.risk}</Badge>
                <Badge value={ticket.source} />
              </div>
              <div className="approval-card__actions">
                <Button variant="success" onClick={() => decide(ticket.id, 'approved')}>
                  Approve
                </Button>
                <Button variant="danger" onClick={() => decide(ticket.id, 'rejected')}>
                  Reject
                </Button>
                <Button variant="outline" onClick={() => requestMoreInfo(ticket.id)}>
                  Request More Info
                </Button>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
