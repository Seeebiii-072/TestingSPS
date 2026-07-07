import { ROLES } from '../config/constants';

const REQUESTER_ROLES = [ROLES.INTERN, ROLES.EMPLOYEE];
const STAFF_ROLES = [ROLES.AGENT, ROLES.SECURITY_ADMIN, ROLES.MANAGER, ROLES.ADMINISTRATOR];
const APPROVER_ROLES = [ROLES.SECURITY_ADMIN, ROLES.MANAGER];
const REPORT_ROLES = [ROLES.MANAGER, ROLES.ADMINISTRATOR];
const ADMIN_ROLES = [ROLES.ADMINISTRATOR];

export const navigationItems = [
  { label: 'Dashboard', to: '/requester', code: 'DB', roles: REQUESTER_ROLES },
  { label: 'Dashboard', to: '/agent', code: 'DB', roles: [ROLES.AGENT] },
  { label: 'Dashboard', to: '/security', code: 'DB', roles: [ROLES.SECURITY_ADMIN] },
  { label: 'Dashboard', to: '/manager', code: 'DB', roles: [ROLES.MANAGER] },
  { label: 'Dashboard', to: '/admin', code: 'DB', roles: [ROLES.ADMINISTRATOR] },
  { label: 'Ticket Queue', to: '/agent/queue', code: 'TQ', roles: STAFF_ROLES },
  { label: 'Submit Request', to: '/requester/submit', code: 'SR', roles: REQUESTER_ROLES },
  { label: 'AI Chat', to: '/requester/ai-chat', code: 'AI', roles: [ROLES.INTERN, ROLES.EMPLOYEE, ROLES.AGENT, ROLES.SECURITY_ADMIN, ROLES.MANAGER, ROLES.ADMINISTRATOR] },
  { label: 'My Tickets', to: '/requester/tickets', code: 'MT', roles: REQUESTER_ROLES },
  { label: 'Approvals', to: '/security/approvals', code: 'AP', roles: APPROVER_ROLES },
  { label: 'Knowledge Base', to: '/admin/knowledge-base', code: 'KB', roles: ADMIN_ROLES },
  { label: 'Reports', to: '/manager/reports', code: 'RP', roles: REPORT_ROLES },
];
