import React, { useState, useEffect } from 'react';
import api from '../services/api';
import StatCard from '../components/StatCard';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorAlert from '../components/ErrorAlert';

export default function Dashboard({ onNavigateToNew, onSelectMeeting }) {
  const [meetings, setMeetings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState({
    total: 0,
    pending: 0,
    inProgress: 0,
    completed: 0,
  });

  const loadDashboardData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getMeetings(50, 0);
      const meetingList = Array.isArray(data) ? data : [];
      setMeetings(meetingList);

      // Aggregate statistics from meeting details if available
      let pendingCount = 0;
      let inProgressCount = 0;
      let completedCount = 0;

      // Sample first 5 meetings for detailed action-item status breakdown
      const detailPromises = meetingList.slice(0, 10).map((m) =>
        api.getMeeting(m.id).catch(() => null)
      );
      const details = await Promise.all(detailPromises);

      details.forEach((d) => {
        if (d && Array.isArray(d.action_items)) {
          d.action_items.forEach((item) => {
            if (item.status === 'pending') pendingCount++;
            else if (item.status === 'in_progress') inProgressCount++;
            else if (item.status === 'completed') completedCount++;
          });
        }
      });

      setStats({
        total: meetingList.length,
        pending: pendingCount,
        inProgress: inProgressCount,
        completed: completedCount,
      });
    } catch (err) {
      console.error('Failed to load dashboard:', err);
      setError(err.message || 'Failed to connect to the backend server.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  return (
    <div>
      {/* Top Banner / Welcome */}
      <div className="flex-between mb-4">
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700 }}>Executive Dashboard</h2>
          <p className="text-muted" style={{ fontSize: '0.9rem' }}>
            Real-time meeting intelligence and actionable student club tracking
          </p>
        </div>
        <button className="btn btn-primary" onClick={onNavigateToNew}>
          ➕ Process New Meeting
        </button>
      </div>

      <ErrorAlert message={error} onRetry={loadDashboardData} onDismiss={() => setError(null)} />

      {/* Stats Cards */}
      <div className="stats-grid">
        <StatCard label="Total Meetings" value={stats.total} icon="📑" variant="total" />
        <StatCard label="Pending Actions" value={stats.pending} icon="⏳" variant="pending" />
        <StatCard label="In Progress" value={stats.inProgress} icon="🔄" variant="in-progress" />
        <StatCard label="Completed Actions" value={stats.completed} icon="✅" variant="completed" />
      </div>

      {/* Recent Meetings Card */}
      <div className="card">
        <div className="flex-between mb-4">
          <h3 className="card-title" style={{ margin: 0 }}>
            <span>🕒</span> Recent Club Meetings
          </h3>
          <span className="text-muted" style={{ fontSize: '0.85rem' }}>
            Showing latest {meetings.length} stored record{meetings.length === 1 ? '' : 's'}
          </span>
        </div>

        {loading ? (
          <LoadingSpinner message="Fetching meetings from SQLite database..." />
        ) : meetings.length === 0 ? (
          <div className="state-box">
            <div className="state-icon">📝</div>
            <div className="state-title">No meetings recorded yet</div>
            <div className="state-desc">
              Paste a student club transcript to automatically extract summary, action items, and decisions.
            </div>
            <button className="btn btn-primary mt-4" onClick={onNavigateToNew}>
              Create First Meeting
            </button>
          </div>
        ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: '8%' }}>ID</th>
                  <th style={{ width: '47%' }}>Executive Summary Preview</th>
                  <th style={{ width: '15%' }}>Extracted Items</th>
                  <th style={{ width: '15%' }}>Recorded Date</th>
                  <th style={{ width: '15%', textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {meetings.map((m) => (
                  <tr key={m.id}>
                    <td>
                      <span className="mono" style={{ color: 'var(--text-muted)' }}>
                        #{m.id}
                      </span>
                    </td>
                    <td>
                      <div
                        style={{
                          fontWeight: 500,
                          lineHeight: 1.4,
                          display: '-webkit-box',
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden',
                        }}
                      >
                        {m.summary}
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                        <span className="badge badge-pending" title="Action items">
                          ⚡ {m.action_items_count}
                        </span>
                        <span className="badge badge-completed" title="Decisions">
                          ✓ {m.decisions_count}
                        </span>
                        <span className="badge badge-cancelled" title="Unresolved issues">
                          ! {m.unresolved_issues_count}
                        </span>
                      </div>
                    </td>
                    <td>
                      <span className="text-muted" style={{ fontSize: '0.8rem' }}>
                        {m.created_at ? new Date(m.created_at).toLocaleString() : 'Recent'}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => onSelectMeeting(m.id)}
                      >
                        View Details →
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
