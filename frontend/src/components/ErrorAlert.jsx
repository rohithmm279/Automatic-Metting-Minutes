import React from 'react';

export default function ErrorAlert({ message, onDismiss, onRetry }) {
  if (!message) return null;

  return (
    <div className="alert alert-danger" role="alert">
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <span style={{ fontSize: '1.2rem' }}>⚠️</span>
        <div>
          <strong>Error:</strong> {message}
        </div>
      </div>
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        {onRetry && (
          <button className="btn btn-secondary btn-sm" onClick={onRetry}>
            Retry
          </button>
        )}
        {onDismiss && (
          <button className="btn btn-secondary btn-sm" onClick={onDismiss} aria-label="Dismiss">
            ✕
          </button>
        )}
      </div>
    </div>
  );
}
