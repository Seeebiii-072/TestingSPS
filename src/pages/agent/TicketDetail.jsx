import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import AsyncState from '../../components/common/AsyncState';
import Badge from '../../components/common/Badge';
import Button from '../../components/common/Button';
import Card from '../../components/common/Card';
import EscalationDialog from '../../components/tickets/EscalationDialog';
import TicketPriorityBadge from '../../components/tickets/TicketPriorityBadge';
import TicketReplyBox from '../../components/tickets/TicketReplyBox';
import TicketStatusBadge from '../../components/tickets/TicketStatusBadge';
import TicketTimeline from '../../components/tickets/TicketTimeline';
import { addEvent, assignTicket, escalateTicket, getTicket, openAttachment, updateTicket, updateTicketStatus } from '../../services/ticketService.js';

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
  const [showEscalationDialog, setShowEscalationDialog] = useState(false);

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

  const handleAssign = async () => {
    setError('');
    try {
      await assignTicket(ticket.id, { agent_id: 'agent-001', actor_id: 'agent-001' });
      await reloadTicket();
    } catch {
      setError('Assignment could not be saved.');
    }
  };

  const handleEscalate = async (escalationData) => {
    setError('');
    try {
      await escalateTicket(ticket.id, {
        note: escalationData.note,
        team: escalationData.team,
      });
      setShowEscalationDialog(false);
      await reloadTicket();
    } catch {
      setError('Escalation could not be saved.');
    }
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

  const handleOpenAttachment = async (attachment) => {
    setError('');
    try {
      await openAttachment(ticket.id, attachment);
    } catch {
      setError('The attachment could not be opened.');
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

  const lockedStatuses = ['closed', 'duplicate', 'resolved'];
  const isLocked = lockedStatuses.includes(ticket.status);

  return (
    <section className="page ticket-detail-page">
      <Link className="ticket-detail-back" to="/agent/queue">
        {'<'} Back to ticket queue
      </Link>

      {isLocked && (
        <div className="ticket-locked-banner" style={{ backgroundColor: '#fff3cd', border: '1px solid #ffc107', borderRadius: '8px', padding: '16px 24px', marginBottom: '20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: '15px', color: '#856404' }}>
            🔒 This ticket is {ticket.status}. Need more help? Submit a new request.
          </span>
          <Link className="button button--primary" to="/requester/submit" style={{ backgroundColor: '#0055a5', color: '#fff', padding: '8px 20px', borderRadius: '6px', textDecoration: 'none', fontSize: '14px', fontWeight: 600 }}>
            New Request
          </Link>
        </div>
      )}

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
          <div className="ticket-detail-header__actions">
            <Button variant="outline" disabled={isLocked} onClick={handleAssign}>
              {ticket.assignedAgentId ? 'Reassign' : 'Assign to agent'}
            </Button>
            <Button variant="outline" disabled={isLocked} onClick={() => setShowEscalationDialog(true)}>
              Escalate
            </Button>
          </div>
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
            <TicketTimeline
              events={ticket.timeline}
              attachments={ticket.attachments}
              onOpenAttachment={handleOpenAttachment}
            />
          </Card>

          {!isLocked && (
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
          )}
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
                <dd>
                  <select
                    className="ticket-detail-edit"
                    value={ticket.category}
                    onChange={(e) => updateTicket(ticket.id, { category: e.target.value }).then(reloadTicket).catch(() => setError('Category update failed.'))}
                  >
                    <option value="access_and_identity">Access and Identity</option>
                    <option value="hardware">Hardware</option>
                    <option value="software">Software</option>
                    <option value="network">Network</option>
                    <option value="email">Email</option>
                    <option value="security">Security</option>
                    <option value="other">Other</option>
                  </select>
                </dd>
              </div>
              <div>
                <dt>Priority</dt>
                <dd>
                  <select
                    className="ticket-detail-edit"
                    value={ticket.priority}
                    onChange={(e) => updateTicket(ticket.id, { priority: e.target.value }).then(reloadTicket).catch(() => setError('Priority update failed.'))}
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </dd>
              </div>
              <div>
                <dt>Risk</dt>
                <dd>
                  <select
                    className="ticket-detail-edit"
                    value={ticket.riskLevel || ticket.risk}
                    onChange={(e) => updateTicket(ticket.id, { risk: e.target.value }).then(reloadTicket).catch(() => setError('Risk update failed.'))}
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </dd>
              </div>
              <div>
                <dt>Assigned team</dt>
                <dd>
                  <select
                    className="ticket-detail-edit"
                    value={ticket.team}
                    onChange={(e) => updateTicket(ticket.id, { team: e.target.value }).then(reloadTicket).catch(() => setError('Team update failed.'))}
                  >
                    <option value="it">IT Support</option>
                    <option value="security">Cybersecurity</option>
                    <option value="devops">DevOps / Infrastructure</option>
                    <option value="hr">HR / People Operations</option>
                    <option value="management">Management</option>
                  </select>
                </dd>
              </div>
              <div>
                <dt>SLA</dt>
                <dd className={ticket.sla.includes('minutes') || ticket.sla.includes('breached') ? 'ticket-sla-at-risk' : ''}>
                  {ticket.sla}
                </dd>
              </div>
            </dl>
          </Card>

          <Card title="AI Summary" subtitle="Classification and context summary. Override when needed.">
            <textarea
              className="ticket-detail-edit ticket-detail-edit--textarea"
              value={ticket.aiSummary || ''}
              onChange={(e) => setTicket((current) => ({ ...current, aiSummary: e.target.value }))}
              onBlur={(e) => {
                const value = e.target.value.trim();
                if (value !== (ticket.aiSummary || '').trim()) {
                  updateTicket(ticket.id, { ai_summary: value }).then(reloadTicket).catch(() => setError('AI summary update failed.'));
                }
              }}
              rows={4}
            />
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

      {showEscalationDialog && (
        <EscalationDialog
          ticket={ticket}
          onEscalate={handleEscalate}
          onCancel={() => setShowEscalationDialog(false)}
        />
      )}
    </section>
  );
}
