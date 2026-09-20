import React from 'react';

/**
 * ActionItemCard - 10x interactive task card
 * Shows task description, assignee avatar, color-coded deadline urgency,
 * AI confidence %, "Needs Review" ambiguity banner, and quick 1-click status cycling.
 */
export default function ActionItemCard({
  item,
  meetingTitle,
  onStatusChange,
  onViewEvidence,
  onSelectMeeting,
  compact = false,
}) {
  if (!item) return null;

  const {
    id,
    task,
    status = 'pending',
    is_inferred = false,
    meeting_id,
  } = item;

  const assignee = item.owner || item.assignee || 'Unassigned';
  const deadline = item.deadline || 'No deadline';
  const rawConfidence = item.confidence ?? item.confidence_score ?? 1.0;

  // Compute confidence percentage (0-100)
  const confidence = typeof rawConfidence === 'number'
    ? Math.round(rawConfidence > 1 ? rawConfidence : rawConfidence * 100)
    : 100;

  const isLowConfidence = confidence < 75 || is_inferred || assignee === 'Unassigned' || !deadline || deadline === 'No deadline';

  // Deadline urgency calculation
  const getDeadlineUrgency = (dlStr) => {
    if (!dlStr || dlStr === 'No deadline' || dlStr === 'TBD') return 'neutral';
    const lower = dlStr.toLowerCase();
    if (lower.includes('today') || lower.includes('overdue') || lower.includes('yesterday') || lower.includes('asap') || lower.includes('immediate')) {
      return 'urgent';
    }
    if (lower.includes('tomorrow') || lower.includes('2 days') || lower.includes('soon') || lower.includes('this week') || lower.includes('wednesday') || lower.includes('friday')) {
      return 'warning';
    }
    return 'normal';
  };

  const urgency = getDeadlineUrgency(deadline);

  // Status cycling
  const nextStatusMap = {
    pending: 'in_progress',
    in_progress: 'completed',
    completed: 'pending',
    cancelled: 'pending',
  };

  const handleStatusCycle = (e) => {
    e.stopPropagation();
    const nextStatus = nextStatusMap[status] || 'pending';
    if (onStatusChange) {
      onStatusChange(meeting_id, id, nextStatus);
    }
  };

  // Get initials for assignee avatar
  const getInitials = (name) => {
    if (!name || name === 'Unassigned') return '?';
    return name
      .split(' ')
      .map((part) => part[0])
      .slice(0, 2)
      .join('')
      .toUpperCase();
  };

  const statusLabels = {
    pending: 'Pending',
    in_progress: 'In Progress',
    completed: 'Done',
    cancelled: 'Cancelled',
  };

  return (
    <div className={`action-card ${status === 'completed' ? 'action-card-completed' : ''} ${compact ? 'action-card-compact' : ''}`}>
      {/* Top Bar: Ambiguity / Needs Review flag if low confidence or missing owner */}
      {isLowConfidence && (
        <div className="action-card-flag">
          <span className="flag-icon">⚠</span>
          <span className="flag-text">
            {assignee === 'Unassigned' ? 'Owner Unassigned' : (!deadline || deadline === 'No deadline') ? 'Deadline Missing' : 'Needs Review'}
          </span>
          <span className="flag-badge">{confidence}% Conf.</span>
        </div>
      )}

      {/* Main Task Description */}
      <div className="action-card-body">
        <p className="action-card-task">{task}</p>

        {/* Meta: Assignee + Deadline */}
        <div className="action-card-meta">
          <div className="action-assignee-pill" title={`Assigned to: ${assignee}`}>
            <span className="assignee-avatar">{getInitials(assignee)}</span>
            <span className="assignee-name">{assignee}</span>
          </div>

          <div className={`action-deadline-pill urgency-${urgency}`} title={`Due: ${deadline}`}>
            <span className="deadline-icon">📅</span>
            <span className="deadline-text">{deadline}</span>
          </div>
        </div>

        {/* Meeting context reference if available */}
        {meetingTitle && (
          <div
            className="action-meeting-link"
            onClick={(e) => {
              e.stopPropagation();
              if (onSelectMeeting && meeting_id) onSelectMeeting(meeting_id);
            }}
          >
            <span className="meeting-link-icon">▣</span>
            <span className="meeting-link-text">{meetingTitle}</span>
          </div>
        )}
      </div>

      {/* Card Footer: Status Cycle Button & AI Confidence / Evidence */}
      <div className="action-card-footer">
        <button
          type="button"
          className={`action-status-btn status-btn-${status}`}
          onClick={handleStatusCycle}
          title="Click to cycle status"
        >
          <span className={`status-indicator-dot dot-${status}`} />
          <span>{statusLabels[status] || status}</span>
        </button>

        <div className="action-card-actions">
          {onViewEvidence && (
            <button
              type="button"
              className="action-evidence-btn"
              onClick={(e) => {
                e.stopPropagation();
                onViewEvidence(item);
              }}
              title="Inspect AI evidence & grounding quote"
            >
              ✦ Evidence
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
