---
id: "3.5"
title: "Create Gemini TOML command templates"
epic: "Gemini CLI Adapter"
sprint: 1
status: ready
effort: S
depends_on: ["1.1"]
traces_to: ["FR-205", "FR-206", "FR-207"]
---

# Story 3.5: Create Gemini TOML command templates

## 1. User Story
As a Gemini CLI user, I want slash commands for searching, checking the status of, and manually saving memories, so that I can interact with the memory system directly from within Gemini.

## 2. Acceptance Criteria
- [ ] All three files exist under `src/memory/adapters/templates/gemini/`
- [ ] Each file is valid TOML with `description` and `prompt` keys
- [ ] `search-memory.toml` contains `{{args}}` in the `prompt` value
- [ ] `search-memory.toml` prompt instructs Gemini to invoke the ai-memory search script via `$AI_MEMORY_INSTALL_DIR` with the query as a discrete argv element (not shell-interpolated)
- [ ] `memory-status.toml` prompt instructs Gemini to run the ai-memory status CLI script
- [ ] `save-memory.toml` prompt instructs Gemini to invoke the manual save script
- [ ] All three files parse without error using a TOML parser in a unit test

## 3. Technical Context
### Files to Create/Modify
- `src/memory/adapters/templates/gemini/search-memory.toml` — create
- `src/memory/adapters/templates/gemini/memory-status.toml` — create
- `src/memory/adapters/templates/gemini/save-memory.toml` — create
- `src/memory/adapters/tests/test_gemini_toml_templates.py` — create unit test that parses all three files with `tomllib` (Python 3.11+) or `tomli`

### Architecture References
- §5 Skill / Command Deployment — provides the `search-memory.toml` reference implementation verbatim; implement it exactly
- §5 Skill / Command Deployment — defines the target install location as `.gemini/commands/` (the installer copies from `templates/gemini/` at install time in Epic 6)

### Standards to Follow
- Files: `snake_case` or `kebab-case` for TOML files as shown in the architecture (project-context.md Docker services use kebab-case; TOML files follow IDE naming convention)
- Tests: `test_*.py` files with `test_` prefix (project-context.md)

## 4. Dependencies
- Story 1.1 must complete first — `VALID_IDE_SOURCES` and canonical schema context is needed for template content accuracy; also `src/memory/adapters/` package must exist for placing the `templates/` subdirectory

## 5. Out of Scope
- Copying templates to `.gemini/commands/` — Epic 6 installer (Story 6.2)
- Cursor SKILL.md equivalents — Stories 4.5 (backlog)
- Codex SKILL.md equivalents — Stories 5.5 (backlog)

## 6. Implementation Notes
- `search-memory.toml` reference from architecture §5:
  ```toml
  description = "Search ai-memory for relevant stored memories"
  prompt = "Search ai-memory for: {{args}}. Execute the command [$AI_MEMORY_INSTALL_DIR/.venv/bin/python, $AI_MEMORY_INSTALL_DIR/src/memory/search.py, --query, {{args}}, --project, <current directory basename>] without shell interpolation. Present the results clearly."
  ```
- `$AI_MEMORY_INSTALL_DIR` is a placeholder the installer resolves at copy time (Story 6.2) — keep it as a literal string in the template
- `{{args}}` is Gemini's template variable for user-supplied command arguments — must appear at least once in `search-memory.toml` prompt
- `memory-status.toml` should instruct Gemini to run `$AI_MEMORY_INSTALL_DIR/.venv/bin/python $AI_MEMORY_INSTALL_DIR/src/memory/status.py` (or equivalent status script)
- `save-memory.toml` should instruct Gemini to invoke `$AI_MEMORY_INSTALL_DIR/adapters/claude/manual_save_memory.py` or the equivalent manual save entry point
- The unit test should use `tomllib` (stdlib in Python 3.11+) or `tomli` (backport); check existing project dependencies to determine which is available; if neither, add `tomli` as a test-only dependency or use `subprocess` to call `python -c "import tomllib; tomllib.load(...)"`
- These are static template files — no logic, no tests for content correctness beyond TOML validity

## 7. Definition of Done
- [ ] All acceptance criteria pass
- [ ] Unit tests written and passing
- [ ] No linter errors
- [ ] Code reviewed
