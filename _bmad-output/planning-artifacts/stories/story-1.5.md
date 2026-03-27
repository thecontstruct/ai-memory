---
id: "1.5"
title: "Add ide_source to store_async.py payload and move pipeline scripts"
epic: "Canonical Schema and Shared Infrastructure"
sprint: 1
status: ready
effort: M
depends_on: ["1.4"]
traces_to: ["FR-102", "NFR-301"]
---

# Story 1.5: Add `ide_source` to `store_async.py` payload and move pipeline scripts

## 1. User Story
As a platform developer, I want the four background pipeline scripts relocated to `adapters/pipeline/` and `store_async.py` to persist `ide_source` metadata, so that every Qdrant point written through the capture path carries its IDE origin and all adapters share a single pipeline location.

## 2. Acceptance Criteria
- [ ] `src/memory/adapters/pipeline/__init__.py` exists
- [ ] All four pipeline scripts exist under `src/memory/adapters/pipeline/`: `store_async.py`, `error_store_async.py`, `user_prompt_store_async.py`, `agent_response_store_async.py`
- [ ] `store_async.py` includes `"ide_source": hook_input.get("ide_source", "claude")` in the chunk payload dict
- [ ] Unit test: after `store_async.py` processes a canonical event with `ide_source="gemini"`, the Qdrant point payload contains `ide_source == "gemini"` (use mocked Qdrant client)
- [ ] Unit test: after processing a canonical event with `ide_source="claude"`, the stored point contains `ide_source == "claude"`
- [ ] `pytest` run scoped to `store_async.py` tests exits 0 with zero failures

## 3. Technical Context
### Files to Create/Modify
- `src/memory/adapters/pipeline/__init__.py` — create as empty package marker
- `src/memory/adapters/pipeline/store_async.py` — moved from `.claude/hooks/scripts/store_async.py`; add `ide_source` line to payload dict
- `src/memory/adapters/pipeline/error_store_async.py` — moved from `.claude/hooks/scripts/error_store_async.py`
- `src/memory/adapters/pipeline/user_prompt_store_async.py` — moved from `.claude/hooks/scripts/user_prompt_store_async.py`
- `src/memory/adapters/pipeline/agent_response_store_async.py` — moved from `.claude/hooks/scripts/agent_response_store_async.py`
- `.claude/hooks/scripts/` — remove all four scripts after move (directory can be left empty or removed)

### Architecture References
- §3 `ide_source` Metadata Field — shows the exact `payload` dict in `store_async.py` with the `ide_source` line to add; use this reference implementation verbatim for the one-line change
- §5 Adapter Script Installation — defines `adapters/pipeline/` as the canonical location for IDE-agnostic background processors

### Standards to Follow
- Files: `snake_case.py` (project-context.md)
- Tests: `test_*.py` files with `test_` prefix on functions (project-context.md)

## 4. Dependencies
- Story 1.4 must complete first because `.claude/settings.json` command paths will be updated in Story 2.1 to point to `adapters/claude/` — the original `.claude/hooks/scripts/` path for the hook entry points (not pipeline scripts) must remain functional until 2.2 updates the config; the pipeline scripts can be moved now because they are called by path via `fork_to_background()` which will be updated to use `adapters/pipeline/` paths

## 5. Out of Scope
- Updating `.claude/settings.json` command paths for the hook entry scripts — Story 2.2
- Adding `ide_source` to `error_store_async.py`, `user_prompt_store_async.py`, or `agent_response_store_async.py` — these scripts may already have or not need `ide_source`; only `store_async.py` is required per the AC
- Backfilling existing Qdrant points without `ide_source` — NFR-302 explicitly defers this

## 6. Implementation Notes
- This is primarily a file move plus a one-line change in `store_async.py` per architecture §3
- Use `mv` (shell) to move files — preserves git history; do not read-and-rewrite
- The `ide_source` line to add in `store_async.py` is: `"ide_source": hook_input.get("ide_source", "claude"),` — the default `"claude"` ensures backward compatibility for any event that did not go through the new normalizer path
- `store_async.py` reads `hook_input` as a dict from stdin via `json.loads(sys.stdin.read())` — `ide_source` will be present in canonical events after Story 1.4 is complete
- The original `.claude/hooks/scripts/` directory is vacated by this story; Story 2.1 moves the hook entry point scripts to `adapters/claude/`
- For the unit test, mock `MemoryStorage` or the Qdrant client at the appropriate boundary and assert `payload["ide_source"]` equals the expected value

## 7. Definition of Done
- [ ] All acceptance criteria pass
- [ ] Unit tests written and passing
- [ ] No linter errors
- [ ] Code reviewed
