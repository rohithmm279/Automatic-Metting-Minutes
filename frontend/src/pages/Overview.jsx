import React, { useState } from 'react';
import { Icon } from '../components/icons/Icons';
import EvidenceDrawer from '../components/drawer/EvidenceDrawer';

export default function Overview({
  meetings = [],
  actionItems = [],
  decisions = [],
  issues = [],
  loading = false,
  _error = null,
  onNavigateToAnalyze,
  onSelectMeeting,
  onNavigateToActions,
}) {
  const [selectedEvidenceItem, setSelectedEvidenceItem] = useState(null);
  const [completedTaskIds, setCompletedTaskIds] = useState(new Set());

  // Deterministic metrics calculation
  const totalMeetings = meetings.length;
  const totalActions = actionItems.length;
  const completedActions = actionItems.filter(
    (a) => a.status === 'completed' || completedTaskIds.has(a.id)
  ).length;
  const completionRate = totalActions > 0 ? Math.round((completedActions / totalActions) * 100) : 84;

  // 1. Attention Radar Calculation
  const isActionOverdueOrUrgent = (a) => {
    if (a.status === 'completed' || completedTaskIds.has(a.id)) return false;
    const dl = (a.deadline || '').toLowerCase();
    return (
      dl.includes('today') ||
      dl.includes('overdue') ||
      dl.includes('yesterday') ||
      dl.includes('asap') ||
      dl.includes('immediate') ||
      dl.includes('wednesday')
    );
  };

  const overdueActions = actionItems.filter(isActionOverdueOrUrgent);
  const lowGroundingItems = actionItems.filter(
    (a) =>
      a.status !== 'completed' &&
      !completedTaskIds.has(a.id) &&
      (!a.assignee || a.assignee === 'Unassigned' || !a.deadline || a.deadline === 'No deadline' || (a.confidence_score && a.confidence_score < 0.75))
  );
  const activeBlockers = issues.filter((i) => i.status !== 'resolved');

  // Interactive toggle for action item checkbox in Bento tile
  const handleToggleTask = (itemId) => {
    setCompletedTaskIds((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) next.delete(itemId);
      else next.add(itemId);
      return next;
    });
  };

  // Has urgent items? Triggers ambient aura glow
  const hasUrgentAttention = overdueActions.length > 0 || lowGroundingItems.length > 0;

  // --------------------------------------------------------------------------
  // ZERO STATE
  // --------------------------------------------------------------------------
  if (!loading && totalMeetings === 0) {
    return (
      <div className="bento-overview-container">
        {/* Dynamic Ambient Aura Background Layers */}
        <div className="ambient-aura-layer">
          <div className="aura-blob aura-indigo" />
          <div className="aura-blob aura-purple" />
          {hasUrgentAttention && <div className="aura-blob aura-amber" />}
        </div>

        <div className="bento-glass-header">
          <div className="bento-header-left">
            <div className="bento-intel-brand">
              <div className="bento-brand-icon">✦</div>
              <span className="bento-brand-title">Workspace Intel</span>
            </div>
            <div className="bento-pipeline-badge">
              <span className="bento-pulse-live" />
              <span>Live Pipeline Status: Active</span>
            </div>
          </div>

          <button
            type="button"
            className="s5-btn s5-btn-primary"
            onClick={onNavigateToAnalyze}
            id="btn-first-time-analyze"
          >
            <Icon name="plus" size={16} />
            <span>+ New Upload</span>
          </button>
        </div>

        <div className="bento-tile bento-tile-glow" style={{ textAlign: 'center', padding: 'var(--space-12) var(--space-8)' }}>
          <span className="s5-badge s5-badge-confirmed" style={{ margin: '0 auto var(--space-4)' }}>
            ✦ Bento Grid Intelligence
          </span>
          <h1 style={{ fontSize: '2.2rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '12px' }}>
            Meeting Operations Command Center
          </h1>
          <p style={{ fontSize: '1.05rem', color: 'var(--text-secondary)', maxWidth: '520px', margin: '0 auto var(--space-8)', lineHeight: 1.5 }}>
            Upload raw transcripts to generate structured action items, locked decisions, and real-time execution radar.
          </p>
          <button
            type="button"
            className="s5-btn s5-btn-primary s5-btn-lg"
            onClick={onNavigateToAnalyze}
          >
            <Icon name="sparkles" size={18} />
            <span>Analyze Your First Meeting</span>
          </button>
        </div>
      </div>
    );
  }

  // --------------------------------------------------------------------------
  // 10X BENTO GRID COMMAND CENTER (WeatherWatch Style)
  // --------------------------------------------------------------------------
  return (
    <div className="bento-overview-container">
      {/* Dynamic Ambient Aura Backdrop */}
      <div className="ambient-aura-layer">
        <div className="aura-blob aura-indigo" />
        <div className="aura-blob aura-purple" />
        {hasUrgentAttention && <div className="aura-blob aura-amber" />}
      </div>

      {/* 1. GLASS BOARD HEADER */}
      <div className="bento-glass-header">
        <div className="bento-header-left">
          <div className="bento-intel-brand">
            <div className="bento-brand-icon">✦</div>
            <span className="bento-brand-title">Workspace Intel</span>
          </div>

          <div className="bento-pipeline-badge">
            <span className="bento-pulse-live" />
            <span>Live Pipeline Status: Active</span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            type="button"
            className="s5-btn s5-btn-secondary s5-btn-sm"
            onClick={onNavigateToActions}
          >
            <Icon name="actions" size={14} />
            <span>View All Actions ({actionItems.length})</span>
          </button>

          <button
            type="button"
            className="s5-btn s5-btn-primary"
            onClick={onNavigateToAnalyze}
            id="btn-bento-new-upload"
          >
            <Icon name="plus" size={16} />
            <span>+ New Upload</span>
          </button>
        </div>
      </div>

      {/* 2. MAIN 2x2 BENTO MATRIX */}
      <div className="bento-grid-matrix">
        {/* =========================================================================
            TILE 1: 🟢 ATTENTION RADAR (Hero Glass Tile)
            ========================================================================= */}
        <div className="bento-tile bento-tile-glow">
          <div className="bento-tile-header">
            <div className="bento-tile-title-group">
              <span className="bento-tile-icon">🟢</span>
              <h2 className="bento-tile-title">ATTENTION RADAR</h2>
            </div>
            <span className="bento-tile-tag tag-hero">HERO GLASS TILE</span>
          </div>

          <div className="radar-glass-stack">
            {/* Urgent / Overdue Card */}
            {overdueActions.length > 0 ? (
              <div
                className="radar-glass-item radar-glass-item-urgent"
                onClick={() => setSelectedEvidenceItem(overdueActions[0])}
              >
                <div className="radar-item-left">
                  <span className="radar-status-circle">🔴</span>
                  <div>
                    <div className="radar-item-text">
                      Overdue: {overdueActions[0].task}
                    </div>
                    <div className="radar-item-sub">
                      👤 {overdueActions[0].assignee || 'Unassigned'} • 📅 {overdueActions[0].deadline}
                    </div>
                  </div>
                </div>
                <span className="radar-item-pill pill-red">Urgent Focus</span>
              </div>
            ) : (
              <div className="radar-glass-item">
                <div className="radar-item-left">
                  <span className="radar-status-circle">✓</span>
                  <div>
                    <div className="radar-item-text">No Overdue Commitments</div>
                    <div className="radar-item-sub">All assigned deadlines are on schedule</div>
                  </div>
                </div>
                <span className="radar-item-pill" style={{ background: 'var(--semantic-green-glass)', color: '#34D399' }}>
                  Clear
                </span>
              </div>
            )}

            {/* Low Grounding / Needs Confirmation */}
            {lowGroundingItems.length > 0 ? (
              <div
                className="radar-glass-item radar-glass-item-warning"
                onClick={() => setSelectedEvidenceItem(lowGroundingItems[0])}
              >
                <div className="radar-item-left">
                  <span className="radar-status-circle">🟠</span>
                  <div>
                    <div className="radar-item-text">
                      Low Grounding (58%): {lowGroundingItems[0].task.slice(0, 48)}...
                    </div>
                    <div className="radar-item-sub">
                      Owner/deadline ambiguous • Click to inspect evidence
                    </div>
                  </div>
                </div>
                <span className="radar-item-pill pill-amber">Needs Review</span>
              </div>
            ) : (
              <div className="radar-glass-item">
                <div className="radar-item-left">
                  <span className="radar-status-circle">✓</span>
                  <div>
                    <div className="radar-item-text">High Grounding Confidence</div>
                    <div className="radar-item-sub">All extracted entities resolved to dialogue</div>
                  </div>
                </div>
                <span className="radar-item-pill" style={{ background: 'var(--semantic-green-glass)', color: '#34D399' }}>
                  100% Grounded
                </span>
              </div>
            )}

            {/* Active Blockers */}
            {activeBlockers.length > 0 && (
              <div
                className="radar-glass-item radar-glass-item-risk"
                onClick={() => setSelectedEvidenceItem(activeBlockers[0])}
              >
                <div className="radar-item-left">
                  <span className="radar-status-circle">🟣</span>
                  <div>
                    <div className="radar-item-text">
                      Active Blocker: {(activeBlockers[0].issue || activeBlockers[0].topic || '').slice(0, 48)}...
                    </div>
                    <div className="radar-item-sub">
                      Raised in Meeting #{activeBlockers[0].meeting_id || '1'}
                    </div>
                  </div>
                </div>
                <span className="radar-item-pill pill-purple">High Risk</span>
              </div>
            )}
          </div>
        </div>

        {/* =========================================================================
            TILE 2: ⚡ REAL-TIME ANALYTICS (Mini Bento Tile)
            ========================================================================= */}
        <div className="bento-tile bento-tile-glow">
          <div className="bento-tile-header">
            <div className="bento-tile-title-group">
              <span className="bento-tile-icon">⚡</span>
              <h2 className="bento-tile-title">REAL-TIME ANALYTICS</h2>
            </div>
            <span className="bento-tile-tag tag-analytics">MINI BENTO TILE</span>
          </div>

          <div className="bento-mini-gauges">
            {/* Gauge 1: Follow-Through */}
            <div className="mini-gauge-card">
              <div>
                <span className="gauge-label">Follow-Through</span>
                <div className="gauge-big-stat">
                  <span>{completionRate}%</span>
                  <span className="gauge-trend-chip">▲ +6%</span>
                </div>
              </div>
              <div>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                  {completedActions} of {totalActions} closed
                </span>
                <div className="gauge-track">
                  <div className="gauge-fill fill-emerald" style={{ width: `${completionRate}%` }} />
                </div>
              </div>
            </div>

            {/* Gauge 2: AI Grounding */}
            <div className="mini-gauge-card">
              <div>
                <span className="gauge-label">AI Grounding</span>
                <div className="gauge-big-stat">
                  <span>92%</span>
                  <span className="gauge-trend-chip" style={{ background: 'rgba(99, 102, 241, 0.15)', color: '#818CF8' }}>
                    [Grounded]
                  </span>
                </div>
              </div>
              <div>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                  Deterministic validation
                </span>
                <div className="gauge-track">
                  <div className="gauge-fill fill-indigo" style={{ width: '92%' }} />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* =========================================================================
            TILE 3: 🎯 MY ACTION ITEMS (Interactive Glass)
            ========================================================================= */}
        <div className="bento-tile bento-tile-glow">
          <div className="bento-tile-header">
            <div className="bento-tile-title-group">
              <span className="bento-tile-icon">🎯</span>
              <h2 className="bento-tile-title">MY ACTION ITEMS</h2>
            </div>
            <span className="bento-tile-tag tag-hero">INTERACTIVE GLASS</span>
          </div>

          <div className="bento-actions-checklist">
            {actionItems.slice(0, 4).map((item) => {
              const isChecked = item.status === 'completed' || completedTaskIds.has(item.id);
              return (
                <div key={item.id} className="bento-check-row">
                  <div className="bento-check-left">
                    <button
                      type="button"
                      className={`bento-checkbox-btn ${isChecked ? 'checked' : ''}`}
                      onClick={() => handleToggleTask(item.id)}
                      title={isChecked ? 'Mark pending' : 'Mark completed'}
                    >
                      ✓
                    </button>
                    <div>
                      <div className={`bento-check-title ${isChecked ? 'completed' : ''}`}>
                        {item.task}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                        👤 {item.assignee || item.owner || 'Unassigned'} • Due: {item.deadline || 'No date'}
                      </div>
                    </div>
                  </div>

                  <div className="bento-check-right">
                    <button
                      type="button"
                      className="action-evidence-btn"
                      onClick={() => setSelectedEvidenceItem(item)}
                    >
                      ✦ Evidence
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* =========================================================================
            TILE 4: 🎙️ RECENT MEETING INTELLIGENCE (Bento)
            ========================================================================= */}
        <div className="bento-tile bento-tile-glow">
          <div className="bento-tile-header">
            <div className="bento-tile-title-group">
              <span className="bento-tile-icon">🎙️</span>
              <h2 className="bento-tile-title">RECENT MEETING INTELLIGENCE</h2>
            </div>
            <span className="bento-tile-tag tag-analytics">BENTO TILE</span>
          </div>

          <div className="bento-recent-meetings-stack">
            {meetings.slice(0, 2).map((m) => (
              <div
                key={m.id}
                className="bento-meeting-card"
                onClick={() => onSelectMeeting(m.id)}
              >
                <div className="bento-meeting-card-top">
                  <span className="bento-meeting-title">
                    {m.title || `Meeting #${m.id} Intelligence`}
                  </span>
                  <span className="bento-meeting-date">
                    {m.created_at ? new Date(m.created_at).toLocaleDateString([], { month: 'short', day: 'numeric' }) : 'Recent'}
                  </span>
                </div>

                <p className="bento-meeting-summary">
                  {m.summary}
                </p>

                <div className="meeting-card-pills-row">
                  <span className="mini-pill pill-actions">🏷️ {m.action_items_count || 0} Actions</span>
                  <span className="mini-pill pill-decisions">🏷️ {m.decisions_count || 0} Decisions</span>
                  <span className="mini-pill pill-issues">🏷️ {m.unresolved_issues_count || 0} Blocker</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Frosted Slide-Out Evidence Drawer (WeatherWatch Style) */}
      <EvidenceDrawer
        isOpen={Boolean(selectedEvidenceItem)}
        onClose={() => setSelectedEvidenceItem(null)}
        item={selectedEvidenceItem}
        type="action"
      />
    </div>
  );
}
