import React, { useState } from 'react';
import { Icon } from './icons/Icons';

/**
 * TitleSelectionPanel
 * Shows before analysis when meeting metadata (title, date, time) needs to be confirmed or chosen.
 * Distinguishes extracted (from transcript), suggestions, and custom entries.
 */
export default function TitleSelectionPanel({
  suggestions = [],
  detectedDate = '',
  detectedTime = '',
  onConfirm,
  onSkip,
}) {
  const [selected, setSelected] = useState(suggestions[0]?.text || '');
  const [customTitle, setCustomTitle] = useState('');
  const [meetingDate, setMeetingDate] = useState(detectedDate || '');
  const [meetingTime, setMeetingTime] = useState(detectedTime || '');
  const [mode, setMode] = useState(suggestions.length > 0 ? 'select' : 'custom');

  const finalTitle = mode === 'custom' ? customTitle.trim() : selected;
  const canConfirm = finalTitle.length > 0;

  const handleConfirm = () => {
    if (canConfirm) {
      onConfirm({
        title: finalTitle,
        date: meetingDate.trim() || null,
        time: meetingTime.trim() || null,
      });
    }
  };

  const typeLabel = {
    extracted: { label: 'Extracted from transcript', color: 'var(--semantic-green)', bg: 'var(--semantic-green-bg)', border: 'var(--semantic-green-border)' },
    suggested: { label: 'AI Keyword Suggestion', color: 'var(--accent-primary)', bg: 'var(--accent-subtle)', border: 'rgba(99,102,241,0.3)' },
  };

  return (
    <div className="title-panel-overlay">
      <div className="title-panel-card">
        {/* Header */}
        <div className="title-panel-header">
          <div className="title-panel-icon">
            <Icon name="file-text" size={20} />
          </div>
          <div>
            <h2 className="title-panel-heading">Confirm Meeting Details</h2>
            <p className="title-panel-sub">
              {suggestions.some((s) => s.type === 'extracted')
                ? 'Review and confirm extracted meeting title, date, and session time.'
                : 'No explicit title was identified. Choose an AI suggestion or enter custom details.'}
            </p>
          </div>
        </div>

        {/* Suggestion list */}
        {suggestions.length > 0 && (
          <div className="title-panel-section">
            <div className="title-panel-section-label">Meeting Title Options</div>
            <div className="title-options-list">
              {suggestions.map((sug, i) => {
                const style = typeLabel[sug.type] || typeLabel.suggested;
                const isChosen = mode === 'select' && selected === sug.text;
                return (
                  <button
                    key={i}
                    type="button"
                    className={'title-option-btn' + (isChosen ? ' chosen' : '')}
                    onClick={() => {
                      setMode('select');
                      setSelected(sug.text);
                    }}
                  >
                    <span className="title-option-radio">{isChosen ? '●' : '○'}</span>
                    <span className="title-option-content">
                      <span className="title-option-text">{sug.text}</span>
                      <span
                        className="title-option-type-badge"
                        style={{ color: style.color, background: style.bg, border: '1px solid ' + style.border }}
                      >
                        {sug.type === 'extracted' ? '✦ ' : '✧ '}{style.label}
                      </span>
                    </span>
                  </button>
                );
              })}

              <button
                type="button"
                className={'title-option-btn' + (mode === 'custom' ? ' chosen' : '')}
                onClick={() => setMode('custom')}
              >
                <span className="title-option-radio">{mode === 'custom' ? '●' : '○'}</span>
                <span className="title-option-content">
                  <span className="title-option-text" style={{ color: 'var(--text-secondary)' }}>
                    Enter a custom title
                  </span>
                  <span
                    className="title-option-type-badge"
                    style={{ color: 'var(--text-muted)', background: 'var(--surface-elevated)', border: '1px solid var(--border-subtle)' }}
                  >
                    Custom
                  </span>
                </span>
              </button>
            </div>
          </div>
        )}

        {(mode === 'custom' || suggestions.length === 0) && (
          <div className="title-panel-section">
            <div className="title-panel-section-label">
              {suggestions.length === 0 ? 'Enter a meeting title' : 'Custom Title'}
            </div>
            {suggestions.length === 0 && (
              <div className="title-panel-no-title-notice">
                <Icon name="issues" size={14} style={{ color: 'var(--semantic-amber)' }} />
                <span>We could not identify an explicit title from this transcript. Please enter a title manually.</span>
              </div>
            )}
            <input
              type="text"
              className="s5-input"
              placeholder="e.g. Cultural Committee - Annual Fest Planning"
              value={customTitle}
              onChange={(e) => setCustomTitle(e.target.value)}
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter' && canConfirm) handleConfirm();
              }}
            />
          </div>
        )}

        {/* Date & Time Confirmation Row */}
        <div className="title-panel-section">
          <div className="title-panel-section-label">Meeting Date & Time (Optional)</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
            <div>
              <label style={{ fontSize: '0.76rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                📅 Meeting Date
              </label>
              <input
                type="text"
                className="s5-input"
                placeholder="e.g. 18 September 2026"
                value={meetingDate}
                onChange={(e) => setMeetingDate(e.target.value)}
              />
            </div>
            <div>
              <label style={{ fontSize: '0.76rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                ⏰ Meeting Time / Range
              </label>
              <input
                type="text"
                className="s5-input"
                placeholder="e.g. 10:00 AM - 11:30 AM"
                value={meetingTime}
                onChange={(e) => setMeetingTime(e.target.value)}
              />
            </div>
          </div>
        </div>

        <div className="title-panel-actions">
          <button type="button" className="s5-btn s5-btn-ghost" onClick={onSkip}>
            Skip (analyze with defaults)
          </button>
          <button
            type="button"
            className="s5-btn s5-btn-primary"
            onClick={handleConfirm}
            disabled={!canConfirm}
          >
            <Icon name="sparkles" size={15} />
            <span>Confirm and Analyze</span>
          </button>
        </div>
      </div>
    </div>
  );
}

