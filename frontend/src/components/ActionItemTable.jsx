import React, { useState } from 'react';
import api from '../services/api';

const STATUS_OPTIONS = [
  { value: 'pending', label: 'Pending' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
];

export default function ActionItemTable({ meetingId, actionItems = [], onStatusUpdate }) {
  const [updatingId, setUpdatingId] = useState(null);
  const [errorMap, setErrorMap] = useState({});

  const handleStatusChange = async (itemId, newStatus) => {
    setUpdatingId(itemId);
    setErrorMap((prev) => ({ ...prev, [itemId]: null }));

    try {
      const result = await api.updateActionItemStatus(meetingId, itemId, newStatus);
      if (result && result.updated) {
        if (onStatusUpdate) {
          onStatusUpdate(itemId, newStatus);
        }
      }
    } catch (err) {
      console.error('Failed to update status:', err);
      setErrorMap((prev) => ({
        ...prev,
        [itemId]: err.message || 'Update failed',
      }));
    } finally {
      setUpdatingId(null);
    }
  };

  if (!actionItems || actionItems.length === 0) {
    return (
      <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
        No action items extracted for this meeting.
      </div>
    );
  }

  return (
    <div className="table-container">
      <table className="data-table">
        <thead>
          <tr>
            <th style={{ width: '45%' }}>Action Task</th>
            <th style={{ width: '20%' }}>Assignee</th>
            <th style={{ width: '15%' }}>Deadline</th>
            <th style={{ width: '20%' }}>Status</th>
          </tr>
        </thead>
        <tbody>
          {actionItems.map((item) => {
            const isUpdating = updatingId === item.id;
            const itemError = errorMap[item.id];

            return (
              <tr key={item.id}>
                <td>
                  <div style={{ fontWeight: 500 }}>{item.task}</div>
                  {item.evidence && (
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontStyle: 'italic', marginTop: '0.25rem' }}>
                      💬 "{item.evidence}"
                    </div>
                  )}
                  {itemError && (
                    <div style={{ color: 'var(--danger)', fontSize: '0.75rem', marginTop: '0.25rem' }}>
                      ⚠️ {itemError}
                    </div>
                  )}
                </td>
                <td>
                  {item.owner ? (
                    <span style={{ color: '#818cf8', fontWeight: 500 }}>👤 {item.owner}</span>
                  ) : (
                    <span style={{ color: 'var(--text-dim)', fontStyle: 'italic' }}>Unassigned</span>
                  )}
                </td>
                <td>
                  {item.deadline ? (
                    <span style={{ color: '#fbbf24' }}>📅 {item.deadline}</span>
                  ) : (
                    <span style={{ color: 'var(--text-dim)', fontStyle: 'italic' }}>None</span>
                  )}
                </td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <select
                      className="status-select"
                      value={item.status}
                      disabled={isUpdating}
                      onChange={(e) => handleStatusChange(item.id, e.target.value)}
                    >
                      {STATUS_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>

                    <span className={`badge badge-${item.status}`}>
                      {item.status.replace('_', ' ')}
                    </span>

                    {isUpdating && (
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        ⏳
                      </span>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
