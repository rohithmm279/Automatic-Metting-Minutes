import React from 'react';

export default function LoadingSpinner({ message = 'Loading...' }) {
  return (
    <div className="state-box">
      <div className="spinner"></div>
      <p className="state-desc">{message}</p>
    </div>
  );
}
