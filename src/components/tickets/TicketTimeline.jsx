const eventCodes = {
  'Email received': 'EM',
  'Form submitted': 'FM',
  'Chat escalation note': 'AI',
  'AI classification suggested': 'AI',
  'Agent assigned': 'AG',
  'Internal note added': 'IN',
  'Internal note': 'IN',
  'Portal comment received': 'PC',
  'Portal comment': 'PC',
  'Status changed': 'ST',
  'Email reply sent': 'ER',
  'Ticket Created': 'TC',
  'Agent Reply Portal': 'RP',
  'Internal Note': 'IN',
  'Status Change': 'ST',
  'Email Received': 'EM',
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

export default function TicketTimeline({ events }) {
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
        {timeline.map((event) => (
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
              <p>{event.message}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
