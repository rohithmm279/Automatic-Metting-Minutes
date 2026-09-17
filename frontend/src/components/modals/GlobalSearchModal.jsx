import React, { useState, useEffect } from 'react';
import { Icon } from '../icons/Icons';

export default function GlobalSearchModal({
  isOpen,
  onClose,
  meetings = [],
  actionItems = [],
  decisions = [],
  issues = [],
  onSelectMeeting,
}) {
  const [query, setQuery] = useState('');

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const q = query.trim().toLowerCase();

  const matchedMeetings = q
    ? meetings.filter((m) => String(m.id).includes(q) || (m.summary && m.summary.toLowerCase().includes(q)))
    : [];

  const matchedActions = q
    ? actionItems.filter((a) => (a.task && a.task.toLowerCase().includes(q)) || (a.owner && a.owner.toLowerCase().includes(q)))
    : [];

  const matchedDecisions = q
    ? decisions.filter((d) => d.decision && d.decision.toLowerCase().includes(q))
    : [];

  const matchedIssues = q
    ? issues.filter((i) => i.issue && i.issue.toLowerCase().includes(q))
    : [];

  const totalMatches = matchedMeetings.length + matchedActions.length + matchedDecisions.length + matchedIssues.length;

  return (
    <div className="s5-modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="s5-modal" style={{ maxWidth: '600px', padding: 0 }} onClick={(e) => e.stopPropagation()}>
        {/* Input Bar */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.75rem',
          padding: '1rem 1.25rem',
          borderBottom: '1px solid var(--border-default)',
          background: 'var(--surface-primary)'
        }}>
          <Icon name="search" size={18} style={{ color: 'var(--text-muted)' }} />
          <input
            type="text"
            placeholder="Search meetings, action items, decisions, or issues..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              color: 'var(--text-primary)',
              fontSize: '0.95rem',
              outline: 'none',
            }}
          />
          {query && (
            <button className="s5-btn s5-btn-ghost s5-btn-sm" onClick={() => setQuery('')}>
              <Icon name="close" size={14} />
            </button>
          )}
        </div>

        {/* Results Body */}
        <div style={{ maxHeight: '420px', overflowY: 'auto', padding: '1rem 1.25rem' }}>
          {!q ? (
            <div style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              Type keywords to search across meetings, tasks, and decisions.
            </div>
          ) : totalMatches === 0 ? (
            <div style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              No results found for &ldquo;{query}&rdquo;.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {/* Meetings */}
              {matchedMeetings.length > 0 && (
                <div>
                  <div style={{ fontSize: '0.72rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
                    Meetings ({matchedMeetings.length})
                  </div>
                  {matchedMeetings.slice(0, 4).map((m) => (
                    <div
                      key={`m-${m.id}`}
                      onClick={() => {
                        onSelectMeeting(m.id);
                        onClose();
                      }}
                      style={{
                        padding: '8px 10px',
                        borderRadius: 'var(--radius-sm)',
                        background: 'var(--surface-elevated)',
                        marginBottom: '4px',
                        cursor: 'pointer',
                        fontSize: '0.84rem',
                      }}
                    >
                      <span style={{ color: 'var(--accent-primary)', fontWeight: 600 }}>#{m.id}</span> — {m.summary.slice(0, 90)}...
                    </div>
                  ))}
                </div>
              )}

              {/* Action Items */}
              {matchedActions.length > 0 && (
                <div>
                  <div style={{ fontSize: '0.72rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
                    Action Items ({matchedActions.length})
                  </div>
                  {matchedActions.slice(0, 5).map((a) => (
                    <div
                      key={`a-${a.id}`}
                      onClick={() => {
                        onSelectMeeting(a.meeting_id);
                        onClose();
                      }}
                      style={{
                        padding: '8px 10px',
                        borderRadius: 'var(--radius-sm)',
                        background: 'var(--surface-elevated)',
                        marginBottom: '4px',
                        cursor: 'pointer',
                        fontSize: '0.84rem',
                        display: 'flex',
                        justifyContent: 'space-between',
                      }}
                    >
                      <span>⚡ {a.task}</span>
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                        {a.owner || 'Unassigned'}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Decisions */}
              {matchedDecisions.length > 0 && (
                <div>
                  <div style={{ fontSize: '0.72rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
                    Decisions ({matchedDecisions.length})
                  </div>
                  {matchedDecisions.slice(0, 4).map((d) => (
                    <div
                      key={`d-${d.id}`}
                      onClick={() => {
                        onSelectMeeting(d.meeting_id);
                        onClose();
                      }}
                      style={{
                        padding: '8px 10px',
                        borderRadius: 'var(--radius-sm)',
                        background: 'var(--surface-elevated)',
                        marginBottom: '4px',
                        cursor: 'pointer',
                        fontSize: '0.84rem',
                      }}
                    >
                      ✓ {d.decision}
                    </div>
                  ))}
                </div>
              )}

              {/* Issues */}
              {matchedIssues.length > 0 && (
                <div>
                  <div style={{ fontSize: '0.72rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
                    Open Issues ({matchedIssues.length})
                  </div>
                  {matchedIssues.slice(0, 4).map((i) => (
                    <div
                      key={`i-${i.id}`}
                      onClick={() => {
                        onSelectMeeting(i.meeting_id);
                        onClose();
                      }}
                      style={{
                        padding: '8px 10px',
                        borderRadius: 'var(--radius-sm)',
                        background: 'var(--surface-elevated)',
                        marginBottom: '4px',
                        cursor: 'pointer',
                        fontSize: '0.84rem',
                      }}
                    >
                      ⚠️ {i.issue}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
