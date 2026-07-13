import { useEffect, useState } from 'react';
import Button from '../common/Button';
import CategorySelect from './CategorySelect';
import FileUpload from './FileUpload';
import { enhanceDescription } from '../../services/aiService';

const priorityOptions = [
  ['low', 'Low'],
  ['medium', 'Medium'],
  ['high', 'High'],
  ['critical', 'Critical'],
];

const initialForm = {
  subject: '',
  description: '',
  category: '',
  priority: 'medium',
  requesterEmail: '',
};

export default function RequestForm({
  onSubmit,
  requesterEmail = '',
  lockRequesterEmail = false,
}) {
  const [form, setForm] = useState({
    ...initialForm,
    requesterEmail,
  });
  const [attachments, setAttachments] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [aiEnhancedDescription, setAiEnhancedDescription] = useState(null);
  const [isEnhancing, setIsEnhancing] = useState(false);
  const [enhanceError, setEnhanceError] = useState('');
  const [showEnhancementPreview, setShowEnhancementPreview] = useState(false);
  const [originalDescription, setOriginalDescription] = useState('');

  useEffect(() => {
    if (!requesterEmail) return;
    setForm((current) => ({ ...current, requesterEmail }));
  }, [requesterEmail]);

  const updateField = (event) => {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  };

  const handleEnhanceDescription = async () => {
    if (!form.subject.trim() || !form.description.trim()) return;
    setIsEnhancing(true);
    setEnhanceError('');
    try {
      const response = await enhanceDescription(form.subject.trim(), form.description.trim());
      let enhanced = response.summary || response.enhanced_description || response.description;
      
      setOriginalDescription(form.description);
      setAiEnhancedDescription(enhanced);
      setForm((current) => ({ ...current, description: enhanced }));
      setShowEnhancementPreview(true);
    } catch {
      setEnhanceError('Could not enhance description with AI. You can still submit your original description.');
    } finally {
      setIsEnhancing(false);
    }
  };

  const acceptEnhancement = () => {
    setShowEnhancementPreview(false);
    setAiEnhancedDescription(null);
  };

  const rejectEnhancement = () => {
    setForm((current) => ({ ...current, description: originalDescription }));
    setShowEnhancementPreview(false);
    setAiEnhancedDescription(null);
  };

  const submitForm = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const finalDescription = (aiEnhancedDescription || form.description).trim();
      await onSubmit({
        ...form,
        description: finalDescription,
        aiSummary: finalDescription,
        attachments,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form className="request-form" onSubmit={submitForm}>
      <div className="request-form__grid">
        <label className="request-field request-field--full">
          <span>Subject / title</span>
          <input
            name="subject"
            required
            value={form.subject}
            placeholder="Briefly describe what you need help with"
            onChange={updateField}
          />
        </label>

        <label className="request-field request-field--full">
          <span>Description</span>
          <textarea
            name="description"
            required
            value={form.description}
            placeholder="Include the impact, relevant error messages, and steps already tried"
            onChange={updateField}
          />
          <small>Do not include passwords, recovery codes, or other secrets.</small>
        </label>

        <CategorySelect value={form.category} onChange={updateField} />

        <label className="request-field">
          <span>Priority hint</span>
          <select name="priority" value={form.priority} onChange={updateField}>
            {priorityOptions.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <small>The service desk will confirm the final priority.</small>
        </label>

        <label className="request-field request-field--full">
          <span>Contact email</span>
          <input
            name="requesterEmail"
            type="email"
            required
            value={form.requesterEmail}
            readOnly={lockRequesterEmail}
            onChange={updateField}
          />
        </label>

        <div className="request-field request-field--full">
          <FileUpload
            onUploaded={(attachment) =>
              setAttachments((current) => [...current, attachment])
            }
          />
        </div>

        <div className="request-field request-field--full request-form__ai-enhance" style={{ marginTop: '10px' }}>
          {!showEnhancementPreview && (
            <Button
              type="button"
              variant="outline"
              onClick={handleEnhanceDescription}
              disabled={isEnhancing || !form.subject.trim() || !form.description.trim()}
            >
              {isEnhancing ? 'Enhancing...' : 'Enhance Description with AI'}
            </Button>
          )}
          {enhanceError && <p className="form-error" style={{ marginTop: '8px', color: 'red' }}>{enhanceError}</p>}
          {showEnhancementPreview && (
            <div className="ai-enhanced-preview" style={{ marginTop: '12px', padding: '8px', backgroundColor: '#f0f7ff', borderRadius: '4px', border: '1px solid #1565c0' }}>
              <span style={{ fontWeight: 'bold', display: 'block', marginBottom: '6px', color: '#1565c0' }}>✨ AI Enhanced Description Preview:</span>
              <textarea
                className="chat-ticket-card__textarea"
                value={aiEnhancedDescription}
                readOnly
                rows={5}
                style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #ddd', backgroundColor: '#f9f9f9', fontFamily: 'inherit' }}
              />
              <div style={{ display: 'flex', gap: '6px', marginTop: '8px' }}>
                <Button
                  type="button"
                  variant="outline"
                  onClick={acceptEnhancement}
                  style={{ flex: 1, fontSize: '0.8rem', padding: '4px 10px', backgroundColor: '#4caf50', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}
                >
                  <span>✓</span> Accept
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={rejectEnhancement}
                  style={{ flex: 1, fontSize: '0.8rem', padding: '4px 10px', backgroundColor: '#f44336', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}
                >
                  <span>✗</span> Reject
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="request-form__footer">
        <p>Submitting creates a real portal-form ticket through the backend API.</p>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Submitting request...' : 'Submit Request'}
        </Button>
      </div>
    </form>
  );
}
