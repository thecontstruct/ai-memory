---
id: "3.4"
title: "Create Gemini pre_compress.py adapter"
epic: "Gemini CLI Adapter"
sprint: 1
status: ready
effort: S
depends_on: ["1.4", "1.5", "3.1"]
traces_to: ["FR-203"]
---

# Story 3.4: Create Gemini `pre_compress.py` adapter

## 1. User Story
As a Gemini CLI user, I want session summaries stored before each context compression, so that important decisions and patterns from long sessions are not lost when the context window is truncated.

## 2. Acceptance Criteria
- [ ] Given a synthetic Gemini `PreCompress` payload, adapter calls the pre_compact pipeline and a session summary point exists in Qdrant's `discussions` collection within 10s
- [ ] The stored point has `ide_source == "gemini"`
- [ ] Adapter exits 0 in all cases including Qdrant unavailable
- [ ] `trigger` field (`"auto"` or `"manual"`) is preserved in the canonical event and passed to the pipeline

## 3. Technical Context
### Files to Create/Modify
- `src/memory/adapters/gemini/pre_compress.py` — create the adapter
- `src/memory/adapters/tests/test_gemini_pre_compress.py` — create unit tests

### Architecture References
- §2 Data Flow Capture Path — adapter follows the capture path with the pre_compact pipeline as the target
- §5 Gemini config example — shows `PreCompress` hook with 60000ms timeout
- §6 Directory Structure — confirms `pre_compress.py` exists under `adapters/gemini/`

### Standards to Follow
- Files: `snake_case.py` (project-context.md)
- Functions: `snake_case` (project-context.md)
- Tests: `test_*.py` files with `test_` prefix (project-context.md)
- No new pip dependencies (architecture §1)

## 4. Dependencies
- Story 1.4 must complete first — `fork_to_background()` and `validate_canonical_event()` must exist
- Story 1.5 must complete first — the pre_compact pipeline script must exist under `adapters/pipeline/`
- Story 3.1 must complete first — `normalize_gemini_event()` is in `schema.py`; this story extends it to handle `PreCompress` fields

## 5. Out of Scope
- `pre_compact_save.py` pipeline script logic — that script already exists and is moved to `adapters/pipeline/` in Story 1.5
- Registering `PreCompress` hook in `.gemini/settings.json` — Epic 6

## 6. Implementation Notes
- `normalize_gemini_event()` must map Gemini `"PreCompress"` hook name to canonical `"PreCompact"` — the IDE-native name differs from the canonical name (architecture §2 hook name mapping table)
- Gemini `PreCompress` stdin fields to expect: `hook_event_name` (`"PreCompress"`), `session_id`, `transcript_path`, `cwd`, `trigger` (`"auto"` or `"manual"`)
- The `trigger` field must be preserved in the canonical event (`"auto"` or `"manual"`) and passed to the pipeline via `fork_to_background()` as part of the canonical event JSON — `pre_compact_save.py` reads this field
- Fork target: `adapters/pipeline/pre_compact_save.py` (or equivalent; check the Claude Code `pre_compact_save.py` for the correct pipeline script name)
- Adapter must exit 0 in all cases — wrap everything in try/except and log errors to stderr; Qdrant unavailable during pre-compress should never block Gemini's compression
- `ide_source="gemini"` in the canonical event ensures the stored `discussions` point carries the IDE provenance (the `ide_source` field in `store_async.py` handles this after Story 1.5)

## 7. Definition of Done
- [ ] All acceptance criteria pass
- [ ] Unit tests written and passing
- [ ] No linter errors
- [ ] Code reviewed
