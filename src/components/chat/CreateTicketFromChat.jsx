import { useState } from 'react';
import Badge from '../common/Badge';
import Button from '../common/Button';

const defaultTicketDraft = {
  subject: 'Helpdesk assistance requested from SecureDesk AI',
  summary: 'The AI assistant could not fully resolve the user request.',
  category: 'General IT',
  priority: 'Medium',
  risk: 'Normal',
  source: 'chat',
};

export default function CreateTicketFromChat({
  draft = defaultTicketDraft,
  onContinue,
  onCreate,
  onCreated,
}) {
  const [isCreating, setIsCreating] = useState(false);
  const [createdTicketNumber, setCreatedTicketNumber] = useState('');

  const createTicket = async () => {
    setIsCreating(true);
    const ticket = await onCreate(draft);
    const ticketNumber = ticket?.ticketNumber || ticket?.ticket_number || ticket?.id || 'created';
    setCreatedTicketNumber(ticketNumber);
    setIsCreating(false);
    onCreated?.(ticketNumber);
  };

  if (createdTicketNumber) {
    return (
      <div className="chat-ticket-card chat-ticket-card--success" role="status">
        <span className="chat-ticket-card__success-icon" aria-hidden="true">
          OK
        </span>
        <div>
          <strong>Ticket {createdTicketNumber} created successfully.</strong>
          <p>A service desk agent will review the request.</p>
        </div>
      </div>
    );
  }

  return (
    <section className="chat-ticket-card" aria-label="Create a support ticket">
      <div className="chat-ticket-card__heading">
        <div>
          <span>Escalation recommended</span>
          <h3>Create a support ticket?</h3>
        </div>
        <Badge value="chat" />
      </div>

      <dl className="chat-ticket-card__details">
        <div>
          <dt>Suggested subject</dt>
          <dd>{draft.subject}</dd>
        </div>
        <div>
          <dt>Summary</dt>
          <dd>{draft.summary}</dd>
        </div>
        <div className="chat-ticket-card__meta">
          <div>
            <dt>Category</dt>
            <dd>{draft.category}</dd>
          </div>
          <div>
            <dt>Priority</dt>
            <dd>{draft.priority}</dd>
          </div>
          <div>
            <dt>Risk</dt>
            <dd>{draft.risk}</dd>
          </div>
          <div>
            <dt>Source</dt>
            <dd>{draft.source}</dd>
          </div>
        </div>
      </dl>

      <div className="chat-ticket-card__actions">
        <Button disabled={isCreating} onClick={createTicket}>
          {isCreating ? 'Creating...' : 'Review & Create Ticket'}
        </Button>
        <Button variant="outline" disabled={isCreating} onClick={onContinue}>
          Continue Chat
        </Button>
      </div>
    </section>
  );
}
