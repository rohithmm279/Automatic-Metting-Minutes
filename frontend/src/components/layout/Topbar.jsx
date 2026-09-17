import React from 'react';
import { Icon } from '../icons/Icons';

export default function Topbar({
  currentView,
  onNavigateToAnalyze,
  selectedClub,
  onSelectClub,
  onOpenSearch,
}) {
  const getViewTitle = () => {
    switch (currentView) {
      case 'overview': return 'Overview';
      case 'analyze': return 'Analyze Meeting';
      case 'meetings': return 'Meeting Records';
      case 'meeting-details': return 'Meeting Analysis';
      case 'actions': return 'Action Items Tracker';
      case 'decisions': return 'Confirmed Decisions';
      case 'issues': return 'Open Blockers & Issues';
      case 'analytics': return 'Club Intelligence Analytics';
      default: return 'Meeting Intelligence';
    }
  };

  const clubs = ['Cultural Committee', 'Robotics Club', 'IEEE Student Branch', 'Design Syndicate'];

  return (
    <header className="s5-topbar">
      <div className="s5-topbar-left">
        <div className="s5-breadcrumb">
          <span>S5</span>
          <Icon name="chevron-right" size={14} style={{ color: 'var(--text-dim)' }} />
          <span className="s5-breadcrumb-current">{getViewTitle()}</span>
        </div>
      </div>

      <div className="s5-topbar-right">
        {/* Quick Search Button */}
        <button
          className="s5-btn s5-btn-secondary s5-btn-sm"
          onClick={onOpenSearch}
          style={{ color: 'var(--text-muted)', gap: '6px' }}
          title="Search meetings, actions & decisions"
        >
          <Icon name="search" size={14} />
          <span style={{ fontSize: '0.8rem' }}>Search</span>
          <kbd style={{
            fontSize: '0.68rem',
            padding: '1px 5px',
            background: 'var(--surface-primary)',
            borderRadius: '4px',
            border: '1px solid var(--border-subtle)',
            color: 'var(--text-dim)'
          }}>
            ⌘K
          </kbd>
        </button>

        {/* Club Context Switcher */}
        <div className="s5-club-badge">
          <span className="pill" />
          <select
            value={selectedClub}
            onChange={(e) => onSelectClub && onSelectClub(e.target.value)}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-primary)',
              fontSize: '0.82rem',
              fontWeight: 500,
              cursor: 'pointer',
              outline: 'none',
            }}
          >
            {clubs.map((c) => (
              <option key={c} value={c} style={{ background: 'var(--surface-elevated)', color: 'var(--text-primary)' }}>
                {c}
              </option>
            ))}
          </select>
        </div>

        {/* Primary Action Button */}
        {currentView !== 'analyze' && (
          <button
            className="s5-btn s5-btn-primary s5-btn-sm"
            onClick={onNavigateToAnalyze}
            id="btn-topbar-analyze"
          >
            <Icon name="sparkles" size={14} />
            <span>Analyze Meeting</span>
          </button>
        )}

        {/* User Avatar */}
        <div
          style={{
            width: '32px',
            height: '32px',
            borderRadius: 'var(--radius-full)',
            background: 'var(--surface-elevated)',
            border: '1px solid var(--border-default)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-secondary)',
            fontSize: '0.8rem',
            fontWeight: 600,
          }}
          title="Club Member Account"
        >
          <Icon name="user" size={15} />
        </div>
      </div>
    </header>
  );
}
