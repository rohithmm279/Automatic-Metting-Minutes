import React from 'react';

export default function ConfirmModal({ isOpen, title, message, onConfirm, onCancel, isDeleting, confirmText }) {
  if (!isOpen) return null;

  return (
    <div className="s5-modal-backdrop" role="dialog" aria-modal="true" onClick={onCancel}>
      <div className="s5-modal" style={{ maxWidth: '440px' }} onClick={(e) => e.stopPropagation()}>
        <h3 style={{ fontSize: '1.15rem', fontWeight: 700, marginBottom: '12px', color: 'var(--semantic-red)' }}>
          🗑️ {title || 'Confirm Deletion'}
        </h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', lineHeight: 1.6, marginBottom: '20px' }}>
          {message || 'Are you sure you want to delete this meeting? All associated action items, decisions, and issues will be permanently removed.'}
        </p>
        <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
          <button className="s5-btn s5-btn-secondary" onClick={onCancel} disabled={isDeleting}>
            Cancel
          </button>
          <button className="s5-btn s5-btn-danger" onClick={onConfirm} disabled={isDeleting}>
            {isDeleting ? 'Deleting...' : (confirmText || 'Delete Meeting')}
          </button>
        </div>
      </div>
    </div>
  );
}
