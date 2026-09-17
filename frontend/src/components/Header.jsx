import React from 'react';

export default function Header({ currentView, setCurrentView }) {
  return (
    <header className="app-header">
      <div className="header-container">
        <div className="brand-section">
          <div className="brand-icon">⚡</div>
          <div>
            <h1 className="brand-title">Automatic Meeting Minutes & Action Item Generator</h1>
            <p className="brand-subtitle">AI-powered meeting minutes and action tracking for student clubs</p>
          </div>
        </div>

        <nav className="nav-tabs" aria-label="Main Navigation">
          <button
            id="nav-dashboard"
            className={`nav-tab ${currentView === 'dashboard' ? 'active' : ''}`}
            onClick={() => setCurrentView('dashboard')}
          >
            📊 Dashboard
          </button>
          <button
            id="nav-new-meeting"
            className={`nav-tab ${currentView === 'new-meeting' ? 'active' : ''}`}
            onClick={() => setCurrentView('new-meeting')}
          >
            ➕ New Meeting
          </button>
          <button
            id="nav-history"
            className={`nav-tab ${currentView === 'history' ? 'active' : ''}`}
            onClick={() => setCurrentView('history')}
          >
            📁 Meeting History
          </button>
        </nav>
      </div>
    </header>
  );
}
