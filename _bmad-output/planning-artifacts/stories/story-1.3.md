---
id: "1.3"
title: "Add resolve_session_id() and resolve_cwd() to schema.py"
epic: "Canonical Schema and Shared Infrastructure"
sprint: 1
status: ready
effort: S
depends_on: ["1.1"]
traces_to: ["FR-601", "FR-602"]
---

# Story 1.3: Add `resolve_session_id()` and `resolve_cwd()` to `schema.py`

## 1. User Story
As a platform developer, I want shared session ID and CWD resolution functions, so that every IDE adapter resolves these values through an identical documented fallback chain instead of each reimplementing the logic.

## 2. Acceptance Criteria
- [ ] `resolve_session_id()` returns native `session_id` when present and non-empty
- [ ] `resolve_session_id()` falls back to `conversation_id` when `session_id` is absent (Cursor)
- [ ] `resolve_session_id()` falls back to `os.path.splitext(os.path.basename(transcript_path))[0]` when both are absent
- [ ] `resolve_session_id()` falls back to a UUID-5 string derived from `f"{cwd}:{timestamp_iso_utc}"` when all three are absent
- [ ] `resolve_cwd()` returns native `cwd` when present and non-empty
- [ ] `resolve_cwd()` falls back to `workspace_roots[0]` for `ide_source="cursor"`
- [ ] `resolve_cwd()` falls back to `CURSOR_PROJECT_DIR` env var for Cursor when `workspace_roots` is also absent
- [ ] `resolve_cwd()` falls back to `GEMINI_CWD` env var for `ide_source="gemini"`
- [ ] `resolve_cwd()` falls back to `os.getcwd()` when all other sources are absent
- [ ] Unit tests cover each fallback level for each IDE source and pass

## 3. Technical Context
### Files to Create/Modify
- `src/memory/adapters/schema.py` — add `resolve_session_id()` and `resolve_cwd()`
- `src/memory/adapters/tests/test_schema.py` — add unit tests covering every fallback level for each IDE

### Architecture References
- §3 Session ID Resolution Strategy — priority table and complete `resolve_session_id()` reference implementation; implement verbatim
- §3 CWD Resolution Strategy — priority table and complete `resolve_cwd()` reference implementation; implement verbatim

### Standards to Follow
- Files: `snake_case.py` (project-context.md)
- Functions: `snake_case` (project-context.md)
- Tests: `test_*.py` files with `test_` prefix on functions (project-context.md)
- No new pip dependencies — `os`, `uuid`, `datetime` are stdlib (architecture §1)

## 4. Dependencies
- Story 1.1 must complete first because these functions are added to the `schema.py` file created in 1.1

## 5. Out of Scope
- Setting `os.environ["CLAUDE_SESSION_ID"]` — that responsibility belongs to Story 1.4's `normalize_claude_event()` and `fork_to_background()`, which call `resolve_session_id()` and then set the env var before pipeline calls
- `normalize_claude_event()` and `fork_to_background()` — Story 1.4

## 6. Implementation Notes
- Architecture §3 specifies the fallback 4 for `session_id` uses `uuid.uuid5(uuid.NAMESPACE_URL, f"{cwd}:{ts}")` where `ts` is `datetime.now(tz=timezone.utc).isoformat()` — use this exactly, not `hashlib.sha256`
- The epics-and-stories.md description mentions `hashlib.sha256` as the fallback — the architecture §3 reference implementation uses `uuid.uuid5` which is the authoritative source; use `uuid.uuid5`
- `resolve_session_id()` accepts a `payload: dict` parameter (the raw IDE stdin dict before normalization)
- `resolve_cwd()` accepts `payload: dict` and `ide_source: str` parameters
- For `resolve_cwd()`, Gemini falls back to `os.environ.get("GEMINI_CWD")` — not a positional fallback into `workspace_roots` (Gemini has no workspace_roots field)
- Test the `os.getcwd()` fallback by patching both the payload and env vars to be absent

## 7. Definition of Done
- [ ] All acceptance criteria pass
- [ ] Unit tests written and passing
- [ ] No linter errors
- [ ] Code reviewed
