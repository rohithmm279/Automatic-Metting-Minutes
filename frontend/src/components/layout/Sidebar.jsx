import React from 'react';
import { Icon } from '../icons/Icons';

export default function Sidebar({
  currentView,
  onNavigate,
  meetingsCount = 0,
  actionItemsCount = 0,
  decisionsCount = 0,
  issuesCount = 0,
  onOpenSystemSpecs,
  backendOnline = true,
}) {
  const navItems = [
    { id: 'overview', label: 'Overview', icon: 'overview', badge: null },
    { id: 'analyze', label: 'Analyze Meeting', icon: 'sparkles', badge: 'AI' },
    { id: 'meetings', label: 'Meetings', icon: 'meetings', badge: meetingsCount || null },
    { id: 'actions', label: 'Action Items', icon: 'actions', badge: actionItemsCount || null },
    { id: 'decisions', label: 'Decisions', icon: 'decisions', badge: decisionsCount || null },
    { id: 'issues', label: 'Open Issues', icon: 'issues', badge: issuesCount || null },
    { id: 'analytics', label: 'Analytics', icon: 'analytics', badge: null },
  ];

  return (
    <aside className="s5-sidebar" aria-label="Main Navigation">
      {/* Brand Header */}
      <div className="s5-sidebar-brand">
        <div className="s5-brand-logo">S5</div>
        <div className="s5-brand-info">
          <span className="s5-brand-title">Meeting Intel</span>
          <span className="s5-brand-tag">Student Clubs</span>
        </div>
      </div>

      {/* Navigation List */}
      <nav className="s5-sidebar-nav">
        <div className="s5-nav-group-label">Intelligence Operations</div>
        {navItems.map((item) => {
          const isActive = currentView === item.id;
          return (
            <button
              key={item.id}
              id={`nav-${item.id}`}
              className={`s5-nav-item ${isActive ? 'active' : ''}`}
              onClick={() => onNavigate(item.id)}
              aria-current={isActive ? 'page' : undefined}
            >
              <div className="s5-nav-item-left">
                <Icon name={item.icon} size={18} />
                <span>{item.label}</span>
              </div>
              {item.badge !== null && (
                <span className="s5-nav-badge">{item.badge}</span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Sidebar Footer / System Telemetry */}
      <div className="s5-sidebar-footer">
        <div className="s5-system-status" title={backendOnline ? 'Backend API connected' : 'Backend offline'}>
          <span className={`s5-status-dot ${backendOnline ? '' : 'offline'}`} />
          <span style={{ flex: 1, fontWeight: 500 }}>
            {backendOnline ? 'AI Pipeline Active' : 'Backend Offline'}
          </span>
          <span style={{ fontSize: '0.68rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
            v1.0
          </span>
        </div>

        <button
          className="s5-btn s5-btn-ghost s5-btn-sm"
          style={{ width: '100%', justifyContent: 'flex-start', color: 'var(--text-muted)' }}
          onClick={onOpenSystemSpecs}
          title="System architecture & academic demonstration details"
        >
          <Icon name="info" size={15} />
          <span>How S5 Works</span>
        </button>
      </div>
    </aside>
  );
}
