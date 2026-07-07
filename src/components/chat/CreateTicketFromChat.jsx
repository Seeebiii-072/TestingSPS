import { useEffect, useMemo, useRef, useState } from 'react';
import Button from '../common/Button';
import { enhanceDescription } from '../../services/aiService';

const defaultTicketDraft = {
  subject: 'Helpdesk assistance requested from SecureDesk AI',
  summary: 'The AI assistant could not fully resolve the user request.',
  category: 'general_it',
  priority: 'medium',
  risk: 'standard',
  source: 'chat',
};

const MAX_ATTACHMENT_SIZE_BYTES = 5 * 1024 * 1024;
const ALLOWED_EXTENSIONS = ['png', 'jpg', 'jpeg', 'pdf', 'docx', 'txt'];

function isAllowedFile(file) {
  const extension = String(file?.name || '').split('.').pop()?.toLowerCase() || '';
  return ALLOWED_EXTENSIONS.includes(extension);
}

function formatPriority(priority) {
  return String(priority || 'medium')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export default function CreateTicketFromChat({
  draft = defaultTicketDraft,
  onContinue,
  onCreate,
  onCreated,
}) {
  const [isCreating, setIsCreating] = useState(false);
  const [createdTicket, setCreatedTicket] = useState(null);
  const [issueTitle, setIssueTitle] = useState('');
  const [issueDescription, setIssueDescription] = useState('');
  const [aiEnhancedDescription, setAiEnhancedDescription] = useState(null);
  const [isEnhancing, setIsEnhancing] = useState(false);
  const [attachment, setAttachment] = useState(null);
  const [formError, setFormError] = useState('');
  const [isDragActive, setIsDragActive] = useState(false);
  const [showEnhancementPreview, setShowEnhancementPreview] = useState(false);
  const [originalDescription, setOriginalDescription] = useState('');
  const fileInputRef = useRef(null);

  useEffect(() => {
    setIssueTitle(draft?.subject || '');
    setIssueDescription(draft?.summary || '');
    setAttachment(null);
    setFormError('');
    setIsDragActive(false);
    setCreatedTicket(null);
  }, [draft]);

  const acceptedFileTypesText = useMemo(
    () => 'PNG, JPG, JPEG, PDF, DOCX, TXT (Max 5MB)',
    [],
  );

  const handleAttachmentSelect = (file) => {
    if (!file) return;

    if (!isAllowedFile(file)) {
      setFormError('Unsupported file type. Please upload PNG, JPG, JPEG, PDF, DOCX, or TXT.');
      return;
    }

    if (file.size > MAX_ATTACHMENT_SIZE_BYTES) {
      setFormError('File size exceeds 5MB limit. Please upload a smaller file.');
      return;
    }

    setAttachment(file);
    setFormError('');
  };

  const handleFileInputChange = (event) => {
    const [file] = event.target.files || [];
    handleAttachmentSelect(file);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setIsDragActive(false);
    const [file] = event.dataTransfer.files || [];
    handleAttachmentSelect(file);
  };

  const handleDragOver = (event) => {
    event.preventDefault();
    setIsDragActive(true);
  };

  const handleDragLeave = (event) => {
    event.preventDefault();
    setIsDragActive(false);
  };

  const handleEnhanceDescription = async () => {
    if (!issueTitle || !issueDescription) return;
    setIsEnhancing(true);
    try {
      const response = await enhanceDescription(issueTitle, issueDescription);
      let enhanced = response.summary || response.enhanced_description || response.description;
      
      // Fix first-person perspective: replace all variations of "user" with "I" or "my"
      enhanced = enhanced
        .replace(/[Tt]he [Uu]ser/g, 'I')
        .replace(/the user/g, 'I')
        .replace(/[Tt]he [Uu]ser's/g, "My")
        .replace(/[Uu]ser's/g, "my")
        .replace(/\b[Tt]he [Uu]ser\b/g, 'I')
        .replace(/\bthe user\b/g, 'I')
        .replace(/I'm/g, 'I am')
        .replace(/\bi am\b/gi, 'I am')
        .replace(/  +/g, ' ');
      
      setOriginalDescription(issueDescription);
      setAiEnhancedDescription(enhanced);
      setIssueDescription(enhanced);
      setShowEnhancementPreview(true);
    } catch {
      setFormError('Could not enhance description with AI. You can still submit your original description.');
    } finally {
      setIsEnhancing(false);
    }
  };

  const acceptEnhancement = () => {
    setShowEnhancementPreview(false);
    setAiEnhancedDescription(null);
  };

  const rejectEnhancement = () => {
    setIssueDescription(originalDescription);
    setShowEnhancementPreview(false);
    setAiEnhancedDescription(null);
  };

  const createTicket = async () => {
    const title = issueTitle.trim();
    const description = (aiEnhancedDescription || issueDescription).trim();

    if (!title || !issueDescription.trim()) {
      setFormError('Issue Title and Issue Description are required.');
      return;
    }

    setFormError('');
    setIsCreating(true);

    try {
      const ticketPayload = {
        ...draft,
        subject: title,
        summary: description,
        description,
      };

      const ticket = await onCreate(ticketPayload, attachment);
      setCreatedTicket(ticket);
      onCreated?.(ticket?.ticketNumber || ticket?.ticket_number || ticket?.id || 'created');
    } catch {
      setFormError('Ticket could not be created. Please try again.');
    } finally {
      setIsCreating(false);
    }
  };

  if (createdTicket) {
    const ticketId = createdTicket.ticketNumber || createdTicket.ticket_number || createdTicket.id;
    const assignedDepartment = createdTicket.assignedTeam || createdTicket.team || 'Auto-assigned';
    const priority = formatPriority(createdTicket.priority);
    const estimatedResponse = createdTicket.sla || 'Will be shared by support team';

    return (
      <section className="chat-ticket-card chat-ticket-card--confirmation" role="status" aria-live="polite">
        <div className="chat-ticket-card__confirmation-icon" aria-hidden="true">✓</div>
        <div className="chat-ticket-card__confirmation-content">
          <h3>Ticket Created Successfully</h3>
          <p>Your request has been submitted successfully.</p>

          <dl className="chat-ticket-card__confirmation-grid">
            <div>
              <dt>Ticket ID</dt>
              <dd>{ticketId}</dd>
            </div>
            <div>
              <dt>Assigned Department</dt>
              <dd>{assignedDepartment}</dd>
            </div>
            <div>
              <dt>Priority</dt>
              <dd>{priority}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>Open</dd>
            </div>
            <div>
              <dt>Estimated Response</dt>
              <dd>{estimatedResponse}</dd>
            </div>
          </dl>

          <div className="chat-ticket-card__actions">
            <Button onClick={onContinue}>Return to Chat</Button>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="chat-ticket-card chat-ticket-card--modern" aria-label="Create support ticket">
      <div className="chat-ticket-card__header">
        <div className="chat-ticket-card__header-icon" aria-hidden="true">🎫</div>
        <div>
          <h3>Create Support Ticket</h3>
          <p>
            I couldn't find the requested information in the Knowledge Base.
            Please provide a few details below.
            Our AI will automatically classify your request and route it to the correct team.
          </p>
        </div>
      </div>

      <div className="chat-ticket-card__form">
        <label className="chat-ticket-card__field">
          <span>Issue Title</span>
          <input
            type="text"
            className="chat-ticket-card__input"
            value={issueTitle}
            onChange={(event) => setIssueTitle(event.target.value)}
            placeholder='Example: "Unable to access VPN"'
            maxLength={200}
            required
            aria-label="Issue Title"
          />
        </label>

        <label className="chat-ticket-card__field">
          <span>Issue Description</span>
          <textarea
            className="chat-ticket-card__textarea chat-ticket-card__textarea--large"
            value={issueDescription}
            onChange={(event) => setIssueDescription(event.target.value)}
            rows={8}
            maxLength={3000}
            required
            aria-label="Issue Description"
            placeholder={'Describe your issue in as much detail as possible.\n\nInclude:\n• What happened\n• When it happened\n• Error messages\n• Steps already tried\n• Expected behaviour'}
          />
        </label>

        <div className="chat-ticket-card__ai-enhance" style={{ margin: '6px 0' }}>
          {!showEnhancementPreview && (
            <Button
              type="button"
              variant="outline"
              onClick={handleEnhanceDescription}
              disabled={isEnhancing || !issueTitle || !issueDescription}
              style={{ fontSize: '0.8rem', padding: '4px 10px' }}
            >
              {isEnhancing ? 'Enhancing...' : '✨ Enhance with AI'}
            </Button>
          )}
          {showEnhancementPreview && (
            <div className="ai-enhanced-preview" style={{ marginTop: '6px', padding: '6px', backgroundColor: '#f0f7ff', borderRadius: '4px', border: '1px solid #1565c0' }}>
              <h4 style={{ fontSize: '0.7rem', marginBottom: '3px', fontWeight: '600', color: '#1565c0' }}>✨ AI Enhanced Preview:</h4>
              <textarea
                className="chat-ticket-card__textarea"
                value={aiEnhancedDescription}
                readOnly
                rows={4}
                style={{ fontSize: '0.8rem', padding: '4px' }}
              />
              <div style={{ display: 'flex', gap: '6px', marginTop: '6px' }}>
                <Button
                  type="button"
                  variant="outline"
                  onClick={acceptEnhancement}
                  style={{ flex: 1, fontSize: '0.7rem', padding: '3px 7px', backgroundColor: '#4caf50', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}
                >
                  <span>✓</span> Accept
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={rejectEnhancement}
                  style={{ flex: 1, fontSize: '0.7rem', padding: '3px 7px', backgroundColor: '#f44336', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}
                >
                  <span>✗</span> Reject
                </Button>
              </div>
            </div>
          )}
        </div>

        <div className="chat-ticket-card__field">
          <span>Attachment (Optional)</span>
          <div
            className={`chat-ticket-card__dropzone ${isDragActive ? 'chat-ticket-card__dropzone--active' : ''}`}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            role="button"
            tabIndex={0}
            aria-label="Attachment upload area"
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                fileInputRef.current?.click();
              }
            }}
          >
            <input
              ref={fileInputRef}
              type="file"
              className="chat-ticket-card__file-input"
              onChange={handleFileInputChange}
              accept=".png,.jpg,.jpeg,.pdf,.docx,.txt"
              aria-label="Upload attachment"
            />
            <p>Drag & drop file here or click to upload</p>
            <small>{acceptedFileTypesText}</small>
            {attachment && (
              <strong className="chat-ticket-card__file-name">{attachment.name}</strong>
            )}
          </div>
        </div>
      </div>

      <div className="chat-ticket-card__next-steps">
        <strong>What happens next?</strong>
        <ul>
          <li>AI classifies the request</li>
          <li>Department assigned automatically</li>
          <li>Ticket created</li>
          <li>Support team notified</li>
          <li>Ticket ID generated</li>
        </ul>
      </div>

      {formError && (
        <p className="chat-ticket-card__error" role="alert">
          {formError}
        </p>
      )}

      <div className="chat-ticket-card__actions">
        <Button disabled={isCreating} onClick={createTicket}>
          {isCreating ? 'Creating...' : 'Create Ticket'}
        </Button>
        <Button variant="outline" disabled={isCreating} onClick={onContinue}>
          Cancel
        </Button>
      </div>
    </section>
  );
}