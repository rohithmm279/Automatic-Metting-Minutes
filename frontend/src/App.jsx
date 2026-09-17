import React, { useState, useEffect, useCallback } from 'react';
import api from './services/api';
import AppShell from './components/layout/AppShell';
import Overview from './pages/Overview';
import AnalyzeMeeting from './pages/AnalyzeMeeting';
import MeetingDetailsView from './pages/MeetingDetailsView';
import ActionTracker from './pages/ActionTracker';
import DecisionsView from './pages/DecisionsView';
import IssuesView from './pages/IssuesView';
import MeetingTimeline from './pages/MeetingTimeline';
import AnalyticsView from './pages/AnalyticsView';

export default function App() {
  const [currentView, setCurrentView] = useState('overview');
  const [selectedMeetingId, setSelectedMeetingId] = useState(null);
  const [meetings, setMeetings] = useState([]);
  const [actionItems, setActionItems] = useState([]);
  const [decisions, setDecisions] = useState([]);
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(true);
  const [backendOnline, setBackendOnline] = useState(true);

  // Load all meetings and aggregate their child records for cross-meeting views
  const refreshAllData = useCallback(async () => {
    setLoading(true);
    try {
      // 1. Health check
      try {
        await api.getHealth();
        setBackendOnline(true);
      } catch (_err) {
        setBackendOnline(false);
      }

      // 2. Fetch list of meetings
      const list = await api.getMeetings(100, 0);
      const meetingList = Array.isArray(list) ? list : [];
      setMeetings(meetingList);

      // 3. Retrieve details for existing meetings to populate tasks, decisions, and issues
      if (meetingList.length > 0) {
        const detailPromises = meetingList.slice(0, 20).map((m) =>
          api.getMeeting(m.id).catch(() => null)
        );
        const detailedMeetings = await Promise.all(detailPromises);

        const allActions = [];
        const allDecisions = [];
        const allIssues = [];

        detailedMeetings.forEach((dm) => {
          if (!dm) return;
          if (Array.isArray(dm.action_items)) {
            dm.action_items.forEach((item) => allActions.push({ ...item, meeting_id: dm.id }));
          }
          if (Array.isArray(dm.decisions)) {
            dm.decisions.forEach((dec) => allDecisions.push({ ...dec, meeting_id: dm.id }));
          }
          if (Array.isArray(dm.unresolved_issues)) {
            dm.unresolved_issues.forEach((iss) => allIssues.push({ ...iss, meeting_id: dm.id }));
          }
        });

        setActionItems(allActions);
        setDecisions(allDecisions);
        setIssues(allIssues);
      } else {
        setActionItems([]);
        setDecisions([]);
        setIssues([]);
      }
    } catch (err) {
      console.error('Failed to load application data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshAllData();
  }, [refreshAllData]);

  const handleSelectMeeting = (meetingId) => {
    setSelectedMeetingId(meetingId);
    setCurrentView('meeting-details');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleMeetingCreated = (meetingId) => {
    setSelectedMeetingId(meetingId);
    setCurrentView('meeting-details');
    refreshAllData();
  };

  const handleMeetingDeleted = () => {
    setSelectedMeetingId(null);
    setCurrentView('overview');
    refreshAllData();
  };

  const handleStatusUpdate = (meetingId, itemId, newStatus) => {
    setActionItems((prev) =>
      prev.map((item) =>
        item.id === itemId ? { ...item, status: newStatus } : item
      )
    );
  };

  return (
    <AppShell
      currentView={currentView}
      onNavigate={(view) => {
        setSelectedMeetingId(null);
        setCurrentView(view);
      }}
      onNavigateToAnalyze={() => {
        setSelectedMeetingId(null);
        setCurrentView('analyze');
      }}
      meetings={meetings}
      actionItems={actionItems}
      decisions={decisions}
      issues={issues}
      onSelectMeeting={handleSelectMeeting}
      backendOnline={backendOnline}
    >
      {/* 1. Overview Command Center */}
      {currentView === 'overview' && (
        <Overview
          meetings={meetings}
          actionItems={actionItems}
          decisions={decisions}
          issues={issues}
          loading={loading}
          onNavigateToAnalyze={() => setCurrentView('analyze')}
          onSelectMeeting={handleSelectMeeting}
          onNavigateToActions={() => setCurrentView('actions')}
        />
      )}

      {/* 2. Analyze Meeting Hero Studio */}
      {currentView === 'analyze' && (
        <AnalyzeMeeting
          onMeetingCreated={handleMeetingCreated}
          onCancel={() => setCurrentView('overview')}
        />
      )}

      {/* 3. Meeting Details Flagship View */}
      {currentView === 'meeting-details' && selectedMeetingId && (
        <MeetingDetailsView
          meetingId={selectedMeetingId}
          onBack={() => setCurrentView('overview')}
          onDeleted={handleMeetingDeleted}
          onSelectMeeting={handleSelectMeeting}
        />
      )}

      {/* 4. Action Items Cross-Meeting Tracker */}
      {currentView === 'actions' && (
        <ActionTracker
          actionItems={actionItems}
          onStatusUpdate={handleStatusUpdate}
          onSelectMeeting={handleSelectMeeting}
        />
      )}

      {/* 5. Confirmed Decisions View */}
      {currentView === 'decisions' && (
        <DecisionsView
          decisions={decisions}
          onSelectMeeting={handleSelectMeeting}
        />
      )}

      {/* 6. Open Issues & Blockers View */}
      {currentView === 'issues' && (
        <IssuesView
          issues={issues}
          onSelectMeeting={handleSelectMeeting}
        />
      )}

      {/* 7. Meeting Timeline & History */}
      {currentView === 'meetings' && (
        <MeetingTimeline
          meetings={meetings}
          onSelectMeeting={handleSelectMeeting}
          onNavigateToAnalyze={() => setCurrentView('analyze')}
          onMeetingDeleted={handleMeetingDeleted}
        />
      )}

      {/* 8. Club Intelligence Analytics */}
      {currentView === 'analytics' && (
        <AnalyticsView
          meetings={meetings}
          actionItems={actionItems}
          decisions={decisions}
          issues={issues}
        />
      )}
    </AppShell>
  );
}
