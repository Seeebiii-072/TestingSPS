import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AsyncState from '../../components/common/AsyncState';
import Badge from '../../components/common/Badge';
import TicketFilters from '../../components/tickets/TicketFilters';
import TicketTable from '../../components/tickets/TicketTable';
import { getTickets } from '../../services/ticketService.js';

const emptyFilters = {
  search: '',
  source: '',
  status: '',
  priority: '',
  category: '',
  risk: '',
};

export default function TicketQueue() {
  const navigate = useNavigate();
  const [filters, setFilters] = useState(emptyFilters);
  const [tickets, setTickets] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);
    setError('');

    getTickets(filters).then((results) => {
      if (!isMounted) return;
      setTickets(results);
      setIsLoading(false);
    }).catch(() => {
      if (!isMounted) return;
      setError('The ticket queue could not be loaded from the backend.');
      setIsLoading(false);
    });

    return () => {
      isMounted = false;
    };
  }, [filters]);

  const updateFilter = (name, value) => {
    setFilters((current) => ({ ...current, [name]: value }));
  };

  return (
    <section className="page ticket-queue-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Agent workspace</p>
          <h1>Ticket Queue</h1>
          <p>
            Review, filter, and open tickets from email, portal forms, and AI
            chat escalations.
          </p>
        </div>
        <Badge tone="blue">{tickets.length} tickets shown</Badge>
      </div>

      <TicketFilters
        filters={filters}
        onChange={updateFilter}
        onReset={() => setFilters(emptyFilters)}
      />

      <section className="ticket-queue-table-card" aria-label="Filtered ticket queue">
        <div className="ticket-queue-table-card__heading">
          <div>
            <strong>Unified ticket queue</strong>
            <span>Click any row to open the complete ticket timeline.</span>
          </div>
          <Badge tone={isLoading ? 'amber' : 'green'}>
            {isLoading ? 'Refreshing' : 'Live backend data'}
          </Badge>
        </div>
        {error ? (
          <AsyncState type="error" title="Ticket queue unavailable" description={error} onAction={() => setFilters({ ...filters })} />
        ) : isLoading ? (
          <AsyncState title="Loading ticket queue" description="Applying filters to backend tickets." />
        ) : (
          <TicketTable
            tickets={tickets}
            onSelectTicket={(ticket) => navigate(`/agent/tickets/${ticket.id}`)}
          />
        )}
      </section>
    </section>
  );
}
