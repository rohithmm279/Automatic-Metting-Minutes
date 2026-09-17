import React from 'react';
import { Icon } from '../components/icons/Icons';

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
  // Deterministic calculations based on real backend data
  const totalMeetings = meetings.length;
  const totalActions = actionItems.length;
  const pendingActions = actionItems.filter((a) => a.status === 'pending').length;
  const inProgressActions = actionItems.filter((a) => a.status === 'in_progress').length;
  const completedActions = actionItems.filter((a) => a.status === 'completed').length;
  const completionRate = totalActions > 0 ? Math.round((completedActions / totalActions) * 100) : 0;

  // Real items needing human attention (e.g. missing owner or missing deadline)
  const itemsNeedingReview = actionItems.filter((a) => !a.owner || !a.deadline);

  // --------------------------------------------------------------------------
  // FIRST-TIME USER ONBOARDING EXPERIENCE (When 0 meetings exist)
  // --------------------------------------------------------------------------
  if (!loading && totalMeetings === 0) {
    return (
      <div style={{ maxWidth: '840px', margin: '0 auto', paddingTop: 'var(--space-6)' }}>
        {/* Welcome Hero */}
        <div style={{
          background: 'linear-gradient(180deg, var(--surface-secondary) 0%, var(--surface-primary) 100%)',
          border: '1px solid var(--border-default)',
          borderRadius: 'var(--radius-xl)',
          padding: 'var(--space-12) var(--space-8)',
          textAlign: 'center',
          boxShadow: 'var(--shadow-lg)',
          position: 'relative',
          overflow: 'hidden'
        }}>
          {/* Subtle brand glow in background */}
          <div style={{
            position: 'absolute',
            top: '-60px',
            left: '50%',
            transform: 'translateX(-50%)',
            width: '260px',
            height: '140px',
            background: 'radial-gradient(ellipse, rgba(99, 102, 241, 0.25) 0%, transparent 70%)',
            pointerEvents: 'none'
          }} />

          <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            background: 'var(--accent-subtle)',
            color: 'var(--accent-primary)',
            padding: '4px 12px',
            borderRadius: 'var(--radius-full)',
            fontSize: '0.78rem',
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            marginBottom: 'var(--space-4)'
          }}>
            <Icon name="sparkles" size={13} />
            AI Meeting Intelligence for Student Clubs
          </span>

          <h1 style={{
            fontSize: '2.4rem',
            fontWeight: 800,
            letterSpacing: '-0.03em',
            lineHeight: 1.15,
            color: 'var(--text-primary)',
            marginBottom: 'var(--space-3)'
          }}>
            Welcome to S5
          </h1>

          <p style={{
            fontSize: '1.1rem',
            color: 'var(--text-secondary)',
            maxWidth: '540px',
            margin: '0 auto var(--space-8)',
            lineHeight: 1.5
          }}>
            Turn your meeting conversations into clear minutes, decisions, and actionable tasks.
          </p>

          <button
            className="s5-btn s5-btn-primary s5-btn-lg"
            onClick={onNavigateToAnalyze}
            id="btn-first-time-analyze"
            style={{ padding: '14px 28px', fontSize: '1.05rem' }}
          >
            <Icon name="sparkles" size={18} />
            <span>Analyze Your First Meeting</span>
          </button>
        </div>

        {/* 3-Step Simple Explainer */}
        <div style={{ marginTop: 'var(--space-12)' }}>
          <div style={{
            fontSize: '0.8rem',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
            color: 'var(--text-muted)',
            textAlign: 'center',
            marginBottom: 'var(--space-6)'
          }}>
            How It Works
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-6)' }}>
            {[
              {
                step: '01',
                title: 'Add transcript',
                desc: 'Upload a text file or paste conversation dialogue from your club meeting.',
                icon: 'file-text',
              },
              {
                step: '02',
                title: 'AI analyzes it',
                desc: 'Identifies executive summaries, tasks, decisions, and unresolved issues.',
                icon: 'sparkles',
              },
              {
                step: '03',
                title: 'Review and act',
                desc: 'Confirm important items, track assignees, and close out action items.',
                icon: 'check-circle',
              },
            ].map((card) => (
              <div
                key={card.step}
                className="s5-card"
                style={{ textAlign: 'center', padding: 'var(--space-6) var(--space-5)' }}
              >
                <div style={{
                  width: '42px',
                  height: '42px',
                  borderRadius: 'var(--radius-lg)',
                  background: 'var(--surface-elevated)',
                  color: 'var(--accent-primary)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  margin: '0 auto var(--space-4)'
                }}>
                  <Icon name={card.icon} size={20} />
                </div>
                <div style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.75rem',
                  color: 'var(--accent-primary)',
                  fontWeight: 600,
                  marginBottom: 'var(--space-1)'
                }}>
                  STEP {card.step}
                </div>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 'var(--space-2)' }}>
                  {card.title}
                </h3>
                <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
                  {card.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // --------------------------------------------------------------------------
  // RETURNING USER: OPERATIONAL MEETING COMMAND CENTER
  // --------------------------------------------------------------------------
  return (
    <div>
      {/* Top Banner */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 'var(--space-8)',
        flexWrap: 'wrap',
        gap: 'var(--space-4)'
      }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>
            Meeting Operations Command Center
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', marginTop: '2px' }}>
            Real-time status across your student club meetings, tasks, and confirmed decisions.
          </p>
        </div>

        <button
          className="s5-btn s5-btn-primary"
          onClick={onNavigateToAnalyze}
          id="btn-overview-new-meeting"
        >
          <Icon name="plus" size={16} />
          <span>New Meeting Analysis</span>
        </button>
      </div>

      {/* Human-in-the-Loop Review Banner if items need attention */}
      {itemsNeedingReview.length > 0 && (
        <div className="s5-review-banner">
          <div className="s5-review-banner-text">
            <Icon name="issues" size={18} />
            <span>
              <strong>{itemsNeedingReview.length} action item{itemsNeedingReview.length === 1 ? '' : 's'} need your review</strong> — owner or deadline was not explicitly mentioned in dialogue.
            </span>
          </div>
          <button
            className="s5-btn s5-btn-secondary s5-btn-sm"
            onClick={onNavigateToActions}
          >
            Review Items →
          </button>
        </div>
      )}

      {/* Metric Cards Grid */}
      <div className="s5-grid-metrics">
        {/* Card 1: Meetings */}
        <div className="s5-metric-card">
          <div className="s5-metric-header">
            <span className="s5-metric-label">Meetings Analyzed</span>
            <div className="s5-metric-icon-box">
              <Icon name="meetings" size={18} />
            </div>
          </div>
          <div className="s5-metric-value">{totalMeetings}</div>
          <div className="s5-metric-subtext">
            <span>Stored in SQLite repository</span>
          </div>
        </div>

        {/* Card 2: Action Items */}
        <div className="s5-metric-card">
          <div className="s5-metric-header">
            <span className="s5-metric-label">Action Items</span>
            <div className="s5-metric-icon-box">
              <Icon name="actions" size={18} />
            </div>
          </div>
          <div className="s5-metric-value">{totalActions}</div>
          <div className="s5-metric-subtext" style={{ color: pendingActions > 0 ? '#FBBF24' : 'var(--text-muted)' }}>
            <span>{pendingActions} pending · {inProgressActions} in progress</span>
          </div>
        </div>

        {/* Card 3: Completion Rate */}
        <div className="s5-metric-card">
          <div className="s5-metric-header">
            <span className="s5-metric-label">Completion Rate</span>
            <div className="s5-metric-icon-box">
              <Icon name="check-circle" size={18} />
            </div>
          </div>
          <div className="s5-metric-value">{completionRate}%</div>
          <div className="s5-metric-subtext">
            <span>{completedActions} of {totalActions} tasks completed</span>
          </div>
        </div>

        {/* Card 4: Attention Needed */}
        <div className="s5-metric-card">
          <div className="s5-metric-header">
            <span className="s5-metric-label">Decisions & Blockers</span>
            <div className="s5-metric-icon-box">
              <Icon name="stamp" size={18} />
            </div>
          </div>
          <div className="s5-metric-value">{decisions.length}</div>
          <div className="s5-metric-subtext" style={{ color: issues.length > 0 ? '#F87171' : 'var(--text-muted)' }}>
            <span>{issues.length} unresolved issue{issues.length === 1 ? '' : 's'}</span>
          </div>
        </div>
      </div>

      {/* Signature UI Strip: Meeting Intelligence Pipeline */}
      <div className="s5-card mb-4" style={{ marginBottom: 'var(--space-8)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-3)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Icon name="pipeline" size={16} style={{ color: 'var(--accent-primary)' }} />
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
              Meeting Intelligence Pipeline
            </span>
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Deterministic flow: Conversation ➔ Structured Actionable Intelligence
          </span>
        </div>

        <div className="s5-pipeline-strip">
          {[
            { label: 'Transcript Input', done: true },
            { label: 'AI Understanding', done: true },
            { label: 'Structured Extraction', done: true },
            { label: 'Pydantic Validation', done: true },
            { label: 'Human Review', done: itemsNeedingReview.length === 0, active: itemsNeedingReview.length > 0 },
            { label: 'Action Tracking', done: true },
          ].map((step, idx, arr) => (
            <React.Fragment key={step.label}>
              <div className={`s5-pipeline-step ${step.done ? 'done' : ''} ${step.active ? 'active' : ''}`}>
                <div className="s5-pipeline-dot">
                  {step.done ? '✓' : step.active ? '●' : '○'}
                </div>
                <span>{step.label}</span>
              </div>
              {idx < arr.length - 1 && <span className="s5-pipeline-arrow">➔</span>}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Recent Meetings Table */}
      <div className="s5-card">
        <div className="s5-card-header">
          <div>
            <h2 className="s5-card-title">
              <Icon name="meetings" size={18} />
              <span>Recent Club Meetings</span>
            </h2>
            <p className="s5-card-subtitle">
              Showing latest recorded sessions
            </p>
          </div>
          <button className="s5-btn s5-btn-secondary s5-btn-sm" onClick={() => onNavigateToAnalyze()}>
            + Add Meeting
          </button>
        </div>

        {meetings.length === 0 ? (
          <div className="s5-empty-state">
            <div className="s5-empty-icon">
              <Icon name="meetings" size={24} />
            </div>
            <div className="s5-empty-title">No Meetings Yet</div>
            <p className="s5-empty-desc">
              Your meeting intelligence history will appear here after your first analysis.
            </p>
            <button className="s5-btn s5-btn-primary s5-btn-sm" onClick={onNavigateToAnalyze}>
              Analyze First Meeting
            </button>
          </div>
        ) : (
          <div className="s5-table-container">
            <table className="s5-table">
              <thead>
                <tr>
                  <th style={{ width: '8%' }}>ID</th>
                  <th style={{ width: '48%' }}>Executive Summary</th>
                  <th style={{ width: '18%' }}>Extractions</th>
                  <th style={{ width: '14%' }}>Recorded</th>
                  <th style={{ width: '12%', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {meetings.slice(0, 8).map((m) => (
                  <tr key={m.id}>
                    <td>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-muted)' }}>
                        #{m.id}
                      </span>
                    </td>
                    <td>
                      <div style={{
                        fontWeight: 500,
                        lineHeight: 1.4,
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                        color: 'var(--text-primary)'
                      }}>
                        {m.summary}
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                        <span className="s5-badge s5-badge-pending" title="Action Items">
                          ⚡ {m.action_items_count}
                        </span>
                        <span className="s5-badge s5-badge-confirmed" title="Decisions">
                          ✓ {m.decisions_count}
                        </span>
                        <span className="s5-badge s5-badge-overdue" title="Unresolved Issues">
                          ! {m.unresolved_issues_count}
                        </span>
                      </div>
                    </td>
                    <td>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        {m.created_at ? new Date(m.created_at).toLocaleDateString() : 'Recent'}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        className="s5-btn s5-btn-secondary s5-btn-sm"
                        onClick={() => onSelectMeeting(m.id)}
                      >
                        View Details
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
