import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import AsyncState from '../../components/common/AsyncState';
import Badge from '../../components/common/Badge';
import Card from '../../components/common/Card';
import TicketPriorityBadge from '../../components/tickets/TicketPriorityBadge';
import TicketReplyBox from '../../components/tickets/TicketReplyBox';
import TicketStatusBadge from '../../components/tickets/TicketStatusBadge';
import TicketTimeline from '../../components/tickets/TicketTimeline';
import { addEvent, getTicket, updateTicket } from '../../services/ticketService.js';

function riskTone(risk) {
  if (risk === 'High Risk') return 'red';
  if (risk === 'Elevated') return 'amber';
  return 'green';
}

export default function TicketDetail() {
  const { ticketId } = useParams();
  const [ticket, setTicket] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);
    setError('');

    getTicket(ticketId).then((result) => {
      if (!isMounted) return;
      setTicket(result);
      setIsLoading(false);
    }).catch(() => {
      if (!isMounted) return;
      setError('The ticket could not be loaded from the backend.');
      setIsLoading(false);
    });

    return () => {
      isMounted = false;
    };
  }, [ticketId, reloadKey]);

  const reloadTicket = async () => {
    const updated = await getTicket(ticket.id);
    setTicket(updated);
  };

  const addComment = async (eventType, message, isPublic) => {
    try {
      await addEvent(ticket.id, {
        event_type: eventType,
        content: message,
        is_public: isPublic,
        channel: 'portal',
      });
      await reloadTicket();
    } catch {
      setError('The timeline update could not be saved.');
    }
  };

  const changeStatus = async (status) => {
    try {
      const updated = await updateTicket(ticket.id, { status });
      setTicket(updated);
    } catch {
      setError('The status change could not be saved.');
    }
  };

  if (error) return <AsyncState type="error" title="Ticket unavailable" description={error} onAction={() => setReloadKey((value) => value + 1)} />;
  if (isLoading) return <AsyncState title="Loading ticket" description="Preparing the unified ticket timeline." />;

  if (!ticket) {
    return (
      <section className="ticket-not-found">
        <h1>Ticket not found</h1>
        <p>The requested ticket does not exist.</p>
        <Link className="button button--primary" to="/agent/queue">
          Return to ticket queue
        </Link>
      </section>
    );
  }

  return (
    <section className="page ticket-detail-page">
      <Link className="ticket-detail-back" to="/agent/queue">
        &lt; Back to ticket queue
      </Link>

      <header className="ticket-detail-header">
        <div>
          <span className="ticket-detail-header__id">{ticket.ticketNumber || ticket.id}</span>
          <h1>{ticket.subject}</h1>
          <p>
            Created by {ticket.requesterName} via{' '}
            {ticket.source.replaceAll('_', ' ')}.
          </p>
        </div>
        <div className="ticket-detail-header__badges">
          <TicketStatusBadge status={ticket.status} />
          <TicketPriorityBadge priority={ticket.priority} />
          <Badge tone={riskTone(ticket.risk)}>{ticket.risk}</Badge>
          <Badge value={ticket.source} />
        </div>
      </header>

      <div className="ticket-detail-layout">
        <main className="ticket-detail-main">
          <Card
            className="ticket-detail-timeline-card"
            title="Unified Ticket Timeline"
            subtitle="Every channel event, agent action, and status change in one record."
            actions={<Badge tone="blue">{ticket.timeline.length} events</Badge>}
          >
            <TicketTimeline events={ticket.timeline} />
          </Card>

          <Card
            className="ticket-detail-reply-card"
            title="Reply and Update"
            subtitle="Public replies and internal notes are added to the same timeline."
          >
            <TicketReplyBox
              currentStatus={ticket.status}
              onAddNote={(message) => addComment('internal_note', message, false)}
              onResolve={() => changeStatus('resolved')}
              onSendReply={(message) => addComment('agent_reply_portal', message, true)}
              onUpdateStatus={changeStatus}
            />
          </Card>
        </main>

        <aside className="ticket-detail-side">
          <Card title="Ticket Details" subtitle="Current routing and requester context.">
            <dl className="ticket-detail-facts">
              <div>
                <dt>Requester</dt>
                <dd>
                  <strong>{ticket.requesterName}</strong>
                  <span>{ticket.requesterEmail}</span>
                </dd>
              </div>
              <div>
                <dt>Source channel</dt>
                <dd>
                  <Badge value={ticket.source} />
                </dd>
              </div>
              <div>
                <dt>Category</dt>
                <dd>{ticket.categoryLabel}</dd>
              </div>
              <div>
                <dt>Assigned team</dt>
                <dd>{ticket.assignedTeam}</dd>
              </div>
              <div>
                <dt>SLA</dt>
                <dd className={ticket.sla.includes('minutes') || ticket.sla.includes('breached') ? 'ticket-sla-at-risk' : ''}>
                  {ticket.sla}
                </dd>
              </div>
            </dl>
          </Card>

          <Card title="AI Summary" subtitle="Classification and context summary.">
            <p className="ticket-detail-ai-summary">{ticket.aiSummary}</p>
          </Card>

          <Card title="Attachments" subtitle={`${ticket.attachments.length} files attached.`}>
            {ticket.attachments.length ? (
              <div className="ticket-attachments">
                {ticket.attachments.map((attachment) => (
                  <a
                    href={attachment.url}
                    key={attachment.id}
                    aria-label={`Open attachment ${attachment.name}`}
                  >
                    <span aria-hidden="true">AT</span>
                    <span>
                      <strong>{attachment.name}</strong>
                      <small>
                        {attachment.type} &middot; {attachment.size}
                      </small>
                    </span>
                  </a>
                ))}
              </div>
            ) : (
              <p className="ticket-attachments-empty">No attachments on this ticket.</p>
            )}
          </Card>
        </aside>
      </div>
    </section>
  );
}
