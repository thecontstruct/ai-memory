---
id: "3.3"
title: "Create Gemini error_detection.py and error_pattern_capture.py adapters"
epic: "Gemini CLI Adapter"
sprint: 1
status: ready
effort: S
depends_on: ["1.4", "1.5", "3.1"]
traces_to: ["FR-202", "FR-601", "FR-602"]
---

# Story 3.3: Create Gemini `error_detection.py` and `error_pattern_capture.py` adapters

## 1. User Story
As a Gemini CLI user, I want shell command errors automatically captured and stored as error patterns, so that the memory system recognizes recurring failures and helps me avoid repeating them.

## 2. Acceptance Criteria
- [ ] Given a Gemini `AfterTool` payload with `tool_name: "run_shell_command"` and output containing an error pattern, `error_detection.py` forks to `error_store_async.py` and exits 0 within 500ms
- [ ] `error_pattern_capture.py` forks to the error pattern pipeline and exits 0 within 500ms
- [ ] Both adapters exit 0 with no output on stdout for non-error payloads
- [ ] Both adapters exit 0 on malformed stdin without unhandled exceptions

## 3. Technical Context
### Files to Create/Modify
- `src/memory/adapters/gemini/error_detection.py` — create the adapter
- `src/memory/adapters/gemini/error_pattern_capture.py` — create the adapter
- `src/memory/adapters/tests/test_gemini_error_adapters.py` — create unit tests

### Architecture References
- §5 IDE Config File Generation (Gemini settings.json example) — shows `run_shell_command` matcher with `sequential: true` and both scripts listed in order
- §6 Directory Structure — confirms `error_detection.py` and `error_pattern_capture.py` exist under `adapters/gemini/`
- §2 Data Flow Capture Path — both adapters follow the capture path: normalize → validate → `fork_to_background()` → exit 0

### Standards to Follow
- Files: `snake_case.py` (project-context.md)
- Functions: `snake_case` (project-context.md)
- Tests: `test_*.py` files with `test_` prefix (project-context.md)
- No stdout output for capture-path adapters (architecture §2)

## 4. Dependencies
- Story 1.4 must complete first — `fork_to_background()` and `validate_canonical_event()` must exist
- Story 1.5 must complete first — `adapters/pipeline/error_store_async.py` must exist at the path these adapters will reference
- Story 3.1 must complete first — `normalize_gemini_event()` is in `schema.py` (added in Story 3.1); these adapters reuse it

## 5. Out of Scope
- Registering these adapters under the `run_shell_command` matcher in `.gemini/settings.json` — Epic 6
- Error pattern extraction logic — reused from existing `hooks_common.py` (`extract_error_signature`)
- Any changes to `error_store_async.py` — it accepts canonical events as-is

## 6. Implementation Notes
- Both adapters are structurally mirrors of their Claude Code equivalents (`adapters/claude/error_detection.py` and `error_pattern_capture.py`) — after migration in Story 2.1 those files can serve as implementation references
- Both scripts call `normalize_gemini_event(raw, "PostToolUse")` — the Gemini hook that fires for `run_shell_command` is `AfterTool`, which maps to canonical `"PostToolUse"`
- `error_detection.py` forks to `adapters/pipeline/error_store_async.py`
- `error_pattern_capture.py` forks to the appropriate error pattern pipeline script (check the existing Claude Code equivalent for the correct pipeline script path)
- Both scripts in `.gemini/settings.json` will be registered under `"matcher": "run_shell_command"` with `"sequential": true` — this story creates the scripts only; config registration is Epic 6
- For non-error payloads, both adapters should exit 0 immediately without forking — check `tool_response` for error indicators using `hooks_common.extract_error_signature()` if applicable, consistent with the Claude Code equivalents

## 7. Definition of Done
- [ ] All acceptance criteria pass
- [ ] Unit tests written and passing
- [ ] No linter errors
- [ ] Code reviewed
