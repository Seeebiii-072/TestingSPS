import { useEffect, useMemo, useRef, useState } from 'react';
import authService from '../../services/authService.js';
import { createTicketFromEscalation, getInitialMessages, sendMessage } from '../../services/chatService.js';
import ChatHeader from './ChatHeader';
import ChatInput from './ChatInput';
import ChatMessage from './ChatMessage';
import ChatSuggestions from './ChatSuggestions';
import CreateTicketFromChat from './CreateTicketFromChat';

function createUserMessage(content) {
  return {
    id: `USER-${Date.now()}`,
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
    id: `ASSISTANT-${Date.now()}`,
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

function normalizeTicketDraft(prefill, fallbackMessage) {
  return {
    subject: prefill?.subject || fallbackMessage.slice(0, 72) || 'Support request from AI Chat',
    summary: prefill?.summary || prefill?.description || fallbackMessage,
    category: prefill?.category || 'general_it',
    priority: prefill?.priority || 'medium',
    risk: prefill?.risk_level || prefill?.risk || 'standard',
    source: 'chat',
  };
}

export default function ChatWindow({ onClose }) {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showTicketCard, setShowTicketCard] = useState(false);
  const [ticketDraft, setTicketDraft] = useState(null);
  const messageAreaRef = useRef(null);
  const sessionId = useMemo(() => `widget-${crypto.randomUUID?.() || Date.now()}`, []);
  const currentUser = authService.getCurrentUser();

  useEffect(() => {
    let isMounted = true;

    getInitialMessages().then((initialMessages) => {
      if (!isMounted) return;
      setMessages(initialMessages.slice(0, 1));
      setIsLoading(false);
    });

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    const messageArea = messageAreaRef.current;
    if (messageArea) messageArea.scrollTop = messageArea.scrollHeight;
  }, [messages, showTicketCard, isLoading]);

  const handleSend = async (content) => {
    if (content.toLowerCase() === 'create ticket') {
      setShowTicketCard(true);
      return;
    }

    setMessages((current) => [...current, createUserMessage(content)]);
    setIsLoading(true);

    try {
      const response = await sendMessage(sessionId, content, currentUser?.id);
      setMessages((current) => [...current, createAssistantMessage(response)]);
      setTicketDraft(normalizeTicketDraft(response.ticket_prefill, content));
      if (response.escalate) setShowTicketCard(true);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateTicket = (draft) =>
    createTicketFromEscalation({
      ...draft,
      description: draft.summary,
      aiSummary: draft.summary,
      requesterEmail: currentUser?.email || 'requester@example.com',
    });

  return (
    <section
      className="chat-window"
      aria-label="SPS SecureDesk AI chat"
      aria-live="polite"
    >
      <ChatHeader onClose={onClose} />

      <div className="chat-window__messages" ref={messageAreaRef}>
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
        {showTicketCard && (
          <CreateTicketFromChat
            draft={ticketDraft || undefined}
            onContinue={() => setShowTicketCard(false)}
            onCreate={handleCreateTicket}
          />
        )}
      </div>

      <div className="chat-window__composer">
        <ChatSuggestions disabled={isLoading} onSelect={handleSend} />
        <ChatInput disabled={isLoading} onSend={handleSend} />
        <p className="chat-safety-footer">
          AI can suggest answers, but sensitive actions require human approval.
        </p>
      </div>
    </section>
  );
}
