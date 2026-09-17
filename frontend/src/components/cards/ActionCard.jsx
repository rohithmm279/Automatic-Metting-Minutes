import React from 'react';
import { Icon } from '../icons/Icons';

export default function ActionCard({
  item,
  _meetingId,
  onStatusChange,
  isUpdating = false,
}) {
  const hasOwner = Boolean(item.owner && item.owner.trim() !== '');
  const hasDeadline = Boolean(item.deadline && item.deadline.trim() !== '');
  const needsReview = !hasOwner || !hasDeadline;

  const getConfidenceInfo = (conf) => {
    const val = typeof conf === 'number' ? Math.round(conf * 100) : 100;
    if (val >= 85) return { label: `${val}% Confidence`, class: 's5-confidence-high', desc: 'Explicitly identified in dialogue' };
    if (val >= 60) return { label: `${val}% Inferred`, class: 's5-confidence-medium', desc: 'Inferred from context' };
    return { label: `${val}% Needs Review`, class: 's5-confidence-low', desc: 'Missing explicit details' };
  };

  const confInfo = getConfidenceInfo(item.confidence);

  return (
    <div className={`s5-action-card status-${item.status}`}>
      {/* Top row: Task & Status Selector */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px' }}>
        <div style={{ flex: 1 }}>
          <h4 className="s5-action-task">{item.task}</h4>
          {needsReview && (
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              fontSize: '0.72rem',
              color: '#FBBF24',
              background: 'rgba(245, 158, 11, 0.1)',
              border: '1px solid rgba(245, 158, 11, 0.25)',
              padding: '2px 6px',
              borderRadius: 'var(--radius-sm)',
              marginTop: '4px',
              fontWeight: 600
            }}>
              <Icon name="issues" size={12} />
              <span>Needs Review: {!hasOwner && !hasDeadline ? 'Owner & Deadline not specified' : !hasOwner ? 'Owner not specified' : 'Deadline not specified'}</span>
            </div>
          )}
        </div>

        {/* Status Dropdown */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <select
            className="s5-select"
            value={item.status}
            disabled={isUpdating}
            onChange={(e) => onStatusChange(item.id, e.target.value)}
            style={{ fontWeight: 600 }}
          >
            <option value="pending">Pending</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </select>
          {isUpdating && <span className="s5-spinner" style={{ width: '12px', height: '12px' }} />}
        </div>
      </div>

      {/* Grounding Evidence Quote */}
      {item.evidence && (
        <div style={{
          fontSize: '0.78rem',
          color: 'var(--text-muted)',
          fontStyle: 'italic',
          background: 'var(--surface-elevated)',
          padding: '6px 10px',
          borderRadius: 'var(--radius-sm)',
          borderLeft: '2px solid var(--accent-primary)',
          display: 'flex',
          alignItems: 'flex-start',
          gap: '6px',
        }}>
          <span style={{ color: 'var(--accent-primary)', fontStyle: 'normal', fontWeight: 600, fontSize: '0.72rem', flexShrink: 0 }}>
            Evidence:
          </span>
          <span style={{ lineHeight: 1.4 }}>"{item.evidence}"</span>
        </div>
      )}

      {/* Metadata Row: Assignee, Deadline, Confidence */}
      <div className="s5-action-meta">
        {/* Assignee */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <Icon name="user" size={14} style={{ color: hasOwner ? 'var(--accent-primary)' : 'var(--text-dim)' }} />
          {hasOwner ? (
            <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{item.owner}</span>
          ) : (
            <span style={{ color: 'var(--text-dim)', fontStyle: 'italic' }}>Unassigned</span>
          )}
        </div>

        <span>•</span>

        {/* Deadline */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <Icon name="clock" size={14} style={{ color: hasDeadline ? '#FBBF24' : 'var(--text-dim)' }} />
          {hasDeadline ? (
            <span style={{ color: '#FCD34D' }}>{item.deadline}</span>
          ) : (
            <span style={{ color: 'var(--text-dim)', fontStyle: 'italic' }}>No deadline</span>
          )}
        </div>

        <span>•</span>

        {/* Confidence Pill */}
        <span className={`s5-confidence-pill ${confInfo.class}`} title={confInfo.desc}>
          {confInfo.label}
        </span>
      </div>
    </div>
  );
}
