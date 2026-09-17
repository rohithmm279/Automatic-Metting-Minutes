import React from 'react';

export default function DecisionsList({ decisions = [] }) {
  if (!decisions || decisions.length === 0) {
    return (
      <div style={{ padding: '1rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
        No explicit decisions recorded in this meeting.
      </div>
    );
  }

  return (
    <div className="item-card-list">
      {decisions.map((dec, idx) => {
        const text = typeof dec === 'string' ? dec : dec.decision;
        return (
          <div key={dec.id || idx} className="item-card decision">
            <span className="item-card-icon">✅</span>
            <div className="item-card-text">
              <strong>Decision:</strong> {text}
            </div>
          </div>
        );
      })}
    </div>
  );
}
