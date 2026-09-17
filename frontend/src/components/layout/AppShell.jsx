import React, { useState } from 'react';
import Sidebar from './Sidebar';
import Topbar from './Topbar';
import GlobalSearchModal from '../modals/GlobalSearchModal';
import SystemSpecsModal from '../modals/SystemSpecsModal';

export default function AppShell({
  children,
  currentView,
  onNavigate,
  onNavigateToAnalyze,
  meetings = [],
  actionItems = [],
  decisions = [],
  issues = [],
  onSelectMeeting,
  backendOnline = true,
}) {
  const [selectedClub, setSelectedClub] = useState('Cultural Committee');
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isSpecsOpen, setIsSpecsOpen] = useState(false);

  // Keyboard shortcut: Ctrl+K or Cmd+K opens global search
  React.useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsSearchOpen(true);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <div className="s5-shell">
      {/* Persistent Left Sidebar */}
      <Sidebar
        currentView={currentView}
        onNavigate={onNavigate}
        meetingsCount={meetings.length}
        actionItemsCount={actionItems.length}
        decisionsCount={decisions.length}
        issuesCount={issues.length}
        onOpenSystemSpecs={() => setIsSpecsOpen(true)}
        backendOnline={backendOnline}
      />

      {/* Main View Area */}
      <div className="s5-main-wrapper">
        <Topbar
          currentView={currentView}
          onNavigateToAnalyze={onNavigateToAnalyze}
          selectedClub={selectedClub}
          onSelectClub={setSelectedClub}
          onOpenSearch={() => setIsSearchOpen(true)}
        />

        <main className="s5-page-container">
          {children}
        </main>
      </div>

      {/* Global Search Modal */}
      <GlobalSearchModal
        isOpen={isSearchOpen}
        onClose={() => setIsSearchOpen(false)}
        meetings={meetings}
        actionItems={actionItems}
        decisions={decisions}
        issues={issues}
        onSelectMeeting={onSelectMeeting}
      />

      {/* Technical Architecture Specs Modal (Faculty / Reviewer Demo) */}
      <SystemSpecsModal
        isOpen={isSpecsOpen}
        onClose={() => setIsSpecsOpen(false)}
      />
    </div>
  );
}
