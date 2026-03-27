---
id: "1.4"
title: "Add normalize_claude_event() and fork_to_background() to schema.py"
epic: "Canonical Schema and Shared Infrastructure"
sprint: 1
status: ready
effort: S
depends_on: ["1.1", "1.2", "1.3"]
traces_to: ["FR-101", "FR-102", "NFR-103", "NFR-201"]
---

# Story 1.4: Add `normalize_claude_event()` and `fork_to_background()` to `schema.py`

## 1. User Story
As a platform developer, I want a Claude Code-specific normalizer and a shared background fork utility, so that Claude Code adapters and all future IDE adapters can translate native payloads to canonical events and spawn pipeline scripts without reimplementing these patterns.

## 2. Acceptance Criteria
- [ ] `normalize_claude_event(raw, hook_event_name)` returns a canonical dict with all required fields populated
- [ ] Returned dict has `ide_source == "claude"`
- [ ] `tool_name` is passed through `normalize_mcp_tool_name()` before being set in the returned dict
- [ ] `fork_to_background(canonical_event, pipeline_script_path)` spawns `subprocess.Popen` with `start_new_session=True`, passes canonical event JSON to stdin, and returns immediately
- [ ] `fork_to_background()` uses `args=[...]` list form — never `shell=True`
- [ ] `fork_to_background()` sets `CLAUDE_SESSION_ID` in the subprocess env from `canonical_event["session_id"]`
- [ ] Unit test asserts `fork_to_background()` raises no exception and the spawned process receives the correct JSON via stdin

## 3. Technical Context
### Files to Create/Modify
- `src/memory/adapters/schema.py` — add `normalize_claude_event()` and `fork_to_background()`
- `src/memory/adapters/tests/test_schema.py` — add unit tests for both functions

### Architecture References
- §2 Claude Code Normalizer — provides the complete `normalize_claude_event()` reference implementation (~10 lines); implement it verbatim
- §2 How Adapters Plug In — defines the `fork_to_background()` contract: `args=[...]` list, `start_new_session=True`, `stdout=subprocess.DEVNULL`, `stderr=subprocess.DEVNULL`
- §4 No Shell Interpolation — confirms `args=[...]` form is required for NFR-201; `shell=True` is explicitly forbidden

### Standards to Follow
- Files: `snake_case.py` (project-context.md)
- Functions: `snake_case` (project-context.md)
- Tests: `test_*.py` files with `test_` prefix on functions (project-context.md)
- No new pip dependencies — `subprocess`, `sys`, `os`, `json` are stdlib (architecture §1)

## 4. Dependencies
- Story 1.1 must complete first — `schema.py` file must exist
- Story 1.2 must complete first — `normalize_claude_event()` calls `normalize_mcp_tool_name()`
- Story 1.3 must complete first — `normalize_claude_event()` calls `resolve_session_id()` and `resolve_cwd()`

## 5. Out of Scope
- `normalize_gemini_event()`, `normalize_cursor_event()`, `normalize_codex_event()` — these are added in their respective adapter stories (3.1, 4.1, 5.1)
- Migrating Claude Code hook scripts to use this normalizer — Story 2.1
- Updating `.claude/settings.json` paths — Story 2.2

## 6. Implementation Notes
- `normalize_claude_event()` reference from architecture §2: calls `resolve_session_id(raw)`, `resolve_cwd(raw, "claude")`, passes `tool_name` through `normalize_mcp_tool_name()` with fallback to original (`mcp_name or tool_name`), sets `ide_source="claude"`
- `fork_to_background()` must set `stdout=subprocess.DEVNULL` and `stderr=subprocess.DEVNULL` — matching the existing `post_tool_capture.py` fork pattern (architecture §2)
- `fork_to_background()` must set `CLAUDE_SESSION_ID` in the subprocess environment: `env={**os.environ, "CLAUDE_SESSION_ID": canonical_event["session_id"]}` — existing pipeline scripts (e.g., `store_async.py`, `InjectionSessionState`) read this env var
- `fork_to_background()` writes canonical event as JSON to subprocess stdin via `Popen.communicate()` or `Popen.stdin.write()` + close — do not keep the process open
- The unit test for `fork_to_background()` can use a short-lived subprocess (e.g., `python -c "import sys; sys.stdin.read()"`) to verify no exception is raised; use `subprocess.PIPE` capture in the test to verify JSON is passed correctly

## 7. Definition of Done
- [ ] All acceptance criteria pass
- [ ] Unit tests written and passing
- [ ] No linter errors
- [ ] Code reviewed
