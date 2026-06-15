import { Navigate, Route, Routes } from 'react-router-dom';
import AppShell from '../components/common/AppShell';
import Login from '../pages/auth/Login';
import Register from '../pages/auth/Register';
import RequesterDashboard from '../pages/requester/RequesterDashboard';
import SubmitRequest from '../pages/requester/SubmitRequest';
import MyTickets from '../pages/requester/MyTickets';
import AIChat from '../pages/requester/AIChat';
import AgentDashboard from '../pages/agent/AgentDashboard';
import TicketQueue from '../pages/agent/TicketQueue';
import TicketDetail from '../pages/agent/TicketDetail';
import SecurityDashboard from '../pages/security/SecurityDashboard';
import ApprovalRequests from '../pages/security/ApprovalRequests';
import ManagerDashboard from '../pages/manager/ManagerDashboard';
import Reports from '../pages/manager/Reports';
import AdminDashboard from '../pages/admin/AdminDashboard';
import Users from '../pages/admin/Users';
import KnowledgeBase from '../pages/admin/KnowledgeBase';
import Categories from '../pages/admin/Categories';
import SLASettings from '../pages/admin/SLASettings';
import EmailSettings from '../pages/admin/EmailSettings';
import NotFound from '../pages/NotFound';

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/requester" replace />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      <Route element={<AppShell />}>
        <Route path="/requester" element={<RequesterDashboard />} />
        <Route path="/requester/submit" element={<SubmitRequest />} />
        <Route path="/requester/tickets" element={<MyTickets />} />
        <Route path="/requester/ai-chat" element={<AIChat />} />

        <Route path="/agent" element={<AgentDashboard />} />
        <Route path="/agent/queue" element={<TicketQueue />} />
        <Route path="/agent/tickets/:ticketId" element={<TicketDetail />} />

        <Route path="/security" element={<SecurityDashboard />} />
        <Route path="/security/approvals" element={<ApprovalRequests />} />

        <Route path="/manager" element={<ManagerDashboard />} />
        <Route path="/manager/reports" element={<Reports />} />

        <Route path="/admin" element={<AdminDashboard />} />
        <Route path="/admin/users" element={<Users />} />
        <Route path="/admin/knowledge-base" element={<KnowledgeBase />} />
        <Route path="/admin/categories" element={<Categories />} />
        <Route path="/admin/sla-settings" element={<SLASettings />} />
        <Route path="/admin/email-settings" element={<EmailSettings />} />

        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
