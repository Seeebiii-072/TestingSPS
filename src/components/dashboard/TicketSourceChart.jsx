const sourceMeta = {
  Email: {
    icon: 'EM',
    description: 'Inbound requests converted from the shared support mailbox.',
    trend: '+4.2%',
  },
  'Portal Form': {
    icon: 'WF',
    description: 'Structured requests submitted through the web portal.',
    trend: '+8.1%',
  },
  Chat: {
    icon: 'AI',
    description: 'AI conversations escalated for human support.',
    trend: '+12.5%',
  },
};

export default function TicketSourceChart({ sources }) {
  const total = sources.reduce((sum, source) => sum + source.value, 0);

  return (
    <section className="channel-summary-grid" aria-label="Ticket channel summary">
      {sources.map((source) => {
        const meta = sourceMeta[source.label];
        const percentage = total > 0 ? Math.round((source.value / total) * 100) : 0;

        return (
          <article className="channel-summary-card" key={source.label}>
            <div className="channel-summary-card__header">
              <span className="channel-summary-card__icon" aria-hidden="true">
                {meta.icon}
              </span>
              <span className="channel-summary-card__trend">{meta.trend}</span>
            </div>
            <strong>{source.value}</strong>
            <h2>
              {source.label === 'Email'
                ? 'Email Tickets'
                : source.label === 'Portal Form'
                  ? 'Web Form Tickets'
                  : 'Chat Escalations'}
            </h2>
            <p>{meta.description}</p>
            <div className="channel-summary-card__bar" aria-label={`${percentage}% of tickets`}>
              <span style={{ width: `${percentage}%`, background: source.color }} />
            </div>
          </article>
        );
      })}
    </section>
  );
}
