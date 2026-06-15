import api from './api.js';

const categoryMap = {
  Cloud: 'cloud',
  Cybersecurity: 'cybersecurity',
  'Identity and Access': 'identity_access',
  'Identity/Access': 'identity_access',
  DevOps: 'devops',
  'Internship/HR': 'internship_hr',
  'Internship / HR': 'internship_hr',
  'General IT': 'general_it',
};

const statusMap = {
  New: 'open',
  Open: 'open',
  'In Progress': 'in_progress',
  'Waiting Approval': 'waiting_approval',
  'Waiting User': 'waiting_user',
  Resolved: 'resolved',
  Closed: 'closed',
};

const teamMap = {
  IT: 'it',
  Security: 'security',
  DevOps: 'devops',
  HR: 'hr',
  Management: 'management',
  'Service Desk': 'it',
};

function normalizeEnum(value) {
  return String(value || '').trim().toLowerCase().replaceAll(' ', '_').replaceAll('/', '_');
}

function toCategory(value) {
  if (!value) return 'general_it';
  return categoryMap[value] || normalizeEnum(value);
}

function toPriority(value) {
  return normalizeEnum(value || 'medium');
}

function toStatus(value) {
  if (!value) return undefined;
  return statusMap[value] || normalizeEnum(value);
}

function toTeam(value) {
  if (!value) return undefined;
  return teamMap[value] || normalizeEnum(value);
}

function compactObject(data) {
  return Object.fromEntries(
    Object.entries(data).filter(([, value]) => value !== undefined && value !== null && value !== ''),
  );
}

function labelFromEmail(email) {
  const name = String(email || 'requester')
    .split('@')[0]
    .replace(/[._-]+/g, ' ')
    .trim();
  return name ? name.replace(/\b\w/g, (letter) => letter.toUpperCase()) : 'Requester';
}

function labelize(value) {
  return String(value || '')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatSlaDueAt(value) {
  if (!value) return 'No SLA set';
  const dueAt = new Date(value);
  const diffMs = dueAt.getTime() - Date.now();
  if (Number.isNaN(diffMs)) return 'No SLA set';
  if (diffMs <= 0) return 'SLA breached';
  const minutes = Math.ceil(diffMs / 60000);
  if (minutes < 60) return `${minutes} minutes remaining`;
  const hours = Math.ceil(minutes / 60);
  if (hours < 48) return `${hours} hours remaining`;
  return `${Math.ceil(hours / 24)} days remaining`;
}

export function normalizeTimelineEvent(event = {}) {
  return {
    ...event,
    id: event.id,
    eventType: event.event_type,
    type: labelize(event.event_type),
    actor: event.actor_email || 'System',
    message: event.content || '',
    createdAt: event.created_at,
    isPublic: event.is_public,
    channel: event.channel,
  };
}

export function normalizeAttachment(attachment = {}) {
  return {
    ...attachment,
    id: attachment.id,
    name: attachment.filename || attachment.name || 'attachment',
    size: attachment.file_size ?? attachment.size ?? 0,
    type: attachment.mime_type || attachment.type || 'application/octet-stream',
    url: attachment.file_path || attachment.url || '#',
    createdAt: attachment.created_at,
  };
}

export function normalizeTicket(ticket = {}) {
  const requesterEmail = ticket.requester_email || ticket.requesterEmail || '';
  const timelineEvents = ticket.timeline_events || ticket.timeline || [];
  const attachments = ticket.attachments || [];

  return {
    ...ticket,
    id: ticket.id,
    ticketNumber: ticket.ticket_number || ticket.ticketNumber || ticket.id,
    ticket_number: ticket.ticket_number,
    requesterName: ticket.requester_name || ticket.requesterName || labelFromEmail(requesterEmail),
    requesterEmail,
    source: ticket.source,
    category: ticket.category,
    categoryLabel: labelize(ticket.category),
    priority: ticket.priority,
    risk: ticket.risk_level === 'high' ? 'High Risk' : 'Standard',
    riskLevel: ticket.risk_level,
    team: ticket.team,
    assignedTeam: labelize(ticket.team),
    status: ticket.status,
    statusLabel: labelize(ticket.status),
    assignedAgentId: ticket.assigned_agent_id,
    aiSummary: ticket.ai_summary || ticket.aiSummary || ticket.description || 'No AI summary available.',
    slaDueAt: ticket.sla_due_at,
    sla: formatSlaDueAt(ticket.sla_due_at),
    createdAt: ticket.created_at,
    updatedAt: ticket.updated_at,
    timeline: timelineEvents.map(normalizeTimelineEvent),
    timeline_events: timelineEvents,
    attachments: attachments.map(normalizeAttachment),
  };
}

function toTicketCreatePayload(data = {}, source = data.source || 'portal_form') {
  return compactObject({
    source,
    subject: data.subject,
    description: data.description || data.summary || data.aiSummary,
    category: toCategory(data.category),
    priority: toPriority(data.priority || 'medium'),
    requester_email: data.requester_email || data.requesterEmail,
    ai_summary: data.ai_summary || data.aiSummary || data.summary,
  });
}

function toTicketUpdatePayload(data = {}) {
  return compactObject({
    status: toStatus(data.status),
    category: data.category ? toCategory(data.category) : undefined,
    priority: data.priority ? toPriority(data.priority) : undefined,
    risk_level: data.risk_level || data.riskLevel,
    team: data.team ? toTeam(data.team) : undefined,
    assigned_agent_id: data.assigned_agent_id ?? data.assignedAgentId,
    ai_summary: data.ai_summary || data.aiSummary,
  });
}

function toBackendFilters(filters = {}) {
  return compactObject({
    status: toStatus(filters.status),
    category: filters.category ? toCategory(filters.category) : undefined,
    team: filters.team ? toTeam(filters.team) : undefined,
    source: filters.source,
    assigned_to_me: filters.assigned_to_me || filters.assignedToMe,
  });
}

function applyClientFilters(tickets, filters = {}) {
  const search = String(filters.search || '').trim().toLowerCase();
  const priority = filters.priority ? toPriority(filters.priority) : '';
  const risk = String(filters.risk || '').toLowerCase();
  const requesterEmail = String(filters.requesterEmail || '').toLowerCase();

  return tickets.filter((ticket) => {
    const matchesSearch =
      !search ||
      [ticket.ticketNumber, ticket.subject, ticket.requesterName, ticket.requesterEmail]
        .join(' ')
        .toLowerCase()
        .includes(search);
    const matchesPriority = !priority || ticket.priority === priority;
    const matchesRisk =
      !risk ||
      ticket.risk.toLowerCase() === risk ||
      ticket.riskLevel?.toLowerCase() === risk ||
      (risk === 'high risk' && ticket.riskLevel === 'high');
    const matchesRequester =
      !requesterEmail || ticket.requesterEmail.toLowerCase() === requesterEmail;

    return matchesSearch && matchesPriority && matchesRisk && matchesRequester;
  });
}

export async function getTickets(filters = {}) {
  const response = await api.get('/tickets', { params: toBackendFilters(filters) });
  return applyClientFilters(response.data.map(normalizeTicket), filters);
}

export async function getTicket(id) {
  const response = await api.get(`/tickets/${id}`);
  return normalizeTicket(response.data);
}

export async function createTicket(data) {
  const response = await api.post('/tickets', toTicketCreatePayload(data));
  return normalizeTicket(response.data);
}

export async function updateTicket(id, data) {
  const response = await api.patch(`/tickets/${id}`, toTicketUpdatePayload(data));
  return normalizeTicket(response.data);
}

export async function addEvent(id, data) {
  const response = await api.post(`/tickets/${id}/events`, {
    event_type: data.event_type || data.eventType,
    content: data.content,
    is_public: data.is_public ?? data.isPublic ?? true,
    channel: data.channel || 'portal',
  });
  return normalizeTimelineEvent(response.data);
}

export async function uploadFile(id, file) {
  const formData = new FormData();
  formData.append('file', file);
  const response = await api.post(`/tickets/${id}/attachments`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return normalizeAttachment(response.data);
}

export async function approveTicket(id, decision, reason) {
  const response = await api.post(`/tickets/${id}/approve`, { decision, reason });
  return normalizeTicket(response.data);
}

export const getTicketById = getTicket;
export const filterTickets = getTickets;

export async function updateTicketStatus(id, status) {
  return updateTicket(id, { status });
}

export async function addTicketComment(id, comment) {
  const commentData = typeof comment === 'string' ? { message: comment } : comment || {};
  const isInternal = String(commentData.type || '').toLowerCase().includes('internal');
  await addEvent(id, {
    event_type: isInternal ? 'internal_note' : 'agent_reply_portal',
    content: commentData.message || commentData.content,
    is_public: !isInternal,
    channel: commentData.channel || 'portal',
  });
  return getTicket(id);
}

export async function addTicketAttachment(id, attachmentOrFile) {
  if (attachmentOrFile instanceof File) {
    await uploadFile(id, attachmentOrFile);
  }
  return getTicket(id);
}

export function createTicketFromChat(data) {
  return createTicket({ ...data, source: 'chat' });
}

export function createTicketFromForm(data) {
  return createTicket({ ...data, source: 'portal_form' });
}

const ticketService = {
  getTickets,
  getTicket,
  getTicketById,
  createTicket,
  updateTicket,
  addEvent,
  uploadFile,
  approveTicket,
  filterTickets,
  updateTicketStatus,
  addTicketComment,
  addTicketAttachment,
  createTicketFromChat,
  createTicketFromForm,
};

export default ticketService;
