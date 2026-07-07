import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { API_URL } from '../../config/constants';

export default function TrackTicket() {
  const [searchParams] = useSearchParams();
  const [ticketNumber, setTicketNumber] = useState(searchParams.get('ticket') || '');
  const [email, setEmail] = useState(searchParams.get('email') || '');
  const [ticket, setTicket] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const lookupTicket = async (ticketNum, emailAddr) => {
    setError('');
    setTicket(null);
    setLoading(true);
    try {
      const params = new URLSearchParams({ email: emailAddr.trim().toLowerCase() });
      const response = await fetch(
        `${API_URL}/tickets/public/${encodeURIComponent(ticketNum.trim())}?${params}`,
      );
      if (!response.ok) {
        if (response.status === 404) {
          setError('No ticket found with that number and email combination.');
        } else {
          setError('Failed to look up ticket. Please try again later.');
        }
        return;
      }
      const data = await response.json();
      setTicket(data);
    } catch {
      setError('Could not connect to the server. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  // Auto-submit if ticket and email are provided via query params
  useEffect(() => {
    const ticketParam = searchParams.get('ticket');
    const emailParam = searchParams.get('email');
    if (ticketParam && emailParam) {
      const timer = setTimeout(() => {
        lookupTicket(ticketParam, emailParam);
      }, 100);
      return () => clearTimeout(timer);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    await lookupTicket(ticketNumber, email);
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleString();
  };

  const statusLabel = (status) => {
    if (!status) return 'Unknown';
    return status.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
  };

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#f4f6f9',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      padding: '40px 20px',
    }}>
      <div style={{
        width: '100%',
        maxWidth: '600px',
        backgroundColor: '#ffffff',
        borderRadius: '8px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
        overflow: 'hidden',
      }}>
        <div style={{
          backgroundColor: '#0055a5',
          padding: '30px 40px',
          textAlign: 'center',
        }}>
          <h1 style={{ color: '#ffffff', margin: 0, fontSize: '24px' }}>SPS SecureDesk AI</h1>
          <p style={{ color: '#d4e4f7', margin: '5px 0 0', fontSize: '14px' }}>IT Helpdesk</p>
        </div>

        <div style={{ padding: '30px 40px' }}>
          <h2 style={{ color: '#1a1a2e', fontSize: '20px', margin: '0 0 20px' }}>Track Your Ticket</h2>

          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: '15px' }}>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 600, fontSize: '14px', color: '#333' }}>
                Ticket Number
              </label>
              <input
                type="text"
                placeholder="e.g. SPS-2026-001"
                value={ticketNumber}
                onChange={(e) => setTicketNumber(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '15px',
                  boxSizing: 'border-box',
                }}
                required
              />
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 600, fontSize: '14px', color: '#333' }}>
                Your Email Address
              </label>
              <input
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '15px',
                  boxSizing: 'border-box',
                }}
                required
              />
            </div>

            {error && (
              <p style={{ color: '#dc2626', fontSize: '14px', marginBottom: '15px' }} role="alert">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%',
                padding: '12px',
                backgroundColor: loading ? '#93c5fd' : '#0055a5',
                color: '#ffffff',
                border: 'none',
                borderRadius: '6px',
                fontSize: '16px',
                fontWeight: 600,
                cursor: loading ? 'not-allowed' : 'pointer',
              }}
            >
              {loading ? 'Looking up...' : 'View Ticket'}
            </button>
          </form>

          <div style={{ marginTop: '20px', textAlign: 'center' }}>
            <a
              href="/submit"
              style={{ color: '#0055a5', fontSize: '14px', textDecoration: 'none' }}
            >
              Submit a new request
            </a>
          </div>
        </div>
      </div>

      {ticket && (
        <div style={{
          width: '100%',
          maxWidth: '600px',
          marginTop: '20px',
          backgroundColor: '#ffffff',
          borderRadius: '8px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
          overflow: 'hidden',
        }}>
          <div style={{
            backgroundColor: '#f8fafc',
            padding: '20px 40px',
            borderBottom: '1px solid #e2e8f0',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0, color: '#0055a5', fontSize: '18px' }}>
                {ticket.ticket_number}
              </h3>
              <span style={{
                display: 'inline-block',
                padding: '4px 12px',
                borderRadius: '12px',
                fontSize: '12px',
                fontWeight: 600,
                backgroundColor: ticket.status === 'duplicate' ? '#f3f4f6' :
                  ticket.status === 'closed' ? '#f3f4f6' :
                  ticket.status === 'resolved' ? '#ccfbf1' :
                  ticket.status === 'open' ? '#dbeafe' : '#fef3c7',
                color: ticket.status === 'duplicate' ? '#6b7280' :
                  ticket.status === 'closed' ? '#6b7280' :
                  ticket.status === 'resolved' ? '#0f766e' :
                  ticket.status === 'open' ? '#1d4ed8' : '#b45309',
                textDecoration: ticket.status === 'duplicate' ? 'line-through' : 'none',
              }}>
                {statusLabel(ticket.status)}
              </span>
            </div>
          </div>

          <div style={{ padding: '20px 40px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <tbody>
                <tr>
                  <td style={{ color: '#888', fontSize: '13px', padding: '6px 0', width: '120px' }}>Subject</td>
                  <td style={{ color: '#1a1a2e', fontSize: '14px', padding: '6px 0', fontWeight: 600 }}>{ticket.subject}</td>
                </tr>
                <tr>
                  <td style={{ color: '#888', fontSize: '13px', padding: '6px 0' }}>Category</td>
                  <td style={{ color: '#1a1a2e', fontSize: '14px', padding: '6px 0' }}>
                    {ticket.category?.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                  </td>
                </tr>
                <tr>
                  <td style={{ color: '#888', fontSize: '13px', padding: '6px 0' }}>Priority</td>
                  <td style={{ color: '#1a1a2e', fontSize: '14px', padding: '6px 0', textTransform: 'capitalize' }}>
                    {ticket.priority}
                  </td>
                </tr>
                <tr>
                  <td style={{ color: '#888', fontSize: '13px', padding: '6px 0' }}>Team</td>
                  <td style={{ color: '#1a1a2e', fontSize: '14px', padding: '6px 0', textTransform: 'capitalize' }}>
                    {ticket.team}
                  </td>
                </tr>
                <tr>
                  <td style={{ color: '#888', fontSize: '13px', padding: '6px 0' }}>Created</td>
                  <td style={{ color: '#1a1a2e', fontSize: '14px', padding: '6px 0' }}>{formatDate(ticket.created_at)}</td>
                </tr>
                <tr>
                  <td style={{ color: '#888', fontSize: '13px', padding: '6px 0' }}>Updated</td>
                  <td style={{ color: '#1a1a2e', fontSize: '14px', padding: '6px 0' }}>{formatDate(ticket.updated_at)}</td>
                </tr>
              </tbody>
            </table>

            {ticket.description && (
              <div style={{ marginTop: '15px', padding: '15px', backgroundColor: '#f9fafb', borderRadius: '6px' }}>
                <h4 style={{ margin: '0 0 8px', fontSize: '13px', color: '#888' }}>Description</h4>
                <p style={{ margin: 0, color: '#333', fontSize: '14px', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
                  {ticket.description}
                </p>
              </div>
            )}

            <div style={{ marginTop: '15px', borderTop: '1px solid #e2e8f0', paddingTop: '15px' }}>
              <h4 style={{ margin: '0 0 10px', fontSize: '13px', color: '#888' }}>Timeline</h4>
              {(ticket.timeline_events || []).length === 0 && (
                <p style={{ color: '#999', fontSize: '13px' }}>No updates yet.</p>
              )}
              {(ticket.timeline_events || []).map((event) => (
                <div key={event.id} style={{
                  padding: '10px 0',
                  borderBottom: '1px solid #f0f0f0',
                  fontSize: '13px',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <strong style={{ color: '#0055a5' }}>
                      {event.event_type?.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                    </strong>
                    <span style={{ color: '#999', fontSize: '12px' }}>{formatDate(event.created_at)}</span>
                  </div>
                  {event.content && <p style={{ margin: '4px 0 0', color: '#555' }}>{event.content}</p>}
                  {event.actor_email && (
                    <p style={{ margin: '2px 0 0', color: '#999', fontSize: '12px' }}>by {event.actor_email}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}