import { useEffect, useMemo, useRef, useState } from 'react';
import ChatInput from '../../components/chat/ChatInput';
import ChatMessage from '../../components/chat/ChatMessage';
import CreateTicketFromChat from '../../components/chat/CreateTicketFromChat';
import Badge from '../../components/common/Badge';
import Card from '../../components/common/Card';
import { createTicketFromEscalation, getInitialMessages, sendMessage, getCategories } from '../../services/chatService.js';
import authService from '../../services/authService.js';
import { addTicketAttachment } from '../../services/ticketService.js';

const quickHelpItems = [
  '❓ How do I reset my password?',
  '❓ How do I connect to VPN?',
  '❓ My email is not working',
  '❓ How do I request software access?',
  '❓ My laptop is running slow',
  '❓ How do I report a phishing email?',
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
  return {
    id: `PAGE-AI-${Date.now()}`,
    role: 'assistant',
    type: 'message',
    content: response.response || response.message || '',
    citations: [],
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
  const [error, setError] = useState('');
  const [categories, setCategories] = useState([]);
  const [expandedCategory, setExpandedCategory] = useState(null);
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

    getCategories().then((data) => {
      if (isMounted) setCategories(data || []);
    }).catch(() => {
      if (isMounted) setCategories([]);
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

    setExpandedCategory(null);
    setError('');
    setMessages((current) => [...current, createUserMessage(content)]);
    setIsLoading(true);

    try {
      const response = await sendMessage(sessionId, content, currentUser?.id);
      setMessages((current) => [...current, createAssistantMessage(response)]);
      const draft = normalizeTicketPrefill(response.ticket_prefill, content);
      setTicketDraft(draft);
      if (response.suggested_categories && response.suggested_categories.length) {
        setCategories(response.suggested_categories);
      }
      if (response.escalate) {
        setShowEscalation(true);
      }
    } catch {
      setError('The AI service could not be reached. Please confirm it is running on port 8001.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateTicket = async (draft = ticketDraft, attachmentFile = null) => {
    const ticket = await createTicketFromEscalation({
      ...draft,
      description: draft.summary,
      aiSummary: draft.summary,
      requesterEmail: currentUser?.email || draft.requester_email || 'requester@example.com',
    });

    if (attachmentFile && ticket?.id) {
      await addTicketAttachment(ticket.id, attachmentFile);
    }

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
              />
            )}
          </div>

          <div className="ai-chat-composer">
            <ChatInput disabled={isLoading} onSend={handleSend} />
            <p className="chat-safety-footer">
              AI can suggest answers, but sensitive actions require human approval.
            </p>
          </div>
        </section>

        <aside className="ai-chat-side-panel">
          <Card
            className="ai-chat-topics-card"
            title="Quick Help"
            subtitle="Click a common issue to get instant help."
          >
            <div className="ai-chat-topics">
              {quickHelpItems.map((item) => (
                <button
                  type="button"
                  disabled={isLoading}
                  key={item}
                  onClick={() => handleSend(item.replace('❓ ', ''))}
                >
                  {item}
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