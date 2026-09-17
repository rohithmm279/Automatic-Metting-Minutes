import React, { useState } from 'react';
import api from '../services/api';
import { Icon } from '../components/icons/Icons';
import ConfirmModal from '../components/ConfirmModal';

export default function MeetingTimeline({
  meetings = [],
  onSelectMeeting,
  onNavigateToAnalyze,
  onMeetingDeleted,
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      await api.deleteMeeting(deleteTarget.id);
      if (onMeetingDeleted) {
        onMeetingDeleted(deleteTarget.id);
      }
      setDeleteTarget(null);
    } catch (err) {
      console.error('Delete failed:', err);
      alert(err.message || 'Failed to delete meeting');
    } finally {
      setIsDeleting(false);
    }
  };

  const filteredMeetings = meetings.filter((m) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return String(m.id).includes(q) || (m.summary && m.summary.toLowerCase().includes(q));
  });

  return (
    <div>
      {/* Header */}
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
            Club Meeting Records & History
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', marginTop: '2px' }}>
            Chronological log of all analyzed student club sessions ({meetings.length} records)
          </p>
        </div>

        <button className="s5-btn s5-btn-primary" onClick={onNavigateToAnalyze}>
          <Icon name="plus" size={16} />
          <span>Analyze New Meeting</span>
        </button>
      </div>

      {/* Search Bar */}
      <div className="s5-card" style={{ marginBottom: 'var(--space-6)', padding: '12px 18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Icon name="search" size={16} style={{ color: 'var(--text-muted)' }} />
          <input
            type="text"
            className="s5-input"
            placeholder="Search meetings by summary keywords or meeting ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ border: 'none', background: 'transparent', padding: '6px' }}
          />
          {searchQuery && (
            <button className="s5-btn s5-btn-ghost s5-btn-sm" onClick={() => setSearchQuery('')}>
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Timeline or Empty State */}
      {filteredMeetings.length === 0 ? (
        <div className="s5-empty-state">
          <div className="s5-empty-icon">
            <Icon name="meetings" size={24} />
          </div>
          <div className="s5-empty-title">
            {searchQuery ? 'No matching meetings' : 'No meetings recorded yet'}
          </div>
          <p className="s5-empty-desc">
            {searchQuery
              ? `No meeting found matching "${searchQuery}".`
              : 'Add your first meeting transcript to begin building your club intelligence repository.'}
          </p>
          <button className="s5-btn s5-btn-primary s5-btn-sm" onClick={onNavigateToAnalyze}>
            Analyze First Meeting
          </button>
        </div>
      ) : (
        <div style={{ position: 'relative', paddingLeft: '28px' }}>
          {/* Vertical timeline spine */}
          <div style={{
            position: 'absolute',
            left: '11px',
            top: '16px',
            bottom: '16px',
            width: '2px',
            background: 'var(--border-default)',
          }} />

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>
            {filteredMeetings.map((m) => (
              <div key={m.id} style={{ position: 'relative' }}>
                {/* Timeline Node Point */}
                <div style={{
                  position: 'absolute',
                  left: '-28px',
                  top: '20px',
                  width: '18px',
                  height: '18px',
                  borderRadius: '50%',
                  background: 'var(--surface-primary)',
                  border: '3px solid var(--accent-primary)',
                  boxShadow: '0 0 8px rgba(99, 102, 241, 0.4)'
                }} />

                {/* Meeting Card */}
                <div className="s5-card">
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px', marginBottom: '8px' }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                        <span style={{
                          fontFamily: 'var(--font-mono)',
                          fontWeight: 700,
                          fontSize: '0.85rem',
                          color: 'var(--accent-primary)'
                        }}>
                          Meeting #{m.id}
                        </span>
                        <span style={{ color: 'var(--text-dim)' }}>•</span>
                        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                          {m.created_at ? new Date(m.created_at).toLocaleString() : 'Recent'}
                        </span>
                      </div>
                      <p style={{ fontSize: '0.92rem', color: 'var(--text-primary)', lineHeight: 1.5 }}>
                        {m.summary}
                      </p>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
                      <button
                        className="s5-btn s5-btn-secondary s5-btn-sm"
                        onClick={() => onSelectMeeting(m.id)}
                      >
                        Details →
                      </button>
                      <button
                        className="s5-btn s5-btn-danger s5-btn-sm"
                        onClick={() => setDeleteTarget(m)}
                        title="Delete meeting"
                      >
                        <Icon name="trash" size={13} />
                      </button>
                    </div>
                  </div>

                  {/* Badges footer */}
                  <div style={{ display: 'flex', gap: '8px', paddingTop: '8px', borderTop: '1px solid var(--border-subtle)', flexWrap: 'wrap' }}>
                    <span className="s5-badge s5-badge-pending" title="Action Items extracted">
                      ⚡ {m.action_items_count} action items
                    </span>
                    <span className="s5-badge s5-badge-confirmed" title="Decisions confirmed">
                      ✓ {m.decisions_count} decisions
                    </span>
                    <span className="s5-badge s5-badge-overdue" title="Unresolved issues">
                      ! {m.unresolved_issues_count} open issues
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Delete Cascade Modal */}
      <ConfirmModal
        isOpen={Boolean(deleteTarget)}
        title={`Delete Meeting #${deleteTarget?.id}`}
        message={`Are you sure you want to delete Meeting #${deleteTarget?.id}? All extracted action items, decisions, and issues will be deleted via cascade.`}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
        isDeleting={isDeleting}
      />
    </div>
  );
}
