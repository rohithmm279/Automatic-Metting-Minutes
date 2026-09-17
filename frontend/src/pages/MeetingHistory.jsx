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
  const [deleteTarget, setDeleteTarget] = useState(null);
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

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      await api.deleteMeeting(deleteTarget.id);
      setMeetings((prev) => prev.filter((m) => m.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch (err) {
      console.error('Delete failed:', err);
      setError(err.message || 'Failed to delete meeting.');
    } finally {
      setIsDeleting(false);
    }
  };

  const filteredMeetings = meetings.filter((m) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      String(m.id).includes(q) ||
      (m.summary && m.summary.toLowerCase().includes(q))
    );
  });

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

      <div className="card mb-4">
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <span style={{ fontSize: '1.2rem' }}>🔍</span>
          <input
            type="text"
            className="form-input"
            placeholder="Search meetings by summary keywords or meeting ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ margin: 0 }}
          />
          {searchQuery && (
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => setSearchQuery('')}
            >
              Clear
            </button>
          )}
        </div>
      </div>

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
                  <th style={{ width: '8%' }}>ID</th>
                  <th style={{ width: '45%' }}>Summary</th>
                  <th style={{ width: '18%' }}>Extracted Elements</th>
                  <th style={{ width: '15%' }}>Date</th>
                  <th style={{ width: '14%', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredMeetings.map((m) => (
                  <tr key={m.id}>
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
                          onClick={() => setDeleteTarget(m)}
                          title="Delete meeting"
                        >
                          🗑️
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ConfirmModal
        isOpen={!!deleteTarget}
        title={`Delete Meeting #${deleteTarget?.id}`}
        message={`Are you sure you want to permanently delete meeting #${deleteTarget?.id}? All associated action items and decisions will be deleted via cascade.`}
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
        isDeleting={isDeleting}
      />
    </div>
  );
}
