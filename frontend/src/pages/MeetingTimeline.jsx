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
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [singleDeleteTarget, setSingleDeleteTarget] = useState(null);
  const [showBatchDeleteModal, setShowBatchDeleteModal] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState(null);

  const filteredMeetings = meetings.filter((m) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      String(m.id).includes(q) ||
      (m.title && m.title.toLowerCase().includes(q)) ||
      (m.summary && m.summary.toLowerCase().includes(q))
    );
  });

  const isSelectionMode = selectedIds.size > 0;
  const isAllSelected =
    filteredMeetings.length > 0 &&
    filteredMeetings.every((m) => selectedIds.has(m.id));

  const toggleSelect = (id, e) => {
    if (e) e.stopPropagation();
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleSelectAll = () => {
    if (isAllSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredMeetings.map((m) => m.id)));
    }
  };

  const clearSelection = () => {
    setSelectedIds(new Set());
  };

  // Single deletion
  const handleSingleDelete = async () => {
    if (!singleDeleteTarget) return;
    setIsDeleting(true);
    setError(null);
    try {
      await api.deleteMeeting(singleDeleteTarget.id);
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(singleDeleteTarget.id);
        return next;
      });
      setSingleDeleteTarget(null);
      if (onMeetingDeleted) {
        onMeetingDeleted();
      }
    } catch (err) {
      console.error('Delete failed:', err);
      setError(err.message || 'Failed to delete meeting');
    } finally {
      setIsDeleting(false);
    }
  };

  // Batch deletion (WhatsApp style)
  const handleBatchDelete = async () => {
    if (selectedIds.size === 0) return;
    setIsDeleting(true);
    setError(null);
    try {
      const idsToDelete = Array.from(selectedIds);
      await Promise.all(idsToDelete.map((id) => api.deleteMeeting(id)));
      clearSelection();
      setShowBatchDeleteModal(false);
      if (onMeetingDeleted) {
        onMeetingDeleted();
      }
    } catch (err) {
      console.error('Batch delete failed:', err);
      setError(err.message || 'Failed to delete selected meetings');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 'var(--space-6)',
          flexWrap: 'wrap',
          gap: 'var(--space-4)',
        }}
      >
        <div>
          <h1
            style={{
              fontSize: '1.75rem',
              fontWeight: 700,
              letterSpacing: '-0.02em',
              color: 'var(--text-primary)',
            }}
          >
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

      {/* Error Alert */}
      {error && (
        <div
          className="s5-card"
          style={{
            marginBottom: 'var(--space-4)',
            padding: '12px 16px',
            backgroundColor: 'rgba(239, 68, 68, 0.12)',
            borderColor: 'var(--semantic-red)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--semantic-red)' }}>
            <Icon name="alert-triangle" size={16} />
            <span style={{ fontSize: '0.88rem', fontWeight: 500 }}>{error}</span>
          </div>
          <button className="s5-btn s5-btn-ghost s5-btn-sm" onClick={() => setError(null)}>
            <Icon name="close" size={14} />
          </button>
        </div>
      )}

      {/* WhatsApp-Style Selection Bar (When 1+ items selected) */}
      {isSelectionMode ? (
        <div
          className="s5-card"
          style={{
            marginBottom: 'var(--space-6)',
            padding: '12px 18px',
            backgroundColor: 'var(--surface-secondary)',
            border: '1.5px solid var(--accent-primary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '12px',
            boxShadow: '0 4px 14px rgba(99, 102, 241, 0.15)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button
              className="s5-btn s5-btn-ghost s5-btn-sm"
              onClick={clearSelection}
              title="Cancel selection"
              style={{ padding: '6px 8px' }}
            >
              <Icon name="close" size={16} />
            </button>
            <span
              style={{
                fontWeight: 700,
                fontSize: '0.95rem',
                color: 'var(--text-primary)',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <span
                style={{
                  background: 'var(--accent-primary)',
                  color: '#fff',
                  borderRadius: '12px',
                  padding: '2px 8px',
                  fontSize: '0.8rem',
                  fontWeight: 700,
                }}
              >
                {selectedIds.size}
              </span>
              Selected
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button
              className="s5-btn s5-btn-secondary s5-btn-sm"
              onClick={handleSelectAll}
            >
              {isAllSelected ? 'Deselect All' : 'Select All'}
            </button>
            <button
              className="s5-btn s5-btn-danger s5-btn-sm"
              onClick={() => setShowBatchDeleteModal(true)}
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <Icon name="trash" size={14} />
              <span>Delete Selected ({selectedIds.size})</span>
            </button>
          </div>
        </div>
      ) : (
        /* Search Bar & Select Toggle */
        <div
          className="s5-card"
          style={{
            marginBottom: 'var(--space-6)',
            padding: '12px 18px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
            flexWrap: 'wrap',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1, minWidth: '240px' }}>
            <Icon name="search" size={16} style={{ color: 'var(--text-muted)' }} />
            <input
              type="text"
              className="s5-input"
              placeholder="Search meetings by summary keywords or meeting ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ border: 'none', background: 'transparent', padding: '6px', width: '100%' }}
            />
            {searchQuery && (
              <button className="s5-btn s5-btn-ghost s5-btn-sm" onClick={() => setSearchQuery('')}>
                Clear
              </button>
            )}
          </div>

          {filteredMeetings.length > 0 && (
            <button
              className="s5-btn s5-btn-ghost s5-btn-sm"
              onClick={handleSelectAll}
              style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}
              title="Select multiple meetings to delete"
            >
              Select
            </button>
          )}
        </div>
      )}

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
          <div
            style={{
              position: 'absolute',
              left: '11px',
              top: '16px',
              bottom: '16px',
              width: '2px',
              background: 'var(--border-default)',
            }}
          />

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>
            {filteredMeetings.map((m) => {
              const isSelected = selectedIds.has(m.id);

              return (
                <div key={m.id} style={{ position: 'relative' }}>
                  {/* Timeline Node Point */}
                  <div
                    style={{
                      position: 'absolute',
                      left: '-28px',
                      top: '20px',
                      width: '18px',
                      height: '18px',
                      borderRadius: '50%',
                      background: isSelected ? 'var(--accent-primary)' : 'var(--surface-primary)',
                      border: isSelected ? '3px solid #fff' : '3px solid var(--accent-primary)',
                      boxShadow: isSelected
                        ? '0 0 10px rgba(99, 102, 241, 0.8)'
                        : '0 0 8px rgba(99, 102, 241, 0.4)',
                      transition: 'all 0.15s ease',
                    }}
                  />

                  {/* Meeting Card (WhatsApp selectable style) */}
                  <div
                    className="s5-card"
                    style={{
                      borderColor: isSelected ? 'var(--accent-primary)' : 'var(--border-subtle)',
                      backgroundColor: isSelected ? 'rgba(99, 102, 241, 0.07)' : 'var(--surface-primary)',
                      boxShadow: isSelected ? '0 4px 16px rgba(99, 102, 241, 0.18)' : undefined,
                      transition: 'all 0.15s ease',
                      cursor: isSelectionMode ? 'pointer' : 'default',
                    }}
                    onClick={isSelectionMode ? () => toggleSelect(m.id) : undefined}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        justifyContent: 'space-between',
                        gap: '16px',
                        marginBottom: '8px',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', flex: 1 }}>
                        {/* WhatsApp-style selection Checkbox */}
                        <div
                          style={{
                            paddingTop: '2px',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                          }}
                          onClick={(e) => toggleSelect(m.id, e)}
                          title={isSelected ? 'Deselect meeting' : 'Select meeting'}
                        >
                          <div
                            style={{
                              width: '20px',
                              height: '20px',
                              borderRadius: '6px',
                              border: isSelected
                                ? '2px solid var(--accent-primary)'
                                : '2px solid var(--border-default)',
                              backgroundColor: isSelected ? 'var(--accent-primary)' : 'transparent',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              color: '#fff',
                              transition: 'all 0.15s ease',
                            }}
                          >
                            {isSelected && <Icon name="check" size={13} style={{ strokeWidth: 2.8 }} />}
                          </div>
                        </div>

                        {/* Card Content */}
                        <div style={{ flex: 1 }}>
                          <div
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '8px',
                              marginBottom: '6px',
                              flexWrap: 'wrap',
                            }}
                          >
                            <span
                              style={{
                                fontWeight: 700,
                                fontSize: '1rem',
                                color: 'var(--text-primary)',
                              }}
                            >
                              {m.title || `Meeting #${m.id}`}
                            </span>
                            <span style={{ color: 'var(--text-dim)' }}>•</span>
                            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                              {m.meeting_date ||
                                (m.created_at
                                  ? new Date(m.created_at).toLocaleDateString()
                                  : 'Recent')}
                            </span>
                          </div>
                          <p
                            style={{
                              fontSize: '0.92rem',
                              color: 'var(--text-primary)',
                              lineHeight: 1.5,
                            }}
                          >
                            {m.summary}
                          </p>
                        </div>
                      </div>

                      {/* Action buttons on card */}
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          flexShrink: 0,
                        }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <button
                          className="s5-btn s5-btn-secondary s5-btn-sm"
                          onClick={() => onSelectMeeting(m.id)}
                        >
                          Details →
                        </button>
                        <button
                          className="s5-btn s5-btn-danger s5-btn-sm"
                          onClick={() => setSingleDeleteTarget(m)}
                          title="Delete meeting"
                        >
                          <Icon name="trash" size={13} />
                        </button>
                      </div>
                    </div>

                    {/* Badges footer */}
                    <div
                      style={{
                        display: 'flex',
                        gap: '8px',
                        paddingTop: '8px',
                        borderTop: '1px solid var(--border-subtle)',
                        flexWrap: 'wrap',
                      }}
                    >
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
              );
            })}
          </div>
        </div>
      )}

      {/* Single Delete Modal */}
      <ConfirmModal
        isOpen={Boolean(singleDeleteTarget)}
        title={`Delete Meeting #${singleDeleteTarget?.id}`}
        message={`Are you sure you want to delete Meeting #${singleDeleteTarget?.id}? All extracted action items, decisions, and issues will be permanently deleted via cascade.`}
        confirmText="Delete Meeting"
        onConfirm={handleSingleDelete}
        onCancel={() => setSingleDeleteTarget(null)}
        isDeleting={isDeleting}
      />

      {/* WhatsApp-Style Batch Delete Modal */}
      <ConfirmModal
        isOpen={showBatchDeleteModal}
        title={`Delete ${selectedIds.size} Selected Meeting${selectedIds.size > 1 ? 's' : ''}`}
        message={`Are you sure you want to permanently delete the ${selectedIds.size} selected meeting record${selectedIds.size > 1 ? 's' : ''}? All associated action items, decisions, and open issues will be deleted via cascade.`}
        confirmText={`Delete Selected (${selectedIds.size})`}
        onConfirm={handleBatchDelete}
        onCancel={() => setShowBatchDeleteModal(false)}
        isDeleting={isDeleting}
      />
    </div>
  );
}
