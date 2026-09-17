import React, { useState } from 'react';
import api from '../services/api';
import { Icon } from '../components/icons/Icons';
import ActionCard from '../components/cards/ActionCard';

export default function ActionTracker({
  actionItems = [],
  onStatusUpdate,
  onSelectMeeting,
}) {
  const [filterStatus, setFilterStatus] = useState('all');
  const [viewMode, setViewMode] = useState('table'); // 'table' | 'cards'
  const [searchQuery, setSearchQuery] = useState('');
  const [updatingId, setUpdatingId] = useState(null);

  const handleStatusChange = async (meetingId, itemId, newStatus) => {
    setUpdatingId(itemId);
    try {
      const res = await api.updateActionItemStatus(meetingId, itemId, newStatus);
      if (res && res.updated) {
        if (onStatusUpdate) {
          onStatusUpdate(meetingId, itemId, newStatus);
        }
      }
    } catch (err) {
      console.error('Status update failed:', err);
      alert(err.message || 'Failed to update action item status');
    } finally {
      setUpdatingId(null);
    }
  };

  const filteredItems = actionItems.filter((item) => {
    // Status filter
    if (filterStatus === 'pending' && item.status !== 'pending') return false;
    if (filterStatus === 'in_progress' && item.status !== 'in_progress') return false;
    if (filterStatus === 'completed' && item.status !== 'completed') return false;
    if (filterStatus === 'needs_review' && (item.owner && item.deadline)) return false;

    // Search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchTask = item.task && item.task.toLowerCase().includes(q);
      const matchOwner = item.owner && item.owner.toLowerCase().includes(q);
      const matchMeeting = String(item.meeting_id).includes(q);
      if (!matchTask && !matchOwner && !matchMeeting) return false;
    }

    return true;
  });

  const pendingCount = actionItems.filter((i) => i.status === 'pending').length;
  const inProgressCount = actionItems.filter((i) => i.status === 'in_progress').length;
  const completedCount = actionItems.filter((i) => i.status === 'completed').length;
  const needsReviewCount = actionItems.filter((i) => !i.owner || !i.deadline).length;

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
            Club Action Items Tracker
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', marginTop: '2px' }}>
            Cross-meeting task execution and accountability ({actionItems.length} total commitments)
          </p>
        </div>

        {/* View Mode Toggle: Table | Cards */}
        <div style={{
          display: 'flex',
          background: 'var(--surface-secondary)',
          border: '1px solid var(--border-default)',
          borderRadius: 'var(--radius-md)',
          padding: '3px'
        }}>
          <button
            className={`s5-btn s5-btn-sm ${viewMode === 'table' ? 's5-btn-secondary' : 's5-btn-ghost'}`}
            onClick={() => setViewMode('table')}
            title="Editorial Table View"
          >
            <Icon name="table" size={14} />
            <span>Table</span>
          </button>
          <button
            className={`s5-btn s5-btn-sm ${viewMode === 'cards' ? 's5-btn-secondary' : 's5-btn-ghost'}`}
            onClick={() => setViewMode('cards')}
            title="Cards View"
          >
            <Icon name="cards" size={14} />
            <span>Cards</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="s5-card" style={{ marginBottom: 'var(--space-6)', padding: '14px 18px' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 'var(--space-4)',
          flexWrap: 'wrap'
        }}>
          {/* Status Tabs */}
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {[
              { id: 'all', label: `All (${actionItems.length})` },
              { id: 'pending', label: `Pending (${pendingCount})` },
              { id: 'in_progress', label: `In Progress (${inProgressCount})` },
              { id: 'completed', label: `Completed (${completedCount})` },
              { id: 'needs_review', label: `Needs Review (${needsReviewCount})` },
            ].map((tab) => (
              <button
                key={tab.id}
                className={`s5-btn s5-btn-sm ${filterStatus === tab.id ? 's5-btn-primary' : 's5-btn-secondary'}`}
                onClick={() => setFilterStatus(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Search Box */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: '240px' }}>
            <Icon name="search" size={14} style={{ color: 'var(--text-muted)' }} />
            <input
              type="text"
              className="s5-input"
              placeholder="Filter tasks or assignees..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ padding: '6px 12px', fontSize: '0.82rem' }}
            />
          </div>
        </div>
      </div>

      {/* Results View */}
      {filteredItems.length === 0 ? (
        <div className="s5-empty-state">
          <div className="s5-empty-icon">
            <Icon name="actions" size={24} />
          </div>
          <div className="s5-empty-title">No Matching Action Items</div>
          <p className="s5-empty-desc">
            {searchQuery
              ? `No tasks found matching "${searchQuery}".`
              : 'There are no tasks under the selected filter.'}
          </p>
        </div>
      ) : viewMode === 'cards' ? (
        /* CARDS VIEW */
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 'var(--space-4)' }}>
          {filteredItems.map((item) => (
            <ActionCard
              key={item.id}
              item={item}
              meetingId={item.meeting_id}
              onStatusChange={(itemId, newStatus) => handleStatusChange(item.meeting_id, itemId, newStatus)}
              isUpdating={updatingId === item.id}
            />
          ))}
        </div>
      ) : (
        /* TABLE VIEW */
        <div className="s5-card" style={{ padding: 0, overflow: 'hidden' }}>
          <div className="s5-table-container" style={{ border: 'none' }}>
            <table className="s5-table">
              <thead>
                <tr>
                  <th style={{ width: '42%' }}>Action Task</th>
                  <th style={{ width: '18%' }}>Assignee</th>
                  <th style={{ width: '14%' }}>Deadline</th>
                  <th style={{ width: '12%' }}>Meeting</th>
                  <th style={{ width: '14%', textAlign: 'right' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item) => {
                  const hasOwner = Boolean(item.owner && item.owner.trim() !== '');
                  const hasDeadline = Boolean(item.deadline && item.deadline.trim() !== '');
                  const isUpdating = updatingId === item.id;

                  return (
                    <tr key={item.id}>
                      <td>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.4 }}>
                          {item.task}
                        </div>
                        {item.evidence && (
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontStyle: 'italic', marginTop: '3px' }}>
                            💬 "{item.evidence}"
                          </div>
                        )}
                        {(!hasOwner || !hasDeadline) && (
                          <div style={{ fontSize: '0.72rem', color: '#FBBF24', marginTop: '3px' }}>
                            ⚠️ Needs Review: {!hasOwner ? 'No owner specified' : 'No deadline'}
                          </div>
                        )}
                      </td>
                      <td>
                        {hasOwner ? (
                          <span style={{ fontWeight: 500, color: 'var(--text-primary)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                            <Icon name="user" size={13} style={{ color: 'var(--accent-primary)' }} />
                            <span>{item.owner}</span>
                          </span>
                        ) : (
                          <span style={{ color: 'var(--text-dim)', fontStyle: 'italic' }}>Unassigned</span>
                        )}
                      </td>
                      <td>
                        {hasDeadline ? (
                          <span style={{ color: '#FCD34D', fontSize: '0.84rem' }}>{item.deadline}</span>
                        ) : (
                          <span style={{ color: 'var(--text-dim)', fontStyle: 'italic' }}>None</span>
                        )}
                      </td>
                      <td>
                        <button
                          className="s5-btn s5-btn-ghost s5-btn-sm"
                          onClick={() => onSelectMeeting && onSelectMeeting(item.meeting_id)}
                          style={{ padding: '2px 6px', fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: 'var(--accent-primary)' }}
                          title="View source meeting"
                        >
                          #{item.meeting_id} →
                        </button>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                          <select
                            className="s5-select"
                            value={item.status}
                            disabled={isUpdating}
                            onChange={(e) => handleStatusChange(item.meeting_id, item.id, e.target.value)}
                            style={{ fontWeight: 600 }}
                          >
                            <option value="pending">Pending</option>
                            <option value="in_progress">In Progress</option>
                            <option value="completed">Completed</option>
                            <option value="cancelled">Cancelled</option>
                          </select>
                          {isUpdating && <span className="s5-spinner" style={{ width: '12px', height: '12px' }} />}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
