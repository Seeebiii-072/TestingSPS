import { useState } from 'react';
import { API_URL } from '../../config/constants';

const CATEGORIES = [
  { value: 'cloud', label: 'Cloud' },
  { value: 'cybersecurity', label: 'Cybersecurity' },
  { value: 'identity_access', label: 'Identity and Access' },
  { value: 'devops', label: 'DevOps' },
  { value: 'internship_hr', label: 'Internship / HR' },
  { value: 'general_it', label: 'General IT' },
];

export default function SubmitTicket() {
  const [subject, setSubject] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('general_it');
  const [priority, setPriority] = useState('medium');
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');

    if (!subject.trim() || !description.trim() || !email.trim()) {
      setError('Please complete all required fields.');
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch(`${API_URL}/tickets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source: 'portal_form',
          subject: subject.trim(),
          description: description.trim(),
          category,
          priority,
          requester_email: email.trim().toLowerCase(),
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        if (response.status === 409 && errData.detail?.error === 'duplicate_ticket') {
          setMessage(
            `A similar ticket already exists: ${errData.detail.existing_ticket_number}. ` +
            `Please check its status instead of submitting a duplicate.`
          );
        } else {
          setError(errData.detail || 'Failed to submit request. Please try again later.');
        }
        return;
      }

      const ticket = await response.json();
      setMessage(
        `Submitted — ticket #${ticket.ticket_number || ticket.id}. ` +
        `You will receive an acknowledgment email at ${email}.`
      );
      setSubject('');
      setDescription('');
      setCategory('general_it');
      setPriority('medium');
    } catch {
      setError('Could not connect to the server. Please try again later.');
    } finally {
      setSubmitting(false);
    }
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
          <h2 style={{ color: '#1a1a2e', fontSize: '20px', margin: '0 0 20px' }}>Submit a Request</h2>

          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: '15px' }}>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 600, fontSize: '14px', color: '#333' }}>
                Subject / Title <span style={{ color: '#dc2626' }}>*</span>
              </label>
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
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

            <div style={{ marginBottom: '15px' }}>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 600, fontSize: '14px', color: '#333' }}>
                Description <span style={{ color: '#dc2626' }}>*</span>
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={5}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '15px',
                  boxSizing: 'border-box',
                  resize: 'vertical',
                }}
                required
              />
            </div>

            <div style={{ marginBottom: '15px' }}>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 600, fontSize: '14px', color: '#333' }}>
                Category <span style={{ color: '#dc2626' }}>*</span>
              </label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '15px',
                  boxSizing: 'border-box',
                  backgroundColor: '#fff',
                }}
              >
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>

            <div style={{ marginBottom: '15px' }}>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 600, fontSize: '14px', color: '#333' }}>
                Priority
              </label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '15px',
                  boxSizing: 'border-box',
                  backgroundColor: '#fff',
                }}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 600, fontSize: '14px', color: '#333' }}>
                Your Email Address <span style={{ color: '#dc2626' }}>*</span>
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

            {message && (
              <p style={{
                color: '#059669',
                fontSize: '14px',
                marginBottom: '15px',
                padding: '12px',
                backgroundColor: '#ecfdf5',
                borderRadius: '6px',
                border: '1px solid #a7f3d0',
              }}>
                {message}
              </p>
            )}

            <button
              type="submit"
              disabled={submitting}
              style={{
                width: '100%',
                padding: '12px',
                backgroundColor: submitting ? '#93c5fd' : '#0055a5',
                color: '#ffffff',
                border: 'none',
                borderRadius: '6px',
                fontSize: '16px',
                fontWeight: 600,
                cursor: submitting ? 'not-allowed' : 'pointer',
                marginBottom: '15px',
              }}
            >
              {submitting ? 'Submitting...' : 'Submit Request'}
            </button>
          </form>

          <div style={{ textAlign: 'center' }}>
            <a
              href="/track"
              style={{ color: '#0055a5', fontSize: '14px', textDecoration: 'none' }}
            >
              Track an existing ticket
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}