import React, { useEffect, useState } from 'react';

const PROCESSING_STAGES = [
  { id: 1, label: 'Transcript Preprocessing', sub: 'Normalizing speaker dialogue and cleaning timestamps' },
  { id: 2, label: 'Conversation Understanding', sub: 'Evaluating dialogue flow and attendee commitments' },
  { id: 3, label: 'Extracting Action Items', sub: 'Identifying assigned tasks, owners, and stated deadlines' },
  { id: 4, label: 'Identifying Confirmed Decisions', sub: 'Capturing agreed resolutions and votes' },
  { id: 5, label: 'Detecting Unresolved Blockers', sub: 'Flagging open questions and pending administrative approvals' },
  { id: 6, label: 'Pydantic Grounding Validation', sub: 'Verifying extracted owners against dialogue evidence' },
  { id: 7, label: 'Structuring Meeting Record', sub: 'Finalizing database persistence and cascade relationships' },
];

export default function PipelineProgress({ isProcessing }) {
  const [activeStage, setActiveStage] = useState(1);

  // Progressive transition through real conceptual stages during the active API request
  useEffect(() => {
    if (!isProcessing) {
      setActiveStage(1);
      return;
    }

    const stageIntervals = [
      setTimeout(() => setActiveStage(2), 1200),
      setTimeout(() => setActiveStage(3), 3200),
      setTimeout(() => setActiveStage(4), 5800),
      setTimeout(() => setActiveStage(5), 8400),
      setTimeout(() => setActiveStage(6), 11000),
      setTimeout(() => setActiveStage(7), 13500),
    ];

    return () => stageIntervals.forEach(clearTimeout);
  }, [isProcessing]);

  if (!isProcessing) return null;

  return (
    <div className="s5-processing-container" role="status" aria-live="polite">
      <div className="s5-processing-header">
        <div style={{
          width: '48px',
          height: '48px',
          borderRadius: 'var(--radius-lg)',
          background: 'var(--accent-subtle)',
          color: 'var(--accent-primary)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto var(--space-3)'
        }}>
          <span className="s5-spinner" style={{ width: '22px', height: '22px' }} />
        </div>
        <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px' }}>
          Analyzing Meeting Conversation
        </h3>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
          We&apos;re turning your club conversation into structured minutes and action items.
        </p>
      </div>

      <div className="s5-processing-stages">
        {PROCESSING_STAGES.map((stage) => {
          const isDone = activeStage > stage.id;
          const isActive = activeStage === stage.id;
          const isPending = activeStage < stage.id;

          return (
            <div
              key={stage.id}
              className={`s5-stage-item ${isDone ? 'completed' : ''} ${isActive ? 'active' : ''} ${isPending ? 'pending' : ''}`}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
                  width: '22px',
                  height: '22px',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  fontFamily: 'var(--font-mono)',
                  background: isDone
                    ? 'var(--semantic-green-bg)'
                    : isActive
                    ? 'var(--accent-primary)'
                    : 'var(--surface-elevated)',
                  color: isDone ? '#34D399' : isActive ? '#FFFFFF' : 'var(--text-dim)',
                  border: isDone
                    ? '1px solid var(--semantic-green-border)'
                    : isActive
                    ? '1px solid var(--accent-primary)'
                    : '1px solid var(--border-subtle)',
                }}>
                  {isDone ? '✓' : stage.id}
                </div>
                <div>
                  <div style={{
                    fontSize: '0.88rem',
                    fontWeight: isActive ? 600 : 500,
                    color: isDone ? '#34D399' : isActive ? 'var(--text-primary)' : 'var(--text-muted)'
                  }}>
                    {stage.label}
                  </div>
                  {isActive && (
                    <div style={{ fontSize: '0.76rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      {stage.sub}
                    </div>
                  )}
                </div>
              </div>

              <div style={{ fontSize: '0.8rem' }}>
                {isDone && <span style={{ color: '#34D399', fontWeight: 600 }}>✓ Done</span>}
                {isActive && (
                  <span style={{ color: 'var(--accent-primary)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span className="s5-spinner" style={{ width: '12px', height: '12px', borderWidth: '1.5px' }} />
                    Running
                  </span>
                )}
                {isPending && <span style={{ color: 'var(--text-dim)' }}>Queued</span>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
