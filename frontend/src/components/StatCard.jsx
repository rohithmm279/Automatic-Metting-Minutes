import React from 'react';

export default function StatCard({ label, value, icon, variant = 'total' }) {
  return (
    <div className="stat-card">
      <div className={`stat-icon ${variant}`}>
        {icon}
      </div>
      <div className="stat-info">
        <span className="stat-value">{value}</span>
        <span className="stat-label">{label}</span>
      </div>
    </div>
  );
}
