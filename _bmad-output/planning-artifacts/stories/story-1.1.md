---
id: "1.1"
title: "Create adapters/schema.py with canonical event schema and validation"
epic: "Canonical Schema and Shared Infrastructure"
sprint: 1
status: ready
effort: M
depends_on: []
traces_to: ["FR-101", "FR-102"]
---

# Story 1.1: Create `adapters/schema.py` with canonical event schema and validation

## 1. User Story
As a platform developer, I want a canonical event schema module with a shared validation function, so that every IDE adapter has a single interface contract with the pipeline.

## 2. Acceptance Criteria
- [ ] `src/memory/adapters/__init__.py` exists as an empty package marker
- [ ] `src/memory/adapters/schema.py` defines `VALID_IDE_SOURCES = {"claude", "gemini", "cursor", "codex"}` and `VALID_HOOK_EVENTS` covering all canonical hook names listed in the architecture
- [ ] `validate_canonical_event()` raises `ValueError` when any of `session_id`, `cwd`, `hook_event_name`, or `ide_source` is missing or not a `str`
- [ ] `validate_canonical_event()` raises `ValueError` when `ide_source` is not in `VALID_IDE_SOURCES`
- [ ] `validate_canonical_event()` raises `ValueError` when `hook_event_name` is not in `VALID_HOOK_EVENTS`
- [ ] Optional fields (`tool_name`, `transcript_path`, `trigger`) pass validation when `None` or a `str`; raise `ValueError` for any other type
- [ ] `tool_input` passes validation when `None` or `dict`; raises `ValueError` otherwise
- [ ] For `hook_event_name == "UserPromptSubmit"`, `user_prompt` must be a non-empty `str` — `validate_canonical_event()` raises `ValueError` if it is `None`, empty, or non-`str`; for every other `hook_event_name`, `user_prompt` must be `None` — raises `ValueError` if non-`None`
- [ ] `is_background_agent` passes validation when `bool`; raises `ValueError` for non-`bool` types
- [ ] `tool_response` passes validation when `None`, `str`, or `dict`; raises `ValueError` otherwise
- [ ] `context_usage_percent` passes when `None` or `float`; raises `ValueError` for `int` or other types
- [ ] `context_tokens` and `context_window_size` pass when `None` or `int`; raise `ValueError` otherwise
- [ ] Unit tests for all of the above cases live in `src/memory/adapters/tests/test_schema.py` and all pass

## 3. Technical Context
### Files to Create/Modify
- `src/memory/adapters/__init__.py` — create as empty package marker
- `src/memory/adapters/schema.py` — create with `VALID_IDE_SOURCES`, `VALID_HOOK_EVENTS`, and `validate_canonical_event()`
- `src/memory/adapters/tests/__init__.py` — create as empty package marker
- `src/memory/adapters/tests/test_schema.py` — create unit tests for all validation cases

### Architecture References
- §2 Canonical Event Schema — defines the exact `canonical_event` dict structure and all field types
- §2 Canonical Event Schema — provides the complete `validate_canonical_event()` reference implementation verbatim; implement this exactly

### Standards to Follow
- Files: `snake_case.py` (project-context.md)
- Functions: `snake_case` (project-context.md)
- Constants: `UPPER_SNAKE` (project-context.md)
- Tests: `test_*.py` files in `tests/` with `test_` prefix on functions (project-context.md)
- No new pip dependencies — stdlib only (architecture §1)

## 4. Dependencies
- No story dependencies — this is the foundation for all other stories

## 5. Out of Scope
- `normalize_mcp_tool_name()` — Story 1.2
- `resolve_session_id()` and `resolve_cwd()` — Story 1.3
- `normalize_claude_event()` and `fork_to_background()` — Story 1.4
- Any normalizer functions for Gemini, Cursor, or Codex

## 6. Implementation Notes
- The canonical event is a plain `dict`, not a Pydantic model — matches the existing `post_tool_capture.py` pattern (architecture §2)
- `VALID_HOOK_EVENTS` must include: `"SessionStart"`, `"PostToolUse"`, `"PreToolUse"`, `"PreCompact"`, `"UserPromptSubmit"`, `"SessionEnd"`, `"Stop"` (architecture §2)
- `VALID_IDE_SOURCES` must include: `"claude"`, `"gemini"`, `"cursor"`, `"codex"` (architecture §2)
- The `validate_canonical_event()` reference implementation is in architecture §2 — implement it verbatim, do not rewrite it
- `user_prompt` validation has asymmetric logic: required non-empty str for `UserPromptSubmit`, must be `None` for all other hook events — both cases raise `ValueError` on violation
- `context_usage_percent` must reject `int` (i.e. `isinstance(value, float)` is False for `int` in Python 3) — this is intentional per the AC

## 7. Definition of Done
- [ ] All acceptance criteria pass
- [ ] Unit tests written and passing
- [ ] No linter errors
- [ ] Code reviewed
