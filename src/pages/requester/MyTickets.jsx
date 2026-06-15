import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import AsyncState from '../../components/common/AsyncState';
import Badge from '../../components/common/Badge';
import Button from '../../components/common/Button';
import FileUpload from '../../components/forms/FileUpload';
import TicketPriorityBadge from '../../components/tickets/TicketPriorityBadge';
import TicketStatusBadge from '../../components/tickets/TicketStatusBadge';
import { addEvent, getTickets } from '../../services/ticketService.js';

function formatUpdatedAt(value) {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value));
}

export default function MyTickets() {
  const [tickets, setTickets] = useState([]);
  const [activeTicketId, setActiveTicketId] = useState('');
  const [comment, setComment] = useState('');
  const [notice, setNotice] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const loadTickets = async () => {
    setError('');
    setIsLoading(true);
    try {
      const results = await getTickets();
      setTickets(
        [...results].sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt)),
      );
    } catch {
      setError('Your tickets could not be loaded from the backend.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadTickets();
  }, []);

  const addComment = async (ticket) => {
    if (!comment.trim()) return;
    try {
      await addEvent(ticket.id, {
        event_type: 'agent_reply_portal',
        content: comment.trim(),
        is_public: true,
        channel: 'portal',
      });
      setComment('');
      setNotice(`Comment added to ${ticket.id}.`);
      await loadTickets();
    } catch {
      setError(`The comment could not be added to ${ticket.id}.`);
    }
  };

  const addAttachment = async (ticket, attachment) => {
    try {
      setNotice(`${attachment.name} uploaded to ${ticket.ticketNumber || ticket.id}.`);
      await loadTickets();
    } catch {
      setError(`The file could not be uploaded to ${ticket.id}.`);
    }
  };

  return (
    <section className="page my-tickets-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Requester portal</p>
          <h1>My Tickets</h1>
          <p>
            Track your requests from email, portal forms, and AI chat in one
            place.
          </p>
        </div>
        <Badge tone="blue">{tickets.length} tickets</Badge>
      </div>

      {notice && (
        <div className="requester-action-notice" role="status">
          {notice}
        </div>
      )}

      {error ? (
        <AsyncState type="error" title="My Tickets unavailable" description={error} onAction={loadTickets} />
      ) : isLoading ? (
        <AsyncState title="Loading My Tickets" description="Collecting your requests from the backend API." />
      ) : tickets.length === 0 ? (
        <AsyncState type="empty" title="No tickets yet" description="Submit a request or start an AI chat to create your first ticket." />
      ) : <div className="requester-ticket-list">
        {tickets.map((ticket) => {
          const isActive = activeTicketId === ticket.id;
          return (
            <article className="requester-ticket" key={ticket.id}>
              <div className="requester-ticket__main">
                <div className="requester-ticket__heading">
                  <div>
                    <span>{ticket.ticketNumber || ticket.id}</span>
                    <h2>{ticket.subject}</h2>
                  </div>
                  <div className="requester-ticket__badges">
                    <Badge value={ticket.source} />
                    <TicketStatusBadge status={ticket.status} />
                    <TicketPriorityBadge priority={ticket.priority} />
                  </div>
                </div>
                <div className="requester-ticket__meta">
                  <span>
                    Last updated <strong>{formatUpdatedAt(ticket.updatedAt)}</strong>
                  </span>
                  <span>
                    Assigned team <strong>{ticket.assignedTeam}</strong>
                  </span>
                  <span>
                    SLA <strong>{ticket.sla}</strong>
                  </span>
                </div>
                <div className="requester-ticket__actions">
                  <Link
                    className="button button--outline"
                    to={`/agent/tickets/${ticket.id}`}
                  >
                    View ticket
                  </Link>
                  <Button
                    variant="secondary"
                    onClick={() => setActiveTicketId(isActive ? '' : ticket.id)}
                  >
                    {isActive ? 'Close actions' : 'Add comment or file'}
                  </Button>
                </div>
              </div>

              {isActive && (
                <div className="requester-ticket__action-panel">
                  <label>
                    Add comment
                    <textarea
                      value={comment}
                      placeholder="Add an update for the service desk..."
                      onChange={(event) => setComment(event.target.value)}
                    />
                  </label>
                  <Button disabled={!comment.trim()} onClick={() => addComment(ticket)}>
                    Add comment
                  </Button>
                  <FileUpload
                    compact
                    label="Upload file"
                    ticketId={ticket.id}
                    onUploaded={(attachment) => addAttachment(ticket, attachment)}
                  />
                </div>
              )}
            </article>
          );
        })}
      </div>}
    </section>
  );
}
