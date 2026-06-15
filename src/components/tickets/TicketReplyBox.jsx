import { useEffect, useState } from 'react';
import Button from '../common/Button';

const statuses = [
  ['open', 'Open'],
  ['in_progress', 'In Progress'],
  ['waiting_approval', 'Waiting Approval'],
  ['waiting_user', 'Waiting User'],
  ['resolved', 'Resolved'],
  ['closed', 'Closed'],
];

export default function TicketReplyBox({
  currentStatus,
  onAddNote,
  onResolve,
  onSendReply,
  onUpdateStatus,
}) {
  const [mode, setMode] = useState('public');
  const [message, setMessage] = useState('');
  const [status, setStatus] = useState(currentStatus);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    setStatus(currentStatus);
  }, [currentStatus]);

  const submitMessage = async () => {
    if (!message.trim()) return;
    setIsSaving(true);
    if (mode === 'public') await onSendReply(message.trim());
    else await onAddNote(message.trim());
    setMessage('');
    setIsSaving(false);
  };

  const updateStatus = async () => {
    setIsSaving(true);
    await onUpdateStatus(status);
    setIsSaving(false);
  };

  const resolveTicket = async () => {
    setIsSaving(true);
    setStatus('Resolved');
    await onResolve();
    setIsSaving(false);
  };

  return (
    <section className="ticket-reply-box" aria-label="Ticket reply composer">
      <div className="ticket-reply-box__tabs" role="tablist">
        <button
          className={mode === 'public' ? 'ticket-reply-box__tab--active' : ''}
          type="button"
          role="tab"
          aria-selected={mode === 'public'}
          onClick={() => setMode('public')}
        >
          Public reply
        </button>
        <button
          className={mode === 'internal' ? 'ticket-reply-box__tab--active' : ''}
          type="button"
          role="tab"
          aria-selected={mode === 'internal'}
          onClick={() => setMode('internal')}
        >
          Internal note
        </button>
      </div>

      <textarea
        value={message}
        aria-label={mode === 'public' ? 'Public reply message' : 'Internal note message'}
        placeholder={
          mode === 'public'
            ? 'Write an email reply to the requester...'
            : 'Add a private note for service desk teams...'
        }
        onChange={(event) => setMessage(event.target.value)}
      />

      <div className="ticket-reply-box__footer">
        <div className="ticket-reply-box__status">
          <label>
            Update status
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              {statuses.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <Button variant="outline" disabled={isSaving} onClick={updateStatus}>
            Update status
          </Button>
        </div>
        <div className="ticket-reply-box__actions">
          <Button variant="success" disabled={isSaving} onClick={resolveTicket}>
            Resolve ticket
          </Button>
          <Button disabled={isSaving || !message.trim()} onClick={submitMessage}>
            {mode === 'public' ? 'Send email reply' : 'Add internal note'}
          </Button>
        </div>
      </div>
    </section>
  );
}
