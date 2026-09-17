import React, { useState } from 'react';
import { Icon } from '../components/icons/Icons';

export default function DecisionsView({ decisions = [], onSelectMeeting }) {
  const [search, setSearch] = useState('');

  const filtered = decisions.filter((d) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (d.decision && d.decision.toLowerCase().includes(q)) || String(d.meeting_id).includes(q);
  });

  return (
    <div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 'var(--space-6)',
        flexWrap: 'wrap',
        gap: 'var(--space-4)'
      }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>
            Confirmed Club Decisions
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', marginTop: '2px' }}>
            Permanent record of agreements, policies, and resolutions settled during meetings ({decisions.length} decisions)
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: '260px' }}>
          <Icon name="search" size={15} style={{ color: 'var(--text-muted)' }} />
          <input
            type="text"
            className="s5-input"
            placeholder="Search decisions or meeting ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ padding: '7px 12px', fontSize: '0.82rem' }}
          />
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="s5-empty-state">
          <div className="s5-empty-icon" style={{ color: 'var(--semantic-green)' }}>
            <Icon name="decisions" size={24} />
          </div>
          <div className="s5-empty-title">
            {search ? 'No matching decisions' : 'No decisions recorded yet'}
          </div>
          <p className="s5-empty-desc">
            {search
              ? `No confirmed decision matches "${search}".`
              : 'As your club analyzes meetings, ratified decisions and settled agreements will be indexed here.'}
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          {filtered.map((d) => (
            <div key={d.id} className="s5-card" style={{ padding: '16px 20px', borderLeft: '3px solid var(--semantic-green)' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                  <div style={{
                    width: '24px',
                    height: '24px',
                    borderRadius: '50%',
                    background: 'var(--semantic-green-bg)',
                    border: '1px solid var(--semantic-green-border)',
                    color: '#34D399',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginTop: '2px',
                    flexShrink: 0
                  }}>
                    <Icon name="check" size={14} />
                  </div>
                  <div>
                    <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.45 }}>
                      {d.decision}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span>Ratified during</span>
                      <button
                        className="s5-btn s5-btn-ghost s5-btn-sm"
                        onClick={() => onSelectMeeting(d.meeting_id)}
                        style={{ padding: '0 4px', color: 'var(--accent-primary)', fontFamily: 'var(--font-mono)' }}
                      >
                        Meeting #{d.meeting_id} →
                      </button>
                    </div>
                  </div>
                </div>

                <span className="s5-badge s5-badge-confirmed" style={{ flexShrink: 0 }}>
                  Confirmed
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
