import { Navigate, Route, Routes } from 'react-router-dom';
import AppShell from '../components/common/AppShell';

import Login from '../pages/auth/Login';
import Register from '../pages/auth/Register';
import ForgotPassword from '../pages/auth/ForgotPassword';
import ResetPassword from '../pages/auth/ResetPassword';
import { NotificationProvider } from '../context/NotificationContext';
import RequesterDashboard from '../pages/requester/RequesterDashboard';
import SubmitRequest from '../pages/requester/SubmitRequest';
import MyTickets from '../pages/requester/MyTickets';
import RequesterTicketDetail from '../pages/requester/RequesterTicketDetail';
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
import TrackTicket from '../pages/public/TrackTicket';
import SubmitTicket from '../pages/public/SubmitTicket';
import NotFound from '../pages/NotFound';
import Unauthorized from '../pages/Unauthorized';
import AsyncState from '../components/common/AsyncState';
import ProtectedRoute from '../components/common/ProtectedRoute';
import { ROLES } from '../config/constants';
import { useAuth } from '../context/AuthContext';

const REQUESTER_ROLES = [ROLES.INTERN, ROLES.EMPLOYEE];
const STAFF_ROLES = [ROLES.AGENT, ROLES.SECURITY_ADMIN, ROLES.MANAGER, ROLES.ADMINISTRATOR];
const APPROVER_ROLES = [ROLES.SECURITY_ADMIN, ROLES.MANAGER];
const REPORT_ROLES = [ROLES.MANAGER, ROLES.ADMINISTRATOR];
const ADMIN_ROLES = [ROLES.ADMINISTRATOR];
const ROLE_HOME_PATHS = {
  [ROLES.INTERN]: '/requester',
  [ROLES.EMPLOYEE]: '/requester',
  [ROLES.AGENT]: '/agent',
  [ROLES.SECURITY_ADMIN]: '/security',
  [ROLES.MANAGER]: '/manager',
  [ROLES.ADMINISTRATOR]: '/admin',
};

function RoleRedirect() {
  const { loading, user } = useAuth();

  if (loading) {
    return <AsyncState title="Loading" description="Opening your workspace." />;
  }

  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={ROLE_HOME_PATHS[user.role] || '/login'} replace />;
}

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/app" element={<RoleRedirect />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/track" element={<TrackTicket />} />
      <Route path="/submit" element={<SubmitTicket />} />

      <Route element={
        <NotificationProvider>
          <AppShell />
        </NotificationProvider>
      }>
        <Route path="/requester" element={
          <ProtectedRoute allowedRoles={REQUESTER_ROLES}>
            <RequesterDashboard />
          </ProtectedRoute>
        } />
        <Route path="/requester/submit" element={
          <ProtectedRoute allowedRoles={REQUESTER_ROLES}>
            <SubmitRequest />
          </ProtectedRoute>
        } />
        <Route path="/requester/tickets" element={
          <ProtectedRoute allowedRoles={REQUESTER_ROLES}>
            <MyTickets />
          </ProtectedRoute>
        } />
        <Route path="/requester/tickets/:ticketId" element={
          <ProtectedRoute allowedRoles={REQUESTER_ROLES}>
            <RequesterTicketDetail />
          </ProtectedRoute>
        } />
        <Route path="/requester/ai-chat" element={
          <ProtectedRoute allowedRoles={REQUESTER_ROLES}>
            <AIChat />
          </ProtectedRoute>
        } />

        <Route path="/agent" element={
          <ProtectedRoute allowedRoles={STAFF_ROLES}>
            <AgentDashboard />
          </ProtectedRoute>
        } />
        <Route path="/agent/queue" element={
          <ProtectedRoute allowedRoles={STAFF_ROLES}>
            <TicketQueue />
          </ProtectedRoute>
        } />
        <Route path="/agent/tickets/:ticketId" element={
          <ProtectedRoute allowedRoles={STAFF_ROLES}>
            <TicketDetail />
          </ProtectedRoute>
        } />

        <Route path="/security" element={
          <ProtectedRoute allowedRoles={[ROLES.SECURITY_ADMIN, ROLES.ADMINISTRATOR]}>
            <SecurityDashboard />
          </ProtectedRoute>
        } />
        <Route path="/security/approvals" element={
          <ProtectedRoute allowedRoles={APPROVER_ROLES}>
            <ApprovalRequests />
          </ProtectedRoute>
        } />

        <Route path="/manager" element={
          <ProtectedRoute allowedRoles={REPORT_ROLES}>
            <ManagerDashboard />
          </ProtectedRoute>
        } />
        <Route path="/manager/reports" element={
          <ProtectedRoute allowedRoles={REPORT_ROLES}>
            <Reports />
          </ProtectedRoute>
        } />

        <Route path="/admin" element={
          <ProtectedRoute allowedRoles={ADMIN_ROLES}>
            <AdminDashboard />
          </ProtectedRoute>
        } />
        <Route path="/admin/users" element={
          <ProtectedRoute allowedRoles={ADMIN_ROLES}>
            <Users />
          </ProtectedRoute>
        } />
        <Route path="/admin/knowledge-base" element={
          <ProtectedRoute allowedRoles={ADMIN_ROLES}>
            <KnowledgeBase />
          </ProtectedRoute>
        } />
        <Route path="/admin/categories" element={
          <ProtectedRoute allowedRoles={ADMIN_ROLES}>
            <Categories />
          </ProtectedRoute>
        } />
        <Route path="/admin/sla-settings" element={
          <ProtectedRoute allowedRoles={ADMIN_ROLES}>
            <SLASettings />
          </ProtectedRoute>
        } />
        <Route path="/admin/email-settings" element={
          <ProtectedRoute allowedRoles={ADMIN_ROLES}>
            <EmailSettings />
          </ProtectedRoute>
        } />

        <Route path="/unauthorized" element={<Unauthorized />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
