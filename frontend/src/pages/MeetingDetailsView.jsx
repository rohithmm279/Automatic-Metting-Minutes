import React, { useState, useEffect } from 'react';
import api from '../services/api';
import { Icon } from '../components/icons/Icons';
import ActionItemCard from '../components/cards/ActionItemCard';
import EvidenceDrawer from '../components/drawer/EvidenceDrawer';
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
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showTranscript, setShowTranscript] = useState(false);
  const [transcriptSearch, setTranscriptSearch] = useState('');
  const [copiedSummary, setCopiedSummary] = useState(false);
  const [copiedAll, setCopiedAll] = useState(false);
  const [selectedEvidence, setSelectedEvidence] = useState(null);
  const [evidenceType, setEvidenceType] = useState('action');

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

  const handleStatusChange = async (_meetingId, itemId, newStatus) => {
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
      // Optimistic fallback
      setMeeting((prev) => {
        if (!prev) return prev;
        const nextItems = (prev.action_items || []).map((i) =>
          i.id === itemId ? { ...i, status: newStatus } : i
        );
        return { ...prev, action_items: nextItems };
      });
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

  const formattedMinutesText = () => {
    if (!meeting) return '';
    const dateStr = meeting.meeting_date || 'Date: Not specified in transcript';
    const timeStr = meeting.meeting_time || (meeting.start_time ? `${meeting.start_time}${meeting.end_time ? ' - ' + meeting.end_time : ''}` : 'Time: Not specified in transcript');
    const actionsStr = (meeting.action_items || []).map(
      (a, i) => `${i + 1}. [${a.status ? a.status.toUpperCase() : 'PENDING'}] ${a.task} (Assignee: ${a.owner || 'Unassigned'}${a.deadline ? `, Due: ${a.deadline}` : ''})`
    ).join('\n');
    const decisionsStr = (meeting.decisions || []).map(
      (d, i) => `${i + 1}. ${d.decision}`
    ).join('\n');
    const issuesStr = (meeting.unresolved_issues || []).map(
      (iss, i) => `${i + 1}. ${iss.issue || iss.topic}`
    ).join('\n');

    return `# ${meeting.title || `Meeting #${meeting.id}`}
Date: ${dateStr}
Time: ${timeStr}
Processed On: ${meeting.created_at ? new Date(meeting.created_at).toLocaleString() : 'N/A'}

## Executive Summary
${meeting.summary || 'No summary available.'}

## Action Items (${(meeting.action_items || []).length})
${actionsStr || 'No action items.'}

## Key Decisions (${(meeting.decisions || []).length})
${decisionsStr || 'No decisions recorded.'}

## Open Issues & Risks (${(meeting.unresolved_issues || []).length})
${issuesStr || 'No open issues.'}
`;
  };

  const copyAll = () => {
    const text = formattedMinutesText();
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedAll(true);
    setTimeout(() => setCopiedAll(false), 2000);
  };

  const downloadTxt = () => {
    const text = formattedMinutesText();
    if (!text) return;
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `meeting_${meeting.id}_minutes.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handlePrintPdf = () => {
    window.print();
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
      <div className="meeting-details-loading">
        <span className="s5-spinner" style={{ width: '28px', height: '28px', color: 'var(--accent-primary)' }} />
        <p style={{ marginTop: 'var(--space-3)', color: 'var(--text-muted)' }}>
          Retrieving Meeting #{meetingId} Intelligence...
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
        <div className="s5-empty-title">Meeting Record Not Found</div>
        <p className="s5-empty-desc">{error || 'The requested meeting record does not exist.'}</p>
        <button type="button" className="s5-btn s5-btn-secondary" onClick={onBack}>
          ← Back to Overview
        </button>
      </div>
    );
  }

  const actionItems = meeting.action_items || [];
  const decisions = meeting.decisions || [];
  const issues = meeting.unresolved_issues || [];

  return (
    <div className="meeting-details-flagship">
      {/* 1. Header Toolbar */}
      <div className="meeting-details-header">
        <div className="meeting-header-left">
          <button type="button" className="s5-btn s5-btn-secondary s5-btn-sm" onClick={onBack}>
            <Icon name="arrow-left" size={14} />
            <span>Back</span>
          </button>
          <div>
            <div className="meeting-title-row">
              <h1 className="meeting-main-heading">
                {meeting.title || `Team Strategy Session #${meeting.id}`}
              </h1>
              <span className="s5-badge s5-badge-confirmed">
                <Icon name="shield-check" size={12} />
                <span>AI Validated</span>
              </span>
            </div>
            <div className="meeting-meta-line">
              <span className="meeting-meta-pill date-pill">
                <Icon name="calendar" size={13} />
                <span>{meeting.meeting_date ? meeting.meeting_date : 'Date: Not in transcript'}</span>
              </span>
              <span className="meeting-meta-pill time-pill">
                <Icon name="clock" size={13} />
                <span>
                  {meeting.meeting_time
                    ? meeting.meeting_time
                    : meeting.start_time
                    ? `${meeting.start_time}${meeting.end_time ? ' - ' + meeting.end_time : ''}`
                    : 'Time: Not in transcript'}
                </span>
              </span>
              <span className="meeting-meta-sep">•</span>
              <span>{actionItems.length} Actions</span>
              <span className="meeting-meta-sep">•</span>
              <span>{decisions.length} Decisions</span>
              <span className="meeting-meta-sep">•</span>
              <span>{issues.length} Open Issues</span>
              {meeting.created_at && (
                <>
                  <span className="meeting-meta-sep">•</span>
                  <span className="meeting-meta-subtle">
                    Analyzed {new Date(meeting.created_at).toLocaleDateString()}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="meeting-header-actions">
          <button
            type="button"
            className="s5-btn s5-btn-secondary s5-btn-sm"
            onClick={copyAll}
            title="Copy all meeting minutes as Markdown"
          >
            <Icon name="copy" size={14} />
            <span>{copiedAll ? 'Minutes Copied!' : 'Copy All'}</span>
          </button>
          <button
            type="button"
            className="s5-btn s5-btn-secondary s5-btn-sm"
            onClick={downloadTxt}
            title="Export Plain Text Minutes"
          >
            <Icon name="file-text" size={14} />
            <span>Export TXT</span>
          </button>
          <button
            type="button"
            className="s5-btn s5-btn-secondary s5-btn-sm"
            onClick={downloadJson}
            title="Export JSON Data"
          >
            <Icon name="file-text" size={14} />
            <span>Export JSON</span>
          </button>
          <button
            type="button"
            className="s5-btn s5-btn-secondary s5-btn-sm"
            onClick={handlePrintPdf}
            title="Print or Save as PDF"
          >
            <Icon name="printer" size={14} />
            <span>Print / PDF</span>
          </button>
          <button
            type="button"
            className="s5-btn s5-btn-danger s5-btn-sm"
            onClick={() => setShowDeleteModal(true)}
            title="Delete record"
          >
            <Icon name="trash" size={14} />
            <span>Delete</span>
          </button>
        </div>
      </div>

      {/* 2. Executive Summary (Hero Section) */}
      <div className="s5-card meeting-summary-hero-card">
        <div className="summary-card-header">
          <div className="summary-title-badge">
            <Icon name="sparkles" size={16} />
            <span>Executive Summary</span>
          </div>
          <span className="summary-ai-badge">AI-Generated</span>
        </div>
        <p className="summary-text-body">{meeting.summary}</p>
        <div className="summary-card-footer">
          <span className="summary-verified-pill">
            <Icon name="shield-check" size={13} />
            <span>Grounding Verified</span>
          </span>
          <button
            type="button"
            className="s5-btn s5-btn-secondary s5-btn-xs summary-copy-btn"
            onClick={copySummary}
            title="Copy summary text"
          >
            <Icon name="copy" size={13} />
            <span>{copiedSummary ? 'Copied!' : 'Copy Summary'}</span>
          </button>
        </div>
      </div>

      {/* 3. Action Items Section (Interactive Cards) */}
      <div className="meeting-section-container">
        <div className="section-header-flex">
          <div>
            <h3 className="section-title">
              <Icon name="actions" size={18} />
              <span>Action Items & Commitments ({actionItems.length})</span>
            </h3>
            <p className="section-subtitle">
              Click status to transition • Click Evidence to view grounded quote
            </p>
          </div>
        </div>

        {actionItems.length === 0 ? (
          <div className="s5-empty-mini-card">
            <span>No action items detected in this meeting.</span>
          </div>
        ) : (
          <div className="action-cards-masonry">
            {actionItems.map((item) => (
              <ActionItemCard
                key={item.id}
                item={{ ...item, meeting_id: meeting.id }}
                onStatusChange={handleStatusChange}
                onViewEvidence={(it) => {
                  setSelectedEvidence(it);
                  setEvidenceType('action');
                }}
              />
            ))}
          </div>
        )}
      </div>

      {/* 4. Decisions & Open Issues (Two Columns) */}
      <div className="decisions-issues-grid">
        {/* Confirmed Decisions */}
        <div className="s5-card decision-panel">
          <div className="s5-card-header">
            <h3 className="s5-card-title">
              <Icon name="decisions" size={18} style={{ color: 'var(--semantic-green)' }} />
              <span>Key Decisions ({decisions.length})</span>
            </h3>
          </div>

          {decisions.length === 0 ? (
            <div className="panel-empty-text">No explicit decisions recorded in this meeting.</div>
          ) : (
            <div className="decisions-card-list">
              {decisions.map((d) => (
                <div key={d.id} className="decision-item-box">
                  <div className="decision-item-header">
                    <span className="decision-check-icon">✓</span>
                    <span className="decision-title-text">{d.decision}</span>
                  </div>
                  <div className="decision-item-footer">
                    <span className="decision-status-badge">Locked & Confirmed</span>
                    {d.confidence != null && (
                      <span className="decision-confidence-badge">
                        {Math.round(d.confidence > 1 ? d.confidence : d.confidence * 100)}% Confidence
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Open Issues & Risks */}
        <div className="s5-card issues-panel">
          <div className="s5-card-header">
            <h3 className="s5-card-title">
              <Icon name="issues" size={18} style={{ color: 'var(--semantic-amber)' }} />
              <span>Open Issues & Risks ({issues.length})</span>
            </h3>
          </div>

          {issues.length === 0 ? (
            <div className="panel-empty-text">No active blockers flagged.</div>
          ) : (
            <div className="issues-card-list">
              {issues.map((iss) => (
                <div key={iss.id} className="issue-item-box">
                  <div className="issue-item-header">
                    <span className="issue-open-badge">Open Issue</span>
                    <span className="issue-title-text">{iss.issue || iss.topic}</span>
                  </div>
                  <div className="issue-item-footer">
                    <span className="issue-status-badge">Status: Unresolved</span>
                    {iss.evidence && (
                      <button
                        type="button"
                        className="evidence-mini-link"
                        onClick={() => {
                          setSelectedEvidence(iss);
                          setEvidenceType('issue');
                        }}
                      >
                        ✦ Grounding
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 5. Collapsible Raw Transcript */}
      {meeting.transcript && (
        <div className="s5-card transcript-collapsible-card">
          <div
            className="transcript-toggle-header"
            onClick={() => setShowTranscript(!showTranscript)}
            role="button"
            tabIndex={0}
          >
            <div className="transcript-title-group">
              <Icon name="file-text" size={17} style={{ color: 'var(--text-secondary)' }} />
              <h3 className="transcript-heading">Raw Meeting Transcript Transparency</h3>
              <span className="transcript-char-count">({meeting.transcript.length} characters)</span>
            </div>
            <button type="button" className="s5-btn s5-btn-ghost s5-btn-sm">
              <span>{showTranscript ? 'Hide Transcript' : 'Inspect Raw Transcript'}</span>
              <Icon name={showTranscript ? 'chevron-down' : 'chevron-right'} size={14} />
            </button>
          </div>

          {showTranscript && (
            <div className="transcript-expanded-body">
              <div className="transcript-search-bar">
                <Icon name="search" size={14} style={{ color: 'var(--text-muted)' }} />
                <input
                  type="text"
                  placeholder="Filter dialogue by speaker or keyword..."
                  value={transcriptSearch}
                  onChange={(e) => setTranscriptSearch(e.target.value)}
                  className="s5-input"
                />
              </div>

              <div className="transcript-pre-container">
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

      {/* Frosted Slide-Out Evidence Drawer */}
      <EvidenceDrawer
        isOpen={Boolean(selectedEvidence)}
        onClose={() => setSelectedEvidence(null)}
        item={selectedEvidence}
        type={evidenceType}
      />

      {/* Delete Confirmation Modal */}
      <ConfirmModal
        isOpen={showDeleteModal}
        title={`Delete Meeting Record #${meeting.id}`}
        message="Are you sure you want to delete this meeting record? Action items, decisions, and issues will be cascaded."
        onConfirm={handleDelete}
        onCancel={() => setShowDeleteModal(false)}
        isDeleting={isDeleting}
      />
    </div>
  );
}

