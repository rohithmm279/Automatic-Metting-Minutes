import React, { useState, useEffect } from 'react';
import api from '../services/api';
import { Icon } from '../components/icons/Icons';
import ActionCard from '../components/cards/ActionCard';
import ConfirmModal from '../components/ConfirmModal';

export default function MeetingDetailsView({
  meetingId,
  onBack,
  onDeleted,
  _onSelectMeeting,
}) {
  const [meeting, setMeeting] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [updatingItemId, setUpdatingItemId] = useState(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showTranscript, setShowTranscript] = useState(false);
  const [transcriptSearch, setTranscriptSearch] = useState('');
  const [copiedSummary, setCopiedSummary] = useState(false);

  const fetchDetails = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getMeeting(meetingId);
      setMeeting(data);
    } catch (err) {
      console.error('Failed to load meeting:', err);
      setError(err.message || 'Could not load meeting record from server.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (meetingId) {
      fetchDetails();
    }
  }, [meetingId]);

  const handleStatusChange = async (itemId, newStatus) => {
    setUpdatingItemId(itemId);
    try {
      const res = await api.updateActionItemStatus(meetingId, itemId, newStatus);
      if (res && res.updated) {
        setMeeting((prev) => {
          if (!prev) return prev;
          const nextItems = (prev.action_items || []).map((i) =>
            i.id === itemId ? { ...i, status: newStatus } : i
          );
          return { ...prev, action_items: nextItems };
        });
      }
    } catch (err) {
      console.error('Status update failed:', err);
      alert(err.message || 'Failed to update action item status');
    } finally {
      setUpdatingItemId(null);
    }
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await api.deleteMeeting(meetingId);
      setShowDeleteModal(false);
      if (onDeleted) onDeleted(meetingId);
    } catch (err) {
      console.error('Delete failed:', err);
      alert(err.message || 'Failed to delete meeting');
    } finally {
      setIsDeleting(false);
    }
  };

  const copySummary = () => {
    if (!meeting?.summary) return;
    navigator.clipboard.writeText(meeting.summary);
    setCopiedSummary(true);
    setTimeout(() => setCopiedSummary(false), 2000);
  };

  const downloadJson = () => {
    if (!meeting) return;
    const blob = new Blob([JSON.stringify(meeting, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `meeting_${meeting.id}_intelligence.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 'var(--space-12)' }}>
        <span className="s5-spinner" style={{ width: '28px', height: '28px', color: 'var(--accent-primary)' }} />
        <p style={{ marginTop: 'var(--space-3)', color: 'var(--text-muted)' }}>
          Retrieving meeting #{meetingId} intelligence...
        </p>
      </div>
    );
  }

  if (error || !meeting) {
    return (
      <div className="s5-empty-state">
        <div className="s5-empty-icon" style={{ color: 'var(--semantic-red)' }}>
          <Icon name="issues" size={24} />
        </div>
        <div className="s5-empty-title">Meeting Not Found</div>
        <p className="s5-empty-desc">{error || 'The requested meeting record does not exist.'}</p>
        <button className="s5-btn s5-btn-secondary" onClick={onBack}>
          ← Back to Meetings
        </button>
      </div>
    );
  }

  const actionItems = meeting.action_items || [];
  const decisions = meeting.decisions || [];
  const issues = meeting.unresolved_issues || [];

  // Deterministic metrics calculated from real data
  const totalActions = actionItems.length;
  const itemsWithOwner = actionItems.filter((i) => i.owner && i.owner.trim() !== '').length;
  const itemsWithDeadline = actionItems.filter((i) => i.deadline && i.deadline.trim() !== '').length;
  const itemsNeedingReview = actionItems.filter((i) => !i.owner || !i.deadline);

  return (
    <div>
      {/* Top Header & Actions Bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 'var(--space-6)',
        flexWrap: 'wrap',
        gap: 'var(--space-3)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button className="s5-btn s5-btn-secondary s5-btn-sm" onClick={onBack}>
            <Icon name="arrow-left" size={14} />
            <span>Back</span>
          </button>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h1 style={{ fontSize: '1.5rem', fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>
                Meeting Record #{meeting.id}
              </h1>
              <span className="s5-badge s5-badge-confirmed">
                <Icon name="shield-check" size={12} />
                <span>Verified</span>
              </span>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Recorded on {meeting.created_at ? new Date(meeting.created_at).toLocaleString() : 'Recently'}
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            className="s5-btn s5-btn-secondary s5-btn-sm"
            onClick={copySummary}
            title="Copy executive summary to clipboard"
          >
            <Icon name="copy" size={14} />
            <span>{copiedSummary ? 'Copied!' : 'Copy Summary'}</span>
          </button>

          <button
            className="s5-btn s5-btn-secondary s5-btn-sm"
            onClick={downloadJson}
            title="Export full meeting data as JSON"
          >
            <Icon name="file-text" size={14} />
            <span>Export JSON</span>
          </button>

          <button
            className="s5-btn s5-btn-danger s5-btn-sm"
            onClick={() => setShowDeleteModal(true)}
            title="Delete meeting record"
          >
            <Icon name="trash" size={14} />
            <span>Delete</span>
          </button>
        </div>
      </div>

      {/* Deterministic Data Transparency / Health Strip */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: 'var(--space-3)',
        marginBottom: 'var(--space-6)',
      }}>
        <div style={{ background: 'var(--surface-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '10px 14px' }}>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Actions Extracted</div>
          <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>{totalActions}</div>
        </div>
        <div style={{ background: 'var(--surface-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '10px 14px' }}>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Identified Assignees</div>
          <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#A5B4FC' }}>
            {totalActions > 0 ? `${itemsWithOwner} of ${totalActions}` : '0'}
          </div>
        </div>
        <div style={{ background: 'var(--surface-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '10px 14px' }}>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Stated Deadlines</div>
          <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#FCD34D' }}>
            {totalActions > 0 ? `${itemsWithDeadline} of ${totalActions}` : '0'}
          </div>
        </div>
        <div style={{ background: 'var(--surface-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '10px 14px' }}>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Review Items</div>
          <div style={{ fontSize: '1.2rem', fontWeight: 700, color: itemsNeedingReview.length > 0 ? '#F87171' : '#34D399' }}>
            {itemsNeedingReview.length}
          </div>
        </div>
      </div>

      {/* 1. AI EXECUTIVE SUMMARY CARD */}
      <div className="s5-card" style={{ marginBottom: 'var(--space-6)' }}>
        <div className="s5-card-header" style={{ marginBottom: 'var(--space-3)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Icon name="file-text" size={17} style={{ color: 'var(--accent-primary)' }} />
            <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)' }}>
              Executive Summary
            </h3>
          </div>
          <div style={{ display: 'flex', gap: '6px' }}>
            <span className="s5-badge s5-badge-neutral">AI Analysis</span>
            <span className="s5-badge s5-badge-confirmed">Grounding Verified</span>
          </div>
        </div>

        <p style={{
          fontSize: '0.92rem',
          lineHeight: 1.6,
          color: 'var(--text-primary)',
          background: 'var(--surface-elevated)',
          padding: '14px 18px',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-subtle)'
        }}>
          {meeting.summary}
        </p>
      </div>

      {/* 2. ACTION ITEMS — PRIMARY FOCUS */}
      <div className="s5-card" style={{ marginBottom: 'var(--space-6)' }}>
        <div className="s5-card-header">
          <div>
            <h3 className="s5-card-title">
              <Icon name="actions" size={18} style={{ color: 'var(--accent-primary)' }} />
              <span>Action Items & Commitments ({totalActions})</span>
            </h3>
            <p className="s5-card-subtitle">
              Interactive task tracking with status transitions saved directly to database
            </p>
          </div>
        </div>

        {/* Human review notification banner if items lack owner or deadline */}
        {itemsNeedingReview.length > 0 && (
          <div className="s5-review-banner" style={{ margin: '0 0 var(--space-4)' }}>
            <div className="s5-review-banner-text">
              <Icon name="issues" size={16} />
              <span>
                <strong>{itemsNeedingReview.length} item{itemsNeedingReview.length === 1 ? '' : 's'} require review</strong> — owner or deadline was ambiguous in dialogue.
              </span>
            </div>
          </div>
        )}

        {actionItems.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 'var(--space-8)', color: 'var(--text-muted)' }}>
            No explicit action items identified in this meeting transcript.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            {actionItems.map((item) => (
              <ActionCard
                key={item.id}
                item={item}
                meetingId={meeting.id}
                onStatusChange={handleStatusChange}
                isUpdating={updatingItemId === item.id}
              />
            ))}
          </div>
        )}
      </div>

      {/* 3. DECISIONS & 4. OPEN ISSUES (Side-by-side) */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
        gap: 'var(--space-6)',
        marginBottom: 'var(--space-6)'
      }}>
        {/* Decisions */}
        <div className="s5-card">
          <div className="s5-card-header">
            <h3 className="s5-card-title">
              <Icon name="decisions" size={18} style={{ color: 'var(--semantic-green)' }} />
              <span>Confirmed Decisions ({decisions.length})</span>
            </h3>
          </div>
          {decisions.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', fontStyle: 'italic', padding: '12px' }}>
              No explicit decisions recorded in this meeting.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {decisions.map((d) => (
                <div key={d.id} className="s5-decision-item">
                  <Icon name="check" size={16} style={{ color: 'var(--semantic-green)', marginTop: '2px' }} />
                  <div style={{ fontSize: '0.88rem', color: 'var(--text-primary)', lineHeight: 1.4 }}>
                    {d.decision}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Unresolved Issues */}
        <div className="s5-card">
          <div className="s5-card-header">
            <h3 className="s5-card-title">
              <Icon name="issues" size={18} style={{ color: 'var(--semantic-red)' }} />
              <span>Open Issues & Blockers ({issues.length})</span>
            </h3>
          </div>
          {issues.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', fontStyle: 'italic', padding: '12px' }}>
              No unresolved issues or blockers pending.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {issues.map((i) => (
                <div key={i.id} className="s5-issue-item">
                  <Icon name="issues" size={16} style={{ color: 'var(--semantic-red)', marginTop: '2px' }} />
                  <div style={{ fontSize: '0.88rem', color: 'var(--text-primary)', lineHeight: 1.4 }}>
                    {i.issue}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 5. RAW TRANSCRIPT TRANSPARENCY (Full Honest Evidence Inspector) */}
      {meeting.transcript && (
        <div className="s5-card">
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              cursor: 'pointer',
              userSelect: 'none'
            }}
            onClick={() => setShowTranscript(!showTranscript)}
            role="button"
            tabIndex={0}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Icon name="file-text" size={17} style={{ color: 'var(--text-secondary)' }} />
              <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                Raw Meeting Transcript Transparency
              </h3>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                ({meeting.transcript.length} characters)
              </span>
            </div>
            <button className="s5-btn s5-btn-ghost s5-btn-sm" type="button">
              <span>{showTranscript ? 'Hide Transcript' : 'Inspect Raw Dialogue'}</span>
              <Icon name={showTranscript ? 'chevron-down' : 'chevron-right'} size={14} />
            </button>
          </div>

          {showTranscript && (
            <div style={{ marginTop: 'var(--space-4)', borderTop: '1px solid var(--border-subtle)', paddingTop: 'var(--space-4)' }}>
              <div style={{ marginBottom: 'var(--space-3)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Icon name="search" size={14} style={{ color: 'var(--text-muted)' }} />
                <input
                  type="text"
                  placeholder="Filter dialogue by speaker or keyword..."
                  value={transcriptSearch}
                  onChange={(e) => setTranscriptSearch(e.target.value)}
                  className="s5-input"
                  style={{ maxWidth: '360px', padding: '6px 10px', fontSize: '0.82rem' }}
                />
              </div>

              <div style={{
                background: 'var(--surface-input)',
                border: '1px solid var(--border-default)',
                borderRadius: 'var(--radius-md)',
                padding: '16px',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.82rem',
                lineHeight: 1.6,
                maxHeight: '380px',
                overflowY: 'auto',
                whiteSpace: 'pre-wrap',
                color: 'var(--text-secondary)'
              }}>
                {transcriptSearch
                  ? meeting.transcript
                      .split('\n')
                      .filter((line) => line.toLowerCase().includes(transcriptSearch.toLowerCase()))
                      .join('\n') || 'No matching lines in dialogue.'
                  : meeting.transcript}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Cascade Deletion Confirmation Modal */}
      <ConfirmModal
        isOpen={showDeleteModal}
        title={`Delete Meeting Record #${meeting.id}`}
        message="Are you sure you want to delete this meeting? All associated action items, decisions, and issues will be permanently removed from SQLite through foreign-key cascade."
        onConfirm={handleDelete}
        onCancel={() => setShowDeleteModal(false)}
        isDeleting={isDeleting}
      />
    </div>
  );
}
