"""Prompt definitions for meeting analysis matching the proven benchmark rules."""


def build_intent_tagging_prompt(transcript: str) -> str:
    """Build the lightweight first-pass prompt used to separate intent types."""

    return f"""Classify this meeting transcript before information extraction.

Return ONLY valid JSON with exactly these fields:
{{
  "meeting_archetype": "corporate_sync | student_casual | technical_design | sales | other",
  "utterance_tags": [
    {{"speaker": "Speaker name or null", "text": "short verbatim excerpt", "intent": "proposal | final_decision | assigned_task | unresolved_issue | context"}}
  ]
}}

Rules:
- Tag only evidence-bearing utterances; omit greetings and filler.
- proposal means tentative, conditional, or approval-dependent language. It is not a final_decision.
- final_decision requires explicit agreement, approval, confirmation, or settled consensus.
- assigned_task requires a concrete deliverable and a named or self-committing owner.
- unresolved_issue covers blockers, pending input, risks, and undecided matters.
- A technical design choice can be a final_decision; a person delivering a design document is an assigned_task.
- Keep event dates in the decision evidence and preparation deadlines in task evidence.
- Do not invent speakers, text, decisions, tasks, or dates.

TRANSCRIPT:
{transcript}

JSON OUTPUT:"""


def build_meeting_analysis_prompt(transcript: str, intent_context: str | None = None) -> str:
    """Build the meeting-analysis prompt optimized for Qwen 2.5 3B."""

    tagged_context = ""
    if intent_context:
        tagged_context = f"""
### PASS 1 INTENT GUIDANCE
Use these tags as a filter, not as facts. Extract decisions only from
`final_decision` evidence, actions only from `assigned_task` evidence, and
unresolved issues only from `proposal` or `unresolved_issue` evidence. Keep
the original transcript as the source of truth and ignore unsupported tags.

{intent_context}
"""

    return f"""Analyze the meeting transcript below strictly according to the following rules.

{tagged_context}

### RULES:

1. SUMMARY
- Produce a concise 3–5 sentence meeting summary synthesizing the concluded state and final consensus.
- Preserve original meaning and tense.
- Action items are planned/pending tasks, NOT completed actions.
- Do not use past-tense verbs to describe pending tasks.
- Accurately mention the meeting purpose, important upcoming commitments, confirmed decisions, and open issues/risks.
- Ground all approvals and statements strictly to the actual speakers. Never state that an external or absent team (e.g. Finance, Legal) approved something when the speaker merely mentioned needing or seeking their sign-off.
- Do not invent facts, people, dates, deadlines, or outcomes.

2. ACTION ITEMS & OWNER BINDING
Extract EVERY concrete task, deliverable, assignment, or agreed prerequisite step that is explicitly assigned or committed to by a speaker.

EXPLICIT ASSIGNMENT LIST PRECEDENCE:
- Treat a transcript wrap-up headed "Action Items", "Next Steps", "Assignments", or similar as the authoritative action-item list.
- Extract every independently numbered or named task in that wrap-up, preserving its named owner and explicit deadline. For example, "Priya: Draft the retry-queue design by Wednesday, September 23rd" is an action item owned by Priya with deadline 2026-09-23.
- Do not replace a wrap-up task with the broader decision that motivated it. A decision such as "use WebSockets with exponential backoff" is not the same as Priya's assigned design-document task.
- Do not omit an explicitly assigned wrap-up task merely because the same topic also appears in the decisions section.

An action item requires:
- a concrete engineering/operational task or deliverable
- an explicit person responsible OR an explicit speaker commitment. A concrete task may remain unassigned when the transcript explicitly says "someone needs to" or equivalent; use owner null rather than inventing a person (e.g.:
  * Assign tasks to the person who explicitly self-commits ("I will do X", "I'll handle this", "My action item is X", "I can take that") -> Owner is strictly that committing speaker;
  * When a speaker addresses someone with an instruction or request that is accepted/acknowledged (e.g., "Dev, please update the status page logic") -> Owner is that person;
  * When tasks are listed with names in a structured list or wrap-up (e.g., "1. Maya: Build pipeline circuit breaker"), the named person is the Owner)
- an expectation that the task will be performed

STRICT ACTION ITEM GUARDRAILS:
- IN-MEETING COMPLETIONS (TEMPORAL AWARENESS): If a participant states they have ALREADY completed a task during the call (e.g., "I just tried it", "I'm pushing the hotfix right now", "Done"), DO NOT mark it as a pending action item. Either mark it with status "completed" or exclude it. Ensure pending action items capture actual future/post-meeting deliverables (e.g., sharing deployment links, verifying build once deployed).
- OWNER BINDING: If Maya says "I'll build it", Maya is the owner, NOT someone else who raised the issue. NEVER assign tasks to the meeting host, facilitator, or Incident Commander simply because they summarized or requested the task at the end.
- NO META-TASKS: Do NOT extract meta-instructions or meeting administrative commands (e.g., "log the action items", "assign tasks to log", "note down the meeting minutes", "record these in Jira") as action items. Do NOT assign fake tasks to facilitators simply because they asked the team to record or log items.
- NO ISSUE RESTATEMENTS: Do NOT turn an unresolved topic into an action merely by writing "look into", "follow up on", "confirm", "check", or "address". These are actions only when a speaker explicitly accepts or is assigned that work.
- NO DECISION RESTATEMENTS: Do NOT turn a confirmed decision into an action. Phrases such as "finalize the event date", "finalize the ticket price", or "choose the venue" belong in decisions when settled, not action_items.
- CATEGORY EVIDENCE: Every action must have transcript evidence of a person or group committing to perform it. A topic being discussed, needed, pending, or mentioned is not enough.
- UNASSIGNED CONCRETE TASKS: "Someone needs to arrange X" is a concrete action with owner null when no later speaker accepts it. Do not discard it, assign it to the facilitator, or convert it into an unresolved issue.
- CORRECTIONS AND ACCEPTANCE: When a request is followed by a speaker's explicit acceptance, extract the accepted core task and use the latest corrected deadline. A later acknowledgement such as "we are on it" is not a separate action.
- CONDITIONAL COMMITMENTS IN RISKS: Treat an explicit commitment inside a risk statement as a pending action item when a speaker says they will do something if a condition occurs (for example, "I'll escalate to the student affairs office by Wednesday if the portal stays down"). Extract the concrete action, bind it to the committing speaker, and preserve the stated deadline; do not leave it only as an unresolved risk.
- NO INCIDENT / TIMELINE TIMESTAMPS AS DEADLINES: Incident event timestamps, alert firing times (e.g. "11:02 AM", "14:30 UTC"), log timestamps, and dialogue timestamps indicate when past events occurred, NOT task deadlines. NEVER treat past incident times as deadlines. If no explicit future calendar date is mentioned for a task, deadline MUST be null.

Do NOT extract general guidance or ongoing responsibilities unless they contain a concrete deliverable.
Normally exclude:
- "Keep us posted."
- "Flag risks early."
- "Stay aligned."
- "Monitor this."
- "Keep an eye on this."
- "Be aware of the risk."

Every action item MUST contain exactly these 4 keys:
"task", "owner", "deadline", "status".

task:
- Include ONLY the core task (e.g., "Build the CI/CD pipeline circuit breaker", "Update status page auto-trigger logic").
- Do NOT include deadline/time expressions in the task. Strip out time phrases like "today", "by tomorrow", "on Thursday", "by next Monday", "by EOD today".
- CRITICAL: Never include the owner or deadline in the task text. For example, output "Arrange laptops for the coding session" rather than "Karthik: Arrange laptops for the coding session by Thursday evening".
- A conversational acknowledgement such as "we are on it", "will update the group soon", or "are we still on track" is not a new action unless the speaker explicitly accepts a concrete deliverable.

owner:
- Extract the person explicitly responsible or committing (e.g. "Maya", "Dev", "Carlos").
- If the speaker says "I will..." or "I'll...", that speaker is the owner.
- If responsibility is genuinely unassigned, use null.
- Never infer ownership merely because someone discussed the topic or facilitated the meeting.
- A date in the meeting header is never an implicit action deadline. Use a deadline only when that action's own dialogue explicitly gives a date or temporal cue.
- Do not extract an unassigned reminder for everyone to attend or join a future meeting. A follow-up meeting is an event, not an action item, unless someone is assigned to organize it.

deadline:
- ALL action item deadlines MUST be formatted strictly as ISO standard dates: YYYY-MM-DD (e.g., "2026-09-20", "2026-09-22", "2026-09-23", "2026-10-05").
- FORWARD RELATIVE DATE MATH RULE:
  * When calculating relative weekdays ("by Wednesday", "by Tuesday", "this Friday", "tomorrow", "by EOD"), ALWAYS compute strictly forward from the Meeting Header Date.
  * "tonight" means the meeting date itself, formatted as that date in ISO YYYY-MM-DD.
  * For example, if the meeting took place on Sunday, September 20, 2026:
    - "today", "tonight", or "today EOD" -> "2026-09-20"
    - "tomorrow" -> "2026-09-21"
    - "by Tuesday" -> "2026-09-22" (September 20 + 2 days = September 22)
    - "by Wednesday" -> "2026-09-23" (September 20 + 3 days = September 23)
    - "this Friday" -> "2026-09-25" (September 20 + 5 days = September 25)
  * NEVER output a deadline date that occurs BEFORE the meeting header date (e.g., NEVER output 2026-09-03 or 2026-09-14 for a meeting held on September 20, 2026).
- If no explicit future calendar deadline exists, use null.
- Never invent "ASAP", "Ongoing", "Soon", etc.

status:
- Always "pending" unless the transcript explicitly states the task has already been completed.

3. DECISIONS (STRICT TAXONOMY & DECISION DISCRIMINATOR)
A Decision is an organizational agreement, policy, schedule target, vendor choice, scope cutoff, or architectural design choice confirmed by the group or meeting lead (e.g., "Launch pricing experiment on September 29, 2026 (pending bugs/QA)", "Keep current paywall layout for the experiment", "Monitor conversion daily and decide on changes after seven days of data").
Format: A flat array of strings.
- CLEAN DECISION TEXT: Strip operational lead-ins such as "Decision –", "Decision:", or "Decision -" from the output string so it begins with the actual decision prose.
Include ALL confirmed strategic choices, launch date policies, milestone/freeze agreements, technical scope alignments, and spending policies explicitly agreed, approved, confirmed, finalized, or decided by the group or meeting lead.
Verbal agreements and consensus choices count as confirmed decisions even if the word "decide" is not used.
REJECT PROPOSALS: If a proposal was contested, modified, or postponed, do NOT classify it as a confirmed decision.
- DECISION EXCLUSION: A sentence assigning, requesting, preparing, sending, booking, testing, arranging, or describing what someone needs to do is an action item, never a decision, even when it contains a deadline.
- DEFERRALS ARE NOT DECISIONS: Statements such as "we have not finalized the date", "let's decide based on the poll", "we'll confirm later", "tentatively Friday", or "not decided yet" are unresolved issues or pending inputs, NEVER decisions.
PENDING APPROVAL RULE: A proposed date, topic, budget, or plan is NOT a decision when the transcript says it is tentative, must be checked, needs confirmation, or awaits faculty/coordinator/external approval. Put that item in unresolved_issues instead. For example, "keep October 7th as a tentative date" plus "confirm with the faculty coordinator" means the event date is pending approval, not finalized.
FORMAT DECISIONS: When the group agrees on an event format, include the complete agreed format as one decision (for example, a one-day event with a morning workshop and afternoon project presentations). Do not omit a confirmed format merely because the date or topic is still pending.
TRANSCRIPT EVIDENCE: Write each decision from the actual transcript. Never copy wording from these instructions or reuse a phrase from another meeting. If no confirmed decision is supported, return [].

4. ACTIONS ARE NOT DECISIONS (DECISION DISCRIMINATOR & ZERO TASK/RISK OVERLAP)
DECISION DISCRIMINATOR:
- Ask: "Is this a structural policy/agreement, or is it an action item, conditional task, or risk mitigation?"
- NEVER classify individual tasks, operational actions, conditional action items, or risk mitigations as Key Decisions:
  * "Escalate billing provider's sandbox stability issue..." is an Action Item (#5), NOT a Key Decision.
  * "Hard freeze campaign creatives today..." is an operational risk mitigation strategy, NOT an independent Key Decision.
- If a person or team is assigned to execute or deliver it (e.g., "Priya Sharma will circulate...", "Dev will escalate..."), it belongs ONLY under Action Items.
- NEVER list an Action Item, conditional task, or deliverable handoff under Decisions. Key Decisions describe structural policies, milestone dates, vendors, or designs.

5. UNRESOLVED ISSUES, RISKS & CONSTRAINTS (ZERO-RISK HANDLING & ROUTINE MONITORING RULE)
Include matters that remain pending, undecided, awaiting external sign-off, or active technical/operational risks discussed in this meeting transcript.
- ROUTINE MONITORING VS. RISK: General statements like "Let's monitor the logs", "Keep an eye on metrics", or routine operational checks are ongoing operational follow-ups, NOT Open Issues or Risks. Only log explicit blockers, unresolved bugs, unanswered questions, or threats to timelines as Open Issues/Risks.
Format: A flat array of strings.
ZERO DATA CONTAMINATION & ZERO-RISK HANDLING: NEVER copy example text or invent risks/issues from other meetings. If no unresolved issues or active risks are present in this transcript, return an empty array []. NEVER generate a dummy risk item containing text like "No issues identified" or "No issues found".
TRANSCRIPT EVIDENCE: Write each issue from a matter actually discussed in this transcript. Do not use a generic fallback phrase when the transcript does not support it.
Do NOT output nested objects or dictionaries inside unresolved_issues. Output ONLY a flat list of strings.
Do NOT classify action items as unresolved issues.
Do NOT classify confirmed decisions as unresolved issues.
- RESOLUTION PRECEDENCE: If a topic is initially pending but a later speaker explicitly accepts or confirms the related task, keep the task and remove the resolved topic from unresolved_issues.

6. STRICT MUTUAL EXCLUSIVITY
Each extracted item must belong to ONE category only:
- ACTION ITEM: Something someone must do.
- DECISION: Something the group has settled or agreed.
- UNRESOLVED ISSUE: Something that remains unresolved, blocked, or a pending risk.
Never put the same semantic item into multiple categories.

7. CONDITIONAL DATES
A date used as a condition or threshold is NOT automatically the deadline of an action item unless the transcript explicitly states the task must be completed by that date.

8. RELATIVE DATE ANCHORING
- Read the meeting header date before resolving relative dates. Compute "tomorrow", named weekdays, and phrases such as "by Wednesday" strictly forward from that meeting date.
- For a meeting on September 21, 2026: "tomorrow" = 2026-09-22, Wednesday = 2026-09-23, Thursday = 2026-09-24, and Friday = 2026-09-25.
- Keep an event date separate from preparation deadlines. A poster draft due Wednesday must have deadline 2026-09-23, even if the event is tentatively planned for October 7.
- Preserve explicit relative deadlines attached to commitments: "I'll contact the coordinator tomorrow" is an action due 2026-09-22; do not move it to a later approval or event date.

9. MULTIPLE COMMITMENTS
Extract every independent commitment from a speaker's turn.

10. FOLLOW-UP MEETINGS
A scheduled future meeting is normally a FOLLOW-UP EVENT, not a strategic decision and not an action item, unless someone is tasked to organize/schedule it.

11. EVIDENCE & OWNER RESOLUTION
Base every extracted item directly on transcript evidence. Resolve first-person commitments using the speaker identity.

12. DEADLINE SEPARATION & ISO DATES
Always keep deadline information separate from task text and formatted in ISO YYYY-MM-DD.
Example:
Transcript Header: Date: September 20, 2026
Transcript: "Rahul will send the beta summary by September 23."
Correct:
task = "Send the beta summary"
owner = "Rahul Mehta"
deadline = "2026-09-23"
Incorrect:
task = "Send the beta summary by September 23"

13. FINAL SELF-CHECK
Before returning JSON, verify:
- Every action is a real concrete commitment with deadline formatted as YYYY-MM-DD or null computed forward from meeting header date.
- No confirmed decision appears as an action.
- No action or deliverable handoff appears as a decision.
- Every owner is supported by the transcript and bound to the actual committing speaker.
- Every decision and unresolved issue is supported by transcript evidence and uses wording specific to this meeting.
- No tentative proposal or pending approval appears in decisions.
- Confirmed event format/scope agreements are included even when the date or topic remains pending.
- Event dates and task deadlines are not confused with one another.
- In-meeting completed tasks are not marked as pending action items; pending action items are real upcoming deliverables.
- Routine monitoring (e.g. "monitor logs", "watch metrics") is not extracted as an unresolved issue or risk.
- If no risks exist, unresolved_issues is [].
- Do not repeat a concrete action item as an unresolved issue. Keep only the underlying blocker, risk, pending approval, or unanswered question.
- No invented facts are present.
- Each semantic item appears in only one category.

### OUTPUT FORMAT

Return ONLY valid JSON in exactly this structure:

{{
  "summary": "Concise 3-5 sentence meeting summary.",
  "action_items": [
    {{
      "task": "Clean task description without deadline words",
      "owner": "Owner name or null",
      "deadline": "YYYY-MM-DD or null",
      "status": "pending"
    }}
  ],
  "decisions": [
    "Settled decision text"
  ],
  "unresolved_issues": [
    "Unresolved issue text"
  ]
}}

No markdown formatting.
Do NOT use ``` or ```json.
No explanations outside the JSON.
No extra fields.

### TRANSCRIPT:
{transcript}

### JSON OUTPUT:"""


# Alias for backward compatibility
build_prompt = build_meeting_analysis_prompt