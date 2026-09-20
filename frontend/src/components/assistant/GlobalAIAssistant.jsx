import React, { useState, useRef, useEffect } from 'react';

/**
 * GlobalAIAssistant - Sticky bottom-right Meeting Intelligence Agent
 * Answers natural language questions about all loaded meetings, actions, decisions, and blockers.
 */
export default function GlobalAIAssistant({
  meetings = [],
  actionItems = [],
  decisions = [],
  issues = [],
  onSelectMeeting,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      sender: 'ai',
      text: "Hello! I am your Meeting Intelligence Agent. Ask me anything about your meetings, overdue action items, decisions, or unresolved risks.",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isOpen]);

  const quickPrompts = [
    "What is overdue or urgent?",
    "What are our critical blockers?",
    "Who has the most tasks?",
    "Summarize recent key decisions",
  ];

  const handleSend = (textToSend) => {
    const promptText = (textToSend || query).trim();
    if (!promptText) return;

    const userMsg = {
      id: Date.now().toString(),
      sender: 'user',
      text: promptText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setQuery('');
    setIsTyping(true);

    // AI Query Engine over loaded workspace dataset
    setTimeout(() => {
      const response = processQuery(promptText.toLowerCase(), {
        meetings,
        actionItems,
        decisions,
        issues,
      });

      const aiMsg = {
        id: (Date.now() + 1).toString(),
        sender: 'ai',
        text: response.text,
        items: response.items,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, aiMsg]);
      setIsTyping(false);
    }, 450);
  };

  const processQuery = (q, data) => {
    // 1. Overdue or urgent tasks
    if (q.includes('overdue') || q.includes('urgent') || q.includes('today') || q.includes('attention')) {
      const urgentActions = data.actionItems.filter((a) => {
        const dl = (a.deadline || '').toLowerCase();
        return (
          a.status !== 'completed' &&
          (dl.includes('today') || dl.includes('overdue') || dl.includes('yesterday') || dl.includes('asap') || dl.includes('wednesday'))
        );
      });

      if (urgentActions.length === 0) {
        return {
          text: "Great news! There are currently no overdue or urgent action items flagged across your meetings.",
        };
      }

      return {
        text: `Found ${urgentActions.length} action item(s) requiring immediate attention:`,
        items: urgentActions.slice(0, 5).map((a) => ({
          title: a.task,
          subtitle: `👤 ${a.assignee || 'Unassigned'} • 📅 ${a.deadline || 'No date'}`,
          type: 'action',
          id: a.id,
          meeting_id: a.meeting_id,
        })),
      };
    }

    // 2. Blockers & Risks
    if (q.includes('blocker') || q.includes('issue') || q.includes('risk') || q.includes('open issues')) {
      if (data.issues.length === 0) {
        return { text: "No unresolved blockers or risks found across the logged meetings." };
      }
      return {
        text: `There are ${data.issues.length} active blockers / open issues currently logged:`,
        items: data.issues.slice(0, 5).map((iss) => ({
          title: iss.issue || iss.topic || 'Unresolved Issue',
          subtitle: `Status: ${iss.status || 'Open'} • Severity: High`,
          type: 'issue',
          id: iss.id,
          meeting_id: iss.meeting_id,
        })),
      };
    }

    // 3. Workload / Who has tasks
    if (q.includes('who') || q.includes('workload') || q.includes('most tasks') || q.includes('assignee')) {
      const counts = {};
      data.actionItems.forEach((a) => {
        const person = a.assignee || 'Unassigned';
        counts[person] = (counts[person] || 0) + 1;
      });

      const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
      if (sorted.length === 0) {
        return { text: "No assigned action items found in the system yet." };
      }

      const summary = sorted.map(([name, count]) => `• **${name}**: ${count} task(s)`).join('\n');
      return {
        text: `Here is the current task distribution across team members:\n\n${summary}`,
      };
    }

    // 4. Decisions
    if (q.includes('decision') || q.includes('decide') || q.includes('agreed')) {
      if (data.decisions.length === 0) {
        return { text: "No confirmed decisions have been recorded yet." };
      }
      return {
        text: `Here are ${Math.min(4, data.decisions.length)} key decisions locked across meetings:`,
        items: data.decisions.slice(0, 5).map((d) => ({
          title: d.decision,
          subtitle: `Status: Confirmed ✓`,
          type: 'decision',
          id: d.id,
          meeting_id: d.meeting_id,
        })),
      };
    }

    // Default overview
    return {
      text: `Across your workspace, I am currently tracking:\n• ▣ **${data.meetings.length} Meetings** analyzed\n• ✓ **${data.actionItems.length} Action Items** (${data.actionItems.filter((a) => a.status === 'completed').length} completed)\n• ◆ **${data.decisions.length} Confirmed Decisions**\n• ⚠ **${data.issues.length} Open Issues / Blockers**\n\nHow can I assist you with these records?`,
    };
  };

  return (
    <div className="global-ai-assistant">
      {/* Floating Launcher Button */}
      {!isOpen && (
        <button
          type="button"
          className="ai-assistant-fab"
          onClick={() => setIsOpen(true)}
          title="Open Meeting Intelligence Assistant"
        >
          <span className="ai-fab-sparkle">✦</span>
          <span className="ai-fab-label">Meeting AI</span>
          {issues.length > 0 && <span className="ai-fab-badge">{issues.length}</span>}
        </button>
      )}

      {/* Assistant Flyout Window */}
      {isOpen && (
        <div className="ai-assistant-window">
          {/* Header */}
          <div className="ai-assistant-header">
            <div className="ai-header-title">
              <span className="ai-header-icon">✦</span>
              <div>
                <h4>Meeting Intelligence</h4>
                <span className="ai-status-indicator">Online • Local Grounding</span>
              </div>
            </div>
            <button
              type="button"
              className="ai-close-btn"
              onClick={() => setIsOpen(false)}
              title="Close Assistant"
            >
              ✕
            </button>
          </div>

          {/* Quick Prompt Chips */}
          <div className="ai-chips-bar">
            {quickPrompts.map((p, idx) => (
              <button
                key={idx}
                type="button"
                className="ai-prompt-chip"
                onClick={() => handleSend(p)}
              >
                {p}
              </button>
            ))}
          </div>

          {/* Messages Body */}
          <div className="ai-messages-container">
            {messages.map((m) => (
              <div key={m.id} className={`ai-message-bubble ${m.sender === 'ai' ? 'msg-ai' : 'msg-user'}`}>
                {m.sender === 'ai' && <div className="bubble-avatar">✦</div>}
                <div className="bubble-content">
                  <p className="bubble-text" style={{ whiteSpace: 'pre-line' }}>{m.text}</p>

                  {/* Render linked items if any */}
                  {Array.isArray(m.items) && m.items.length > 0 && (
                    <div className="bubble-items-list">
                      {m.items.map((it, i) => (
                        <div
                          key={i}
                          className="bubble-item-card"
                          onClick={() => {
                            if (it.meeting_id && onSelectMeeting) {
                              onSelectMeeting(it.meeting_id);
                              setIsOpen(false);
                            }
                          }}
                        >
                          <span className="bubble-item-title">{it.title}</span>
                          <span className="bubble-item-sub">{it.subtitle}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  <span className="bubble-time">{m.timestamp}</span>
                </div>
              </div>
            ))}

            {isTyping && (
              <div className="ai-message-bubble msg-ai">
                <div className="bubble-avatar">✦</div>
                <div className="bubble-typing-dots">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Footer */}
          <form
            className="ai-input-form"
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
          >
            <input
              type="text"
              className="ai-input-field"
              placeholder="Ask about tasks, decisions, blockers..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <button
              type="submit"
              className="ai-send-btn"
              disabled={!query.trim() || isTyping}
            >
              ➤
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
