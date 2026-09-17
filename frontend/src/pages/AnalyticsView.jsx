import React from 'react';
import { Icon } from '../components/icons/Icons';

export default function AnalyticsView({
  meetings = [],
  actionItems = [],
  decisions = [],
  issues = [],
}) {
  // Deterministic computations from actual database records
  const totalMeetings = meetings.length;
  const totalActions = actionItems.length;
  const completedActions = actionItems.filter((a) => a.status === 'completed').length;
  const pendingActions = actionItems.filter((a) => a.status === 'pending').length;
  const inProgressActions = actionItems.filter((a) => a.status === 'in_progress').length;
  const cancelledActions = actionItems.filter((a) => a.status === 'cancelled').length;

  const completionRate = totalActions > 0 ? Math.round((completedActions / totalActions) * 100) : 0;

  // Workload by Assignee
  const ownerCounts = {};
  actionItems.forEach((item) => {
    const owner = item.owner && item.owner.trim() ? item.owner.trim() : 'Unassigned';
    ownerCounts[owner] = (ownerCounts[owner] || 0) + 1;
  });

  const sortedOwners = Object.entries(ownerCounts).sort((a, b) => b[1] - a[1]);

  // Average extractions per meeting
  const avgActions = totalMeetings > 0 ? (totalActions / totalMeetings).toFixed(1) : 0;
  const avgDecisions = totalMeetings > 0 ? (decisions.length / totalMeetings).toFixed(1) : 0;
  const avgIssues = totalMeetings > 0 ? (issues.length / totalMeetings).toFixed(1) : 0;

  return (
    <div>
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>
          Club Intelligence Analytics
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', marginTop: '2px' }}>
          Deterministic operational metrics synthesized from your recorded club sessions
        </p>
      </div>

      {/* Top Level Metric Cards */}
      <div className="s5-grid-metrics">
        <div className="s5-metric-card">
          <div className="s5-metric-header">
            <span className="s5-metric-label">Total Meetings</span>
            <div className="s5-metric-icon-box"><Icon name="meetings" size={18} /></div>
          </div>
          <div className="s5-metric-value">{totalMeetings}</div>
          <div className="s5-metric-subtext">Persisted in SQLite database</div>
        </div>

        <div className="s5-metric-card">
          <div className="s5-metric-header">
            <span className="s5-metric-label">Overall Completion</span>
            <div className="s5-metric-icon-box"><Icon name="check-circle" size={18} /></div>
          </div>
          <div className="s5-metric-value">{completionRate}%</div>
          <div className="s5-metric-subtext">{completedActions} of {totalActions} closed</div>
        </div>

        <div className="s5-metric-card">
          <div className="s5-metric-header">
            <span className="s5-metric-label">Ratified Decisions</span>
            <div className="s5-metric-icon-box"><Icon name="decisions" size={18} /></div>
          </div>
          <div className="s5-metric-value">{decisions.length}</div>
          <div className="s5-metric-subtext">Across {totalMeetings} sessions</div>
        </div>

        <div className="s5-metric-card">
          <div className="s5-metric-header">
            <span className="s5-metric-label">Pending Blockers</span>
            <div className="s5-metric-icon-box"><Icon name="issues" size={18} /></div>
          </div>
          <div className="s5-metric-value" style={{ color: issues.length > 0 ? '#F87171' : 'var(--text-primary)' }}>
            {issues.length}
          </div>
          <div className="s5-metric-subtext">Awaiting administrative input</div>
        </div>
      </div>

      {/* Grid: Status Distribution & Workload by Member */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 'var(--space-6)', marginBottom: 'var(--space-6)' }}>
        {/* Action Status Breakdown */}
        <div className="s5-card">
          <div className="s5-card-header">
            <h3 className="s5-card-title">
              <Icon name="actions" size={18} style={{ color: 'var(--accent-primary)' }} />
              <span>Action Item Status Distribution</span>
            </h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {[
              { label: 'Completed', count: completedActions, color: '#10B981', bg: 'var(--semantic-green-bg)' },
              { label: 'Pending', count: pendingActions, color: '#F59E0B', bg: 'var(--semantic-amber-bg)' },
              { label: 'In Progress', count: inProgressActions, color: '#38BDF8', bg: 'var(--semantic-blue-bg)' },
              { label: 'Cancelled', count: cancelledActions, color: '#EF4444', bg: 'var(--semantic-red-bg)' },
            ].map((st) => {
              const pct = totalActions > 0 ? Math.round((st.count / totalActions) * 100) : 0;
              return (
                <div key={st.label}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.84rem', marginBottom: '5px' }}>
                    <span style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{st.label}</span>
                    <span style={{ color: 'var(--text-muted)' }}>
                      {st.count} ({pct}%)
                    </span>
                  </div>
                  <div style={{ height: '7px', borderRadius: 'var(--radius-full)', background: 'var(--surface-elevated)', overflow: 'hidden' }}>
                    <div style={{ width: `${pct}%`, height: '100%', background: st.color, transition: 'width 0.4s ease' }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Workload by Assignee */}
        <div className="s5-card">
          <div className="s5-card-header">
            <h3 className="s5-card-title">
              <Icon name="user" size={18} style={{ color: 'var(--accent-primary)' }} />
              <span>Workload Allocation by Assignee</span>
            </h3>
          </div>

          {sortedOwners.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', fontStyle: 'italic', padding: '12px' }}>
              No commitments recorded yet.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {sortedOwners.slice(0, 6).map(([owner, count]) => {
                const pct = totalActions > 0 ? Math.round((count / totalActions) * 100) : 0;
                return (
                  <div key={owner} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', background: 'var(--surface-elevated)', borderRadius: 'var(--radius-md)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div style={{ width: '24px', height: '24px', borderRadius: '50%', background: 'var(--surface-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem', fontWeight: 600, color: 'var(--accent-primary)' }}>
                        {owner.charAt(0).toUpperCase()}
                      </div>
                      <span style={{ fontSize: '0.88rem', fontWeight: 500, color: 'var(--text-primary)' }}>{owner}</span>
                    </div>
                    <span className="s5-badge s5-badge-neutral">
                      {count} task{count === 1 ? '' : 's'} ({pct}%)
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Extraction Density Card */}
      <div className="s5-card">
        <div className="s5-card-header">
          <h3 className="s5-card-title">
            <Icon name="sparkles" size={18} style={{ color: 'var(--accent-primary)' }} />
            <span>Average Meeting Extraction Density</span>
          </h3>
          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            Empirical throughput per processed conversation
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-4)', textAlign: 'center' }}>
          <div style={{ background: 'var(--surface-elevated)', padding: '14px', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--text-primary)' }}>{avgActions}</div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '4px' }}>Avg Tasks / Meeting</div>
          </div>
          <div style={{ background: 'var(--surface-elevated)', padding: '14px', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#34D399' }}>{avgDecisions}</div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '4px' }}>Avg Decisions / Meeting</div>
          </div>
          <div style={{ background: 'var(--surface-elevated)', padding: '14px', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#F87171' }}>{avgIssues}</div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '4px' }}>Avg Blockers / Meeting</div>
          </div>
        </div>
      </div>
    </div>
  );
}
