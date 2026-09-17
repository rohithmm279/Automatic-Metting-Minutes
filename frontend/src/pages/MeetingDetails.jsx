import React, { useState, useEffect } from 'react';
import api from '../services/api';
import ActionItemTable from '../components/ActionItemTable';
import DecisionsList from '../components/DecisionsList';
import UnresolvedIssuesList from '../components/UnresolvedIssuesList';
import ConfirmModal from '../components/ConfirmModal';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorAlert from '../components/ErrorAlert';

export default function MeetingDetails({ meetingId, onBack, onDeleted }) {
  const [meeting, setMeeting] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showTranscript, setShowTranscript] = useState(false);

  const fetchMeeting = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getMeeting(meetingId);
      setMeeting(data);
    } catch (err) {
      console.error('Failed to load meeting details:', err);
      setError(err.message || `Meeting ${meetingId} could not be retrieved.`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (meetingId) {
      fetchMeeting();
    }
  }, [meetingId]);

  const handleActionItemStatusUpdate = (itemId, newStatus) => {
    setMeeting((prev) => {
      if (!prev) return prev;
      const updatedItems = (prev.action_items || []).map((item) =>
        item.id === itemId ? { ...item, status: newStatus } : item
      );
      return { ...prev, action_items: updatedItems };
    });
  };

  const handleDeleteMeeting = async () => {
    setIsDeleting(true);
    try {
      await api.deleteMeeting(meetingId);
      setShowDeleteModal(false);
      if (onDeleted) {
        onDeleted(meetingId);
      }
    } catch (err) {
      console.error('Delete error:', err);
      setError(err.message || `Failed to delete meeting ${meetingId}.`);
      setShowDeleteModal(false);
    } finally {
      setIsDeleting(false);
    }
  };

  if (loading) {
    return <LoadingSpinner message={`Retrieving meeting #${meetingId} from database...`} />;
  }

  if (error && !meeting) {
    return (
      <div>
        <ErrorAlert message={error} onRetry={fetchMeeting} />
        <button className="btn btn-secondary mt-4" onClick={onBack}>
          ← Back to Meetings
        </button>
      </div>
    );
  }

  if (!meeting) {
    return (
      <div className="state-box">
        <div className="state-title">Meeting Not Found</div>
        <p className="state-desc">The requested meeting does not exist or has been deleted.</p>
        <button className="btn btn-secondary mt-4" onClick={onBack}>
          ← Back to Dashboard
        </button>
      </div>
    );
  }

  return (
    <div>
      {/* Top action bar */}
      <div className="flex-between mb-4">
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <button className="btn btn-secondary btn-sm" onClick={onBack}>
            ← Back
          </button>
          <div>
            <h2 style={{ fontSize: '1.4rem', fontWeight: 700 }}>
              Meeting #{meeting.id}
            </h2>
            <p className="text-muted" style={{ fontSize: '0.825rem' }}>
              Recorded on {meeting.created_at ? new Date(meeting.created_at).toLocaleString() : 'Recently'}
            </p>
          </div>
        </div>

        <button
          id="btn-delete-meeting"
          className="btn btn-danger btn-sm"
          onClick={() => setShowDeleteModal(true)}
        >
          🗑️ Delete Meeting
        </button>
      </div>

      <ErrorAlert message={error} onDismiss={() => setError(null)} />

      {/* 1. Summary Section */}
      <div className="card mb-4">
        <h3 className="card-title">
          <span>📋</span> Executive Summary
        </h3>
        <div className="summary-box">
          {meeting.summary}
        </div>
      </div>

      {/* 2. Action Items Section */}
      <div className="card mb-4">
        <div className="flex-between mb-4">
          <h3 className="card-title" style={{ margin: 0 }}>
            <span>⚡</span> Action Items & Commitments ({meeting.action_items?.length || 0})
          </h3>
          <span className="text-dim" style={{ fontSize: '0.8rem' }}>
            Interactive status tracking with SQLite persistence
          </span>
        </div>

        <ActionItemTable
          meetingId={meeting.id}
          actionItems={meeting.action_items}
          onStatusUpdate={handleActionItemStatusUpdate}
        />
      </div>

      {/* 3. Decisions & 4. Unresolved Issues side-by-side or stacked */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem', marginBottom: '1.5rem' }}>
        {/* Decisions */}
        <div className="card">
          <h3 className="card-title">
            <span>✅</span> Confirmed Decisions ({meeting.decisions?.length || 0})
          </h3>
          <DecisionsList decisions={meeting.decisions} />
        </div>

        {/* Unresolved Issues */}
        <div className="card">
          <h3 className="card-title">
            <span>❓</span> Unresolved Issues & Blockers ({meeting.unresolved_issues?.length || 0})
          </h3>
          <UnresolvedIssuesList issues={meeting.unresolved_issues} />
        </div>
      </div>

      {/* Collapsible Transcript Accordion */}
      {meeting.transcript && (
        <div className="transcript-accordion">
          <div
            className="transcript-header"
            onClick={() => setShowTranscript((prev) => !prev)}
            role="button"
            tabIndex={0}
          >
            <span>📜 Raw Meeting Transcript ({meeting.transcript.length} chars)</span>
            <span>{showTranscript ? '▲ Hide' : '▼ Expand'}</span>
          </div>
          {showTranscript && (
            <div className="transcript-body">
              {meeting.transcript}
            </div>
          )}
        </div>
      )}

      {/* Delete Confirmation Modal */}
      <ConfirmModal
        isOpen={showDeleteModal}
        title={`Delete Meeting #${meeting.id}`}
        message="Are you sure you want to delete this meeting? This will permanently remove the summary, action items, decisions, and issues from the database through foreign-key cascade."
        onConfirm={handleDeleteMeeting}
        onCancel={() => setShowDeleteModal(false)}
        isDeleting={isDeleting}
      />
    </div>
  );
}
