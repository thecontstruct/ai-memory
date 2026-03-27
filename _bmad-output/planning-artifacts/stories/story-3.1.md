---
id: "3.1"
title: "Create Gemini session_start.py adapter"
epic: "Gemini CLI Adapter"
sprint: 1
status: ready
effort: M
depends_on: ["1.3", "1.4"]
traces_to: ["FR-201", "FR-601", "FR-602", "FR-603"]
---

# Story 3.1: Create Gemini `session_start.py` adapter

## 1. User Story
As a Gemini CLI user, I want relevant memories injected at the start of each session, so that the AI has project-specific context without me having to repeat it.

## 2. Acceptance Criteria
- [ ] `src/memory/adapters/gemini/__init__.py` exists
- [ ] Given a synthetic Gemini `SessionStart` stdin fixture for a project with seeded Qdrant data, stdout parses as JSON and contains `hookSpecificOutput.additionalContext` with at least 1 retrieved memory
- [ ] Given an empty Qdrant index, adapter exits 0 with `{"hookSpecificOutput": {"additionalContext": ""}}` on stdout
- [ ] Given Qdrant unreachable, adapter exits 0 with empty `additionalContext` and no exception on stderr
- [ ] Given malformed stdin JSON, adapter exits 0 with valid empty JSON output
- [ ] `cwd` is resolved using `resolve_cwd()` fallback chain; test covers payload where `cwd` is absent
- [ ] Per NFR-101 procedure: 10 sequential invocations with fixed synthetic fixtures against Qdrant seeded with ≥100 points; wall-clock from stdin closed to stdout flush; p95 < 3000ms and p99 < 5000ms
- [ ] Nothing other than valid JSON is written to stdout (logging goes to stderr only)

## 3. Technical Context
### Files to Create/Modify
- `src/memory/adapters/gemini/__init__.py` — create as empty package marker
- `src/memory/adapters/gemini/session_start.py` — create the adapter
- `src/memory/adapters/schema.py` — add `normalize_gemini_event()` to this shared module
- `src/memory/adapters/tests/test_gemini_session_start.py` — create unit and performance tests

### Architecture References
- §2 Data Flow Retrieval Path — defines the full execution sequence: normalize → validate → background_agent check → detect_project → MemorySearch → inject_with_priority → stdout JSON
- §2 Canonical Event Schema — `ide_source` must be `"gemini"` in the normalized event
- §3 Session ID Resolution Strategy — `resolve_session_id()` fallback chain applies
- §3 CWD Resolution Strategy — `resolve_cwd(payload, "gemini")` fallback chain applies; Gemini falls back to `GEMINI_CWD` env var

### Standards to Follow
- Files: `snake_case.py` (project-context.md)
- Functions: `snake_case` (project-context.md)
- Tests: `test_*.py` files with `test_` prefix (project-context.md)
- No new pip dependencies (architecture §1)
- structlog for all logging; logging goes to stderr only, never stdout (project-context.md)

## 4. Dependencies
- Story 1.3 must complete first — `resolve_session_id()` and `resolve_cwd()` must exist in `schema.py`
- Story 1.4 must complete first — `validate_canonical_event()` and `fork_to_background()` must exist; `normalize_gemini_event()` follows the same pattern as `normalize_claude_event()`

## 5. Out of Scope
- Gemini `after_tool_capture.py` (capture path) — Story 3.2
- Gemini `error_detection.py` and `error_pattern_capture.py` — Story 3.3
- Gemini `pre_compress.py` — Story 3.4
- TOML command templates — Story 3.5
- Registering this adapter in `.gemini/settings.json` — Epic 6

## 6. Implementation Notes
- Add `normalize_gemini_event()` to `src/memory/adapters/schema.py` (not in the gemini/ adapter directory) — it is a shared normalizer like `normalize_claude_event()`
- `normalize_gemini_event()` maps Gemini-native fields to canonical: `session_id`, `transcript_path`, `cwd` (via `resolve_cwd(payload, "gemini")`), `hook_event_name` (Gemini `"SessionStart"` → canonical `"SessionStart"`), `timestamp`, sets `ide_source="gemini"`
- Gemini `SessionStart` stdin fields to expect: `session_id`, `transcript_path`, `cwd`, `hook_event_name` (native: `"SessionStart"`), `timestamp`
- Empty-context payload is `{"hookSpecificOutput": {"additionalContext": ""}}` — used for: empty results, Qdrant unreachable, malformed stdin, background agent (architecture §2 retrieval path)
- All errors must be caught and logged to stderr via structlog; adapter must always exit 0 (non-blocking per architecture §2)
- Use existing `MemorySearch.search()` and `inject_with_priority()` pipeline functions — do not reimplement retrieval
- `is_background_agent` defaults to `False` for Gemini — Gemini does not have this field; if present in payload, use it; otherwise `False`
- Stdout must be flushed explicitly: `print(json.dumps(output)); sys.stdout.flush()` before `sys.exit(0)`

## 7. Definition of Done
- [ ] All acceptance criteria pass
- [ ] Unit tests written and passing
- [ ] No linter errors
- [ ] Code reviewed
