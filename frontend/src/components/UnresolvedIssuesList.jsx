import React from 'react';

export default function UnresolvedIssuesList({ issues = [] }) {
  if (!issues || issues.length === 0) {
    return (
      <div style={{ padding: '1rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
        No unresolved issues or blockers pending.
      </div>
    );
  }

  return (
    <div className="item-card-list">
      {issues.map((iss, idx) => {
        const text = typeof iss === 'string' ? iss : iss.issue;
        return (
          <div key={iss.id || idx} className="item-card issue">
            <span className="item-card-icon">⚠️</span>
            <div className="item-card-text">
              <strong>Unresolved Blocker:</strong> {text}
            </div>
          </div>
        );
      })}
    </div>
  );
}
