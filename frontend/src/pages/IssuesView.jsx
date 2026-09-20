import React, { useState } from 'react';
import { Icon } from '../components/icons/Icons';
import EvidenceDrawer from '../components/drawer/EvidenceDrawer';

export default function IssuesView({ issues = [], onSelectMeeting }) {
  const [search, setSearch] = useState('');
  const [selectedSeverity, setSelectedSeverity] = useState('all');
  const [resolvedIds, setResolvedIds] = useState(new Set());
  const [selectedEvidence, setSelectedEvidence] = useState(null);

  // Assign deterministic severity based on keywords if not provided
  const getSeverity = (text) => {
    const lower = (text || '').toLowerCase();
    if (lower.includes('security') || lower.includes('budget') || lower.includes('gateway') || lower.includes('cancel') || lower.includes('emergency') || lower.includes('critical')) {
      return 'critical';
    }
    if (lower.includes('approval') || lower.includes('speaker') || lower.includes('auditorium') || lower.includes('venue') || lower.includes('permit') || lower.includes('booking')) {
      return 'high';
    }
    if (lower.includes('quote') || lower.includes('pricing') || lower.includes('catering') || lower.includes('wifi') || lower.includes('vendor')) {
      return 'medium';
    }
    return 'low';
  };

  const handleToggleResolve = (id) => {
    setResolvedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const filtered = issues.filter((i) => {
    const severity = getSeverity(i.issue);
    if (selectedSeverity !== 'all' && severity !== selectedSeverity) return false;

    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (i.issue && i.issue.toLowerCase().includes(q)) || String(i.meeting_id).includes(q);
  });

  const criticalCount = issues.filter((i) => getSeverity(i.issue) === 'critical').length;
  const highCount = issues.filter((i) => getSeverity(i.issue) === 'high').length;
  const mediumCount = issues.filter((i) => getSeverity(i.issue) === 'medium').length;

  return (
    <div className="issues-view-page">
      {/* 1. Header */}
      <div className="issues-header-flex">
        <div>
          <h1 className="issues-main-title">Open Issues & Risk Register</h1>
          <p className="issues-subtitle">
            Active organizational blockers, missing approvals, and risk dependencies ({issues.length} active blockers)
          </p>
        </div>

        <div className="issues-search-box">
          <Icon name="search" size={15} style={{ color: 'var(--text-muted)' }} />
          <input
            type="text"
            className="s5-input"
            placeholder="Search open blockers..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* 2. Severity Filter Tabs */}
      <div className="s5-card issues-toolbar-card">
        <div className="issues-tabs-list">
          {[
            { id: 'all', label: `All (${issues.length})` },
            { id: 'critical', label: `🔴 Critical (${criticalCount})` },
            { id: 'high', label: `🟠 High (${highCount})` },
            { id: 'medium', label: `🟡 Medium (${mediumCount})` },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`s5-btn s5-btn-sm ${selectedSeverity === tab.id ? 's5-btn-primary' : 's5-btn-secondary'}`}
              onClick={() => setSelectedSeverity(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* 3. List */}
      {filtered.length === 0 ? (
        <div className="s5-empty-state">
          <div className="s5-empty-icon" style={{ color: 'var(--semantic-green)' }}>
            <Icon name="check-circle" size={24} />
          </div>
          <div className="s5-empty-title">
            {search ? 'No matching blockers' : 'Zero Open Blockers'}
          </div>
          <p className="s5-empty-desc">
            {search
              ? `No unresolved blocker matches "${search}".`
              : 'All discussed risks have either been resolved or ratified into decisions.'}
          </p>
        </div>
      ) : (
        <div className="issues-stack">
          {filtered.map((item) => {
            const severity = getSeverity(item.issue);
            const isResolved = resolvedIds.has(item.id);

            return (
              <div
                key={item.id}
                className={`s5-card issue-risk-card severity-card-${severity} ${isResolved ? 'issue-resolved' : ''}`}
              >
                <div className="issue-card-main">
                  <div className="issue-card-top-row">
                    <span className={`issue-severity-pill severity-${severity}`}>
                      {severity.toUpperCase()} RISK
                    </span>
                    <span className="issue-meeting-tag">
                      Raised in{' '}
                      <button
                        type="button"
                        className="issue-meeting-link"
                        onClick={() => onSelectMeeting(item.meeting_id)}
                      >
                        Meeting #{item.meeting_id} →
                      </button>
                    </span>
                  </div>

                  <h3 className="issue-title-heading">{item.issue}</h3>
                </div>

                <div className="issue-card-actions-row">
                  <button
                    type="button"
                    className="issue-evidence-btn"
                    onClick={() => setSelectedEvidence(item)}
                  >
                    ✦ Grounding Quote
                  </button>

                  <button
                    type="button"
                    className={`issue-resolve-btn ${isResolved ? 'resolved' : ''}`}
                    onClick={() => handleToggleResolve(item.id)}
                  >
                    {isResolved ? '✓ Resolved' : 'Mark as Resolved'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Grounding Inspector Drawer */}
      <EvidenceDrawer
        isOpen={Boolean(selectedEvidence)}
        onClose={() => setSelectedEvidence(null)}
        item={selectedEvidence}
        type="issue"
      />
    </div>
  );
}
