import React, { useState } from 'react';
import api from '../services/api';
import { Icon } from '../components/icons/Icons';
import ActionItemCard from '../components/cards/ActionItemCard';
import EvidenceDrawer from '../components/drawer/EvidenceDrawer';

export default function ActionTracker({
  actionItems = [],
  onStatusUpdate,
  onSelectMeeting,
}) {
  const [filterStatus, setFilterStatus] = useState('all');
  const [viewMode, setViewMode] = useState('cards'); // 'cards' (default) | 'table'
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEvidenceItem, setSelectedEvidenceItem] = useState(null);
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
      // Fallback local update for UI fluidity
      if (onStatusUpdate) {
        onStatusUpdate(meetingId, itemId, newStatus);
      }
    } finally {
      setUpdatingId(null);
    }
  };

  const isUrgent = (a) => {
    const dl = (a.deadline || '').toLowerCase();
    return (
      a.status !== 'completed' &&
      (dl.includes('today') || dl.includes('overdue') || dl.includes('yesterday') || dl.includes('asap') || dl.includes('wednesday'))
    );
  };

  const isNeedsReview = (a) => {
    const owner = a.owner || a.assignee;
    const rawConf = a.confidence ?? a.confidence_score ?? 1.0;
    return (
      a.status !== 'completed' &&
      (!owner || owner === 'Unassigned' || !a.deadline || a.deadline === 'No deadline' || (typeof rawConf === 'number' && rawConf < 0.75))
    );
  };

  const filteredItems = actionItems.filter((item) => {
    if (filterStatus === 'urgent' && !isUrgent(item)) return false;
    if (filterStatus === 'needs_review' && !isNeedsReview(item)) return false;
    if (filterStatus === 'pending' && item.status !== 'pending') return false;
    if (filterStatus === 'in_progress' && item.status !== 'in_progress') return false;
    if (filterStatus === 'completed' && item.status !== 'completed') return false;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchTask = item.task && item.task.toLowerCase().includes(q);
      const matchAssignee = (item.assignee || item.owner || '').toLowerCase().includes(q);
      const matchMeeting = String(item.meeting_id).includes(q);
      if (!matchTask && !matchAssignee && !matchMeeting) return false;
    }

    return true;
  });

  const urgentCount = actionItems.filter(isUrgent).length;
  const needsReviewCount = actionItems.filter(isNeedsReview).length;
  const pendingCount = actionItems.filter((i) => i.status === 'pending').length;
  const inProgressCount = actionItems.filter((i) => i.status === 'in_progress').length;
  const completedCount = actionItems.filter((i) => i.status === 'completed').length;

  return (
    <div className="action-tracker-page">
      {/* 1. Header */}
      <div className="tracker-header-flex">
        <div>
          <h1 className="tracker-main-title">Action Items & Commitments</h1>
          <p className="tracker-subtitle">
            Living task matrix with explainable AI grounding ({actionItems.length} total across all meetings)
          </p>
        </div>

        {/* View Mode Toggle: Cards (default) | Table */}
        <div className="view-toggle-pills">
          <button
            type="button"
            className={`s5-btn s5-btn-sm ${viewMode === 'cards' ? 's5-btn-secondary' : 's5-btn-ghost'}`}
            onClick={() => setViewMode('cards')}
            title="Interactive Task Cards"
          >
            <Icon name="cards" size={14} />
            <span>Cards</span>
          </button>
          <button
            type="button"
            className={`s5-btn s5-btn-sm ${viewMode === 'table' ? 's5-btn-secondary' : 's5-btn-ghost'}`}
            onClick={() => setViewMode('table')}
            title="Dense Table View"
          >
            <Icon name="table" size={14} />
            <span>Table</span>
          </button>
        </div>
      </div>

      {/* 2. Filter & Search Toolbar */}
      <div className="s5-card tracker-toolbar-card">
        <div className="tracker-toolbar-flex">
          {/* Status Filter Tabs */}
          <div className="tracker-tabs-list">
            {[
              { id: 'all', label: `All (${actionItems.length})` },
              { id: 'urgent', label: `🔴 Urgent (${urgentCount})` },
              { id: 'needs_review', label: `🟡 Needs Review (${needsReviewCount})` },
              { id: 'in_progress', label: `In Progress (${inProgressCount})` },
              { id: 'pending', label: `Pending (${pendingCount})` },
              { id: 'completed', label: `Done (${completedCount})` },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                className={`s5-btn s5-btn-sm ${filterStatus === tab.id ? 's5-btn-primary' : 's5-btn-secondary'}`}
                onClick={() => setFilterStatus(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Search Box */}
          <div className="tracker-search-box">
            <Icon name="search" size={14} style={{ color: 'var(--text-muted)' }} />
            <input
              type="text"
              className="s5-input"
              placeholder="Search task, assignee..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>
      </div>

      {/* 3. Main Results Display */}
      {filteredItems.length === 0 ? (
        <div className="s5-empty-state">
          <div className="s5-empty-icon"><Icon name="actions" size={24} /></div>
          <div className="s5-empty-title">No Matching Action Items</div>
          <p className="s5-empty-desc">
            {searchQuery
              ? `No commitments matching "${searchQuery}".`
              : 'There are no tasks under the selected filter.'}
          </p>
        </div>
      ) : viewMode === 'cards' ? (
        /* INTERACTIVE CARD MATRIX */
        <div className="action-cards-masonry">
          {filteredItems.map((item) => (
            <ActionItemCard
              key={item.id}
              item={item}
              meetingTitle={`Meeting #${item.meeting_id || '1'}`}
              onStatusChange={(meetingId, itemId, newStatus) =>
                handleStatusChange(meetingId || item.meeting_id, itemId, newStatus)
              }
              onViewEvidence={(it) => setSelectedEvidenceItem(it)}
              onSelectMeeting={onSelectMeeting}
            />
          ))}
        </div>
      ) : (
        /* DENSE TABLE VIEW */
        <div className="s5-card" style={{ padding: 0, overflow: 'hidden' }}>
          <div className="s5-table-container" style={{ border: 'none' }}>
            <table className="s5-table">
              <thead>
                <tr>
                  <th style={{ width: '40%' }}>Action Task</th>
                  <th style={{ width: '18%' }}>Assignee</th>
                  <th style={{ width: '14%' }}>Deadline</th>
                  <th style={{ width: '12%' }}>Meeting</th>
                  <th style={{ width: '16%', textAlign: 'right' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item) => {
                  const assignee = item.assignee || item.owner || 'Unassigned';
                  const isUpdating = updatingId === item.id;
                  return (
                    <tr key={item.id}>
                      <td>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.4 }}>
                          {item.task}
                        </div>
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '4px' }}>
                          <button
                            type="button"
                            className="evidence-inline-link"
                            onClick={() => setSelectedEvidenceItem(item)}
                          >
                            ✦ Grounding Evidence
                          </button>
                        </div>
                      </td>
                      <td>
                        <span style={{ fontWeight: 500, color: 'var(--text-primary)' }}>
                          {assignee}
                        </span>
                      </td>
                      <td>
                        <span style={{ color: 'var(--semantic-amber)', fontSize: '0.84rem' }}>
                          {item.deadline || 'None'}
                        </span>
                      </td>
                      <td>
                        <button
                          type="button"
                          className="s5-btn s5-btn-ghost s5-btn-sm"
                          onClick={() => onSelectMeeting && onSelectMeeting(item.meeting_id)}
                        >
                          #{item.meeting_id} →
                        </button>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <select
                          className="s5-select"
                          value={item.status}
                          disabled={isUpdating}
                          onChange={(e) => handleStatusChange(item.meeting_id, item.id, e.target.value)}
                        >
                          <option value="pending">Pending</option>
                          <option value="in_progress">In Progress</option>
                          <option value="completed">Done</option>
                          <option value="cancelled">Cancelled</option>
                        </select>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Explainable AI Evidence Drawer */}
      <EvidenceDrawer
        isOpen={Boolean(selectedEvidenceItem)}
        onClose={() => setSelectedEvidenceItem(null)}
        item={selectedEvidenceItem}
        type="action"
      />
    </div>
  );
}
