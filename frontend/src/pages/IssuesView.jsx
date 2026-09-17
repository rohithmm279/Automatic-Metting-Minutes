import React, { useState } from 'react';
import { Icon } from '../components/icons/Icons';

export default function IssuesView({ issues = [], onSelectMeeting }) {
  const [search, setSearch] = useState('');

  const filtered = issues.filter((i) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (i.issue && i.issue.toLowerCase().includes(q)) || String(i.meeting_id).includes(q);
  });

  return (
    <div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 'var(--space-6)',
        flexWrap: 'wrap',
        gap: 'var(--space-4)'
      }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>
            Open Issues & Unresolved Blockers
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', marginTop: '2px' }}>
            Items that remain undecided, blocked, or awaiting administrative confirmation ({issues.length} active issues)
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: '260px' }}>
          <Icon name="search" size={15} style={{ color: 'var(--text-muted)' }} />
          <input
            type="text"
            className="s5-input"
            placeholder="Search open blockers or meeting ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ padding: '7px 12px', fontSize: '0.82rem' }}
          />
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="s5-empty-state">
          <div className="s5-empty-icon" style={{ color: 'var(--semantic-green)' }}>
            <Icon name="check-circle" size={24} />
          </div>
          <div className="s5-empty-title">
            {search ? 'No matching issues found' : 'Zero Open Blockers'}
          </div>
          <p className="s5-empty-desc">
            {search
              ? `No unresolved blocker matches "${search}".`
              : 'All discussed topics have either been resolved into actions or ratified into decisions.'}
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          {filtered.map((item) => (
            <div key={item.id} className="s5-card" style={{ padding: '16px 20px', borderLeft: '3px solid var(--semantic-red)' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                  <div style={{
                    width: '24px',
                    height: '24px',
                    borderRadius: '50%',
                    background: 'var(--semantic-red-bg)',
                    border: '1px solid var(--semantic-red-border)',
                    color: '#F87171',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginTop: '2px',
                    flexShrink: 0
                  }}>
                    <Icon name="issues" size={13} />
                  </div>
                  <div>
                    <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.45 }}>
                      {item.issue}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span>Raised in</span>
                      <button
                        className="s5-btn s5-btn-ghost s5-btn-sm"
                        onClick={() => onSelectMeeting(item.meeting_id)}
                        style={{ padding: '0 4px', color: 'var(--accent-primary)', fontFamily: 'var(--font-mono)' }}
                      >
                        Meeting #{item.meeting_id} →
                      </button>
                    </div>
                  </div>
                </div>

                <span className="s5-badge s5-badge-overdue" style={{ flexShrink: 0 }}>
                  Awaiting Resolution
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
