import { useState } from 'react';

export default function ChatInput({ disabled = false, onSend }) {
  const [value, setValue] = useState('');

  const submitMessage = (event) => {
    event.preventDefault();
    const message = value.trim();
    if (!message || disabled) return;
    onSend(message);
    setValue('');
  };

  return (
    <form className="chat-input" onSubmit={submitMessage}>
      <button
        className="chat-input__attachment"
        type="button"
        disabled
        aria-label="Attachments are not available in chat"
        title="Attachments are not available yet"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="m9 12 5.3-5.3a3 3 0 0 1 4.2 4.2l-7.8 7.8a5 5 0 0 1-7.1-7.1l8-8" />
        </svg>
      </button>
      <input
        type="text"
        value={value}
        disabled={disabled}
        aria-label="Ask a helpdesk question"
        placeholder="Ask a helpdesk question…"
        onChange={(event) => setValue(event.target.value)}
      />
      <button
        className="chat-input__send"
        type="submit"
        disabled={disabled || !value.trim()}
        aria-label="Send message"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="m4 4 16 8-16 8 3-8-3-8Z" />
          <path d="M7 12h13" />
        </svg>
      </button>
    </form>
  );
}
