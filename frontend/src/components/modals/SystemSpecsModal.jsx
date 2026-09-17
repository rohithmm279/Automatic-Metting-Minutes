import React from 'react';
import { Icon } from '../icons/Icons';

export default function SystemSpecsModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="s5-modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="s5-modal" style={{ maxWidth: '640px' }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{
              width: '36px',
              height: '36px',
              borderRadius: 'var(--radius-md)',
              background: 'var(--accent-subtle)',
              color: 'var(--accent-primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <Icon name="sparkles" size={18} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                How S5 Meeting Intelligence Works
              </h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Technical architecture & verification pipeline for academic review
              </p>
            </div>
          </div>
          <button className="s5-btn s5-btn-ghost s5-btn-sm" onClick={onClose} aria-label="Close modal">
            <Icon name="close" size={16} />
          </button>
        </div>

        {/* Conceptual Pipeline Flow */}
        <div style={{
          background: 'var(--surface-elevated)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-lg)',
          padding: '1.25rem',
          marginBottom: '1.25rem'
        }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
            Deterministic 5-Stage System Pipeline
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
            {[
              { step: '01', title: 'Transcript Preprocessing', desc: 'Normalizes speech transcripts, attendees, speaker tags, and timestamps via TranscriptProcessor service.' },
              { step: '02', title: 'Local LLM Inference', desc: 'Executes zero-temperature prompt engineering with Qwen2.5:3b via local Ollama API (no external cloud leakage).' },
              { step: '03', title: 'Structured Extraction', desc: 'Directly parses JSON into domain models: Summary, Action Items, Decisions, and Unresolved Issues.' },
              { step: '04', title: 'Pydantic & Grounding Validation', desc: 'Verifies owner presence against dialogue transcript to eliminate hallucinated commitments.' },
              { step: '05', title: 'FastAPI REST & SQLite Persistence', desc: 'Atomic database persistence with foreign-key cascade integrity and live PATCH status tracking.' },
            ].map((p, idx) => (
              <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.72rem',
                  color: 'var(--accent-primary)',
                  background: 'var(--accent-subtle)',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  fontWeight: 600
                }}>
                  {p.step}
                </span>
                <div>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>{p.title}</div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>{p.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Technical Architecture Specs */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '1.5rem' }}>
          <div style={{ background: 'var(--surface-primary)', padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Backend Engine</div>
            <div style={{ fontWeight: 600, fontSize: '0.88rem', color: 'var(--text-primary)' }}>FastAPI + Uvicorn</div>
          </div>
          <div style={{ background: 'var(--surface-primary)', padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Local Model</div>
            <div style={{ fontWeight: 600, fontSize: '0.88rem', color: 'var(--text-primary)' }}>Qwen2.5:3b (Ollama)</div>
          </div>
          <div style={{ background: 'var(--surface-primary)', padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Persistence</div>
            <div style={{ fontWeight: 600, fontSize: '0.88rem', color: 'var(--text-primary)' }}>SQLite with Foreign Keys</div>
          </div>
          <div style={{ background: 'var(--surface-primary)', padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Frontend Framework</div>
            <div style={{ fontWeight: 600, fontSize: '0.88rem', color: 'var(--text-primary)' }}>React 19 + Vite</div>
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button className="s5-btn s5-btn-secondary" onClick={onClose}>
            Close Specifications
          </button>
        </div>
      </div>
    </div>
  );
}
