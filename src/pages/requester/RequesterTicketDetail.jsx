import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import AsyncState from '../../components/common/AsyncState';
import Badge from '../../components/common/Badge';
import Button from '../../components/common/Button';
import Card from '../../components/common/Card';
import FileUpload from '../../components/forms/FileUpload';
import TicketPriorityBadge from '../../components/tickets/TicketPriorityBadge';
import TicketStatusBadge from '../../components/tickets/TicketStatusBadge';
import TicketTimeline from '../../components/tickets/TicketTimeline';
import { addEvent, getTicket, openAttachment } from '../../services/ticketService.js';

function riskTone(risk) {
  if (risk === 'High Risk') return 'red';
  if (risk === 'Elevated') return 'amber';
  return 'green';
}

export default function RequesterTicketDetail() {
  const { ticketId } = useParams();
  const [ticket, setTicket] = useState(null);
  const [message, setMessage] = useState('');
  const [notice, setNotice] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);
    setError('');

    getTicket(ticketId)
      .then((result) => {
        if (!isMounted) return;
        console.log('[RequesterTicketDetail] Ticket loaded successfully:', result);
        setTicket(result);
      })
      .catch((err) => {
        if (isMounted) {
          console.error('[RequesterTicketDetail] Failed to load ticket:', err);
          setError(`This ticket could not be loaded from the backend. ${err?.response?.status === 403 ? 'You may not have permission to view this ticket.' : ''}`);
        }
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [ticketId, reloadKey]);

  const reloadTicket = () => setReloadKey((value) => value + 1);

  const addRequesterUpdate = async () => {
    if (!message.trim() || !ticket) return;

    setIsSaving(true);
    setError('');
    try {
      await addEvent(ticket.id, {
        event_type: 'agent_reply_portal',
        content: message.trim(),
        is_public: true,
        channel: 'portal',
      });
      setMessage('');
      setNotice('Your update was added to the ticket.');
      reloadTicket();
    } catch {
      setError('Your update could not be added to this ticket.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleOpenAttachment = async (attachment) => {
    setError('');
    try {
      await openAttachment(ticket.id, attachment);
    } catch {
      setError('The attachment could not be opened.');
    }
  };

  if (error) {
    return (
      <AsyncState
        type="error"
        title="Ticket unavailable"
        description={error}
        onAction={reloadTicket}
      />
    );
  }

  if (isLoading) {
    return <AsyncState title="Loading ticket" description="Preparing your ticket details." />;
  }

  if (!ticket) {
    return (
      <AsyncState
        type="empty"
        title="Ticket not found"
        description="This ticket could not be found for your account."
      >
        <Link className="button button--primary" to="/requester/tickets">
          Return to My Tickets
        </Link>
      </AsyncState>
    );
  }

  const visibleTimeline = ticket.timeline.filter((event) => event.isPublic !== false);

  return (
    <section className="page ticket-detail-page">
      <Link className="ticket-detail-back" to="/requester/tickets">
        &lt; Back to My Tickets
      </Link>

      <header className="ticket-detail-header">
        <div>
          <span className="ticket-detail-header__id">{ticket.ticketNumber || ticket.id}</span>
          <h1>{ticket.subject}</h1>
          <p>
            Submitted via {ticket.source.replaceAll('_', ' ')} and routed to{' '}
            {ticket.assignedTeam}.
          </p>
        </div>
        <div className="ticket-detail-header__badges">
          <TicketStatusBadge status={ticket.status} />
          <TicketPriorityBadge priority={ticket.priority} />
          <Badge tone={riskTone(ticket.risk)}>{ticket.risk}</Badge>
          <Badge value={ticket.source} />
        </div>
      </header>

      {notice && (
        <div className="requester-action-notice" role="status">
          {notice}
        </div>
      )}

      <div className="ticket-detail-layout">
        <main className="ticket-detail-main">
          <Card
            className="ticket-detail-timeline-card"
            title="Ticket Timeline"
            subtitle="Public updates and requester-visible activity for this request."
            actions={<Badge tone="blue">{visibleTimeline.length} updates</Badge>}
          >
            <TicketTimeline
              events={visibleTimeline}
              attachments={ticket.attachments}
              onOpenAttachment={handleOpenAttachment}
            />
          </Card>

          <Card title="Add Update" subtitle="Send a public update to the service desk.">
            <div className="requester-ticket__action-panel">
              <label>
                Add comment
                <textarea
                  value={message}
                  placeholder="Add an update for the service desk..."
                  onChange={(event) => setMessage(event.target.value)}
                />
              </label>
              <Button disabled={isSaving || !message.trim()} onClick={addRequesterUpdate}>
                {isSaving ? 'Adding...' : 'Add comment'}
              </Button>
              <FileUpload
                compact
                label="Upload file"
                ticketId={ticket.id}
                onUploaded={() => {
                  setNotice('File uploaded to this ticket.');
                  reloadTicket();
                }}
              />
            </div>
          </Card>
        </main>

        <aside className="ticket-detail-side">
          <Card title="Ticket Details" subtitle="Current status and routing.">
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

          <Card title="Summary" subtitle="Request context captured for the service desk.">
            <p className="ticket-detail-ai-summary">{ticket.aiSummary}</p>
          </Card>

           <Card title="Attachments" subtitle={`${ticket.attachments.length} files attached.`}>
             {ticket.attachments.length ? (
               <div className="ticket-attachments">
                 {ticket.attachments.map((attachment) => (
                   <button
                     type="button"
                     key={attachment.id}
                     aria-label={`Open attachment ${attachment.name}`}
                     onClick={() => handleOpenAttachment(attachment)}
                   >
                     <span aria-hidden="true">AT</span>
                     <span>
                       <strong>{attachment.name}</strong>
                       <small>
                         {attachment.type} &middot; {attachment.size}
                       </small>
                     </span>
                   </button>
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
