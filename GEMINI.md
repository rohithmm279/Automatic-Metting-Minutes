# S5 PROJECT — TOKEN OPTIMIZATION & SAFE EDITING RULES

## 1. COMMUNICATION
- Skip greetings, fluff, preambles, and repeated summaries.
- Start directly with actionable information.
- Do not output unchanged code.
- For code changes, prefer exact localized edits over full-file rewrites.
- Keep responses concise.

## 2. FILE & CODE ANALYSIS
- Read only the files and functions necessary for the requested task.
- For large files, inspect targeted sections rather than the entire file.
- Do not inspect unrelated files.
- Do not regenerate existing files unnecessarily.

## 3. CODE MODIFICATION
- Preserve the existing architecture and project structure.
- Make the smallest safe change that solves the requested problem.
- Do not refactor unrelated code.
- Do not rename working files, functions, APIs, database tables, or schemas unless explicitly requested.
- Preserve existing behavior unless the requested change requires otherwise.

## 4. TESTING
- Run only tests relevant to the change.
- For backend changes, run the existing test suite when appropriate.
- Do not run expensive Gemini/API benchmarks unless explicitly requested.
- Never consume external API quota for a task that can be verified locally.
- Do not repeatedly rerun successful tests without a reason.

## 5. API & AI SAFETY
- Never print, expose, commit, or modify API keys.
- Never hardcode secrets.
- Preserve Gemini primary/backup key handling.
- Preserve the current model configuration unless explicitly requested.
- Do not add additional Gemini API calls without explicit justification.
- Prefer local deterministic validation over extra AI calls.

## 6. PROJECT ARCHITECTURE
- Current AI flow:
  Transcript → preprocessing → ONE Gemini call → local validation → structured output
- Preserve Gemini primary → backup failover.
- Preserve local rule-based fallback.
- Preserve Pydantic schemas, SQLite persistence, FastAPI APIs, and frontend compatibility.
- Do not redesign the frontend unless explicitly requested.

## 7. OUTPUT
- Do not generate verbose comments or docstrings unless necessary.
- Do not create documentation, tests, scripts, or secondary files unless explicitly requested or required to verify a change.
- When reporting completed work, provide:
  1. Files changed
  2. What changed
  3. Tests run and result
  4. Any remaining issue

## 8. BENCHMARK PROTECTION
- Do not modify benchmark/evaluation logic unless explicitly requested.
- Do not delete existing benchmark results.
- Do not overwrite a successful benchmark accidentally.
- Use --fresh only when a fresh benchmark is explicitly requested.