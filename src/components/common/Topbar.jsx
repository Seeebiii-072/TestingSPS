import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import SearchInput from './SearchInput';
import { useAuth } from '../../context/AuthContext';
import { useNotifications } from '../../context/NotificationContext';
import { ROLES } from '../../config/constants';

const pageTitles = {
  '/requester': 'Dashboard',
  '/requester/submit': 'Submit Request',
  '/requester/tickets': 'My Tickets',
  '/requester/ai-chat': 'AI Chat',
  '/agent': 'Agent Dashboard',
  '/agent/queue': 'Ticket Queue',
  '/security': 'Security Dashboard',
  '/security/approvals': 'Approvals',
  '/manager': 'Manager Dashboard',
  '/manager/reports': 'Reports',
  '/admin': 'Admin Settings',
  '/admin/users': 'Users',
  '/admin/knowledge-base': 'Knowledge Base',
  '/admin/categories': 'Categories',
  '/admin/sla-settings': 'SLA Settings',
  '/admin/email-settings': 'Email Settings',
};

function getPageTitle(pathname) {
  if (pathname.startsWith('/agent/tickets/')) return 'Ticket Detail';
  return pageTitles[pathname] || 'SecureDesk AI';
}

/** Resolve the correct ticket detail path based on user role. */
function getTicketPath(user, ticketId) {
  if (!user) return `/agent/tickets/${ticketId}`;
  const { role } = user;
  if (role === ROLES.INTERN || role === ROLES.EMPLOYEE) {
    return `/requester/tickets/${ticketId}`;
  }
  return `/agent/tickets/${ticketId}`;
}

export default function Topbar({ onOpenMenu }) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const {
    notifications,
    unreadCount,
    isOpen,
    dropdownRef,
    toggleDropdown,
    closeDropdown,
    markAsRead,
    markAllAsRead,
  } = useNotifications();

  const handleSignOut = () => {
    logout(navigate);
  };

  const handleNotificationClick = (notification) => {
    markAsRead([notification.id]);
    closeDropdown();
    if (notification.ticket_id) {
      navigate(getTicketPath(user, notification.ticket_id));
    }
  };

  const handleNotificationKeyDown = (e, notification) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleNotificationClick(notification);
    }
  };

  return (
    <header className="topbar">
      <button
        className="icon-button menu-button"
        type="button"
        aria-label="Open navigation"
        onClick={onOpenMenu}
      >
        Menu
      </button>

      <div className="topbar__context">
        <span className="topbar__label">SPS SecureDesk AI</span>
        <strong>{getPageTitle(pathname)}</strong>
      </div>

      <div className="topbar__search">
        <SearchInput
          aria-label="Search helpdesk"
          placeholder="Search tickets, users, or articles"
        />
      </div>

      <div className="topbar__actions">
        <div className="notification-dropdown" ref={dropdownRef}>
          <button
            className="notification-button"
            type="button"
            aria-label={`Notifications, ${unreadCount} unread`}
            onClick={toggleDropdown}
            aria-expanded={isOpen}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M14 21h-4" />
            </svg>
            {unreadCount > 0 && <span className="notification-button__count">{unreadCount}</span>}
          </button>

          {isOpen && (
            <div className="notification-dropdown__panel" role="menu">
              <div className="notification-dropdown__header">
                <strong>Notifications</strong>
                {unreadCount > 0 && (
                  <button type="button" onClick={markAllAsRead}>Mark all read</button>
                )}
              </div>
              <div className="notification-dropdown__list">
                {notifications.length === 0 && (
                  <p className="notification-dropdown__empty">No notifications yet.</p>
                )}
                {notifications.map((notification) => (
                  <div
                    key={notification.id}
                    className={`notification-dropdown__item ${notification.is_read ? '' : 'notification-dropdown__item--unread'}`}
                    role="menuitem"
                    tabIndex={0}
                    onClick={() => handleNotificationClick(notification)}
                    onKeyDown={(e) => handleNotificationKeyDown(e, notification)}
                  >
                    <div className="notification-dropdown__item-content">
                      <strong>{notification.title}</strong>
                      {notification.message && <p>{notification.message}</p>}
                      <span>{new Date(notification.created_at).toLocaleString()}</span>
                    </div>
                    {!notification.is_read && <span className="notification-dropdown__dot" />}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="profile-menu">
          <button
            className="profile-menu__trigger"
            type="button"
            aria-label="Open user profile menu"
            aria-expanded={isProfileOpen}
            aria-haspopup="menu"
            onClick={() => setIsProfileOpen((value) => !value)}
          >
            <span className="user-avatar" aria-hidden="true">
              SD
            </span>
            <span className="profile-menu__copy">
              <strong>Service Desk User</strong>
              <span>Operations</span>
            </span>
            <span className="profile-menu__chevron" aria-hidden="true">
              v
            </span>
          </button>

          {isProfileOpen && (
            <div className="profile-menu__dropdown" role="menu">
              <button type="button" role="menuitem">
                Profile settings
              </button>
              <button type="button" role="menuitem">
                Help & support
              </button>
              <button type="button" role="menuitem" onClick={handleSignOut}>
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}