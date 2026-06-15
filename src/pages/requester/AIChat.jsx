import { useEffect, useMemo, useRef, useState } from 'react';
import ChatInput from '../../components/chat/ChatInput';
import ChatMessage from '../../components/chat/ChatMessage';
import ChatSuggestions from '../../components/chat/ChatSuggestions';
import CreateTicketFromChat from '../../components/chat/CreateTicketFromChat';
import Badge from '../../components/common/Badge';
import Button from '../../components/common/Button';
import Card from '../../components/common/Card';
import { createTicketFromEscalation, getInitialMessages, sendMessage } from '../../services/chatService.js';
import authService from '../../services/authService.js';

const knowledgeTopics = [
  'VPN',
  'Email',
  'Laptop',
  'Cloud Checklist',
  'Phishing',
  'Intern Onboarding',
  'Access Policy',
  'Product Overviews',
];

const initialTicketDraft = {
  subject: 'Helpdesk assistance requested from SecureDesk AI',
  summary:
    'The requester needs additional help after reviewing approved knowledge-base guidance.',
  category: 'general_it',
  priority: 'medium',
  risk: 'standard',
  source: 'chat',
};

function createUserMessage(content) {
  return {
    id: `PAGE-USER-${Date.now()}`,
    role: 'user',
    type: 'message',
    content,
    createdAt: new Date().toISOString(),
  };
}

function createAssistantMessage(response) {
  const sources = Array.isArray(response.source)
    ? response.source
    : response.source
      ? [response.source]
      : [];

  return {
    id: `PAGE-AI-${Date.now()}`,
    role: 'assistant',
    type: 'message',
    content: response.response || response.message || '',
    citations: sources.map((source, index) => ({
      id: `${source}-${index}`,
      label: String(source),
      source: String(source),
    })),
    createdAt: new Date().toISOString(),
  };
}

function normalizeTicketPrefill(prefill, fallbackMessage) {
  if (!prefill) {
    return {
      ...initialTicketDraft,
      subject: `${fallbackMessage.slice(0, 68)}${fallbackMessage.length > 68 ? '...' : ''}`,
      summary: fallbackMessage,
    };
  }

  return {
    ...initialTicketDraft,
    ...prefill,
    summary: prefill.summary || prefill.description || fallbackMessage,
    category: prefill.category || 'general_it',
    priority: prefill.priority || 'medium',
    risk: prefill.risk_level || prefill.risk || 'standard',
  };
}

export default function AIChat() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showEscalation, setShowEscalation] = useState(false);
  const [ticketDraft, setTicketDraft] = useState(initialTicketDraft);
  const [ticketConfirmation, setTicketConfirmation] = useState('');
  const [error, setError] = useState('');
  const conversationRef = useRef(null);
  const sessionId = useMemo(() => `chat-${crypto.randomUUID?.() || Date.now()}`, []);
  const currentUser = authService.getCurrentUser();

  useEffect(() => {
    let isMounted = true;

    getInitialMessages().then((initialMessages) => {
      if (!isMounted) return;
      setMessages(initialMessages);
      setIsLoading(false);
    });

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    const conversation = conversationRef.current;
    if (conversation) conversation.scrollTop = conversation.scrollHeight;
  }, [isLoading, messages, showEscalation]);

  const handleSend = async (content) => {
    if (content.toLowerCase() === 'create ticket') {
      setShowEscalation(true);
      return;
    }

    setError('');
    setMessages((current) => [...current, createUserMessage(content)]);
    setIsLoading(true);

    try {
      const response = await sendMessage(sessionId, content, currentUser?.id);
      setMessages((current) => [...current, createAssistantMessage(response)]);
      const draft = normalizeTicketPrefill(response.ticket_prefill, content);
      setTicketDraft(draft);
      if (response.escalate) setShowEscalation(true);
    } catch {
      setError('The AI service could not be reached. Please confirm it is running on port 8001.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateTicket = async (draft = ticketDraft) => {
    const ticket = await createTicketFromEscalation({
      ...draft,
      description: draft.summary,
      aiSummary: draft.summary,
      requesterEmail: currentUser?.email || draft.requester_email || 'requester@example.com',
    });
    setTicketConfirmation(`Ticket ${ticket.ticketNumber || ticket.id} created successfully.`);
    return ticket;
  };

  return (
    <section className="page ai-chat-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">AI-assisted support</p>
          <h1>SecureDesk AI Assistant</h1>
          <p>
            Ask helpdesk questions using approved SPS knowledge or prepare a
            support ticket for human review.
          </p>
        </div>
        <Badge tone="blue">Live AI service</Badge>
      </div>

      {error && <div className="requester-action-notice" role="alert">{error}</div>}

      <div className="ai-chat-layout">
        <section className="ai-chat-conversation-card" aria-label="AI conversation">
          <div className="ai-chat-conversation-card__header">
            <div className="ai-chat-conversation-card__identity">
              <span aria-hidden="true">AI</span>
              <div>
                <strong>SPS SecureDesk AI</strong>
                <small>Knowledge-base assistant</small>
              </div>
            </div>
            <Badge tone="green">Available</Badge>
          </div>

          <div className="ai-chat-conversation" ref={conversationRef}>
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
            {isLoading && (
              <div className="chat-typing" aria-label="SecureDesk AI is responding">
                <span />
                <span />
                <span />
              </div>
            )}
            {showEscalation && (
              <CreateTicketFromChat
                draft={ticketDraft}
                onContinue={() => setShowEscalation(false)}
                onCreate={handleCreateTicket}
                onCreated={(ticketNumber) =>
                  setTicketConfirmation(`Ticket ${ticketNumber} created successfully.`)
                }
              />
            )}
          </div>

          <div className="ai-chat-composer">
            <ChatSuggestions disabled={isLoading} onSelect={handleSend} />
            <ChatInput disabled={isLoading} onSend={handleSend} />
            <p className="chat-safety-footer">
              AI can suggest answers, but sensitive actions require human approval.
            </p>
          </div>
        </section>

        <aside className="ai-chat-side-panel">
          <Card
            className="ai-chat-preview-card"
            title="Ticket Preview"
            subtitle="Prepared from the current AI conversation."
            actions={<Badge value="chat" />}
          >
            <dl className="ai-chat-ticket-preview">
              <div>
                <dt>Suggested subject</dt>
                <dd>{ticketDraft.subject}</dd>
              </div>
              <div>
                <dt>Suggested category</dt>
                <dd>{String(ticketDraft.category).replaceAll('_', ' ')}</dd>
              </div>
              <div className="ai-chat-ticket-preview__badges">
                <span>
                  <dt>Priority</dt>
                  <dd>
                    <Badge value={ticketDraft.priority} />
                  </dd>
                </span>
                <span>
                  <dt>Risk level</dt>
                  <dd>
                    <Badge tone={ticketDraft.risk === 'high' ? 'red' : 'green'}>
                      {ticketDraft.risk}
                    </Badge>
                  </dd>
                </span>
                <span>
                  <dt>Source</dt>
                  <dd>
                    <Badge value="chat" />
                  </dd>
                </span>
              </div>
            </dl>
            <Button
              className="ai-chat-ticket-preview__button"
              onClick={() => handleCreateTicket(ticketDraft)}
            >
              Create Ticket
            </Button>
            {ticketConfirmation && (
              <p className="ai-chat-ticket-confirmation" role="status">
                {ticketConfirmation}
              </p>
            )}
          </Card>

          <Card
            className="ai-chat-topics-card"
            title="Knowledge Base Topics"
            subtitle="Start with an approved support topic."
          >
            <div className="ai-chat-topics">
              {knowledgeTopics.map((topic) => (
                <button
                  type="button"
                  disabled={isLoading}
                  key={topic}
                  onClick={() => handleSend(topic)}
                >
                  <span aria-hidden="true">{topic.slice(0, 2).toUpperCase()}</span>
                  {topic}
                </button>
              ))}
            </div>
          </Card>

          <div className="ai-chat-safety-note">
            <span aria-hidden="true">!</span>
            <p>
              SecureDesk AI answers from the approved knowledge base only.
              Sensitive requests require human approval.
            </p>
          </div>
        </aside>
      </div>
    </section>
  );
}
