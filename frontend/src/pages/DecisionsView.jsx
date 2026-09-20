import React, { useState } from 'react';
import { Icon } from '../components/icons/Icons';
import EvidenceDrawer from '../components/drawer/EvidenceDrawer';

export default function DecisionsView({ decisions = [], onSelectMeeting }) {
  const [search, setSearch] = useState('');
  const [selectedEvidence, setSelectedEvidence] = useState(null);

  const filtered = decisions.filter((d) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (d.decision && d.decision.toLowerCase().includes(q)) || String(d.meeting_id).includes(q);
  });

  return (
    <div className="decisions-view-page">
      {/* 1. Header */}
      <div className="decisions-header-flex">
        <div>
          <h1 className="decisions-main-title">Decisions Knowledge Bank</h1>
          <p className="decisions-subtitle">
            Permanent institutional memory of ratified policies, dates, and agreements ({decisions.length} recorded)
          </p>
        </div>

        <div className="decisions-search-box">
          <Icon name="search" size={15} style={{ color: 'var(--text-muted)' }} />
          <input
            type="text"
            className="s5-input"
            placeholder="Search decisions or meeting ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* 2. List */}
      {filtered.length === 0 ? (
        <div className="s5-empty-state">
          <div className="s5-empty-icon" style={{ color: 'var(--semantic-green)' }}>
            <Icon name="decisions" size={24} />
          </div>
          <div className="s5-empty-title">
            {search ? 'No matching decisions' : 'No decisions recorded yet'}
          </div>
          <p className="s5-empty-desc">
            {search
              ? `No confirmed decision matches "${search}".`
              : 'As your team analyzes meetings, ratified decisions and agreements will be organized here.'}
          </p>
        </div>
      ) : (
        <div className="decisions-stack">
          {filtered.map((d) => (
            <div key={d.id} className="s5-card decision-knowledge-card">
              <div className="decision-card-main">
                <div className="decision-icon-bubble">
                  <Icon name="check" size={15} />
                </div>
                <div className="decision-content">
                  <h3 className="decision-heading-text">{d.decision}</h3>
                  <div className="decision-meta-row">
                    <span>Source:</span>
                    <button
                      type="button"
                      className="decision-source-link"
                      onClick={() => onSelectMeeting(d.meeting_id)}
                    >
                      Meeting #{d.meeting_id} →
                    </button>
                    <span className="decision-dot-sep">•</span>
                    <span className="decision-status-pill">Ratified & Confirmed</span>
                  </div>
                </div>
              </div>

              <div className="decision-card-actions">
                <button
                  type="button"
                  className="decision-evidence-btn"
                  onClick={() => setSelectedEvidence(d)}
                >
                  ✦ View Grounding
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Grounding Inspector Drawer */}
      <EvidenceDrawer
        isOpen={Boolean(selectedEvidence)}
        onClose={() => setSelectedEvidence(null)}
        item={selectedEvidence}
        type="decision"
      />
    </div>
  );
}
