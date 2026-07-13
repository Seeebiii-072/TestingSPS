import { useEffect, useState } from 'react';
import ticketService from '../../services/ticketService.js';
import { useAuth } from '../../context/AuthContext';
import { enhanceDescription } from '../../services/aiService';

const CATEGORIES = [
  'Cloud',
  'Cybersecurity',
  'Identity and Access',
  'DevOps',
  'Internship/HR',
  'General IT',
];

export default function GuestReportForm() {
  const { user } = useAuth();
  const [subject, setSubject] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [priority, setPriority] = useState('medium');
  const [files, setFiles] = useState([]);
  const [email, setEmail] = useState(user?.email || '');
  const [aiEnhancedDescription, setAiEnhancedDescription] = useState(null);
  const [isEnhancing, setIsEnhancing] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [showEnhancementPreview, setShowEnhancementPreview] = useState(false);
  const [isDescriptionEnhanced, setIsDescriptionEnhanced] = useState(false);
  const [showAcceptReject, setShowAcceptReject] = useState(false);
  const [originalDescription, setOriginalDescription] = useState('');
  const [isEnhancedAccepted, setIsEnhancedAccepted] = useState(false);

  useEffect(() => {
    if (user?.email) {
      setEmail(user.email);
    }
  }, [user?.email]);

  const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024;

  const onFilesChange = (e) => {
    const selectedFiles = Array.from(e.target.files || []);
    const oversized = selectedFiles.filter((f) => f.size > MAX_FILE_SIZE_BYTES);
    if (oversized.length > 0) {
      setError(`File(s) exceed 5MB limit: ${oversized.map((f) => f.name).join(', ')}`);
      return;
    }
    setFiles(selectedFiles);
    setError('');
  };

  const handleEnhanceDescription = async () => {
    if (!subject.trim() || !description.trim()) return;
    setIsEnhancing(true);
    try {
      const response = await enhanceDescription(subject.trim(), description.trim());
      let enhanced = response.enhanced_description || response.summary || response.description;
      
      // Store original description before enhancing
      setOriginalDescription(description);
      setAiEnhancedDescription(enhanced);
      setDescription(enhanced);
      setShowEnhancementPreview(true);
      setShowAcceptReject(true);
    } catch {
      setError('Could not enhance description with AI. You can still submit your original description.');
    } finally {
      setIsEnhancing(false);
    }
  };

  const acceptEnhancement = () => {
    // Keep the enhanced description (already set in handleEnhanceDescription)
    setShowAcceptReject(false);
    setShowEnhancementPreview(false);
    setAiEnhancedDescription(null);
    setIsEnhancedAccepted(true);
  };

  const rejectEnhancement = () => {
    // Restore original description
    setDescription(originalDescription);
    setShowAcceptReject(false);
    setShowEnhancementPreview(false);
    setAiEnhancedDescription(null);
    setIsEnhancedAccepted(false);
  };

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');

    if (!subject.trim() || !description.trim() || !category || !email.trim()) {
      setError('Please complete the required fields.');
      return;
    }

    setIsSubmitting(true);
    try {
      const finalDescription = (aiEnhancedDescription || description).trim();
      const payload = {
        subject: subject.trim(),
        description: finalDescription,
        category,
        priority,
        requester_email: (user?.email || email).trim(),
      };

      // create ticket from portal form
      const ticket = await ticketService.createTicketFromForm(payload);

      // upload attachments if any
      if (files.length && ticket?.id) {
        // limit: 5 files
        const uploadFiles = files.slice(0, 5);
        const requesterEmail = user?.email || email;
        for (const f of uploadFiles) {
          try {
            await ticketService.uploadFile(ticket.id, f, requesterEmail);
          } catch (uploadErr) {
            console.warn('Attachment upload failed', uploadErr);
            setError(`Attachment upload failed: ${uploadErr?.response?.data?.detail || uploadErr?.message || 'Unknown error'}`);
            // Continue with submission - don't block the ticket
          }
        }
      }

      setMessage(`Submitted — ticket #${ticket.ticketNumber || ticket.id || 'created'}. We will follow up via email.`);
      setSubject('');
      setDescription('');
      setFiles([]);
      if (!user) setEmail('');
    } catch (err) {
      console.error(err);
      setError('Failed to submit report. Please try again later.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form className="guest-form" onSubmit={submit}>
      <h3>Guest reporting form</h3>
      <label>
        Subject / title (required)
        <input value={subject} onChange={(e) => setSubject(e.target.value)} required />
      </label>

      <label>
        Description (required)
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          required
          rows={5}
          style={showEnhancementPreview ? { border: '2px solid #1565c0', backgroundColor: '#e3f2fd' } : {}}
        />
      </label>

      {showEnhancementPreview && (
        <div style={{ margin: '6px 0', padding: '8px', backgroundColor: '#f0f7ff', borderRadius: '4px', border: '1px solid #1565c0' }}>
          <p style={{ fontSize: '0.75rem', fontWeight: '600', color: '#1565c0', marginBottom: '6px' }}>✨ Enhanced Description:</p>
          <div style={{ display: 'flex', gap: '6px', marginTop: '8px' }}>
            <button
              type="button"
              onClick={acceptEnhancement}
              style={{ fontSize: '0.8rem', padding: '4px 10px', backgroundColor: '#4caf50', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', flex: 1 }}
            >
              <span>✓</span> Accept
            </button>
            <button
              type="button"
              onClick={rejectEnhancement}
              style={{ fontSize: '0.8rem', padding: '4px 10px', backgroundColor: '#f44336', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', flex: 1 }}
            >
              <span>✗</span> Reject
            </button>
          </div>
        </div>
      )}

      {!showEnhancementPreview && (
        <div className="guest-form__ai-enhance" style={{ margin: '8px 0' }}>
          <button
            type="button"
            className="secondary-button"
            onClick={handleEnhanceDescription}
            disabled={isEnhancing || !subject.trim() || !description.trim()}
            style={{ width: '100%', fontSize: '0.85rem', padding: '6px 12px' }}
          >
            {isEnhancing ? 'Enhancing...' : '✨ Enhance Description with AI'}
          </button>
        </div>
      )}

      <label>
        Category (required)
        <select value={category} onChange={(e) => setCategory(e.target.value)} required>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </label>

      <label>
        Priority hint (optional)
        <select value={priority} onChange={(e) => setPriority(e.target.value)}>
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
        </select>
      </label>

      <label>
        Attachments (screenshots, logs) — max 5 files, 5MB each
        <input type="file" onChange={onFilesChange} multiple />
      </label>

      <label>
        Contact email {user ? '(prefilled)' : '(required)'}
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          disabled={!!user}
        />
      </label>

      {error && <p className="form-error" role="alert">{error}</p>}
      {message && <p className="form-success">{message}</p>}

      <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
        <button className="secondary-button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Submitting...' : 'Submit report'}
        </button>
      </div>
    </form>
  );
}
