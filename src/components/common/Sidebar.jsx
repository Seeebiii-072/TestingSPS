import { NavLink } from 'react-router-dom';
import { navigationItems } from '../../data/navigation';
import Brand from './Brand';

export default function Sidebar({
  isCollapsed = false,
  isOpen = false,
  onClose,
  onToggleCollapse,
}) {
  return (
    <aside
      className={`sidebar ${isOpen ? 'sidebar--open' : ''} ${
        isCollapsed ? 'sidebar--collapsed' : ''
      }`}
    >
      <div className="sidebar__brand">
        <Brand compact={isCollapsed} />
        <button
          className="icon-button sidebar__close"
          type="button"
          aria-label="Close navigation"
          onClick={onClose}
        >
          X
        </button>
      </div>

      <nav className="sidebar__nav" aria-label="Primary navigation">
        <p className="nav-section__label">Workspace</p>
        {navigationItems.map((item) => (
          <NavLink
            className={({ isActive }) =>
              `nav-link ${isActive ? 'nav-link--active' : ''}`
            }
            end
            key={item.to}
            onClick={onClose}
            title={isCollapsed ? item.label : undefined}
            to={item.to}
          >
            <span className="nav-link__icon" aria-hidden="true">
              {item.code}
            </span>
            <span className="nav-link__text">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar__footer">
        <div className="sidebar__status">
          <span className="status-dot" />
          <div className="sidebar__status-copy">
            <strong>All systems operational</strong>
            <span>Development environment</span>
          </div>
        </div>
        <button
          className="sidebar__collapse-button"
          type="button"
          aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          onClick={onToggleCollapse}
        >
          <span aria-hidden="true">{isCollapsed ? '>' : '<'}</span>
          <span className="sidebar__collapse-label">
            {isCollapsed ? 'Expand' : 'Collapse sidebar'}
          </span>
        </button>
      </div>
    </aside>
  );
}
