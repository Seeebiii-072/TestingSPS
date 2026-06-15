import axios from 'axios';
import { AI_URL } from '../config/constants.js';
import { createTicketFromChat } from './ticketService.js';

const aiApi = axios.create({
  baseURL: AI_URL,
});

export function getInitialMessages() {
  return Promise.resolve([
    {
      id: 'WELCOME',
      role: 'assistant',
      type: 'message',
      content:
        'Hi, I am SPS SecureDesk AI. Ask a support question, or I can help prepare a ticket for a human agent.',
      citations: [],
      createdAt: new Date().toISOString(),
    },
  ]);
}

export async function sendMessage(session_id, message, user_id) {
  const response = await aiApi.post('/chat', { session_id, message, user_id });
  return response.data;
}

export async function createTicketFromEscalation(draft) {
  return createTicketFromChat(draft);
}

const chatService = {
  getInitialMessages,
  sendMessage,
  createTicketFromEscalation,
};

export default chatService;
