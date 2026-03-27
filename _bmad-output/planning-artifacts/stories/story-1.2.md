---
id: "1.2"
title: "Add normalize_mcp_tool_name() to schema.py"
epic: "Canonical Schema and Shared Infrastructure"
sprint: 1
status: ready
effort: S
depends_on: ["1.1"]
traces_to: ["FR-101"]
---

# Story 1.2: Add `normalize_mcp_tool_name()` to `schema.py`

## 1. User Story
As a platform developer, I want a shared MCP tool name normalizer, so that IDE-specific MCP tool name formats are all converted to a single canonical `mcp:<server>:<tool>` format before storage.

## 2. Acceptance Criteria
- [ ] `normalize_mcp_tool_name("mcp_postgres_query")` returns `"mcp:postgres:query"`
- [ ] `normalize_mcp_tool_name("MCP:postgres_query")` returns `"mcp:unknown:postgres_query"`
- [ ] `normalize_mcp_tool_name("MCP:query")` returns `"mcp:unknown:query"`
- [ ] `normalize_mcp_tool_name("Write")` returns `None`
- [ ] `normalize_mcp_tool_name("mcp_slack_send")` returns `"mcp:slack:send"`
- [ ] All unit tests are in `test_schema.py` and pass

## 3. Technical Context
### Files to Create/Modify
- `src/memory/adapters/schema.py` — add `normalize_mcp_tool_name()` function
- `src/memory/adapters/tests/test_schema.py` — add unit tests for all AC cases

### Architecture References
- §2 MCP Tool Name Normalization — provides the complete `normalize_mcp_tool_name()` reference implementation using `re.match`; implement it verbatim
- §3 MCP Tool Name Storage — explains that normalized `mcp:<server>:<tool>` format is stored in Qdrant `tool_name` field

### Standards to Follow
- Files: `snake_case.py` (project-context.md)
- Functions: `snake_case` (project-context.md)
- Tests: `test_*.py` files with `test_` prefix on functions (project-context.md)
- No new pip dependencies — `re` is stdlib (architecture §1)

## 4. Dependencies
- Story 1.1 must complete first because `normalize_mcp_tool_name()` is added to the `schema.py` file created in 1.1, and tests extend `test_schema.py` created in 1.1

## 5. Out of Scope
- Normalization of non-MCP tool names (e.g., `"Write"` → `"Write"` is a no-op handled by callers checking for `None` return)
- Gemini-to-canonical tool name mapping for non-MCP tools (e.g., `"write_file"` → `"Write"`) — handled in each adapter's normalizer

## 6. Implementation Notes
- Gemini pattern: `^mcp_([^_]+)_(.+)$` — captures server as group 1, tool as group 2 (architecture §2)
- Cursor pattern: `^MCP:(.+)$` — server defaults to `"unknown"` because Cursor does not expose the server name (architecture §2, Known Limitation 3)
- If neither pattern matches, return `None` — callers use `mcp_name or tool_name` to fall back to the original tool name
- The reference implementation in architecture §2 uses `re.match` (not `re.search`) — match from start of string is correct and intentional
- `mcp_slack_send` → group 1 = `"slack"`, group 2 = `"send"` → `"mcp:slack:send"`

## 7. Definition of Done
- [ ] All acceptance criteria pass
- [ ] Unit tests written and passing
- [ ] No linter errors
- [ ] Code reviewed
