---
project_name: ai-memory
feature: "FEATURE-001: Multi-IDE Support"
author: Phil Mahncke
date: 2026-03-26
version: "1.1"
status: approved
approved_by: Phil Mahncke
approved_date: 2026-03-26
github_issue: "Hidden-History/ai-memory#27"
input_documents:
  - analyst-discovery-research.md
  - "GitHub issue #27 + community discussion"
  - "Gemini CLI hooks reference (geminicli.com/docs/hooks/reference)"
  - "Cursor IDE hooks reference (cursor.com/docs/agent/hooks)"
  - "Codex CLI hooks reference (developers.openai.com/codex/hooks)"
---

# Product Requirements Document — FEATURE-001: Multi-IDE Support

**Prepared by:** Phil Mahncke (PM)
**Date:** 2026-03-26
**Version:** 1.1-draft
**GitHub Issue:** [Hidden-History/ai-memory#27](https://github.com/Hidden-History/ai-memory/issues/27)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Success Criteria](#2-success-criteria)
3. [Product Scope](#3-product-scope)
4. [User Journeys](#4-user-journeys)
5. [Functional Requirements](#5-functional-requirements)
6. [Non-Functional Requirements](#6-non-functional-requirements)
7. [Out of Scope](#7-out-of-scope)

---

## 1. Executive Summary

ai-memory v2.2.6 provides persistent, cross-session memory for Claude Code via a hook-based adapter that captures patterns, retrieves context, and injects relevant memories at session boundaries and tool events. The system is currently hard-coupled to the Claude Code hook protocol (`.claude/settings.json`, JSON stdin/stdout, exit codes 0/1).

**FEATURE-001** extends ai-memory to support three additional AI coding tools: **Gemini CLI**, **Cursor IDE**, and **OpenAI Codex CLI**. Each tool has a distinct hook protocol, config schema, stdin/stdout contract, and event model. The goal is a shared memory brain: memories captured in one IDE are immediately available in all others, with zero additional configuration per project after install.

This is the highest-priority feature for the ai-memory roadmap, prioritized above stabilization and adoption, per the user decision recorded in issue #27. The primary target user is an individual developer who uses two or more AI coding tools concurrently and needs institutional memory — patterns, error fixes, conventions, decisions — to follow them across tool boundaries.

The implementation strategy is an **IDE-specific adapter layer**: thin translation scripts per IDE that normalize foreign hook payloads into the canonical internal event schema that the existing storage and retrieval pipeline already consumes. The Claude Code hook scripts are not modified. All four IDEs read from and write to the same Qdrant collections.

---

## 2. Success Criteria

All criteria are measured against a project where ai-memory is installed and at least one prior Claude Code session has produced stored memories.

| ID | Criterion | Measurement Method | Target |
|----|-----------|-------------------|--------|
| SC-01 | Zero-config activation after install for each new IDE | Run `ai-memory add-project` on a repo; verify config files exist for all configured IDEs without manual edits | Config files present and valid within 30s of command completion |
| SC-02 | Session-start memory injection latency overhead (Gemini, Cursor, Codex) | Measure wall-clock time from hook invocation to stdout flush in session_start adapters across 10 runs on a cold Qdrant index | p95 < 3000ms; p99 < 5000ms |
| SC-03 | PostToolUse capture hook returns control to the IDE within latency budget | Measure wall-clock time from hook invocation to exit(0) across 50 Edit/Write events | p95 < 500ms; p99 < 1000ms |
| SC-04 | Cross-IDE memory recall: memory stored in Claude Code session is retrievable in Gemini CLI session | In a new Gemini CLI session on the same project, session_start adapter injects at least 1 memory previously stored by Claude Code PostToolUse hook | Pass/fail: injected context contains content from Claude Code session |
| SC-05 | Cross-IDE memory recall: memory stored in Gemini CLI session is retrievable in Cursor session | In a new Cursor session on the same project, session_start adapter injects at least 1 memory previously stored by Gemini AfterTool adapter | Pass/fail: injected context contains content from Gemini session |
| SC-06 | Error pattern sharing: error_pattern captured in one IDE is injected in a subsequent session in a different IDE | Trigger an error event in IDE A; open IDE B session on same project; verify sessionStart output references the captured error | Pass/fail |
| SC-07 | No regression in Claude Code hook behavior after FEATURE-001 ships | Run existing Claude Code integration test suite against v2.2.6 baseline; zero new failures permitted | 0 regression failures |
| SC-08 | Installer adds only supported IDEs that are detected as installed | `add-project` does not write Gemini config when `gemini` binary is absent from PATH | Pass/fail per IDE detection check |
| SC-09 | Slash command / skill invocation retrieves memory within latency budget | In each IDE, invoke the search-memory skill/command with a known query; verify output contains at least 1 relevant memory | Pass/fail; p95 < 5000ms end-to-end |
| SC-10 | MCP tool events captured with normalized tool name | Trigger an MCP tool call in Gemini or Cursor; verify Qdrant point has `tool_name` in `mcp:<server>:<tool>` format | Pass/fail |

---

## 3. Product Scope

### Phase 1 — Adapter Layer + Installer + MCP Tool Capture (This PRD)

Deliver an adapter for each of the three target IDEs. Each adapter:
- Translates the IDE's hook payload into the canonical internal event schema
- Calls the existing storage/retrieval pipeline without modification
- Is registered in the IDE's config file by the installer

Deliver installer changes that:
- Detect which IDEs are installed on the system
- Write the appropriate IDE-native config files
- Register env vars and hook commands in those configs
- Support `add-project` mode for per-project activation

Deliver MCP tool capture for Gemini CLI and Cursor IDE:
- Matcher configs that capture `mcp_<server>_<tool>` (Gemini) and `MCP:<name>` (Cursor) events
- Canonical normalization of MCP tool names to `mcp:<server>:<tool>` format in FR-101

Deliver Codex CLI `UserPromptSubmit` and `Stop` hook adapters for per-turn context injection and session summary capture.

Deliver `search-memory` and `memory-status` skill registration for Codex CLI into `.agents/skills/`.

### Phase 2 — Command/Skill Parity + Disabled Triggers

Deliver equivalent slash commands or skills for Gemini CLI and Cursor IDE matching Claude Code's existing `aim-search`, `aim-status`, and `aim-save` skills. Codex CLI skills are partially delivered in Phase 1; Phase 2 ensures full parity (including `aim-save` equivalent).

Deliver the three disabled triggers (decision_keywords, best_practices_keywords, session_history_keywords) enabled and mapped to the equivalent per-prompt hook events in each IDE.

### Phase 3 — Future IDEs

Define the adapter interface as a formal internal spec. Register adapters for any IDE that exposes a hook or extension API equivalent to the event model required by the core pipeline (minimum: session_start, post_tool_use, pre_compact equivalents). Candidates include: Windsurf, Aider, Continue.dev.

---

## 4. User Journeys

### UJ-01: Install and Activate (New User, Multiple IDEs)

**Actor:** Developer with Claude Code, Gemini CLI, and Cursor IDE installed.

1. Developer runs `ai-memory install` (or `add-project` on an existing repo).
2. Installer detects Claude Code, Gemini CLI, and Cursor IDE as present.
3. Installer writes `.claude/settings.json` (unchanged from current), `.gemini/settings.json`, and `.cursor/hooks.json` with ai-memory hooks registered.
4. Developer opens a Gemini CLI session on the project. Session-start context injection fires. No manual config step was required.

**Exit condition:** All three IDEs inject memory on next session open without any developer action beyond the initial install command.

### UJ-02: First Session in a New IDE (Existing User)

**Actor:** Developer who has been using ai-memory with Claude Code for 2 weeks. They open Gemini CLI on the same project for the first time.

1. Gemini CLI fires `SessionStart` hook.
2. Gemini session_start adapter reads the hook payload, resolves `cwd` to the project, queries Qdrant using the same retrieval pipeline as Claude Code.
3. Memories stored by Claude Code sessions (code patterns, conventions, error fixes) are injected as `additionalContext` in the Gemini `SessionStart` output.
4. Developer sees Gemini respond with awareness of project conventions without re-explaining them.

**Exit condition:** Developer does not need to re-establish project context in the new IDE.

### UJ-03: Cross-IDE Memory Recall (Active Multi-IDE Workflow)

**Actor:** Developer who uses Cursor for frontend work and Gemini CLI for backend work on the same monorepo.

1. In a Cursor session, the developer refactors a module. Cursor `postToolUse` fires on `Write`. Cursor adapter normalizes the payload and stores a `code-pattern` memory in Qdrant.
2. The developer switches to Gemini CLI for a backend task in the same project.
3. Gemini `SessionStart` fires. The session_start adapter queries Qdrant and retrieves the pattern stored by the Cursor session.
4. Gemini injects the cross-IDE memory as context.

**Exit condition:** The developer's Gemini session has awareness of the Cursor session's stored pattern without any manual action.

### UJ-04: Cross-IDE Error Pattern Sharing

**Actor:** Developer who encountered a recurring dependency error in a Claude Code session.

1. In a Claude Code session, a `Bash` tool run produces a traceback. The `error_detection` hook captures it and stores an `error_pattern` memory.
2. The developer opens a Codex CLI session on the same project.
3. Codex `SessionStart` fires. The Codex session_start adapter retrieves the stored `error_pattern`.
4. The injected context includes the error and its resolution, preventing the developer from hitting the same error again.

**Exit condition:** Codex CLI session has the error pattern in context before the developer encounters it.

### UJ-05: Pre-Compact / Session Summary Across IDEs

**Actor:** Developer whose Gemini CLI session is approaching context limit.

1. Gemini fires `PreCompress` hook with `trigger: auto`.
2. Gemini pre_compact adapter normalizes the event and calls the existing `pre_compact_save.py` pipeline logic to store a session summary in the `discussions` collection.
3. On the next session (in any IDE), session_start retrieves the session summary.

**Exit condition:** Session continuity is preserved across context compression events in Gemini CLI.

### UJ-06: Slash Command / Skill Search (Manual Memory Lookup)

**Actor:** Developer mid-session in any IDE who wants to explicitly search memory for a specific topic.

1. Developer invokes the search-memory skill/command (e.g., `/search-memory authentication patterns` in Gemini, the `search-memory` skill in Cursor or Codex).
2. The command calls the ai-memory search script with the provided query.
3. Ranked results are presented inline in the session.
4. Developer continues the session with the retrieved context.

**Exit condition:** Developer retrieves relevant memories on-demand without leaving the IDE session.

### UJ-07: Per-Turn Trigger Injection (Keyword-Aware Context)

**Actor:** Developer in a Gemini, Cursor, or Codex session asking a question that contains a decision or convention keyword.

1. Developer types "why did we choose postgres over mysql for this project?"
2. The `UserPromptSubmit` / `BeforeAgent` / `beforeSubmitPrompt` hook fires.
3. The decision_keywords trigger adapter detects the keyword pattern, queries the `discussions` collection, and injects up to 2 matching decision memories into the prompt context.
4. The IDE responds with awareness of the stored decision rationale.

**Exit condition:** IDE has decision context injected before generating a response, without any explicit search command from the developer.

### UJ-08: MCP Tool Event Capture

**Actor:** Developer using an MCP-connected tool (e.g., a database query tool or external API tool) within Gemini CLI or Cursor IDE.

1. Developer invokes an MCP tool through the IDE agent.
2. The IDE fires an `AfterTool` (Gemini: `mcp_<server>_<tool>`) or `postToolUse` (Cursor: `MCP:<name>`) event.
3. The adapter captures the MCP tool event, normalizes the tool name to `mcp:<server>:<tool>` format, and routes to the storage pipeline.
4. The captured event is stored in Qdrant with `tool_name` in canonical format and `ide_source` set appropriately.

**Exit condition:** MCP tool interactions are captured and available for cross-session retrieval alongside native tool events.

---

## 5. Functional Requirements

Requirements are organized by component. Each FR is tagged with a phase and traces to one or more user journeys.

---

### 5.1 Canonical Internal Event Schema

**FR-101** [Phase 1] — The system must define a canonical event schema that all IDE adapters translate their native payloads into before invoking the storage or retrieval pipeline.

- Required fields: `session_id` (str), `cwd` (str), `hook_event_name` (str), `tool_name` (str | null), `tool_input` (dict | null), `tool_response` (dict | null), `transcript_path` (str | null), `ide_source` (str — one of `claude`, `gemini`, `cursor`, `codex`).
- MCP tool name normalization: tool names matching `mcp_<server>_<tool>` (Gemini) or `MCP:<name>` (Cursor) must be normalized to `mcp:<server>:<tool>` before the canonical event is constructed. The normalization function must handle both formats and produce consistent output. When the server component cannot be determined from the `MCP:<name>` Cursor format, the server segment must default to `unknown`.
- **Test criteria:** A unit test must verify that each adapter produces a dict containing all required fields for each supported event type. Missing or wrong-type fields must raise `ValueError` before any pipeline call is made. A unit test must verify that `mcp_postgres_query`, `MCP:postgres_query`, and `MCP:query` each produce distinct but valid `mcp:<server>:<tool>` strings.
- **Traces to:** UJ-01, UJ-02, UJ-03, UJ-04, UJ-05, UJ-08

**FR-102** [Phase 1] — The `ide_source` field must be stored as metadata on every Qdrant point written through a non-Claude-Code adapter.

- **Test criteria:** After a Gemini adapter write, a direct Qdrant scroll of the stored point must return `payload.ide_source == "gemini"`. Existing Claude Code points that lack this field must not be modified.
- **Traces to:** UJ-03

---

### 5.2 Gemini CLI Adapter

**FR-201** [Phase 1] — The system must provide a `SessionStart` adapter for Gemini CLI that reads the `BeforeAgent` or `SessionStart` hook JSON from stdin and outputs a JSON object with `hookSpecificOutput.additionalContext` populated with retrieved memories.

- The adapter must parse the Gemini-native stdin fields: `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `timestamp`.
- The adapter must map `cwd` to project context using the existing `detect_project()` function.
- The adapter output must be valid JSON only — no trailing text, no stderr content on stdout.
- **Test criteria:** Given a synthetic Gemini `SessionStart` stdin payload pointing to a project with known Qdrant fixtures, the adapter must produce stdout containing `hookSpecificOutput.additionalContext` with at least 1 retrieved memory within 3000ms. Given an empty Qdrant index, the adapter must exit 0 with a valid JSON output (additionalContext may be empty string).
- **Traces to:** UJ-02, UJ-04

**FR-202** [Phase 1] — The system must provide an `AfterTool` adapter for Gemini CLI that reads the `AfterTool` hook JSON from stdin and forks pattern/code capture to a background process.

- The adapter must parse Gemini-specific fields: `tool_name`, `tool_input`, `tool_response.llmContent`, `mcp_context`.
- The adapter must map `tool_name` to the canonical tool name (e.g., `write_file` → `Write`, `edit_file` → `Edit`).
- MCP tool names matching `mcp_<server>_<tool>` must be passed through FR-101 normalization before the background fork.
- The adapter must exit 0 in all cases and must not emit any output that blocks or modifies Gemini's tool execution.
- **Test criteria:** Given a synthetic Gemini `AfterTool` payload for a file write event, the adapter must fork a background process and exit 0 within 500ms. The background process must store a memory point in Qdrant within 10s. Given a malformed stdin payload, the adapter must exit 0 without raising an unhandled exception. Given a payload with `tool_name: "mcp_postgres_query"`, the stored point must have `tool_name == "mcp:postgres:query"`.
- **Traces to:** UJ-03, UJ-05, UJ-08

**FR-203** [Phase 1] — The system must provide a `PreCompress` adapter for Gemini CLI that maps to the existing `pre_compact_save` pipeline.

- The adapter must parse `trigger` field from the Gemini `PreCompress` payload.
- **Test criteria:** Given a synthetic Gemini `PreCompress` payload, the adapter must call the pre_compact pipeline and store a session summary memory within 10s. Adapter must exit 0 in all cases.
- **Traces to:** UJ-05

**FR-204** [Phase 1] — The Gemini CLI adapter scripts must be registered in `.gemini/settings.json` under the `hooks` key using Gemini's config format, with `AI_MEMORY_INSTALL_DIR` resolvable from the command string.

- Config format: `{ "hooks": { "AfterTool": [{ "matcher": ".*", "hooks": [{ "type": "command", "command": "...", "timeout": 60000 }] }] } }`
- The `AfterTool` matcher array must include a second entry with `matcher: "mcp_.*"` pointing to the same adapter command, to ensure MCP tool events are captured (see FR-208).
- **Test criteria:** The installer must produce a `.gemini/settings.json` that passes JSON schema validation against the Gemini hooks config format. The command value must not contain shell interpolation of user-supplied input.
- **Traces to:** UJ-01

**FR-205** [Phase 1] — The system must register a `search-memory` TOML command for Gemini CLI in `.gemini/commands/search-memory.toml`.

- TOML format:
  ```toml
  description = "Search ai-memory for relevant stored memories"
  prompt = "Search ai-memory for: {{args}}. Run: python3 $AI_MEMORY_INSTALL_DIR/src/memory/cli/search.py --query '{{args}}' --project $(pwd). Present the results clearly."
  ```
- `{{args}}` is the user-supplied search query passed at invocation.
- The prompt must instruct Gemini to invoke the ai-memory search script and present ranked results.
- **Test criteria:** The installed `.gemini/commands/search-memory.toml` must be valid TOML, must contain `description` and `prompt` keys, and `{{args}}` must appear in `prompt`. Invoking `/search-memory error handling` in a Gemini session must trigger the search script.
- **Traces to:** UJ-06

**FR-206** [Phase 1] — The system must register a `memory-status` TOML command for Gemini CLI in `.gemini/commands/memory-status.toml`.

- TOML format:
  ```toml
  description = "Show ai-memory system status: Qdrant health, collection counts, recent activity"
  prompt = "Check ai-memory status. Run: python3 $AI_MEMORY_INSTALL_DIR/src/memory/cli/status.py. Present the output as a status summary."
  ```
- **Test criteria:** The installed `.gemini/commands/memory-status.toml` must be valid TOML and must contain `description` and `prompt` keys.
- **Traces to:** UJ-06

**FR-207** [Phase 1] — The system must register a `save-memory` TOML command for Gemini CLI in `.gemini/commands/save-memory.toml` matching the `aim-save` Claude Code skill.

- **Test criteria:** The installed file must be valid TOML with `description` and `prompt`. The prompt must invoke the ai-memory manual save script.
- **Traces to:** UJ-06

**FR-208** [Phase 1] — The Gemini CLI `AfterTool` matcher config must include a dedicated entry for MCP tool events using the `mcp_.*` pattern.

- Config entry: `{ "matcher": "mcp_.*", "hooks": [{ "type": "command", "command": "<same AfterTool adapter command>", "timeout": 60000 }] }`
- The adapter invoked for MCP events must apply FR-101 normalization before the pipeline call.
- **Test criteria:** Given a Gemini `AfterTool` event with `hook_event_name: "AfterTool"` and `tool_name: "mcp_slack_send"`, the stored Qdrant point must have `tool_name == "mcp:slack:send"`.
- **Traces to:** UJ-08

---

### 5.3 Cursor IDE Adapter

**FR-301** [Phase 1] — The system must provide a `sessionStart` adapter for Cursor IDE that reads the `sessionStart` hook JSON from stdin and outputs a JSON object with `additional_context` populated with retrieved memories.

- The adapter must parse Cursor-specific fields: `conversation_id`, `generation_id`, `model`, `hook_event_name`, `cursor_version`, `workspace_roots`, `transcript_path`, `session_id`, `is_background_agent`, `composer_mode`.
- `session_id` must be sourced from the Cursor `session_id` field. When absent, fall back to `conversation_id`.
- `cwd` must be resolved from `workspace_roots[0]` when the Cursor `cwd` field is absent.
- **Test criteria:** Given a synthetic Cursor `sessionStart` payload with `workspace_roots` but no `cwd`, the adapter must resolve project from `workspace_roots[0]` and produce valid JSON output containing `additional_context`. Given a payload with `is_background_agent: true`, the adapter must exit 0 with empty `additional_context` (no retrieval for background agents).
- **Traces to:** UJ-02, UJ-04

**FR-302** [Phase 1] — The system must provide a `postToolUse` adapter for Cursor IDE that reads the `postToolUse` hook JSON from stdin and forks pattern capture to a background process.

- The adapter must parse Cursor-specific fields: `tool_name`, `tool_input`, `tool_output`, `tool_use_id`, `cwd`, `duration`, `model`.
- The adapter must map Cursor tool type strings to canonical tool names: `Write` → `Write`, `Read` → `Read`, `Shell` → `Bash`.
- MCP tool names matching `MCP:<name>` must be passed through FR-101 normalization before the background fork.
- **Known issue:** Cursor has symlink resolution issues with `.claude/` folder references. Adapter must resolve script paths via `AI_MEMORY_INSTALL_DIR` env var, not relative symlinks.
- **Test criteria:** Given a Cursor `postToolUse` payload with `tool_name: "Write"`, the adapter must fork to background and exit 0 within 500ms. Given a payload with an unsupported `tool_name`, the adapter must exit 0 without forking. Path resolution must not use symlinks under `.claude/`. Given a payload with `tool_name: "MCP:github_search"`, the stored point must have `tool_name == "mcp:unknown:github_search"`.
- **Traces to:** UJ-03, UJ-08

**FR-303** [Phase 1] — The system must provide a `preCompact` adapter for Cursor IDE that maps to the existing `pre_compact_save` pipeline.

- The adapter must parse `trigger`, `context_usage_percent`, `context_tokens`, `context_window_size` from the Cursor `preCompact` payload.
- **Test criteria:** Given a synthetic Cursor `preCompact` payload, the adapter must store a session summary within 10s. Adapter must exit 0 in all cases.
- **Traces to:** UJ-05

**FR-304** [Phase 1] — The Cursor IDE adapter scripts must be registered in `.cursor/hooks.json` under the `hooks` key using Cursor's config format, with `version: 1` and correct event names.

- Config format: `{ "version": 1, "hooks": { "postToolUse": [{ "command": "...", "timeout": 5 }] } }`
- The `postToolUse` hook array must include a second entry with matcher `MCP:.*` for MCP tool capture (see FR-309).
- **Test criteria:** The installer must produce a `.cursor/hooks.json` that passes JSON schema validation. All fire-and-forget event hooks (`postToolUse`, `preCompact`, `sessionStart`) must not use `failClosed: true`. The command string must not contain shell interpolation of user-supplied paths.
- **Traces to:** UJ-01

**FR-305** [Phase 1] — The system must register a `search-memory` skill for Cursor IDE in `.cursor/skills/search-memory/SKILL.md`.

- SKILL.md format (YAML frontmatter + markdown body):
  ```yaml
  ---
  name: search-memory
  description: Search ai-memory for relevant stored memories
  allowed-tools: Bash
  ---
  ```
  Body must contain instructions for the agent to run the ai-memory search CLI script with the user's query and present results. The script must be invoked via `$AI_MEMORY_INSTALL_DIR`.
- **Test criteria:** The installed SKILL.md must be valid YAML frontmatter with `name` and `description` fields. The body must reference `$AI_MEMORY_INSTALL_DIR` for script resolution.
- **Traces to:** UJ-06

**FR-306** [Phase 1] — The system must register a `memory-status` skill for Cursor IDE in `.cursor/skills/memory-status/SKILL.md`.

- SKILL.md format with YAML frontmatter (`name: memory-status`, `description: Check AI Memory system status`) and body instructing the agent to invoke the ai-memory status CLI script.
- **Test criteria:** Installed SKILL.md must pass YAML frontmatter parse with required fields present.
- **Traces to:** UJ-06

**FR-307** [Phase 1] — The system must register a `save-memory` skill for Cursor IDE in `.cursor/skills/save-memory/SKILL.md` matching the `aim-save` Claude Code skill.

- **Test criteria:** Installed SKILL.md must be valid with `name` and `description`. Body must invoke ai-memory manual save script via `$AI_MEMORY_INSTALL_DIR`.
- **Traces to:** UJ-06

**FR-308** [Phase 1] — The Cursor IDE `postToolUse` hook config must include a dedicated matcher entry for MCP tool events using the `MCP:.*` pattern.

- Config entry: `{ "matcher": "MCP:.*", "command": "<same postToolUse adapter command>", "timeout": 5 }`
- **Test criteria:** A Cursor `postToolUse` event with `tool_name: "MCP:database_query"` must be captured by this matcher and produce a Qdrant point with `tool_name == "mcp:unknown:database_query"`.
- **Traces to:** UJ-08

---

### 5.4 OpenAI Codex CLI Adapter

**FR-401** [Phase 1] — The system must provide a `SessionStart` adapter for Codex CLI that reads the `SessionStart` hook JSON from stdin and outputs a JSON object with `hookSpecificOutput` populated with retrieved memories.

- The adapter must parse Codex-specific fields: `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `model`, `turn_id`.
- Output must be valid JSON matching the Codex stdout schema: `{ "hookSpecificOutput": { "systemMessage": "..." } }` or equivalent context-injection field.
- **Test criteria:** Given a synthetic Codex `SessionStart` stdin payload pointing to a project with known Qdrant fixtures, the adapter must produce stdout with `hookSpecificOutput` containing at least 1 retrieved memory within 3000ms. Given malformed stdin, the adapter must exit 0 with valid JSON output.
- **Traces to:** UJ-02, UJ-04

**FR-402** [Phase 1] — The system must provide a `PostToolUse` adapter for Codex CLI that reads the `PostToolUse` hook JSON from stdin and forks pattern capture to a background process.

- Codex `PostToolUse` currently supports Bash tool only. The adapter must handle at minimum: Bash tool events, which carry command/output data relevant to error detection.
- **Known constraint:** Codex `PreToolUse` and `PostToolUse` are Bash-only as of the current Codex CLI release. File write/edit events (Write, Edit) do not trigger `PostToolUse` hooks. This means file-write capture is not available for Codex until Codex expands `PostToolUse` to cover additional tool types. This is a platform gap, not an implementation gap. Track upstream Codex changelog for expansion.
- **Test criteria:** Given a Codex `PostToolUse` payload for a Bash tool event, the adapter must fork to background and exit 0 within 500ms. The background process must invoke error_detection if the tool output contains an error signature matching the existing `TRIGGER_CONFIG` patterns.
- **Traces to:** UJ-04

**FR-403** [Phase 1] — The Codex CLI adapter scripts must be registered in `.codex/hooks.json` using Codex's config format.

- Config format: `{ "hooks": { "SessionStart": [{ "matcher": ".*", "hooks": [{ "type": "command", "command": "...", "timeout": 600 }] }] } }`
- **Test criteria:** The installer must produce a `.codex/hooks.json` that passes JSON schema validation. The default timeout of 600s must be reduced to 30s for SessionStart and 10s for PostToolUse in the generated config. The command string must not contain shell interpolation of user-supplied paths.
- **Traces to:** UJ-01

**FR-404** [Phase 1] — The system must provide a `UserPromptSubmit` adapter for Codex CLI that reads the `UserPromptSubmit` hook JSON from stdin and performs per-turn context injection.

- The adapter mirrors the behavior of `context_injection_tier2.py` in Claude Code: it reads the user prompt from stdin, queries Qdrant for relevant memories using a lightweight semantic match, and outputs context to stdout in Codex's `UserPromptSubmit` output format (`{ "hookSpecificOutput": { "additionalContext": "..." } }` or equivalent).
- The adapter must complete and flush stdout within 2000ms to avoid perceptible per-turn latency.
- When Qdrant is unavailable, the adapter must exit 0 with valid empty JSON output — it must never block the turn.
- **Test criteria:** Given a Codex `UserPromptSubmit` payload with prompt `"what authentication pattern do we use?"`, the adapter must query Qdrant and produce stdout with at least 1 injected memory within 2000ms on a populated index. Given Qdrant unavailable, exit 0 with valid JSON within 200ms.
- **Traces to:** UJ-02, UJ-07

**FR-405** [Phase 1] — The system must provide a `Stop` adapter for Codex CLI that reads the `Stop` hook JSON from stdin and captures a session summary.

- The adapter mirrors the behavior of `agent_response_capture.py` in Claude Code: it extracts the session transcript from the `Stop` payload, generates a session summary, and stores it in the `discussions` collection under `type: "session"`.
- The `Stop` adapter runs synchronously (not fire-and-forget) because it fires at session end where latency does not block the user.
- **Test criteria:** Given a synthetic Codex `Stop` payload containing a transcript of at least 5 turns, the adapter must store a session summary point in Qdrant's `discussions` collection within 10s. The point must have `type == "session"` and `ide_source == "codex"`.
- **Traces to:** UJ-05

**FR-406** [Phase 1] — The system must register a `search-memory` skill for Codex CLI in `.agents/skills/search-memory/SKILL.md`.

- SKILL.md format (YAML frontmatter + markdown body, same format as Cursor):
  ```yaml
  ---
  name: search-memory
  description: Search ai-memory for relevant stored memories
  allowed-tools: shell
  ---
  ```
  Body must instruct the agent to invoke the ai-memory search CLI script using `$AI_MEMORY_INSTALL_DIR` and present ranked results to the user.
- The `.agents/skills/` path is the Codex-native skill directory. The `.codex/skills/` path is an alias and must also be supported if Codex resolves both.
- **Test criteria:** The installed SKILL.md must pass YAML frontmatter parse with `name` and `description` present. Body must reference `$AI_MEMORY_INSTALL_DIR`.
- **Traces to:** UJ-06

**FR-407** [Phase 1] — The system must register a `memory-status` skill for Codex CLI in `.agents/skills/memory-status/SKILL.md`.

- SKILL.md format with YAML frontmatter (`name: memory-status`, `description: Check AI Memory system status`) and body instructing the agent to invoke the ai-memory status CLI script via `$AI_MEMORY_INSTALL_DIR`.
- **Test criteria:** Installed SKILL.md must pass YAML frontmatter parse with required fields present.
- **Traces to:** UJ-06

**FR-408** [Phase 1] — Codex CLI MCP integration note: Codex CLI supports `mcp_servers` config for MCP server registration. Whether `PostToolUse` or other hooks fire on MCP tool invocations is not confirmed in the current Codex CLI hook documentation. MCP event capture for Codex is a known gap pending upstream clarification. The adapter must log a warning if an unrecognized tool name pattern is encountered that may indicate an MCP tool.

- **Test criteria:** Given a Codex `PostToolUse` payload with an unrecognized `tool_name` not matching any known Codex native tool, the adapter must log a structured warning (`"unrecognized_tool_name"`) to stderr and exit 0 without forking.
- **Traces to:** UJ-08

---

### 5.5 Installer Changes

**FR-501** [Phase 1] — The installer must detect the presence of each target IDE before writing its config file.

- Detection method: check for `gemini` binary in PATH for Gemini CLI; check for `.cursor` directory existence or `cursor` binary in PATH for Cursor; check for `codex` binary in PATH for Codex CLI.
- The installer must not write a config file for an IDE that is not detected.
- **Test criteria:** On a system where only `gemini` is in PATH (not `codex` or `cursor`), `add-project` must produce `.gemini/settings.json` and must not produce `.cursor/hooks.json` or `.codex/hooks.json`. Test with mocked PATH.
- **Traces to:** UJ-01 (SC-08)

**FR-502** [Phase 1] — The installer must support an `--ide` flag that explicitly includes or excludes IDEs regardless of detection result.

- Example: `ai-memory add-project --ide gemini,cursor` must write Gemini and Cursor configs even if detection fails.
- **Test criteria:** `add-project --ide gemini` on a system with no `gemini` in PATH must produce `.gemini/settings.json`. `add-project --ide none` must skip all IDE config generation.
- **Traces to:** UJ-01

**FR-503** [Phase 1] — The installer must write all required env vars into each IDE's config file using that IDE's native env block mechanism.

- Required env vars to propagate: `AI_MEMORY_INSTALL_DIR`, `AI_MEMORY_PROJECT_ID`, `QDRANT_HOST`, `QDRANT_PORT`, `EMBEDDING_HOST`, `EMBEDDING_PORT`, `SIMILARITY_THRESHOLD`, `LOG_LEVEL`.
- For Gemini CLI: write to `env` block in `.gemini/settings.json`.
- For Cursor IDE: write to `env` block in `sessionStart` hook output or equivalent.
- For Codex CLI: write to the `hooks.json` command string using `env` propagation.
- **Test criteria:** After `add-project`, each generated config file must contain all 8 required env vars. Verify by parsing the generated JSON and asserting key presence.
- **Traces to:** UJ-01

**FR-504** [Phase 1] — The installer must not overwrite an existing IDE config file if it already contains ai-memory hook registrations.

- Detection: check for the presence of `AI_MEMORY_INSTALL_DIR` string in the existing config file.
- When an existing registration is detected, the installer must print a warning and skip that IDE's config write.
- **Test criteria:** Run `add-project` twice on the same project. Second run must not modify the config files written by the first run. File mtime must be unchanged on second run.
- **Traces to:** UJ-01

**FR-505** [Phase 1] — The installer must support a `--force` flag that overwrites existing IDE config files.

- **Test criteria:** `add-project --force` on a project with existing configs must overwrite all IDE config files. File mtime must be newer after the run.
- **Traces to:** UJ-01

**FR-506** [Phase 1] — The installer must create the `.gemini/commands/` directory and write TOML command files for `search-memory`, `memory-status`, and `save-memory` when Gemini CLI is detected.

- **Test criteria:** After `add-project` with Gemini detected, `.gemini/commands/search-memory.toml`, `.gemini/commands/memory-status.toml`, and `.gemini/commands/save-memory.toml` must exist and be valid TOML.
- **Traces to:** UJ-01, UJ-06

**FR-507** [Phase 1] — The installer must create `.cursor/skills/<name>/SKILL.md` files for `search-memory`, `memory-status`, and `save-memory` when Cursor IDE is detected.

- **Test criteria:** After `add-project` with Cursor detected, all three SKILL.md files must exist under `.cursor/skills/` and pass YAML frontmatter validation.
- **Traces to:** UJ-01, UJ-06

**FR-508** [Phase 1] — The installer must create `.agents/skills/<name>/SKILL.md` files for `search-memory` and `memory-status` when Codex CLI is detected.

- **Test criteria:** After `add-project` with Codex detected, `.agents/skills/search-memory/SKILL.md` and `.agents/skills/memory-status/SKILL.md` must exist and pass YAML frontmatter validation.
- **Traces to:** UJ-01, UJ-06

---

### 5.6 Event Normalization

**FR-601** [Phase 1] — Each adapter must normalize the IDE-native session identifier to the canonical `session_id` field using a documented fallback chain.

- Fallback chain: (1) native `session_id` field; (2) `conversation_id` (Cursor); (3) `transcript_path` basename (strip extension); (4) generate a UUID seeded from `cwd + timestamp`.
- The resolved `session_id` must be set in the subprocess environment as `CLAUDE_SESSION_ID` to maintain compatibility with existing pipeline code that reads this env var.
- **Test criteria:** Given a payload with no `session_id` and no `conversation_id` but a valid `transcript_path`, the adapter must resolve `session_id` from the transcript path basename. Verify via unit test asserting `os.environ["CLAUDE_SESSION_ID"]` is set before the background fork.
- **Traces to:** UJ-02, UJ-03, UJ-04

**FR-602** [Phase 1] — Each adapter must resolve `cwd` using a documented fallback chain.

- Fallback chain: (1) native `cwd` field; (2) `workspace_roots[0]` (Cursor); (3) `GEMINI_CWD` / `CURSOR_PROJECT_DIR` / env equivalents; (4) `os.getcwd()` at adapter invocation time.
- **Test criteria:** Given a Cursor payload with no `cwd` field but `workspace_roots: ["/home/user/project"]`, the adapter must set `cwd = "/home/user/project"`. Verify via unit test.
- **Traces to:** UJ-01, UJ-02

**FR-603** [Phase 1] — Each adapter's stdout output must conform strictly to the target IDE's required JSON format.

- Gemini: stdout must be valid JSON; plain text output causes Gemini to warn and may be suppressed.
- Cursor: stdout must be valid JSON matching the Cursor output schema.
- Codex: stdout must be valid JSON.
- Claude Code: stdout is plain text or JSON with `systemMessage` (unchanged).
- **Test criteria:** For each adapter, run 100 synthetic payloads and assert that `json.loads(captured_stdout)` succeeds for every output. Assert that stderr is clean (no output on stdout from logging).
- **Traces to:** UJ-02, UJ-03

---

### 5.7 Phase 2: Keyword Trigger Adapters

The three trigger scripts (`decision_keyword_trigger.py.disabled`, `best_practices_keyword_trigger.py.disabled`, `session_history_trigger.py.disabled`) exist in the Claude Code hooks directory and implement the full detection and injection logic. Phase 2 enables these scripts and creates per-prompt hook adapters for Gemini, Cursor, and Codex that translate their per-turn hook payloads into the format these scripts expect (JSON stdin with `prompt` and `cwd` fields).

**FR-701** [Phase 2] — The three disabled trigger scripts must be enabled for Claude Code by renaming them (removing `.disabled` suffix) and setting `enabled: true` in `TRIGGER_CONFIG`.

- **decision_keywords trigger:** Detects keywords ("why did we", "what was decided", "remember when", etc.) in the user prompt; searches `discussions` collection filtered to `type: "decision"`; injects up to 2 results.
- **best_practices_keywords trigger:** Detects keywords ("best practice", "coding standard", "convention", "how should I", etc.); searches `conventions` collection filtered to `type: ["rule", "guideline"]`; injects up to 3 results. Conventions are global (not project-scoped).
- **session_history_keywords trigger:** Detects keywords ("what have we done", "project status", "where were we", etc.); searches `discussions` collection filtered to `type: "session"`; injects up to 3 results.
- All three scripts already implement graceful degradation (exit 0 on any failure) and Qdrant unavailability handling.
- **Test criteria:** With `enabled: true` in TRIGGER_CONFIG, each trigger script must fire on a matching prompt and inject context, and must exit 0 silently on a non-matching prompt. Verified via integration test with synthetic Claude Code `UserPromptSubmit` payloads.
- **Traces to:** UJ-07

**FR-702** [Phase 2] — The system must provide a `UserPromptSubmit` trigger adapter for Gemini CLI that maps the Gemini `BeforeAgent` hook to the same trigger pipeline as FR-701.

- The adapter must read the Gemini `BeforeAgent` payload from stdin, extract the `prompt` field (or equivalent user input field), construct a synthetic JSON payload in the format `{"prompt": "<user_input>", "cwd": "<cwd>"}`, and invoke each enabled trigger script, collecting their stdout to inject as `additionalContext` in the Gemini output.
- Hook mapping: Gemini `BeforeAgent` → Claude Code `UserPromptSubmit` equivalent.
- The adapter must complete within 2000ms and must not block the session if triggers take too long (apply a per-trigger subprocess timeout of 1500ms).
- **Test criteria:** Given a Gemini `BeforeAgent` payload with prompt `"what was decided about the auth approach?"`, the adapter must invoke `decision_keyword_trigger.py`, capture its stdout, and include it in `hookSpecificOutput.additionalContext`. Given a non-matching prompt, the adapter must produce empty `additionalContext` and exit 0 within 200ms.
- **Traces to:** UJ-07

**FR-703** [Phase 2] — The system must provide a `beforeSubmitPrompt` trigger adapter for Cursor IDE that maps the Cursor per-turn hook to the same trigger pipeline as FR-701.

- Hook mapping: Cursor `beforeSubmitPrompt` (or equivalent per-turn hook) → Claude Code `UserPromptSubmit` equivalent.
- The adapter must extract the user prompt from the Cursor payload, invoke enabled trigger scripts with a per-trigger timeout of 1500ms, and inject collected output into the Cursor output JSON.
- **Test criteria:** Given a Cursor `beforeSubmitPrompt` payload with prompt `"best practice for error handling here?"`, the adapter must invoke `best_practices_keyword_trigger.py` and return results in Cursor JSON output format within 2000ms.
- **Traces to:** UJ-07

**FR-704** [Phase 2] — The system must provide a `UserPromptSubmit` trigger adapter for Codex CLI that maps the Codex `UserPromptSubmit` hook to the same trigger pipeline as FR-701.

- The Codex `UserPromptSubmit` hook fires natively on each user turn, so the adapter receives the Codex `UserPromptSubmit` payload directly and invokes trigger scripts.
- Per-trigger subprocess timeout: 1500ms. Total adapter timeout: 2000ms.
- The Phase 1 FR-404 `UserPromptSubmit` adapter handles semantic memory injection; the Phase 2 FR-704 adapter handles keyword-triggered injection. These may be merged into a single `UserPromptSubmit` adapter with both behaviors or kept separate, at implementation discretion.
- **Test criteria:** Given a Codex `UserPromptSubmit` payload with prompt `"where were we on the migration task?"`, the adapter must invoke `session_history_trigger.py` and include results in the Codex output JSON within 2000ms.
- **Traces to:** UJ-07

---

### 5.8 Phase 2: Gemini CLI Slash Command Parity

*Note: FR-205, FR-206, FR-207 in Phase 1 deliver the TOML command registrations for Gemini. Phase 2 adds any additional parity items not covered in Phase 1 and validates end-to-end invocation in a live Gemini session.*

**FR-801** [Phase 2] — End-to-end validation of Gemini CLI slash commands must be performed against a live Gemini CLI session.

- **Test criteria:** In a live Gemini CLI session with ai-memory installed, invoking `/search-memory authentication` must trigger the search script and return at least 1 result from a pre-populated Qdrant index. Invoking `/memory-status` must return Qdrant health and collection counts. SC-09 must pass.
- **Traces to:** UJ-06 (SC-09)

---

## 6. Non-Functional Requirements

### 6.1 Latency

**NFR-101** — The `SessionStart`/`BeforeAgent`/`sessionStart` adapter hook for each IDE must complete (stdout flushed, process exits) within 3000ms at p95 measured over 10 sequential invocations against a running Qdrant instance with a minimum of 100 stored points.

**NFR-102** — The `PostToolUse`/`AfterTool`/`postToolUse` adapter hook for each IDE must complete (background fork complete, process exits 0) within 500ms at p95. The background store process must complete within 10s.

**NFR-103** — Adapters must not add latency to IDE tool execution. All capture operations must be fire-and-forget (fork to background, exit immediately) using the existing `subprocess.Popen(start_new_session=True)` pattern from `post_tool_capture.py`.

**NFR-104** — Per-turn trigger adapters (FR-702, FR-703, FR-704) must complete within 2000ms with a per-trigger subprocess timeout of 1500ms. Triggers that exceed their timeout must be silently abandoned; the adapter must still exit 0 with valid JSON output.

### 6.2 Security

**NFR-201** — Adapter scripts must not construct shell command strings using string interpolation of any value sourced from hook stdin. All file paths and arguments must be passed via `sys.argv` or as structured data to `subprocess.Popen(args=[...])`, never via `shell=True`.

**NFR-202** — The security scanning pipeline (3-layer: regex, detect-secrets, SpaCy NER) that runs before Qdrant writes must be invoked identically for all IDE adapters. No IDE adapter may bypass or short-circuit the security scan.

**NFR-203** — IDE config files written by the installer must not contain credentials, API keys, or user-identifiable information other than the env vars listed in FR-503. `AI_MEMORY_PROJECT_ID` must be derived from project directory name, not from any external identifier.

### 6.3 Backward Compatibility

**NFR-301** — The Claude Code hook scripts (`.claude/hooks/scripts/*.py`) must not be modified by FEATURE-001. The Claude Code `.claude/settings.json` schema must not change. The existing Claude Code hook behavior must be byte-for-byte identical to v2.2.6 baseline.

**NFR-302** — Existing Qdrant collections and point schemas must not change. The `ide_source` metadata field added by FR-102 must be stored on new points only; existing points without this field must remain valid and retrievable.

**NFR-303** — All adapter scripts must degrade gracefully when Qdrant is unavailable: exit 0, produce valid (empty) JSON output for retrieval hooks, and log the failure to stderr only.

### 6.4 Testability

**NFR-401** — Each adapter must be testable in isolation using synthetic stdin payloads (no live IDE required). Unit tests must cover: valid payload, malformed JSON payload, missing required fields, Qdrant unavailable, empty results.

**NFR-402** — The installer config-generation logic must be testable without a live filesystem IDE installation. Integration tests may mock binary detection and filesystem writes.

---

## 7. Out of Scope

The following are explicitly excluded from FEATURE-001 (all phases):

- **Windows support for Codex CLI** — Codex CLI has temporarily disabled Windows support upstream. ai-memory adapters will not be tested on Windows for this feature.
- **Multi-user / team memory sharing** — This feature targets individual developers. Shared Qdrant instance across multiple users is a v3.0 enterprise concern.
- **IDE UI integration** — No Cursor extension, Gemini plugin, or Codex CLI plugin. Hooks only.
- **Automatic migration of memories tagged with `ide_source`** — Points stored before FEATURE-001 will lack `ide_source` metadata. No backfill migration is included.
- **Cursor enterprise/team config precedence** — Cursor supports enterprise > team > project > user config precedence. FEATURE-001 only targets project-level config (`.cursor/hooks.json`).
- **Codex CLI user-level hooks** (`~/.codex/hooks.json`) — FEATURE-001 only targets repo-level `.codex/hooks.json`.
- **BeforeModel / AfterModel hooks (Gemini)** — These fire on every LLM inference call. The overhead and value tradeoff is not established. Not included.
- **Langfuse tracing for non-Claude-Code adapters** — Tracing instrumentation will be added in a follow-on; FEATURE-001 adapters must not block on Langfuse initialization.
- **MCP tool capture for Codex CLI** — Pending upstream confirmation of whether Codex hooks fire on MCP tool invocations (see FR-408). This gap will be revisited when Codex CLI hook documentation is updated.
- **`aim-save` skill for Codex CLI** — Manual save equivalent for Codex is Phase 2, not Phase 1.

Items previously listed as Out of Scope that are now in scope:
- Gemini CLI slash commands (`/search-memory`, `/memory-status`, `/save-memory`) — moved to Phase 1 (FR-205, FR-206, FR-207).
- Cursor IDE skill registration (`search-memory`, `memory-status`, `save-memory`) — moved to Phase 1 (FR-305, FR-306, FR-307).
- Three disabled triggers (decision_keywords, best_practices_keywords, session_history_keywords) — moved to Phase 2 (FR-701 through FR-704).
- MCP tool event capture for Gemini CLI and Cursor IDE — moved to Phase 1 (FR-208, FR-308, FR-101 normalization).
