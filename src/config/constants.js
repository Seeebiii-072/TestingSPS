export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
export const AI_URL = import.meta.env.VITE_AI_URL || 'http://localhost:8001';

export const ROLES = {
  INTERN: 'intern',
  EMPLOYEE: 'employee',
  AGENT: 'agent',
  SECURITY_ADMIN: 'security_admin',
  MANAGER: 'manager',
  ADMINISTRATOR: 'administrator',
};

export const TICKET_STATUS = {
  OPEN: 'open',
  IN_PROGRESS: 'in_progress',
  WAITING_APPROVAL: 'waiting_approval',
  WAITING_USER: 'waiting_user',
  RESOLVED: 'resolved',
  CLOSED: 'closed',
};

export const CATEGORIES = [
  { value: 'cloud', label: 'Cloud' },
  { value: 'cybersecurity', label: 'Cybersecurity' },
  { value: 'identity_access', label: 'Identity and Access' },
  { value: 'devops', label: 'DevOps' },
  { value: 'internship_hr', label: 'Internship / HR' },
  { value: 'general_it', label: 'General IT' },
];

export const STATUS_COLORS = {
  open: 'bg-blue-100 text-blue-800',
  in_progress: 'bg-amber-100 text-amber-800',
  waiting_approval: 'bg-red-100 text-red-800',
  waiting_user: 'bg-purple-100 text-purple-800',
  resolved: 'bg-teal-100 text-teal-800',
  closed: 'bg-gray-100 text-gray-600',
};

export const SOURCE_LABELS = {
  email: 'Email',
  portal_form: 'Web Form',
  chat: 'AI Chat',
};
