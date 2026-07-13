const eventCodes = {
  'Email received': 'EM',
  'Form submitted': 'FM',
  'Chat escalation note': 'AI',
  'AI classification suggested': 'AI',
  'AI classification': 'AS',
  'Agent assigned': 'AG',
  'Internal note added': 'IN',
  'Internal note': 'IN',
  'Portal comment received': 'PC',
  'Portal comment': 'PC',
  'Status changed': 'ST',
  'Email reply sent': 'ER',
  'Ticket Created': 'TC',
  'Ticket created': 'TC',
  'Agent Reply Portal': 'RP',
  'Internal Note': 'IN',
  'Status Change': 'ST',
  'Email Received': 'EM',
  'AI summary edited': 'AS',
  'Approval requested': 'AP',
  'Approval resolved': 'AP',
  'Field update': 'FU',
  'File Uploaded': 'AT',
};

function formatEventDate(value) {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value));
}

function isFileUploadEvent(event) {
  return event.eventType === 'file_uploaded' || event.type === 'File Uploaded';
}

function findEventAttachment(event, attachments) {
  if (!isFileUploadEvent(event)) return null;
  const eventFilename = String(event.message || event.content || '').trim().toLowerCase();
  return attachments.find((attachment) => attachment.name.toLowerCase() === eventFilename) || null;
}

export default function TicketTimeline({ events, attachments = [], onOpenAttachment }) {
  const timeline = [...events].sort(
    (a, b) => new Date(b.createdAt) - new Date(a.createdAt),
  );

  return (
    <div className="ticket-timeline">
      <div className="ticket-timeline__banner">
        <span aria-hidden="true">UT</span>
        <div>
          <strong>One unified ticket timeline</strong>
          <p>
            Email, portal form, AI chat, agent notes, and status updates appear
            together in chronological order.
          </p>
        </div>
      </div>

      <ol className="ticket-timeline__list">
        {timeline.map((event) => {
          const attachment = findEventAttachment(event, attachments);
          return (
            <li className="ticket-timeline__event" key={event.id}>
              <span className="ticket-timeline__event-icon" aria-hidden="true">
                {eventCodes[event.type] || 'EV'}
              </span>
              <div className="ticket-timeline__event-card">
                <div className="ticket-timeline__event-heading">
                  <div>
                    <strong>{event.type}</strong>
                    <span>{event.actor}</span>
                  </div>
                  <time dateTime={event.createdAt}>{formatEventDate(event.createdAt)}</time>
                </div>
                {attachment && onOpenAttachment ? (
                  <button
                    type="button"
                    className="ticket-timeline__attachment"
                    onClick={() => onOpenAttachment(attachment)}
                  >
                    <span aria-hidden="true">AT</span>
                    <span>{attachment.name}</span>
                  </button>
                ) : (
                  <p>{event.message}</p>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
