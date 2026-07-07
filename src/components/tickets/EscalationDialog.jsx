import { useState } from 'react';
import Button from '../common/Button';

const teams = [
  { value: 'it', label: 'IT Support' },
  { value: 'hr', label: 'HR / People Operations' },
  { value: 'security', label: 'Cybersecurity' },
  { value: 'devops', label: 'DevOps / Infrastructure' },
  { value: 'management', label: 'Management' },
];

export default function EscalationDialog({ ticket, onEscalate, onCancel }) {
  const [selectedTeam, setSelectedTeam] = useState('');
  const [details, setDetails] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!selectedTeam.trim() || !details.trim()) return;
    setIsSubmitting(true);
    try {
      await onEscalate({
        team: selectedTeam,
        note: details,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="escalation-dialog-overlay" onClick={onCancel}>
      <div className="escalation-dialog" onClick={(e) => e.stopPropagation()}>
        <header className="escalation-dialog__header">
          <h2>Escalate Ticket</h2>
          <p>Route this ticket to a specialized team with details</p>
        </header>

        <section className="escalation-dialog__content">
          <div className="escalation-dialog__section">
            <h3>Select Team</h3>
            <select
              className="escalation-dialog__select"
              value={selectedTeam}
              onChange={(e) => setSelectedTeam(e.target.value)}
              disabled={isSubmitting}
            >
              <option value="">Choose a team...</option>
              {teams.map((team) => (
                <option key={team.value} value={team.value}>
                  {team.label}
                </option>
              ))}
            </select>
          </div>

          <div className="escalation-dialog__section">
            <h3>Ticket Details</h3>
            <div className="escalation-dialog__details">
              <div className="escalation-detail-item">
                <dt>Ticket #</dt>
                <dd>{ticket.ticketNumber || ticket.id}</dd>
              </div>
              <div className="escalation-detail-item">
                <dt>Subject</dt>
                <dd>{ticket.subject}</dd>
              </div>
              <div className="escalation-detail-item">
                <dt>Requester</dt>
                <dd>{ticket.requesterName}</dd>
              </div>
              <div className="escalation-detail-item">
                <dt>Priority</dt>
                <dd>{ticket.priority}</dd>
              </div>
              <div className="escalation-detail-item">
                <dt>Category</dt>
                <dd>{ticket.category}</dd>
              </div>
            </div>
          </div>

          <div className="escalation-dialog__section">
            <h3>Escalation Note</h3>
            <textarea
              className="escalation-dialog__textarea"
              placeholder="Explain why this ticket is being escalated and any relevant context..."
              value={details}
              onChange={(e) => setDetails(e.target.value)}
              disabled={isSubmitting}
              rows={6}
            />
          </div>
        </section>

        <footer className="escalation-dialog__footer">
          <Button variant="outline" onClick={onCancel} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={handleSubmit}
            disabled={isSubmitting || !selectedTeam.trim() || !details.trim()}
          >
            {isSubmitting ? 'Escalating...' : 'Escalate Ticket'}
          </Button>
        </footer>
      </div>
    </div>
  );
}
