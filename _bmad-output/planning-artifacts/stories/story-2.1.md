---
id: "2.1"
title: "Migrate Claude Code hook scripts to adapters/claude/"
epic: "Claude Code Adapter Migration"
sprint: 1
status: ready
effort: M
depends_on: ["1.5"]
traces_to: ["FR-101", "FR-102", "NFR-301"]
---

# Story 2.1: Migrate Claude Code hook scripts to `adapters/claude/`

## 1. User Story
As a platform developer, I want all Claude Code hook scripts moved to `adapters/claude/` and updated to normalize through the canonical schema, so that Claude Code is a peer adapter like Gemini and Cursor rather than a special-cased entry point with direct pipeline access.

## 2. Acceptance Criteria
- [ ] `src/memory/adapters/claude/__init__.py` exists
- [ ] All hook scripts listed in the architecture's `claude/` directory exist under `src/memory/adapters/claude/`
- [ ] Each migrated script reads `json.loads(sys.stdin.read())`, calls `normalize_claude_event(raw, "<EventName>")`, and calls `validate_canonical_event(event)` before any pipeline call
- [ ] No script reads raw hook fields directly from `sys.stdin` without going through the normalizer
- [ ] `.claude/hooks/scripts/` directory is empty or removed after migration
- [ ] Existing Claude Code integration test suite passes with zero new failures (SC-07)

## 3. Technical Context
### Files to Create/Modify
- `src/memory/adapters/claude/__init__.py` — create as empty package marker
- `src/memory/adapters/claude/session_start.py` — moved and updated from `.claude/hooks/scripts/session_start.py`
- `src/memory/adapters/claude/post_tool_capture.py` — moved and updated
- `src/memory/adapters/claude/context_injection_tier2.py` — moved and updated
- `src/memory/adapters/claude/error_detection.py` — moved and updated
- `src/memory/adapters/claude/error_pattern_capture.py` — moved and updated
- `src/memory/adapters/claude/first_edit_trigger.py` — moved and updated
- `src/memory/adapters/claude/new_file_trigger.py` — moved and updated
- `src/memory/adapters/claude/pre_compact_save.py` — moved and updated
- `src/memory/adapters/claude/user_prompt_capture.py` — moved and updated
- `src/memory/adapters/claude/agent_response_capture.py` — moved and updated
- `src/memory/adapters/claude/best_practices_retrieval.py` — moved and updated
- `src/memory/adapters/claude/langfuse_stop_hook.py` — moved and updated
- `src/memory/adapters/claude/manual_save_memory.py` — moved and updated
- `.claude/hooks/scripts/` — empty/remove all hook entry point scripts after move

### Architecture References
- §2 Claude Code as Adapter — before/after code example showing the ~5-line stdin parsing change per hook
- §5 Adapter Script Installation — lists all scripts expected under `adapters/claude/`
- §2 Data Flow Capture Path — confirms the correct call sequence: `normalize_claude_event()` → `validate_canonical_event()` → `fork_to_background()`

### Standards to Follow
- Files: `snake_case.py` (project-context.md)
- Functions: `snake_case` (project-context.md)
- Tests: `test_*.py` files with `test_` prefix on functions (project-context.md)

## 4. Dependencies
- Story 1.5 must complete first because: (a) `normalize_claude_event()` and `validate_canonical_event()` from Story 1.4 must exist, and (b) `adapters/pipeline/` must exist so `fork_to_background()` can reference the moved pipeline scripts

## 5. Out of Scope
- Updating `.claude/settings.json` command paths — Story 2.2
- Any changes to downstream pipeline logic (`store_async.py`, `error_store_async.py`, etc.) — pipeline is unchanged by this story

## 6. Implementation Notes
- This is a ~5-line change per script per the architecture's before/after example in §2
- The `hook_event_name` argument to `normalize_claude_event()` must match the canonical name for that script:
  - `session_start.py` → `"SessionStart"`
  - `post_tool_capture.py` → `"PostToolUse"`
  - `pre_compact_save.py` → `"PreCompact"`
  - `user_prompt_capture.py` → `"UserPromptSubmit"`
  - `error_detection.py`, `error_pattern_capture.py` → `"PostToolUse"` (these are also PostToolUse hooks for Bash)
  - `langfuse_stop_hook.py` → `"Stop"`
- The change per script: replace `hook_input = json.loads(sys.stdin.read())` + direct field access with `raw = json.loads(sys.stdin.read()); event = normalize_claude_event(raw, "<EventName>"); validate_canonical_event(event)` then use `event["field"]` instead of `hook_input.get("field")`
- Use `mv` (shell) to move files — preserves git history
- `fork_to_background()` calls in migrated scripts must reference pipeline scripts at their new `adapters/pipeline/` paths

## 7. Definition of Done
- [ ] All acceptance criteria pass
- [ ] Unit tests written and passing
- [ ] No linter errors
- [ ] Code reviewed
