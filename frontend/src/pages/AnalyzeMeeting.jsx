import React, { useState, useRef } from 'react';
import api from '../services/api';
import { Icon } from '../components/icons/Icons';
import PipelineProgress from '../components/pipeline/PipelineProgress';

const SAMPLE_TRANSCRIPTS = {
  annual_fest: {
    title: 'Annual Fest Coordination',
    text: `[Meeting: Annual Fest Planning | Attendees: Priya, Meera, Vikram, Aditya]
Priya: Alright, let's get started, today we're talking about annual fest planning.
Aditya: Someone needs to book the auditorium, it can't wait too long.
Vikram: True, we will confirm the booking by Thursday.
Priya: Actually, sorry, I meant before the weekend, not what I said earlier.
Vikram: Meera, can you look into it - we need to set up the registration desk?
Meera: I'll set up the registration desk sometime next week.
Aditya: What should we do about the event date?
Priya: Let's stick with the event date we discussed earlier.
Aditya: Okay, let's finalize the event date then — that's settled.
Vikram: Any update on the guest's travel plans?
Priya: The guest's travel plans are still not confirmed. We're waiting to hear back.
Meera: The budget approval is still not confirmed from finance.
Vikram: Aditya, would you be able to coordinate with campus security?
Aditya: Aditya will coordinate with campus security by Friday.
Meera: Just circling back — about booking the auditorium, are we still on track?
Priya: Yeah, on it, will update the group soon.
Vikram: I think that covers it for today. Meeting adjourned.`,
  },
  tech_hackathon: {
    title: 'Technical Hackathon Sprint',
    text: `[Meeting: Technical Hackathon Sprint | Attendees: Rahul, Sneha, Ankit, Divya]
Rahul: Welcome team. We have 3 weeks until the 24-hour campus hackathon.
Sneha: The problem statements from sponsoring companies have arrived.
Ankit: I will review and upload the problem statements to GitHub by Monday.
Divya: We need high-speed Wi-Fi access tokens for 150 participants from IT department.
Rahul: Divya, can you submit the official IT requisition by tomorrow 5 PM?
Divya: Yes, I will submit the network access request tomorrow.
Sneha: What about the catering arrangements for midnight snacks?
Rahul: That is still pending administrative quote approval.
Ankit: Decision: let's use Discord as the primary mentor communication channel.
Sneha: Agreed, Discord is officially chosen.
Rahul: Excellent. Let's sync again this Thursday.`,
  },
  design_review: {
    title: 'Design Syndicate Poster Review',
    text: `[Meeting: Design Syndicate Review | Attendees: Maya, Karan, Rohan]
Maya: Today we are approving the social media posters for orientation week.
Karan: The main banner layout is finished, but we need high-res club logos.
Maya: Karan, please export the SVG vector assets by Wednesday evening.
Karan: Done, I will export the vectors Wednesday.
Rohan: What about the print shop quotation for vinyl stickers?
Maya: The sticker pricing is still unconfirmed, waiting for vendor response.
Rohan: Decision: we will proceed with the dark indigo color theme for all materials.
Maya: Perfect, theme settled. Great session everyone.`,
  },
};

export default function AnalyzeMeeting({ onMeetingCreated, onCancel }) {
  const [transcript, setTranscript] = useState('');
  const [meetingTitle, setMeetingTitle] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef(null);

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!transcript.trim()) {
      setError('Please provide a meeting transcript before analyzing.');
      return;
    }

    setIsProcessing(true);
    setError(null);

    try {
      const payload = meetingTitle.trim()
        ? `[Meeting: ${meetingTitle.trim()}]\n${transcript.trim()}`
        : transcript.trim();

      const response = await api.createMeeting(payload);

      if (response && response.meeting_id) {
        onMeetingCreated(response.meeting_id, response);
      } else {
        throw new Error('Unexpected server response format.');
      }
    } catch (err) {
      console.error('Analysis error:', err);
      setError(
        err.message || 'We could not analyze this meeting. Ensure the backend server and Ollama are active.'
      );
      setIsProcessing(false);
    }
  };

  const handleFileDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    const files = e.dataTransfer.files;
    if (files && files[0]) {
      readFile(files[0]);
    }
  };

  const handleFileSelect = (e) => {
    const files = e.target.files;
    if (files && files[0]) {
      readFile(files[0]);
    }
  };

  const readFile = (file) => {
    const reader = new FileReader();
    reader.onload = (event) => {
      setTranscript(event.target.result || '');
      if (!meetingTitle) {
        const cleanName = file.name.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ');
        setMeetingTitle(cleanName);
      }
      setError(null);
    };
    reader.readAsText(file);
  };

  const loadSample = (key) => {
    const sample = SAMPLE_TRANSCRIPTS[key];
    if (sample) {
      setMeetingTitle(sample.title);
      setTranscript(sample.text);
      setError(null);
    }
  };

  return (
    <div style={{ maxWidth: '820px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>
          Analyze a Meeting
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '2px' }}>
          Add your meeting conversation to extract summaries, commitments, decisions, and blockers.
        </p>
      </div>

      {/* Error state with user-friendly recovery */}
      {error && (
        <div style={{
          background: 'var(--semantic-red-bg)',
          border: '1px solid var(--semantic-red-border)',
          borderRadius: 'var(--radius-md)',
          padding: '14px 18px',
          marginBottom: 'var(--space-6)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 'var(--space-3)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Icon name="issues" size={18} style={{ color: 'var(--semantic-red)' }} />
            <div>
              <div style={{ fontWeight: 600, color: '#FCA5A5', fontSize: '0.88rem' }}>
                Analysis could not be completed
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                {error}
              </div>
            </div>
          </div>
          <button className="s5-btn s5-btn-secondary s5-btn-sm" onClick={() => setError(null)}>
            Dismiss
          </button>
        </div>
      )}

      {/* Main Analysis Form or Processing Experience */}
      {isProcessing ? (
        <PipelineProgress isProcessing={isProcessing} />
      ) : (
        <div className="s5-card">
          <form onSubmit={handleSubmit}>
            {/* Quick Sample Selector */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '10px 14px',
              background: 'var(--surface-elevated)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
              marginBottom: 'var(--space-6)',
              flexWrap: 'wrap',
              gap: '8px'
            }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Icon name="sparkles" size={14} style={{ color: 'var(--accent-primary)' }} />
                <span>Not sure what to upload? Try an example:</span>
              </span>
              <div style={{ display: 'flex', gap: '6px' }}>
                <button
                  type="button"
                  className="s5-btn s5-btn-secondary s5-btn-sm"
                  onClick={() => loadSample('annual_fest')}
                >
                  Annual Fest (SC001)
                </button>
                <button
                  type="button"
                  className="s5-btn s5-btn-secondary s5-btn-sm"
                  onClick={() => loadSample('tech_hackathon')}
                >
                  Hackathon
                </button>
                <button
                  type="button"
                  className="s5-btn s5-btn-secondary s5-btn-sm"
                  onClick={() => loadSample('design_review')}
                >
                  Design Review
                </button>
              </div>
            </div>

            {/* Title / Context input */}
            <div style={{ marginBottom: 'var(--space-5)' }}>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '6px' }}>
                Meeting Title or Context <span style={{ color: 'var(--text-dim)', fontWeight: 400 }}>(Optional)</span>
              </label>
              <input
                type="text"
                className="s5-input"
                placeholder="e.g. Cultural Committee — Annual Fest Planning"
                value={meetingTitle}
                onChange={(e) => setMeetingTitle(e.target.value)}
              />
            </div>

            {/* Drag & Drop File Zone */}
            <div style={{ marginBottom: 'var(--space-5)' }}>
              <input
                type="file"
                ref={fileInputRef}
                style={{ display: 'none' }}
                accept=".txt,.csv"
                onChange={handleFileSelect}
              />
              <div
                className={`s5-dropzone ${isDragOver ? 'drag-active' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
                onDragLeave={() => setIsDragOver(false)}
                onDrop={handleFileDrop}
                onClick={() => fileInputRef.current && fileInputRef.current.click()}
              >
                <div style={{
                  width: '40px',
                  height: '40px',
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--surface-elevated)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--accent-primary)'
                }}>
                  <Icon name="upload-cloud" size={20} />
                </div>
                <div>
                  <div style={{ fontSize: '0.92rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                    Drop transcript file here, or click to browse
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                    Supported text formats: .txt, .csv, raw conversation notes
                  </div>
                </div>
              </div>
            </div>

            {/* Raw Transcript Area */}
            <div style={{ marginBottom: 'var(--space-6)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                <label style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                  Meeting Conversation Dialogue <span style={{ color: 'var(--semantic-red)' }}>*</span>
                </label>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  {transcript.length} characters
                </span>
              </div>
              <textarea
                className="s5-textarea"
                placeholder="Or paste conversation dialogue directly here...&#10;&#10;Priya: Let's confirm the venue by Friday.&#10;Vikram: I will handle the venue booking.&#10;Aditya: What about the guest travel plans?"
                value={transcript}
                onChange={(e) => setTranscript(e.target.value)}
                required
              />
            </div>

            {/* Form Actions */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: 'var(--space-2)' }}>
              <button
                type="button"
                className="s5-btn s5-btn-ghost"
                onClick={onCancel}
              >
                Cancel
              </button>

              <button
                type="submit"
                id="btn-submit-analyze"
                className="s5-btn s5-btn-primary s5-btn-lg"
                disabled={!transcript.trim()}
              >
                <Icon name="sparkles" size={16} />
                <span>Analyze Meeting</span>
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
