---
id: "3.2"
title: "Create Gemini after_tool_capture.py adapter"
epic: "Gemini CLI Adapter"
sprint: 1
status: ready
effort: M
depends_on: ["1.2", "1.4", "1.5", "3.1"]
traces_to: ["FR-202", "FR-208", "FR-601", "FR-602"]
---

# Story 3.2: Create Gemini `after_tool_capture.py` adapter

## 1. User Story
As a Gemini CLI user, I want code patterns and tool results captured after each file edit or MCP tool call, so that the memory system learns from my work across sessions.

## 2. Acceptance Criteria
- [ ] Given a Gemini `AfterTool` payload with `tool_name: "write_file"`, adapter forks to background and exits 0 within 500ms
- [ ] Background process stores a Qdrant point within 10s of adapter exit
- [ ] Given `tool_name: "mcp_postgres_query"`, stored Qdrant point has `tool_name == "mcp:postgres:query"`
- [ ] Given `tool_name: "mcp_slack_send"`, stored Qdrant point has `tool_name == "mcp:slack:send"`
- [ ] Given malformed stdin, adapter exits 0 without raising an unhandled exception
- [ ] Adapter emits no output to stdout (exit 0, no JSON required for AfterTool)
- [ ] Tool name mapping is applied: `"write_file"` → `"Write"`, `"edit_file"` → `"Edit"`, `"create_file"` → `"Write"`
- [ ] Per NFR-102 procedure: 50 sequential invocations with fixed synthetic fixtures against Qdrant seeded with ≥100 points; wall-clock from stdin closed to process exit; p95 < 500ms and p99 < 1000ms

## 3. Technical Context
### Files to Create/Modify
- `src/memory/adapters/gemini/after_tool_capture.py` — create the adapter
- `src/memory/adapters/tests/test_gemini_after_tool_capture.py` — create unit and performance tests
- `src/memory/adapters/schema.py` — extend `normalize_gemini_event()` (added in Story 3.1) to handle `AfterTool` payload fields including `tool_response.llmContent` mapping

### Architecture References
- §2 Data Flow Capture Path — defines the capture sequence: normalize → validate → `fork_to_background(canonical_event, store_async_path)` → exit 0
- §2 MCP Tool Name Normalization — `normalize_mcp_tool_name()` is called on `tool_name` before setting in canonical event
- §2 Canonical Event Schema — `tool_response` is `dict | str | None`; `tool_name` is canonical after normalization

### Standards to Follow
- Files: `snake_case.py` (project-context.md)
- Functions: `snake_case` (project-context.md)
- Tests: `test_*.py` files with `test_` prefix (project-context.md)
- No new pip dependencies (architecture §1)
- No stdout output for capture-path adapters (architecture §2 capture path)

## 4. Dependencies
- Story 1.2 must complete first — `normalize_mcp_tool_name()` is called during normalization
- Story 1.4 must complete first — `fork_to_background()` and `validate_canonical_event()` must exist
- Story 1.5 must complete first — `adapters/pipeline/store_async.py` must exist at the path `fork_to_background()` will reference
- Story 3.1 must complete first — `normalize_gemini_event()` is added to `schema.py` in Story 3.1; this story extends it for `AfterTool` fields

## 5. Out of Scope
- `error_detection.py` and `error_pattern_capture.py` for `run_shell_command` — Story 3.3
- Registering matchers in `.gemini/settings.json` — Epic 6
- Pre-compress / session-end capture — Stories 3.3 and 3.4

## 6. Implementation Notes
- Gemini `AfterTool` stdin fields to expect: `tool_name` (Gemini-native), `tool_input`, `tool_response` (may be nested as `{"llmContent": "..."}`)
- `normalize_gemini_event()` for `AfterTool` must map `tool_response.llmContent` to the canonical `tool_response` field (architecture §2): `tool_response = raw.get("tool_response", {}).get("llmContent") if isinstance(raw.get("tool_response"), dict) else raw.get("tool_response")`
- Tool name mapping (Gemini → canonical) to apply before MCP check:
  - `"write_file"` → `"Write"`
  - `"edit_file"` → `"Edit"`
  - `"create_file"` → `"Write"`
  - `"read_file"` → `"Read"`
  - `"run_shell_command"` → `"Bash"`
  - MCP names matching `^mcp_` → pass through `normalize_mcp_tool_name()`
- Adapter must not write anything to stdout; all error handling must log to stderr and exit 0
- `fork_to_background()` path: `adapters/pipeline/store_async.py`
- Performance requirement (NFR-102): p95 < 500ms measured from stdin close to process exit; the fork itself is immediate, so most time is process startup overhead — ensure no blocking I/O before the fork

## 7. Definition of Done
- [ ] All acceptance criteria pass
- [ ] Unit tests written and passing
- [ ] No linter errors
- [ ] Code reviewed
