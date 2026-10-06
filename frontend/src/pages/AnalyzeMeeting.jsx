import React, { useState, useRef } from "react";
import api from "../services/api";
import { Icon } from "../components/icons/Icons";
import PipelineProgress from "../components/pipeline/PipelineProgress";
import TitleSelectionPanel from "../components/TitleSelectionPanel";

const SAMPLE_TRANSCRIPTS = {
  annual_fest: {
    title: "Annual Fest Coordination",
    text: "[Meeting: Annual Fest Planning | Attendees: Priya, Meera, Vikram, Aditya]\nPriya: Alright, let us get started, today we are talking about annual fest planning.\nAditya: Someone needs to book the auditorium, it can not wait too long.\nVikram: True, we will confirm the booking by Thursday.\nPriya: Actually, sorry, I meant before the weekend, not what I said earlier.\nVikram: Meera, can you look into it - we need to set up the registration desk?\nMeera: I will set up the registration desk sometime next week.\nAditya: What should we do about the event date?\nPriya: Let us stick with the event date we discussed earlier.\nAditya: Okay, let us finalize the event date then, that is settled.\nVikram: Any update on the guest travel plans?\nPriya: The guest travel plans are still not confirmed. We are waiting to hear back.\nMeera: The budget approval is still not confirmed from finance.\nVikram: Aditya, would you be able to coordinate with campus security?\nAditya: Aditya will coordinate with campus security by Friday.\nMeera: Just circling back about booking the auditorium, are we still on track?\nPriya: Yeah, on it, will update the group soon.\nVikram: I think that covers it for today. Meeting adjourned.",
  },
  tech_hackathon: {
    title: "Technical Hackathon Sprint",
    text: "[Meeting: Technical Hackathon Sprint | Attendees: Rahul, Sneha, Ankit, Divya]\nRahul: Welcome team. We have 3 weeks until the 24-hour campus hackathon.\nSneha: The problem statements from sponsoring companies have arrived.\nAnkit: I will review and upload the problem statements to GitHub by Monday.\nDivya: We need high-speed Wi-Fi access tokens for 150 participants from IT department.\nRahul: Divya, can you submit the official IT requisition by tomorrow 5 PM?\nDivya: Yes, I will submit the network access request tomorrow.\nSneha: What about the catering arrangements for midnight snacks?\nRahul: That is still pending administrative quote approval.\nAnkit: Decision: let us use Discord as the primary mentor communication channel.\nSneha: Agreed, Discord is officially chosen.\nRahul: Excellent. Let us sync again this Thursday.",
  },
  design_review: {
    title: "Design Syndicate Poster Review",
    text: "[Meeting: Design Syndicate Review | Attendees: Maya, Karan, Rohan]\nMaya: Today we are approving the social media posters for orientation week.\nKaran: The main banner layout is finished, but we need high-res club logos.\nMaya: Karan, please export the SVG vector assets by Wednesday evening.\nKaran: Done, I will export the vectors Wednesday.\nRohan: What about the print shop quotation for vinyl stickers?\nMaya: The sticker pricing is still unconfirmed, waiting for vendor response.\nRohan: Decision: we will proceed with the dark indigo color theme for all materials.\nMaya: Perfect, theme settled. Great session everyone.",
  },
};

const BRACKET_RE = /\[Meeting:\s*([^|\]]+?)(?:\s*\|[^\]]*)?]/i;

function extractMetadataSuggestions(transcriptText) {
  if (!transcriptText || !transcriptText.trim()) {
    return { suggestions: [], detectedDate: "", detectedTime: "" };
  }

  const rawLines = transcriptText.split(/\r?\n/);
  const nonEmptyLines = rawLines.map((l) => l.trim()).filter(Boolean);
  const headerBlock = rawLines.slice(0, 15).join("\n");
  const suggestions = [];

  // 1. Bracket format: [Meeting: Annual Fest Planning | Attendees: ...]
  const bracketMatch = BRACKET_RE.exec(headerBlock);
  if (bracketMatch) {
    suggestions.push({ text: bracketMatch[1].trim(), type: "extracted" });
  }

  // 2. Labeled headers (Meeting: ..., **Meeting:** ..., Subject: ..., Topic: ..., Title: ...)
  if (suggestions.length === 0) {
    for (const line of nonEmptyLines.slice(0, 8)) {
      const cleanLine = line.replace(/^\s*[*#_~`]+\s*|\s*[*#_~`]+\s*$/g, "").trim();
      const match = /^(?:Meeting|Subject|Topic|Title|Re)\s*[:\-]\s*(.+)$/i.exec(cleanLine);
      if (match) {
        const raw = match[1].replace(/^\s*[*#_~`]+\s*|\s*[*#_~`]+\s*$/g, "").trim();
        if (!/^\d/.test(raw) && raw.length > 3) {
          suggestions.push({ text: raw, type: "extracted" });
          break;
        }
      }
    }
  }

  // 3. Markdown Heading / Bold Title / Standalone Title at top
  if (suggestions.length === 0 && nonEmptyLines.length > 0) {
    const firstLine = nonEmptyLines[0];
    const cleanFirst = firstLine.replace(/^\s*[*#_~`]+\s*|\s*[*#_~`]+\s*$/g, "").trim();

    // Check if it's not a metadata line or dialogue line
    const isMetadataLine = /^(?:Date|Time|Attendees?|Present|Location|Schedule|Agenda)\s*[:\-]/i.test(cleanFirst);
    const isSpeakerLine = /^[A-Z][a-zA-Z\s]{1,25}:/i.test(cleanFirst);

    if (!isMetadataLine && !isSpeakerLine && cleanFirst.length > 3 && cleanFirst.length <= 120) {
      const isMdTitle = /^#{1,6}\s+|\*{2}|_{2}/.test(firstLine);
      const nextLine = nonEmptyLines[1] || "";
      const isFollowedByMetaOrDialogue = /^(?:\*{0,2}(?:Date|Time|Attendees?|Present|Location|Schedule|Agenda)\*{0,2}\s*[:\-])|^[A-Z][a-zA-Z\s]{1,25}:/i.test(nextLine);

      if (isMdTitle || isFollowedByMetaOrDialogue) {
        suggestions.push({ text: cleanFirst, type: "extracted" });
      }
    }
  }

  // 4. Keyword suggestions fallback
  if (suggestions.length === 0) {
    const firstFewLines = nonEmptyLines.slice(0, 5).join(" ");
    if (/annual\s+fest/i.test(firstFewLines)) {
      suggestions.push({ text: "Annual Fest Planning", type: "suggested" });
    } else if (/hackathon/i.test(firstFewLines)) {
      suggestions.push({ text: "Technical Hackathon Sprint", type: "suggested" });
    } else if (/design|poster|syndicate/i.test(firstFewLines)) {
      suggestions.push({ text: "Design Syndicate Review", type: "suggested" });
    } else if (/budget|finance/i.test(firstFewLines)) {
      suggestions.push({ text: "Budget & Finance Review", type: "suggested" });
    } else if (/pricing|product\s+sync|atlas/i.test(firstFewLines)) {
      suggestions.push({ text: "Weekly Product Sync", type: "suggested" });
    }
  }

  // Extract detected date and time
  let detectedDate = "";
  let detectedTime = "";

  // Date detection supporting **Date:**, Date:, Date/Time:, etc.
  for (const line of nonEmptyLines.slice(0, 10)) {
    const dateMatch = /\*{0,2}(?:Date(?:\s*(?:&|\/)\s*Time)?)\*{0,2}\s*[:\-]?\*{0,2}\s*([^\n\r,]+(?:,\s*\d{4}|\s+\d{4}|\/\d{2,4}|-\d{2,4}))/i.exec(line);
    if (dateMatch) {
      detectedDate = dateMatch[1].replace(/[*_~`]/g, "").trim();
      break;
    }
  }

  // Time detection supporting **Time:**, Time:, Schedule:, etc.
  for (const line of nonEmptyLines.slice(0, 10)) {
    const timeMatch = /\*{0,2}(?:Time|Schedule)\*{0,2}\s*[:\-]?\*{0,2}\s*([^\n\r*]+)/i.exec(line);
    if (timeMatch) {
      detectedTime = timeMatch[1].replace(/[*_~`]/g, "").trim();
      break;
    }
  }

  return { suggestions, detectedDate, detectedTime };
}

export default function AnalyzeMeeting({ onMeetingCreated, onCancel }) {
  const [transcript, setTranscript] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [showTitlePanel, setShowTitlePanel] = useState(false);
  const [titleSuggestions, setTitleSuggestions] = useState([]);
  const [detectedDate, setDetectedDate] = useState("");
  const [detectedTime, setDetectedTime] = useState("");
  const fileInputRef = useRef(null);
  const errorMessage = error && typeof error === "object" ? error.message : error;
  const errorTitle = error && typeof error === "object" && error.status === 400
    ? "Transcript needs attention"
    : "Analysis could not be completed";

  const handleAnalyzeClick = (e) => {
    if (e) e.preventDefault();
    if (!transcript.trim()) {
      setError("Please provide a meeting transcript before analyzing.");
      return;
    }
    setError(null);
    const meta = extractMetadataSuggestions(transcript);
    setTitleSuggestions(meta.suggestions);
    setDetectedDate(meta.detectedDate);
    setDetectedTime(meta.detectedTime);
    setShowTitlePanel(true);
  };

  const handleMetadataConfirmed = async ({ title, date: confirmedDate, time: confirmedTime }) => {
    setShowTitlePanel(false);
    await submitToApi(title, confirmedDate, confirmedTime);
  };

  const handleTitleSkip = async () => {
    setShowTitlePanel(false);
    await submitToApi(null, null, null);
  };

  const submitToApi = async (title, confirmedDate, confirmedTime) => {
    setIsProcessing(true);
    setError(null);
    try {
      let payload = transcript.trim();
      let headerPrefix = "";
      if (title && !BRACKET_RE.test(payload.slice(0, 200))) {
        headerPrefix += "[Meeting: " + title;
        if (confirmedDate) headerPrefix += " | Date: " + confirmedDate;
        if (confirmedTime) headerPrefix += " | Time: " + confirmedTime;
        headerPrefix += "]\n";
        payload = headerPrefix + payload;
      }
      const response = await api.createMeeting(payload);
      if (response && response.meeting_id) {
        onMeetingCreated(response.meeting_id, response);
      } else {
        throw new Error("Unexpected server response format.");
      }
    } catch (err) {
      console.error("Analysis error:", err);
      setError({
        message: err.message || "We could not analyze this meeting. Ensure the backend server and Ollama are active.",
        status: err.status,
      });
      setIsProcessing(false);
    }
  };

  const handleFileDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    const files = e.dataTransfer.files;
    if (files && files[0]) readFile(files[0]);
  };

  const handleFileSelect = (e) => {
    const files = e.target.files;
    if (files && files[0]) readFile(files[0]);
  };

  const readFile = (file) => {
    const reader = new FileReader();
    reader.onload = (event) => {
      setTranscript(event.target.result || "");
      setError(null);
    };
    reader.readAsText(file);
  };

  const loadSample = (key) => {
    const sample = SAMPLE_TRANSCRIPTS[key];
    if (sample) {
      setTranscript(sample.text);
      setError(null);
    }
  };

  if (showTitlePanel) {
    return (
      <div style={{ maxWidth: "820px", margin: "0 auto" }}>
        <TitleSelectionPanel
          suggestions={titleSuggestions}
          detectedDate={detectedDate}
          detectedTime={detectedTime}
          onConfirm={handleMetadataConfirmed}
          onSkip={handleTitleSkip}
        />
      </div>
    );
  }

  return (
    <div style={{ maxWidth: "820px", margin: "0 auto" }}>
      <div style={{ marginBottom: "var(--space-6)" }}>
        <h1 style={{ fontSize: "1.75rem", fontWeight: 700, letterSpacing: "-0.02em", color: "var(--text-primary)" }}>
          Analyze a Meeting
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", marginTop: "2px" }}>
          Add your meeting conversation to extract summaries, commitments, decisions, and blockers.
        </p>
      </div>

      {error && (
        <div style={{ background: "var(--semantic-red-bg)", border: "1px solid var(--semantic-red-border)", borderRadius: "var(--radius-md)", padding: "14px 18px", marginBottom: "var(--space-6)", display: "flex", alignItems: "center", justifyContent: "space-between", gap: "var(--space-3)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <Icon name="issues" size={18} style={{ color: "var(--semantic-red)" }} />
            <div>
              <div style={{ fontWeight: 600, color: "#FCA5A5", fontSize: "0.88rem" }}>{errorTitle}</div>
              <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "2px" }}>{errorMessage}</div>
            </div>
          </div>
          <button className="s5-btn s5-btn-secondary s5-btn-sm" onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      {isProcessing ? (
        <PipelineProgress isProcessing={isProcessing} />
      ) : (
        <div className="s5-card">
          <form onSubmit={handleAnalyzeClick}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 14px", background: "var(--surface-elevated)", borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)", marginBottom: "var(--space-6)", flexWrap: "wrap", gap: "8px" }}>
              <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", display: "flex", alignItems: "center", gap: "6px" }}>
                <Icon name="sparkles" size={14} style={{ color: "var(--accent-primary)" }} />
                <span>Not sure what to upload? Try an example:</span>
              </span>
              <div style={{ display: "flex", gap: "6px" }}>
                <button type="button" className="s5-btn s5-btn-secondary s5-btn-sm" onClick={() => loadSample("annual_fest")}>Annual Fest (SC001)</button>
                <button type="button" className="s5-btn s5-btn-secondary s5-btn-sm" onClick={() => loadSample("tech_hackathon")}>Hackathon</button>
                <button type="button" className="s5-btn s5-btn-secondary s5-btn-sm" onClick={() => loadSample("design_review")}>Design Review</button>
              </div>
            </div>

            <div style={{ marginBottom: "var(--space-5)" }}>
              <input type="file" ref={fileInputRef} style={{ display: "none" }} accept=".txt,.csv" onChange={handleFileSelect} />
              <div className={"s5-dropzone" + (isDragOver ? " drag-active" : "")} onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }} onDragLeave={() => setIsDragOver(false)} onDrop={handleFileDrop} onClick={() => fileInputRef.current && fileInputRef.current.click()}>
                <div style={{ width: "40px", height: "40px", borderRadius: "var(--radius-md)", background: "var(--surface-elevated)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--accent-primary)" }}>
                  <Icon name="upload-cloud" size={20} />
                </div>
                <div>
                  <div style={{ fontSize: "0.92rem", fontWeight: 600, color: "var(--text-primary)" }}>Drop transcript file here, or click to browse</div>
                  <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginTop: "2px" }}>Supported text formats: .txt, .csv, raw conversation notes</div>
                </div>
              </div>
            </div>

            <div style={{ marginBottom: "var(--space-6)" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "6px" }}>
                <label style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--text-primary)" }}>
                  Meeting Conversation Dialogue <span style={{ color: "var(--semantic-red)" }}>*</span>
                </label>
                <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>{transcript.length} characters</span>
              </div>
              <textarea className="s5-textarea" placeholder={"Or paste conversation dialogue directly here...\n\nPriya: Let us confirm the venue by Friday.\nVikram: I will handle the venue booking.\nAditya: What about the guest travel plans?"} value={transcript} onChange={(e) => setTranscript(e.target.value)} required />
            </div>

            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: "var(--space-2)" }}>
              <button type="button" className="s5-btn s5-btn-ghost" onClick={onCancel}>Cancel</button>
              <button type="submit" id="btn-submit-analyze" className="s5-btn s5-btn-primary s5-btn-lg" disabled={!transcript.trim()}>
                <Icon name="sparkles" size={16} />
                <span>Analyze Meeting</span>
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
