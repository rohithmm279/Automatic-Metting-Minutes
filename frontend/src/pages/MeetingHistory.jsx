import React, { useState, useEffect } from 'react';
import api from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorAlert from '../components/ErrorAlert';
import ConfirmModal from '../components/ConfirmModal';

export default function MeetingHistory({ onSelectMeeting, onNavigateToNew }) {
  const [meetings, setMeetings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [singleDeleteTarget, setSingleDeleteTarget] = useState(null);
  const [showBatchDeleteModal, setShowBatchDeleteModal] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const fetchMeetings = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getMeetings(100, 0);
      setMeetings(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to load meetings:', err);
      setError(err.message || 'Failed to fetch meeting history from backend.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMeetings();
  }, []);

  const filteredMeetings = meetings.filter((m) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      String(m.id).includes(q) ||
      (m.summary && m.summary.toLowerCase().includes(q))
    );
  });

  const isSelectionMode = selectedIds.size > 0;
  const isAllSelected =
    filteredMeetings.length > 0 &&
    filteredMeetings.every((m) => selectedIds.has(m.id));

  const toggleSelect = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
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

  const handleSingleDelete = async () => {
    if (!singleDeleteTarget) return;
    setIsDeleting(true);
    try {
      await api.deleteMeeting(singleDeleteTarget.id);
      setMeetings((prev) => prev.filter((m) => m.id !== singleDeleteTarget.id));
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(singleDeleteTarget.id);
        return next;
      });
      setSingleDeleteTarget(null);
    } catch (err) {
      console.error('Delete failed:', err);
      setError(err.message || 'Failed to delete meeting.');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleBatchDelete = async () => {
    if (selectedIds.size === 0) return;
    setIsDeleting(true);
    try {
      const idsToDelete = Array.from(selectedIds);
      await Promise.all(idsToDelete.map((id) => api.deleteMeeting(id)));
      setMeetings((prev) => prev.filter((m) => !selectedIds.has(m.id)));
      setSelectedIds(new Set());
      setShowBatchDeleteModal(false);
    } catch (err) {
      console.error('Batch delete failed:', err);
      setError(err.message || 'Failed to delete selected meetings.');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div>
      <div className="flex-between mb-4">
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700 }}>Meeting History</h2>
          <p className="text-muted" style={{ fontSize: '0.9rem' }}>
            Browse, search, and manage all persisted student club meeting minutes
          </p>
        </div>
        <button className="btn btn-primary" onClick={onNavigateToNew}>
          ➕ New Meeting
        </button>
      </div>

      <ErrorAlert message={error} onRetry={fetchMeetings} onDismiss={() => setError(null)} />

      {/* WhatsApp style batch selection bar or search bar */}
      {isSelectionMode ? (
        <div className="card mb-4" style={{ backgroundColor: 'var(--surface-secondary)', border: '1.5px solid var(--accent-primary)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <button className="btn btn-secondary btn-sm" onClick={() => setSelectedIds(new Set())}>
                ✕
              </button>
              <span style={{ fontWeight: 700 }}>{selectedIds.size} Selected</span>
            </div>
            <div style={{ display: 'flex', gap: '10px' }}>
              <button className="btn btn-secondary btn-sm" onClick={handleSelectAll}>
                {isAllSelected ? 'Deselect All' : 'Select All'}
              </button>
              <button className="btn btn-danger btn-sm" onClick={() => setShowBatchDeleteModal(true)}>
                🗑️ Delete Selected ({selectedIds.size})
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="card mb-4">
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
            <span style={{ fontSize: '1.2rem' }}>🔍</span>
            <input
              type="text"
              className="form-input"
              placeholder="Search meetings by summary keywords or meeting ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ margin: 0, flex: 1 }}
            />
            {searchQuery && (
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setSearchQuery('')}
              >
                Clear
              </button>
            )}
            {filteredMeetings.length > 0 && (
              <button className="btn btn-secondary btn-sm" onClick={handleSelectAll}>
                Select
              </button>
            )}
          </div>
        </div>
      )}

      <div className="card">
        {loading ? (
          <LoadingSpinner message="Loading historical records..." />
        ) : filteredMeetings.length === 0 ? (
          <div className="state-box">
            <div className="state-icon">📂</div>
            <div className="state-title">
              {searchQuery ? 'No matching meetings found' : 'No meetings in history'}
            </div>
            <p className="state-desc">
              {searchQuery
                ? 'Try a different search keyword or clear the search input.'
                : 'Create your first meeting to populate the database history.'}
            </p>
          </div>
        ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: '5%' }}>
                    <input
                      type="checkbox"
                      checked={isAllSelected}
                      onChange={handleSelectAll}
                    />
                  </th>
                  <th style={{ width: '8%' }}>ID</th>
                  <th style={{ width: '42%' }}>Summary</th>
                  <th style={{ width: '18%' }}>Extracted Elements</th>
                  <th style={{ width: '15%' }}>Date</th>
                  <th style={{ width: '12%', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredMeetings.map((m) => {
                  const isSelected = selectedIds.has(m.id);
                  return (
                    <tr key={m.id} style={{ backgroundColor: isSelected ? 'rgba(99, 102, 241, 0.08)' : undefined }}>
                      <td>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelect(m.id)}
                        />
                      </td>
                      <td>
                        <span className="mono" style={{ fontWeight: 600, color: 'var(--text-muted)' }}>
                          #{m.id}
                        </span>
                      </td>
                      <td>
                        <div
                          style={{
                            fontWeight: 500,
                            lineHeight: 1.4,
                            display: '-webkit-box',
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: 'vertical',
                            overflow: 'hidden',
                          }}
                        >
                          {m.summary}
                        </div>
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                          <span className="badge badge-pending" title="Action Items">
                            ⚡ {m.action_items_count}
                          </span>
                          <span className="badge badge-completed" title="Decisions">
                            ✓ {m.decisions_count}
                          </span>
                          <span className="badge badge-cancelled" title="Unresolved Issues">
                            ! {m.unresolved_issues_count}
                          </span>
                        </div>
                      </td>
                      <td>
                        <span className="text-muted" style={{ fontSize: '0.8rem' }}>
                          {m.created_at ? new Date(m.created_at).toLocaleDateString() : '—'}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', gap: '0.4rem' }}>
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => onSelectMeeting(m.id)}
                            title="View meeting details"
                          >
                            View
                          </button>
                          <button
                            className="btn btn-danger btn-sm"
                            onClick={() => setSingleDeleteTarget(m)}
                            title="Delete meeting"
                          >
                            🗑️
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ConfirmModal
        isOpen={!!singleDeleteTarget}
        title={`Delete Meeting #${singleDeleteTarget?.id}`}
        message={`Are you sure you want to permanently delete meeting #${singleDeleteTarget?.id}? All associated action items and decisions will be deleted via cascade.`}
        confirmText="Delete Meeting"
        onConfirm={handleSingleDelete}
        onCancel={() => setSingleDeleteTarget(null)}
        isDeleting={isDeleting}
      />

      <ConfirmModal
        isOpen={showBatchDeleteModal}
        title={`Delete ${selectedIds.size} Selected Meetings`}
        message={`Are you sure you want to permanently delete the ${selectedIds.size} selected meetings? All associated action items, decisions, and issues will be deleted via cascade.`}
        confirmText={`Delete Selected (${selectedIds.size})`}
        onConfirm={handleBatchDelete}
        onCancel={() => setShowBatchDeleteModal(false)}
        isDeleting={isDeleting}
      />
    </div>
  );
}
