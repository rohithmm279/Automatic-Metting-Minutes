import React from 'react';

export default function ConfirmModal({ isOpen, title, message, onConfirm, onCancel, isDeleting }) {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal-content">
        <h3 style={{ fontSize: '1.2rem', marginBottom: '0.75rem', color: '#fca5a5' }}>
          🗑️ {title || 'Confirm Deletion'}
        </h3>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', lineHeight: '1.6' }}>
          {message || 'Are you sure you want to delete this meeting? All associated action items, decisions, and issues will be permanently removed.'}
        </p>
        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onCancel} disabled={isDeleting}>
            Cancel
          </button>
          <button className="btn btn-danger" onClick={onConfirm} disabled={isDeleting}>
            {isDeleting ? 'Deleting...' : 'Delete Meeting'}
          </button>
        </div>
      </div>
    </div>
  );
}
