---
project_name: ai-memory
feature: "FEATURE-001: Multi-IDE Support"
author: Phil Mahncke
date: 2026-03-27
version: "1.0"
status: draft
phase: "Phase 1"
prd_version: "1.1"
architecture_version: "1.0"
---

# Epics and Stories — FEATURE-001: Multi-IDE Support

## Table of Contents

1. [Epic 1: Canonical Schema and Shared Infrastructure](#epic-1-canonical-schema-and-shared-infrastructure)
2. [Epic 2: Claude Code Adapter Migration](#epic-2-claude-code-adapter-migration)
3. [Epic 3: Gemini CLI Adapter](#epic-3-gemini-cli-adapter)
4. [Epic 4: Cursor IDE Adapter](#epic-4-cursor-ide-adapter)
5. [Epic 5: Codex CLI Adapter](#epic-5-codex-cli-adapter)
6. [Epic 6: Installer and Config Generation](#epic-6-installer-and-config-generation)
7. [Epic 7: Integration Testing](#epic-7-integration-testing)
8. [Epic 8: Phase 2 — Keyword Triggers + Per-Turn Injection (Placeholder)](#epic-8-phase-2--keyword-triggers--per-turn-injection-placeholder)

---

## Epic 1: Canonical Schema and Shared Infrastructure

The canonical event schema is the foundation every adapter and pipeline script builds on. Nothing in Epics 2–5 can be built until the schema module, its normalizer functions, its validation function, and the `ide_source` pipeline change all exist and pass unit tests.

---

### Story 1.1: Create `adapters/schema.py` with canonical event schema and validation

**Epic:** Canonical Schema and Shared Infrastructure
**Traces to:** FR-101, FR-102
**Architecture:** §2 Canonical Event Schema
**Depends on:** None
**Estimated effort:** M

**Description:**
Create `src/memory/adapters/__init__.py` and `src/memory/adapters/schema.py` containing the canonical event dict definition, `VALID_IDE_SOURCES`, `VALID_HOOK_EVENTS`, and `validate_canonical_event()`. This module is the single interface contract between any IDE adapter and the pipeline.

**Acceptance Criteria:**
- [ ] `src/memory/adapters/__init__.py` exists as an empty package marker
- [ ] `src/memory/adapters/schema.py` defines `VALID_IDE_SOURCES = {"claude", "gemini", "cursor", "codex"}` and `VALID_HOOK_EVENTS` covering all canonical hook names listed in the architecture
- [ ] `validate_canonical_event()` raises `ValueError` when any of `session_id`, `cwd`, `hook_event_name`, or `ide_source` is missing or not a `str`
- [ ] `validate_canonical_event()` raises `ValueError` when `ide_source` is not in `VALID_IDE_SOURCES`
- [ ] `validate_canonical_event()` raises `ValueError` when `hook_event_name` is not in `VALID_HOOK_EVENTS`
- [ ] Optional fields (`tool_name`, `transcript_path`, `user_prompt`, `trigger`) pass validation when `None` or a `str`; raise `ValueError` for any other type
- [ ] `tool_response` passes validation when `None`, `str`, or `dict`; raises `ValueError` otherwise
- [ ] `context_usage_percent` passes when `None` or `float`; raises `ValueError` for `int` or other types
- [ ] `context_tokens` and `context_window_size` pass when `None` or `int`; raise `ValueError` otherwise
- [ ] Unit tests for all of the above cases live in `src/memory/adapters/tests/test_schema.py` and all pass

**Implementation Notes:**
- Module path: `src/memory/adapters/schema.py`
- Canonical event is a plain `dict`, not a Pydantic model — matches the existing `post_tool_capture.py` pattern
- `is_background_agent` is required for Cursor adapter logic but is not a required canonical field for validation (it defaults to `False`)

---

### Story 1.2: Add `normalize_mcp_tool_name()` to `schema.py`

**Epic:** Canonical Schema and Shared Infrastructure
**Traces to:** FR-101
**Architecture:** §2 MCP Tool Name Normalization
**Depends on:** Story 1.1
**Estimated effort:** S

**Description:**
Add `normalize_mcp_tool_name()` to `schema.py`. The function converts Gemini-format (`mcp_<server>_<tool>`) and Cursor-format (`MCP:<name>`) tool names to canonical `mcp:<server>:<tool>` format, and returns `None` for non-MCP tool names.

**Acceptance Criteria:**
- [ ] `normalize_mcp_tool_name("mcp_postgres_query")` returns `"mcp:postgres:query"`
- [ ] `normalize_mcp_tool_name("MCP:postgres_query")` returns `"mcp:unknown:postgres_query"`
- [ ] `normalize_mcp_tool_name("MCP:query")` returns `"mcp:unknown:query"`
- [ ] `normalize_mcp_tool_name("Write")` returns `None`
- [ ] `normalize_mcp_tool_name("mcp_slack_send")` returns `"mcp:slack:send"`
- [ ] All unit tests are in `test_schema.py` and pass

**Implementation Notes:**
- Use `re.match` per the architecture's reference implementation
- Gemini pattern: `^mcp_([^_]+)_(.+)$`; Cursor pattern: `^MCP:(.+)$`
- When Cursor format cannot determine the server, the server segment defaults to `"unknown"`

---

### Story 1.3: Add `resolve_session_id()` and `resolve_cwd()` to `schema.py`

**Epic:** Canonical Schema and Shared Infrastructure
**Traces to:** FR-601, FR-602
**Architecture:** §3 Session ID Resolution Strategy, §3 CWD Resolution Strategy
**Depends on:** Story 1.1
**Estimated effort:** S

**Description:**
Add `resolve_session_id()` and `resolve_cwd()` to `schema.py`. These functions implement the documented 4-level fallback chains so every adapter can call them identically instead of reimplementing the logic.

**Acceptance Criteria:**
- [ ] `resolve_session_id()` returns native `session_id` when present and non-empty
- [ ] `resolve_session_id()` falls back to `conversation_id` when `session_id` is absent (Cursor)
- [ ] `resolve_session_id()` falls back to `os.path.splitext(os.path.basename(transcript_path))[0]` when both are absent
- [ ] `resolve_session_id()` falls back to a 16-character hex string derived from `hashlib.sha256(f"{cwd}:{timestamp}")` when all three are absent
- [ ] `resolve_cwd()` returns native `cwd` when present and non-empty
- [ ] `resolve_cwd()` falls back to `workspace_roots[0]` for `ide_source="cursor"`
- [ ] `resolve_cwd()` falls back to `CURSOR_PROJECT_DIR` env var for Cursor when `workspace_roots` is also absent
- [ ] `resolve_cwd()` falls back to `GEMINI_CWD` env var for `ide_source="gemini"`
- [ ] `resolve_cwd()` falls back to `os.getcwd()` when all other sources are absent
- [ ] Unit tests cover each fallback level for each IDE source and pass

**Implementation Notes:**
- File: `src/memory/adapters/schema.py`
- `resolve_session_id()` sets `os.environ["CLAUDE_SESSION_ID"]` before returning — required for pipeline compatibility (FR-601)
- Use `hashlib` and `datetime` from stdlib; no new dependencies

---

### Story 1.4: Add `normalize_claude_event()` and `fork_to_background()` to `schema.py`

**Epic:** Canonical Schema and Shared Infrastructure
**Traces to:** FR-101, FR-102, NFR-103, NFR-201
**Architecture:** §2 Claude Code Normalizer, §2 How Adapters Plug In
**Depends on:** Story 1.1, Story 1.2, Story 1.3
**Estimated effort:** S

**Description:**
Add `normalize_claude_event()` and `fork_to_background()` to `schema.py`. `normalize_claude_event()` is the Claude Code-specific normalizer that maps native Claude stdin fields to the canonical event dict. `fork_to_background()` encapsulates the `subprocess.Popen(start_new_session=True)` pattern used by all capture adapters.

**Acceptance Criteria:**
- [ ] `normalize_claude_event(raw, hook_event_name)` returns a canonical dict with all required fields populated
- [ ] Returned dict has `ide_source == "claude"`
- [ ] `tool_name` is passed through `normalize_mcp_tool_name()` before being set in the returned dict
- [ ] `fork_to_background(canonical_event, pipeline_script_path)` spawns `subprocess.Popen` with `start_new_session=True`, passes canonical event JSON to stdin, and returns immediately
- [ ] `fork_to_background()` uses `args=[...]` list form — never `shell=True`
- [ ] `fork_to_background()` sets `CLAUDE_SESSION_ID` in the subprocess env from `canonical_event["session_id"]`
- [ ] Unit test asserts `fork_to_background()` raises no exception and the spawned process receives the correct JSON via stdin

**Implementation Notes:**
- File: `src/memory/adapters/schema.py`
- `fork_to_background()` must set `stdout=subprocess.DEVNULL`, `stderr=subprocess.DEVNULL`, matching the existing `post_tool_capture.py` fork pattern
- `normalize_claude_event()` matches the architecture's reference implementation exactly — ~10 lines

---

### Story 1.5: Add `ide_source` to `store_async.py` payload and move pipeline scripts

**Epic:** Canonical Schema and Shared Infrastructure
**Traces to:** FR-102, NFR-301
**Architecture:** §3 `ide_source` Metadata Field, §5 Adapter Script Installation
**Depends on:** Story 1.4
**Estimated effort:** M

**Description:**
Move the four background pipeline scripts (`store_async.py`, `error_store_async.py`, `user_prompt_store_async.py`, `agent_response_store_async.py`) from `.claude/hooks/scripts/` to `src/memory/adapters/pipeline/`. Add `"ide_source": hook_input.get("ide_source", "claude")` to the payload dict in `store_async.py` so that every Qdrant point written through the capture path carries the `ide_source` metadata field.

**Acceptance Criteria:**
- [ ] `src/memory/adapters/pipeline/__init__.py` exists
- [ ] All four pipeline scripts exist under `src/memory/adapters/pipeline/`
- [ ] `store_async.py` includes `"ide_source": hook_input.get("ide_source", "claude")` in the chunk payload dict
- [ ] Unit test: after `store_async.py` processes a canonical event with `ide_source="gemini"`, the Qdrant point payload contains `ide_source == "gemini"` (use mocked Qdrant client)
- [ ] Unit test: after processing a canonical event with `ide_source="claude"`, the stored point contains `ide_source == "claude"`
- [ ] Existing test suite for `store_async.py` still passes (no regressions)

**Implementation Notes:**
- This is a file move plus a one-line change per the architecture's reference implementation in §3
- The original `.claude/hooks/scripts/` files are removed after the move — they will be replaced by `adapters/claude/` symlinks or path updates in Story 2.1
- `store_async.py` reads `hook_input` as a dict from stdin — `ide_source` is already in the canonical event that all adapters produce after Story 1.4

---

## Epic 2: Claude Code Adapter Migration

Migrating the existing Claude Code hooks validates the canonical schema against real payloads before any new IDE adapter is written. Claude Code hooks must continue to behave identically to v2.2.6 after migration, confirmed by the existing test suite (SC-07, NFR-301).

---

### Story 2.1: Migrate Claude Code hook scripts to `adapters/claude/`

**Epic:** Claude Code Adapter Migration
**Traces to:** FR-101, FR-102, NFR-301
**Architecture:** §2 Claude Code as Adapter, §6 Directory Structure
**Depends on:** Story 1.5
**Estimated effort:** M

**Description:**
Move all existing Claude Code hook scripts from `.claude/hooks/scripts/` to `src/memory/adapters/claude/`. Update each script to import and call `normalize_claude_event()` and `validate_canonical_event()` from `memory.adapters.schema` instead of parsing raw stdin directly. Add `src/memory/adapters/claude/__init__.py`.

**Acceptance Criteria:**
- [ ] `src/memory/adapters/claude/__init__.py` exists
- [ ] All hook scripts listed in the architecture's `claude/` directory exist under `src/memory/adapters/claude/`
- [ ] Each migrated script reads `json.loads(sys.stdin.read())`, calls `normalize_claude_event(raw, "<EventName>")`, and calls `validate_canonical_event(event)` before any pipeline call
- [ ] No script reads raw hook fields directly from `sys.stdin` without going through the normalizer
- [ ] `.claude/hooks/scripts/` directory is empty or removed after migration
- [ ] Existing Claude Code integration test suite passes with zero new failures (SC-07)

**Implementation Notes:**
- This is a ~5-line change per script per the architecture's before/after example in §2
- The `hook_event_name` argument to `normalize_claude_event()` must match the canonical name for that script (e.g., `"PostToolUse"`, `"SessionStart"`, `"PreCompact"`)
- Do not change any downstream pipeline logic — only the stdin parsing block changes

---

### Story 2.2: Update `.claude/settings.json` command paths to `adapters/claude/`

**Epic:** Claude Code Adapter Migration
**Traces to:** FR-101, NFR-301
**Architecture:** §2 Claude Code as Adapter, §5 IDE Config File Generation
**Depends on:** Story 2.1
**Estimated effort:** S

**Description:**
Update every hook command path in `.claude/settings.json` (and the installer template that generates it) to reference `$AI_MEMORY_INSTALL_DIR/adapters/claude/<script>.py` instead of the old `.claude/hooks/scripts/` paths.

**Acceptance Criteria:**
- [ ] All hook command strings in `.claude/settings.json` reference `$AI_MEMORY_INSTALL_DIR/adapters/claude/` paths
- [ ] No command string references `.claude/hooks/scripts/`
- [ ] The installer template that generates `.claude/settings.json` is updated to the new paths
- [ ] A Claude Code session started with the updated config fires hooks successfully (verified via existing integration test or manual smoke test)
- [ ] `.claude/settings.json` JSON schema is unchanged (NFR-301)

**Implementation Notes:**
- File to update: `.claude/settings.json` and the installer template for Claude Code config generation
- The schema of `.claude/settings.json` must not change — only the `command` string values inside each hook entry change
- If the installer reads a template file rather than generating config inline, update the template; if it generates inline, update the generation logic

---

## Epic 3: Gemini CLI Adapter

Gemini CLI has three Phase 1 hook adapters (`session_start`, `after_tool_capture`, `pre_compress`) plus error detection adapters, three TOML commands, and one MCP matcher config entry. All adapters normalize through `schema.py` from Epic 1.

---

### Story 3.1: Create Gemini `session_start.py` adapter

**Epic:** Gemini CLI Adapter
**Traces to:** FR-201, FR-601, FR-602, FR-603
**Architecture:** §2 Data Flow Retrieval Path, §2 Canonical Event Schema
**Depends on:** Story 1.3, Story 1.4
**Estimated effort:** M

**Description:**
Create `src/memory/adapters/gemini/session_start.py`. The script reads a Gemini `SessionStart` JSON payload from stdin, normalizes it through `normalize_gemini_event()` (to be added to `schema.py`), runs the existing retrieval pipeline, and writes `{"hookSpecificOutput": {"additionalContext": "<markdown>"}}` to stdout.

**Acceptance Criteria:**
- [ ] `src/memory/adapters/gemini/__init__.py` exists
- [ ] Given a synthetic Gemini `SessionStart` stdin fixture for a project with seeded Qdrant data, stdout parses as JSON and contains `hookSpecificOutput.additionalContext` with at least 1 retrieved memory
- [ ] Given an empty Qdrant index, adapter exits 0 with `{"hookSpecificOutput": {"additionalContext": ""}}` on stdout
- [ ] Given Qdrant unreachable, adapter exits 0 with empty `additionalContext` and no exception on stderr
- [ ] Given malformed stdin JSON, adapter exits 0 with valid empty JSON output
- [ ] `cwd` is resolved using `resolve_cwd()` fallback chain; test covers payload where `cwd` is absent
- [ ] Adapter completes within 3000ms at p95 (tested with 10 sequential invocations per NFR-101)
- [ ] Nothing other than valid JSON is written to stdout (logging goes to stderr only)

**Implementation Notes:**
- Add `normalize_gemini_event()` to `schema.py` that maps Gemini-native fields (`session_id`, `transcript_path`, `cwd`, `hook_event_name`, `timestamp`) to the canonical dict with `ide_source="gemini"`
- Empty-context payload is `{"hookSpecificOutput": {"additionalContext": ""}}` per the architecture's retrieval path
- Use existing `MemorySearch.search()` and `inject_with_priority()` pipeline functions

---

### Story 3.2: Create Gemini `after_tool_capture.py` adapter

**Epic:** Gemini CLI Adapter
**Traces to:** FR-202, FR-208, FR-601, FR-602
**Architecture:** §2 Data Flow Capture Path, §2 MCP Tool Name Normalization
**Depends on:** Story 1.2, Story 1.4, Story 1.5
**Estimated effort:** M

**Description:**
Create `src/memory/adapters/gemini/after_tool_capture.py`. The script reads a Gemini `AfterTool` payload from stdin, normalizes it (mapping Gemini tool names to canonical names and passing MCP tool names through `normalize_mcp_tool_name()`), forks to background via `fork_to_background()`, and exits 0.

**Acceptance Criteria:**
- [ ] Given a Gemini `AfterTool` payload with `tool_name: "write_file"`, adapter forks to background and exits 0 within 500ms
- [ ] Background process stores a Qdrant point within 10s of adapter exit
- [ ] Given `tool_name: "mcp_postgres_query"`, stored Qdrant point has `tool_name == "mcp:postgres:query"`
- [ ] Given `tool_name: "mcp_slack_send"`, stored Qdrant point has `tool_name == "mcp:slack:send"`
- [ ] Given malformed stdin, adapter exits 0 without raising an unhandled exception
- [ ] Adapter emits no output to stdout (exit 0, no JSON required for AfterTool)
- [ ] Tool name mapping is applied: `"write_file"` → `"Write"`, `"edit_file"` → `"Edit"`, `"create_file"` → `"Write"`

**Implementation Notes:**
- `normalize_gemini_event()` must map `tool_response.llmContent` to `tool_response` in the canonical event
- MCP tool names matching `mcp_<server>_<tool>` go through `normalize_mcp_tool_name()` before `fork_to_background()`
- Adapter is registered in `.gemini/settings.json` under both `edit_file|write_file|create_file` and `mcp_.*` matchers (FR-204, FR-208) — this story only creates the adapter; Story 6.1 handles config generation

---

### Story 3.3: Create Gemini `error_detection.py` and `error_pattern_capture.py` adapters

**Epic:** Gemini CLI Adapter
**Traces to:** FR-202, FR-601, FR-602
**Architecture:** §6 Directory Structure (gemini adapter scripts)
**Depends on:** Story 1.4, Story 1.5
**Estimated effort:** S

**Description:**
Create `src/memory/adapters/gemini/error_detection.py` and `src/memory/adapters/gemini/error_pattern_capture.py`. These handle `AfterTool` events with `tool_name: "run_shell_command"` (the Gemini equivalent of Bash error hooks). Both mirror the Claude Code equivalents, normalizing through `normalize_gemini_event()` and forking to the appropriate pipeline script.

**Acceptance Criteria:**
- [ ] Given a Gemini `AfterTool` payload with `tool_name: "run_shell_command"` and output containing an error pattern, `error_detection.py` forks to `error_store_async.py` and exits 0 within 500ms
- [ ] `error_pattern_capture.py` forks to the error pattern pipeline and exits 0 within 500ms
- [ ] Both adapters exit 0 with no output on stdout for non-error payloads
- [ ] Both adapters exit 0 on malformed stdin without unhandled exceptions

**Implementation Notes:**
- These adapters are registered under the `run_shell_command` matcher in `.gemini/settings.json` using `sequential: true` per the architecture's config example
- Both scripts reuse `normalize_gemini_event()` from `schema.py` — no new normalizer needed

---

### Story 3.4: Create Gemini `pre_compress.py` adapter

**Epic:** Gemini CLI Adapter
**Traces to:** FR-203
**Architecture:** §2 Data Flow Capture Path
**Depends on:** Story 1.4, Story 1.5
**Estimated effort:** S

**Description:**
Create `src/memory/adapters/gemini/pre_compress.py`. The script reads a Gemini `PreCompress` payload from stdin, normalizes it (mapping `trigger` field), and calls the existing `pre_compact_save` pipeline to store a session summary in the `discussions` collection.

**Acceptance Criteria:**
- [ ] Given a synthetic Gemini `PreCompress` payload, adapter calls the pre_compact pipeline and a session summary point exists in Qdrant's `discussions` collection within 10s
- [ ] The stored point has `ide_source == "gemini"`
- [ ] Adapter exits 0 in all cases including Qdrant unavailable
- [ ] `trigger` field (`"auto"` or `"manual"`) is preserved in the canonical event and passed to the pipeline

**Implementation Notes:**
- `normalize_gemini_event()` maps Gemini `PreCompress` → canonical `hook_event_name: "PreCompact"`
- File: `src/memory/adapters/gemini/pre_compress.py`
- Calls `pre_compact_save` pipeline from `adapters/pipeline/`

---

### Story 3.5: Create Gemini TOML command templates

**Epic:** Gemini CLI Adapter
**Traces to:** FR-205, FR-206, FR-207
**Architecture:** §5 Skill / Command Deployment
**Depends on:** Story 1.1
**Estimated effort:** S

**Description:**
Create the three Gemini TOML command template files: `src/memory/adapters/templates/gemini/search-memory.toml`, `memory-status.toml`, and `save-memory.toml`. These templates are copied to `.gemini/commands/` by the installer (Epic 6).

**Acceptance Criteria:**
- [ ] All three files exist under `src/memory/adapters/templates/gemini/`
- [ ] Each file is valid TOML with `description` and `prompt` keys
- [ ] `search-memory.toml` contains `{{args}}` in the `prompt` value
- [ ] `search-memory.toml` prompt instructs Gemini to invoke the ai-memory search script via `$AI_MEMORY_INSTALL_DIR` with the query as a discrete argv element (not shell-interpolated)
- [ ] `memory-status.toml` prompt instructs Gemini to run the ai-memory status CLI script
- [ ] `save-memory.toml` prompt instructs Gemini to invoke the manual save script
- [ ] All three files parse without error using a TOML parser in a unit test

**Implementation Notes:**
- TOML format follows the architecture's `search-memory.toml` reference in §5
- `$AI_MEMORY_INSTALL_DIR` is a placeholder the installer resolves at copy time (Story 6.2)
- `{{args}}` is Gemini's template variable for user-supplied command arguments

---

## Epic 4: Cursor IDE Adapter

Cursor IDE has three Phase 1 hook adapters (`session_start`, `post_tool_capture`, `pre_compact`) plus error adapters, three SKILL.md files, and an MCP matcher config entry. Cursor has unique fields (`is_background_agent`, `workspace_roots`, `conversation_id`) and does not support a top-level `env` block in its config.

---

### Story 4.1: Create Cursor `session_start.py` adapter

**Epic:** Cursor IDE Adapter
**Traces to:** FR-301, FR-601, FR-602, FR-603
**Architecture:** §2 Data Flow Retrieval Path, §2 Canonical Event Schema
**Depends on:** Story 1.3, Story 1.4
**Estimated effort:** M

**Description:**
Create `src/memory/adapters/cursor/__init__.py` and `src/memory/adapters/cursor/session_start.py`. The script reads a Cursor `sessionStart` JSON payload, normalizes it through `normalize_cursor_event()` (to be added to `schema.py`), handles `is_background_agent: true` by returning empty context immediately, runs the retrieval pipeline for normal sessions, and writes `{"additional_context": "<markdown>"}` to stdout.

**Acceptance Criteria:**
- [ ] Given a Cursor `sessionStart` payload with `workspace_roots: ["/path/to/project"]` and no `cwd`, `cwd` resolves to `"/path/to/project"`
- [ ] Given `is_background_agent: true`, adapter exits 0 with `{"additional_context": ""}` without querying Qdrant
- [ ] Given a populated Qdrant index, stdout contains `additional_context` with at least 1 retrieved memory
- [ ] Given an empty Qdrant index, adapter exits 0 with `{"additional_context": ""}`
- [ ] `session_id` resolves from `session_id` → `conversation_id` → `transcript_path` → generated fallback per FR-601
- [ ] No content other than valid JSON is written to stdout
- [ ] Adapter completes within 3000ms at p95 (NFR-101)

**Implementation Notes:**
- Add `normalize_cursor_event()` to `schema.py` mapping Cursor-native fields including `conversation_id`, `workspace_roots`, `is_background_agent`, and `cursor_version`
- Empty-context payload is `{"additional_context": ""}` per the architecture
- Cursor script paths must use `AI_MEMORY_INSTALL_DIR` env var, not relative symlinks (FR-302 known issue)

---

### Story 4.2: Create Cursor `post_tool_capture.py` adapter

**Epic:** Cursor IDE Adapter
**Traces to:** FR-302, FR-308, FR-601, FR-602
**Architecture:** §2 Data Flow Capture Path, §2 MCP Tool Name Normalization
**Depends on:** Story 1.2, Story 1.4, Story 1.5
**Estimated effort:** M

**Description:**
Create `src/memory/adapters/cursor/post_tool_capture.py`. The script reads a Cursor `postToolUse` payload, maps Cursor tool names to canonical names (`Write` → `Write`, `Edit` → `Edit`, `Shell` → `Bash`), passes MCP tool names through `normalize_mcp_tool_name()`, forks to background for supported tools, and exits 0.

**Acceptance Criteria:**
- [ ] Given `tool_name: "Write"`, adapter forks to background and exits 0 within 500ms
- [ ] Given `tool_name: "Edit"`, adapter forks to background and exits 0 within 500ms
- [ ] Given `tool_name: "MCP:github_search"`, stored Qdrant point has `tool_name == "mcp:unknown:github_search"`
- [ ] Given `tool_name: "MCP:database_query"`, stored point has `tool_name == "mcp:unknown:database_query"`
- [ ] Given an unsupported `tool_name`, adapter exits 0 without forking (no background process spawned)
- [ ] Script path resolution uses `AI_MEMORY_INSTALL_DIR` env var, not relative paths or symlinks
- [ ] Given malformed stdin, adapter exits 0 without raising an unhandled exception

**Implementation Notes:**
- `normalize_cursor_event()` maps `tool_output` to `tool_response` in the canonical dict
- Cursor `Shell` → canonical `Bash` tool name mapping is required per FR-302
- `cwd` resolves from Cursor payload's `cwd` field directly (Cursor provides it in `postToolUse`)

---

### Story 4.3: Create Cursor `error_detection.py` and `error_pattern_capture.py` adapters

**Epic:** Cursor IDE Adapter
**Traces to:** FR-302
**Architecture:** §6 Directory Structure (cursor adapter scripts)
**Depends on:** Story 1.4, Story 1.5
**Estimated effort:** S

**Description:**
Create `src/memory/adapters/cursor/error_detection.py` and `src/memory/adapters/cursor/error_pattern_capture.py`. These handle `postToolUse` events with `tool_name: "Shell"` (the Cursor equivalent of Bash error hooks), mirroring the Claude Code equivalents.

**Acceptance Criteria:**
- [ ] Given a Cursor `postToolUse` payload with `tool_name: "Shell"` and error-pattern output, `error_detection.py` forks to `error_store_async.py` and exits 0 within 500ms
- [ ] `error_pattern_capture.py` forks to the error pattern pipeline and exits 0 within 500ms
- [ ] Both adapters exit 0 on malformed stdin without unhandled exceptions
- [ ] Both adapters produce no stdout output

**Implementation Notes:**
- Registered in `.cursor/hooks.json` under `"Shell"` matcher, separate from the `Write|Edit` matcher
- Both scripts use `normalize_cursor_event()` from `schema.py`

---

### Story 4.4: Create Cursor `pre_compact.py` adapter

**Epic:** Cursor IDE Adapter
**Traces to:** FR-303
**Architecture:** §2 Data Flow Capture Path
**Depends on:** Story 1.4, Story 1.5
**Estimated effort:** S

**Description:**
Create `src/memory/adapters/cursor/pre_compact.py`. The script reads a Cursor `preCompact` payload, normalizes it (preserving `context_usage_percent`, `context_tokens`, `context_window_size`), and calls the `pre_compact_save` pipeline to store a session summary.

**Acceptance Criteria:**
- [ ] Given a synthetic Cursor `preCompact` payload, adapter stores a session summary in the `discussions` Qdrant collection within 10s
- [ ] Stored point has `ide_source == "cursor"`
- [ ] `context_usage_percent` (float), `context_tokens` (int), and `context_window_size` (int) are preserved in the canonical event and passed to the pipeline
- [ ] Adapter exits 0 in all cases

**Implementation Notes:**
- `normalize_cursor_event()` maps `preCompact` → canonical `hook_event_name: "PreCompact"`
- Cursor-specific context fields (`context_usage_percent`, `context_tokens`, `context_window_size`) must pass `validate_canonical_event()` with the correct types per Story 1.1

---

### Story 4.5: Create Cursor SKILL.md templates

**Epic:** Cursor IDE Adapter
**Traces to:** FR-305, FR-306, FR-307
**Architecture:** §5 Skill / Command Deployment
**Depends on:** Story 1.1
**Estimated effort:** S

**Description:**
Create the three Cursor skill template files: `src/memory/adapters/templates/cursor/search-memory/SKILL.md`, `memory-status/SKILL.md`, and `save-memory/SKILL.md`. These are copied to `.cursor/skills/` by the installer (Epic 6).

**Acceptance Criteria:**
- [ ] All three files exist under `src/memory/adapters/templates/cursor/<name>/SKILL.md`
- [ ] Each file has valid YAML frontmatter with `name` and `description` fields and `allowed-tools: Bash`
- [ ] `search-memory/SKILL.md` body references `$AI_MEMORY_INSTALL_DIR` and instructs passing the query as a discrete argv element
- [ ] `memory-status/SKILL.md` body instructs invocation of the ai-memory status CLI script via `$AI_MEMORY_INSTALL_DIR`
- [ ] `save-memory/SKILL.md` body instructs invocation of the manual save script via `$AI_MEMORY_INSTALL_DIR`
- [ ] A unit test parses the YAML frontmatter of each file and asserts `name` and `description` are present

**Implementation Notes:**
- Format follows the architecture's `search-memory/SKILL.md` reference in §5
- `allowed-tools: Bash` (capital B) per FR-305 — Codex uses `allowed-tools: shell` (lowercase)

---

## Epic 5: Codex CLI Adapter

Codex CLI has four Phase 1 adapters: `session_start`, `post_tool_capture` (Bash-only — platform gap for Write/Edit), `context_injection` (UserPromptSubmit per-turn injection), and `stop` (session summary). Two skill files round out Phase 1.

---

### Story 5.1: Create Codex `session_start.py` adapter

**Epic:** Codex CLI Adapter
**Traces to:** FR-401, FR-601, FR-602, FR-603
**Architecture:** §2 Data Flow Retrieval Path
**Depends on:** Story 1.3, Story 1.4
**Estimated effort:** M

**Description:**
Create `src/memory/adapters/codex/__init__.py` and `src/memory/adapters/codex/session_start.py`. The script reads a Codex `SessionStart` JSON payload, normalizes it through `normalize_codex_event()` (to be added to `schema.py`), runs the retrieval pipeline, and writes `{"hookSpecificOutput": {"systemMessage": "<markdown>"}}` to stdout.

**Acceptance Criteria:**
- [ ] Given a synthetic Codex `SessionStart` fixture for a project with seeded Qdrant data, stdout parses as JSON with `hookSpecificOutput.systemMessage` containing at least 1 retrieved memory
- [ ] Given an empty Qdrant index, adapter exits 0 with `{"hookSpecificOutput": {"systemMessage": ""}}`
- [ ] Given Qdrant unreachable, adapter exits 0 with empty `systemMessage` and no exception on stderr
- [ ] Given malformed stdin, adapter exits 0 with valid empty JSON output
- [ ] `session_id` resolves via FR-601 fallback chain (Codex has `session_id` and `turn_id` but no `conversation_id`)
- [ ] Nothing other than valid JSON is written to stdout
- [ ] Adapter completes within 3000ms at p95 (NFR-101)

**Implementation Notes:**
- Add `normalize_codex_event()` to `schema.py` mapping Codex-native fields (`session_id`, `transcript_path`, `cwd`, `hook_event_name`, `model`, `turn_id`) to the canonical dict with `ide_source="codex"`
- Empty-context payload is `{"hookSpecificOutput": {"systemMessage": ""}}` per the architecture

---

### Story 5.2: Create Codex `post_tool_capture.py` adapter (Bash-only)

**Epic:** Codex CLI Adapter
**Traces to:** FR-402, FR-408
**Architecture:** §5 Codex CLI config, §6 Codex platform gaps
**Depends on:** Story 1.4, Story 1.5
**Estimated effort:** S

**Description:**
Create `src/memory/adapters/codex/post_tool_capture.py`. This adapter handles Codex `PostToolUse` events for Bash tool only (platform gap: Write/Edit are not available in Codex PostToolUse). It forks to error detection and error pattern capture in background and exits 0. For unrecognized tool names, it logs a structured warning to stderr and exits 0 without forking.

**Acceptance Criteria:**
- [ ] Given a Codex `PostToolUse` payload with `tool_name: "Bash"` and error-pattern output, adapter forks to error pipeline and exits 0 within 500ms
- [ ] Given a `tool_name` not matching any known Codex native tool, adapter logs `{"event": "unrecognized_tool_name", "tool_name": "<value>"}` to stderr and exits 0 without forking (FR-408)
- [ ] Given malformed stdin, adapter exits 0 without unhandled exception
- [ ] Adapter produces no stdout output

**Implementation Notes:**
- Known platform gap: Codex `PostToolUse` is Bash-only per FR-402; Write/Edit events do not fire PostToolUse hooks in Codex CLI
- Structured warning to stderr must include the unrecognized `tool_name` value (FR-408)
- Fork targets `error_store_async.py` and `error_pattern_capture` pipeline scripts

---

### Story 5.3: Create Codex `context_injection.py` adapter (UserPromptSubmit)

**Epic:** Codex CLI Adapter
**Traces to:** FR-404
**Architecture:** §2 Data Flow Retrieval Path
**Depends on:** Story 1.3, Story 1.4
**Estimated effort:** M

**Description:**
Create `src/memory/adapters/codex/context_injection.py`. This adapter handles Codex `UserPromptSubmit` events: it reads the user prompt from stdin, queries Qdrant for semantically relevant memories, and returns them in `{"hookSpecificOutput": {"additionalContext": "<markdown>"}}` format. It must complete within 2000ms and never block the user turn.

**Acceptance Criteria:**
- [ ] Given a Codex `UserPromptSubmit` payload with prompt `"what authentication pattern do we use?"` and a populated Qdrant index, stdout contains `hookSpecificOutput.additionalContext` with at least 1 injected memory within 2000ms
- [ ] Given Qdrant unavailable, adapter exits 0 with valid empty JSON within 200ms (non-blocking)
- [ ] Given an empty Qdrant index, adapter exits 0 with `{"hookSpecificOutput": {"additionalContext": ""}}`
- [ ] `user_prompt` in the canonical event is a non-empty string (as required by FR-101 for UserPromptSubmit events)
- [ ] Nothing other than valid JSON is written to stdout

**Implementation Notes:**
- Uses `normalize_codex_event()` with `hook_event_name: "UserPromptSubmit"` and `user_prompt` populated
- Query Qdrant with the `user_prompt` text using `MemorySearch.search()` — same approach as `context_injection_tier2.py` in the Claude adapter
- 2000ms wall-clock budget must be enforced; use `httpx` timeout on the Qdrant client call

---

### Story 5.4: Create Codex `stop.py` adapter

**Epic:** Codex CLI Adapter
**Traces to:** FR-405
**Architecture:** §2 Data Flow Capture Path
**Depends on:** Story 1.4, Story 1.5
**Estimated effort:** S

**Description:**
Create `src/memory/adapters/codex/stop.py`. This adapter handles the Codex `Stop` event (session end): it extracts the session transcript from the payload, generates a session summary, and stores it synchronously in the `discussions` collection with `type: "session"`. It runs synchronously because latency at session end does not block the user.

**Acceptance Criteria:**
- [ ] Given a synthetic Codex `Stop` payload containing a transcript of at least 5 turns, adapter stores a session summary point in Qdrant's `discussions` collection within 10s
- [ ] Stored point has `type == "session"` and `ide_source == "codex"`
- [ ] Adapter exits 0 in all cases including Qdrant unavailable
- [ ] Adapter produces no stdout output

**Implementation Notes:**
- Mirrors `agent_response_capture.py` in the Claude adapter
- `normalize_codex_event()` maps Codex `Stop` → canonical `hook_event_name: "Stop"`
- Runs synchronously (not fire-and-forget) per FR-405 — `fork_to_background()` is not used here

---

### Story 5.5: Create Codex SKILL.md templates

**Epic:** Codex CLI Adapter
**Traces to:** FR-406, FR-407
**Architecture:** §5 Skill / Command Deployment
**Depends on:** Story 1.1
**Estimated effort:** S

**Description:**
Create the two Codex skill template files: `src/memory/adapters/templates/codex/search-memory/SKILL.md` and `memory-status/SKILL.md`. These are copied to `.agents/skills/` (and optionally `.codex/skills/`) by the installer (Epic 6).

**Acceptance Criteria:**
- [ ] Both files exist under `src/memory/adapters/templates/codex/<name>/SKILL.md`
- [ ] Each file has valid YAML frontmatter with `name` and `description` fields and `allowed-tools: shell`
- [ ] `search-memory/SKILL.md` body references `$AI_MEMORY_INSTALL_DIR` and instructs passing the query as a discrete argv element
- [ ] `memory-status/SKILL.md` body instructs invocation of the status CLI script via `$AI_MEMORY_INSTALL_DIR`
- [ ] A unit test parses the YAML frontmatter of each file and asserts `name` and `description` are present

**Implementation Notes:**
- `allowed-tools: shell` (lowercase) per FR-406 — Cursor uses `allowed-tools: Bash`
- The installer (Story 6.2) handles creating both `.agents/skills/` and `.codex/skills/` paths per FR-406

---

## Epic 6: Installer and Config Generation

The installer detects which IDEs are present, generates their config files with all required env vars and hook command strings, and deploys skill/command files. It must be idempotent (FR-504) and support `--ide` (FR-502) and `--force` (FR-505) flags.

---

### Story 6.1: Implement IDE detection and `--ide` flag

**Epic:** Installer and Config Generation
**Traces to:** FR-501, FR-502
**Architecture:** §5 Installer Changes, IDE Detection Functions
**Depends on:** Story 2.2
**Estimated effort:** S

**Description:**
Add IDE detection functions (`detect_gemini_cli()`, `detect_cursor_ide()`, `detect_codex_cli()`) to the installer. Add `--ide <list>` flag parsing that overrides detection. Implement `--ide none` to skip all IDE config generation.

**Acceptance Criteria:**
- [ ] On a system where only `gemini` is in PATH (not `codex` or `cursor-agent`), `add-project` calls detection functions and returns `True` only for Gemini
- [ ] `add-project --ide gemini` on a system with no `gemini` in PATH still returns `True` for Gemini detection (flag overrides)
- [ ] `add-project --ide none` returns `False` for all IDEs
- [ ] `add-project --ide gemini,cursor` returns `True` for Gemini and Cursor, `False` for Codex
- [ ] Cursor detection checks for `agent` or `cursor-agent` binary (not cursor directory)
- [ ] All detection functions are unit-testable with mocked PATH

**Implementation Notes:**
- Detection uses `command -v <binary>` pattern per the architecture's `detect_*` bash functions
- `--ide` flag parsing must split on comma and validate against known IDE names; unknown names produce a clear error
- The installer is `scripts/install.sh` per the architecture §5

---

### Story 6.2: Implement config file generation for Gemini, Cursor, and Codex

**Epic:** Installer and Config Generation
**Traces to:** FR-503, FR-504, FR-505, FR-506, FR-507, FR-508
**Architecture:** §5 IDE Config File Generation, §5 Skill / Command Deployment
**Depends on:** Story 6.1, Story 3.5, Story 4.5, Story 5.5
**Estimated effort:** L

**Description:**
Implement `write_gemini_config()`, `write_cursor_config()`, and `write_codex_config()` functions in the installer. Each function generates the appropriate IDE config file with all required hook entries and env vars, deploys skill/command templates to project directories, and enforces idempotency and merge behavior.

**Acceptance Criteria:**
- [ ] After `add-project` with Gemini detected, `.gemini/settings.json` is valid JSON containing all 8 required env vars in the `env` block and hook entries for `SessionStart`, `AfterTool` (both matchers), and `PreCompress`
- [ ] After `add-project` with Cursor detected, `.cursor/hooks.json` is valid JSON with `"version": 1` and hook entries for `sessionStart`, `postToolUse` (both matchers including `MCP:.*`), and `preCompact`; all command strings include inline env var assignments for all 8 required vars
- [ ] After `add-project` with Codex detected, `.codex/hooks.json` is valid JSON with hook entries for `SessionStart`, `PostToolUse` (Bash matcher), `UserPromptSubmit`, and `Stop`; all command strings include inline env var assignments for all 8 required vars
- [ ] After `add-project` with Gemini detected, `.gemini/commands/search-memory.toml`, `memory-status.toml`, and `save-memory.toml` exist and are valid TOML (FR-506)
- [ ] After `add-project` with Cursor detected, `.cursor/skills/search-memory/SKILL.md`, `memory-status/SKILL.md`, and `save-memory/SKILL.md` exist and pass YAML frontmatter validation (FR-507)
- [ ] After `add-project` with Codex detected, `.agents/skills/search-memory/SKILL.md` and `memory-status/SKILL.md` exist; `.codex/skills/` symlinks or copies also exist (FR-508)
- [ ] Running `add-project` twice on the same project does not modify configs already containing `AI_MEMORY_INSTALL_DIR` (FR-504); file mtime is unchanged on second run
- [ ] `add-project --force` overwrites existing IDE config files (FR-505)
- [ ] No command string contains shell interpolation of user-supplied input (NFR-201, NFR-203)
- [ ] If an existing config file is valid JSON but lacks ai-memory keys, the installer merges ai-memory keys into the existing object while preserving unrelated keys

**Implementation Notes:**
- Codex and Cursor configs require inline env var assignments per the architecture's note on missing `env` block support
- The installer expands `$AI_MEMORY_INSTALL_DIR` and `$AI_MEMORY_PROJECT_ID` to absolute values at write time, never leaving them as literal dollar-sign strings in the output (except where Gemini's `env` block provides the expansion at runtime)
- `AI_MEMORY_PROJECT_ID` is derived from the project directory basename, not from user-supplied input

---

## Epic 7: Integration Testing

Cross-IDE memory sharing tests validate that the same Qdrant index serves all four adapters correctly. Synthetic payload tests verify each adapter in isolation. Installer tests confirm config file output matches schema.

---

### Story 7.1: Cross-IDE memory sharing integration tests

**Epic:** Integration Testing
**Traces to:** SC-04, SC-05, SC-06, FR-101, FR-102
**Architecture:** §2 System Design (unified Qdrant)
**Depends on:** Story 3.1, Story 3.2, Story 4.1, Story 4.2, Story 5.1, Story 5.2
**Estimated effort:** M

**Description:**
Write integration tests that verify memories written by one IDE's capture adapter are retrievable by another IDE's session_start adapter. Tests use synthetic stdin payloads and a shared test Qdrant instance (no live IDE required per NFR-401).

**Acceptance Criteria:**
- [ ] Test: Claude Code `post_tool_capture.py` writes a fixture memory → Gemini `session_start.py` retrieves it; `additionalContext` contains the fixture marker (SC-04)
- [ ] Test: Gemini `after_tool_capture.py` writes a fixture memory → Cursor `session_start.py` retrieves it; `additional_context` contains the fixture marker (SC-05)
- [ ] Test: Claude Code `error_pattern_capture.py` writes an error pattern → Codex `session_start.py` retrieves it; `systemMessage` contains the fixture marker (SC-06)
- [ ] Test: Qdrant point written by Gemini adapter has `payload.ide_source == "gemini"` (FR-102)
- [ ] Test: Qdrant point written by Cursor adapter has `payload.ide_source == "cursor"` (FR-102)
- [ ] All tests are runnable without a live IDE via synthetic stdin fixture files

**Implementation Notes:**
- Tests live in a dedicated integration test directory (e.g., `tests/integration/test_cross_ide_memory.py`)
- Use a local Qdrant test instance (the project already has Qdrant running per the existing stack)
- Fixture memories should include a unique marker string (UUID or timestamp-based) to avoid false positives from pre-existing test data

---

### Story 7.2: Adapter unit tests with synthetic payloads

**Epic:** Integration Testing
**Traces to:** NFR-401, FR-101, FR-603
**Architecture:** §7 Performance and Scale
**Depends on:** Story 3.1, Story 3.2, Story 3.4, Story 4.1, Story 4.2, Story 4.4, Story 5.1, Story 5.3, Story 5.4
**Estimated effort:** M

**Description:**
Write unit tests for each new adapter covering: valid payload, malformed JSON payload, missing required fields, Qdrant unavailable, and empty results. Also verify stdout-only JSON output (no mixed stdout/stderr content) across 10 synthetic invocations per adapter.

**Acceptance Criteria:**
- [ ] Each session_start adapter (Gemini, Cursor, Codex) has tests for all 5 cases (valid, malformed, missing fields, Qdrant unavailable, empty results)
- [ ] Each capture adapter (Gemini after_tool, Cursor post_tool, Codex post_tool) has tests for: valid payload → fork spawned, malformed payload → exit 0 no exception, unsupported tool_name → exit 0 no fork
- [ ] For each session_start adapter, 10 synthetic payloads all produce valid JSON on stdout (FR-603)
- [ ] Tests mock the Qdrant client to avoid requiring a live Qdrant instance
- [ ] All tests pass with `pytest`

**Implementation Notes:**
- Tests live in `src/memory/adapters/tests/` per adapter subdirectory
- Use `subprocess.run()` with captured stdout/stderr to test adapters as black boxes
- Qdrant unavailability can be simulated by pointing `QDRANT_HOST` to a non-listening port

---

### Story 7.3: Installer config generation tests

**Epic:** Integration Testing
**Traces to:** FR-501, FR-502, FR-503, FR-504, FR-505, SC-08
**Architecture:** §5 Installer Changes
**Depends on:** Story 6.1, Story 6.2
**Estimated effort:** S

**Description:**
Write tests for the installer's config generation logic: IDE detection with mocked PATH, generated config files validated against expected JSON schema, idempotency, `--force` overwrite, and `--ide` flag behavior.

**Acceptance Criteria:**
- [ ] Test: mocked PATH with only `gemini` → `add-project` produces `.gemini/settings.json` only; `.cursor/hooks.json` and `.codex/hooks.json` are absent (SC-08)
- [ ] Test: `add-project --ide gemini` on system without `gemini` binary → `.gemini/settings.json` is produced
- [ ] Test: `add-project --ide none` → no IDE config files produced
- [ ] Test: `.gemini/settings.json` output passes JSON schema validation and contains all 8 env vars
- [ ] Test: `.cursor/hooks.json` output has `version: 1` and all command strings include all 8 env var name prefixes
- [ ] Test: second `add-project` run on same project → config file mtime is unchanged
- [ ] Test: `add-project --force` → config file mtime is newer after second run

**Implementation Notes:**
- Mock binary detection by setting `PATH` in the test subprocess environment
- Use `tempfile.mkdtemp()` for test project directories to avoid polluting the real workspace
- JSON schema validation for generated configs can use `jsonschema` (already in the project's test dependencies or add as dev dependency)

---

## Epic 8 (Placeholder): Phase 2 — Keyword Triggers + Per-Turn Injection

This epic covers Phase 2 deliverables. No stories are defined yet.

**Phase 2 FRs covered by this epic:**

- **FR-701** — Enable the three disabled keyword trigger scripts for Claude Code (`decision_keywords`, `best_practices_keywords`, `session_history_keywords`) by removing `.disabled` suffix and setting `enabled: true`
- **FR-702** — Gemini CLI `BeforeAgent` → keyword trigger adapter (`context_injection.py` + `keyword_trigger_adapter.py`)
- **FR-703** — Cursor IDE `beforeSubmitPrompt` → keyword trigger adapter
- **FR-704** — Codex CLI `UserPromptSubmit` → keyword trigger adapter (may merge with Phase 1 FR-404 adapter)
- **FR-801** — End-to-end validation of Gemini CLI slash commands against a live Gemini CLI session

**Phase 2 will also deliver:**
- Gemini CLI `BeforeAgent` per-turn context injection (`context_injection.py`, `user_prompt_capture.py`, `best_practices_retrieval.py`)
- Cursor IDE `beforeSubmitPrompt` per-turn injection adapters
- Gemini `SessionEnd` → agent response capture (`session_end.py`)
- Cursor `stop` → agent response capture
- Gemini and Cursor `BeforeTool` first-edit and new-file triggers
- `aim-save` parity skill for Codex CLI

**Dependency note:** Phase 2 depends on all Phase 1 epics being complete and the keyword trigger scripts having their `TRIGGER_CONFIG` updated to `enabled: true`.
