import api from './api.js';
import { getTickets } from './ticketService.js';

const sourceMeta = {
  email: { label: 'Email', color: '#2563eb' },
  portal_form: { label: 'Portal Form', color: '#0f766e' },
  chat: { label: 'Chat', color: '#7c3aed' },
};

function labelize(value) {
  return String(value || '')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function normalizeSummary(summary, tickets = []) {
  const totalTickets = summary.total_tickets || 0;
  const openTickets = Object.entries(summary.by_status || {})
    .filter(([status]) => !['resolved', 'closed'].includes(status))
    .reduce((total, [, count]) => total + count, 0);
  const resolvedTickets = totalTickets - openTickets;
  const slaCompliance =
    totalTickets > 0 ? Math.max(0, Math.round(((totalTickets - summary.sla_breached) / totalTickets) * 100)) : 100;

  const ticketsBySource = Object.entries(sourceMeta).map(([key, meta]) => ({
    label: meta.label,
    value: summary.by_source?.[key] || 0,
    color: meta.color,
  }));

  const ticketsByCategory = Object.entries(summary.by_category || {}).map(([key, value]) => ({
    label: labelize(key),
    value,
  }));

  const highRiskAccessRequests = tickets
    .filter((ticket) => ticket.riskLevel === 'high')
    .map((ticket) => ({
      ticketId: ticket.ticketNumber || ticket.id,
      subject: ticket.subject,
      requesterName: ticket.requesterName,
      status: ticket.statusLabel || labelize(ticket.status),
      ageHours: Math.max(0, Math.round((Date.now() - new Date(ticket.createdAt).getTime()) / 3600000)),
    }));

  return {
    raw: summary,
    dashboardStats: {
      totalTickets,
      openTickets,
      slaCompliance,
      highRiskRequests: summary.high_risk_total || 0,
    },
    ticketsBySource,
    ticketsByCategory,
    slaPerformance: [
      { period: 'Current', met: slaCompliance },
      { period: 'Target', met: 95 },
      { period: 'Previous', met: slaCompliance },
    ],
    resolvedVsOpen: [
      { label: 'Open', value: openTickets },
      { label: 'Resolved / Closed', value: resolvedTickets },
    ],
    highRiskAccessRequests,
  };
}

export async function getSummary(date_from, date_to) {
  const params = {};
  if (date_from) params.date_from = date_from;
  if (date_to) params.date_to = date_to;

  const [summaryResponse, tickets] = await Promise.all([
    api.get('/reports/summary', { params }),
    getTickets().catch(() => []),
  ]);

  return normalizeSummary(summaryResponse.data, tickets);
}

export async function getDashboardStats() {
  const reports = await getSummary();
  return reports.dashboardStats;
}

export const getReports = getSummary;

const reportService = {
  getSummary,
  getDashboardStats,
  getReports,
};

export default reportService;
