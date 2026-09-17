import React, { useState } from 'react';
import api from '../services/api';
import ErrorAlert from '../components/ErrorAlert';

const SAMPLE_SC001_TRANSCRIPT = `[Meeting: Annual Fest Planning | Attendees: Priya, Meera, Vikram, Aditya]
Priya: Alright, let's get started, today we're talking about annual fest planning.
Aditya: So yeah, Someone needs to book the auditorium, it can't wait too long.
Vikram: Yeah, true, we'll figure out who.
Priya: Actually, sorry, I meant before the weekend, not what I said earlier.
Vikram: Alright, Meera, can you look into it - we need to set up the registration desk?
Meera: I'll set up the registration desk sometime next week.
Aditya: Umm, what should we do about the event date?
Priya: Maybe we should go with event date we discussed earlier.
Meera: I think we should reconsider it, actually.
Aditya: Okay, let's finalize the event date then - that's settled.
Vikram: Cool, so any update on the guest's travel plans?
Priya: The guest's travel plans is still not confirmed. We're waiting to hear back.
Priya: Okay so any update on the budget approval?
Meera: The budget approval is still not confirmed. We're waiting to hear back.
Vikram: Alright, Aditya, would you be able to coordinate with campus security?
Aditya: Aditya will coordinate with campus security.
Aditya: Wait, let me correct that - it's actually by Friday.
Meera: Just circling back - about book the auditorium, are we still on track?
Priya: Yeah, on it, will update the group soon.
Aditya: Alright, switching gears for a second - anything else before we wrap up?
Vikram: Nah, I think that covers it for today.
Priya: Cool, thanks everyone, meeting adjourned.`;

export default function NewMeeting({ onMeetingCreated, onCancel }) {
  const [transcript, setTranscript] = useState('');
  const [meetingTitle, setMeetingTitle] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!transcript.trim()) {
      setError('Please paste or enter a meeting transcript before submitting.');
      return;
    }

    setIsProcessing(true);
    setError(null);

    try {
      // Include title header in transcript if provided by user
      const fullTranscript = meetingTitle.trim()
        ? `[Meeting: ${meetingTitle.trim()}]\n${transcript.trim()}`
        : transcript.trim();

      const response = await api.createMeeting(fullTranscript);

      if (response && response.meeting_id) {
        onMeetingCreated(response.meeting_id, response);
      } else {
        throw new Error('Unexpected response format from server.');
      }
    } catch (err) {
      console.error('Meeting processing error:', err);
      setError(
        err.message || 'Failed to process meeting transcript. Ensure Ollama and FastAPI are running.'
      );
    } finally {
      setIsProcessing(false);
    }
  };

  const handleLoadSample = () => {
    setMeetingTitle('Annual Fest Planning (SC001)');
    setTranscript(SAMPLE_SC001_TRANSCRIPT);
    setError(null);
  };

  return (
    <div style={{ maxWidth: '850px', margin: '0 auto' }}>
      <div className="flex-between mb-4">
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700 }}>Process New Meeting</h2>
          <p className="text-muted" style={{ fontSize: '0.9rem' }}>
            Submit a club transcript for automated preprocessing, Qwen2.5:3b extraction, and SQLite storage
          </p>
        </div>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={handleLoadSample}
          disabled={isProcessing}
        >
          🪄 Load Sample Transcript (SC001)
        </button>
      </div>

      <ErrorAlert message={error} onDismiss={() => setError(null)} />

      <div className="card">
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="meeting-title">
              Meeting Title / Club Context <span className="text-dim">(Optional)</span>
            </label>
            <input
              id="meeting-title"
              type="text"
              className="form-input"
              placeholder="e.g. Robotics Club — Weekly Sprint Planning"
              value={meetingTitle}
              onChange={(e) => setMeetingTitle(e.target.value)}
              disabled={isProcessing}
            />
          </div>

          <div className="form-group">
            <div className="flex-between" style={{ marginBottom: '0.5rem' }}>
              <label className="form-label" htmlFor="transcript-input" style={{ margin: 0 }}>
                Raw Meeting Transcript <span style={{ color: 'var(--danger)' }}>*</span>
              </label>
              <span className="text-muted" style={{ fontSize: '0.8rem' }}>
                {transcript.length} characters
              </span>
            </div>
            <textarea
              id="transcript-input"
              className="form-textarea"
              placeholder="Paste raw meeting dialogue here...&#10;&#10;Example:&#10;Alice: Welcome everyone. Let's finalize the budget by Friday.&#10;Bob: I will coordinate the venue permit..."
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              disabled={isProcessing}
              required
            />
          </div>

          <div className="flex-between mt-4">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onCancel}
              disabled={isProcessing}
            >
              Cancel
            </button>

            <button
              id="btn-process-meeting"
              type="submit"
              className="btn btn-primary"
              disabled={isProcessing || !transcript.trim()}
              style={{ minWidth: '180px' }}
            >
              {isProcessing ? (
                <>
                  <span className="spinner" style={{ width: '16px', height: '16px', borderWidth: '2px' }}></span>
                  <span>Processing with Qwen...</span>
                </>
              ) : (
                <>⚡ Extract Minutes & Actions</>
              )}
            </button>
          </div>
        </form>

        {isProcessing && (
          <div
            style={{
              marginTop: '1.5rem',
              padding: '1.25rem',
              borderRadius: 'var(--radius-md)',
              background: 'rgba(99, 102, 241, 0.08)',
              border: '1px solid rgba(99, 102, 241, 0.2)',
              textAlign: 'center',
            }}
          >
            <p style={{ fontWeight: 600, color: '#818cf8', marginBottom: '0.25rem' }}>
              🤖 Neural Inference in Progress
            </p>
            <p className="text-muted" style={{ fontSize: '0.85rem' }}>
              Preprocessing transcript ➔ Running Qwen2.5:3b via Ollama ➔ Validating extraction schema ➔ Saving to SQLite...
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
