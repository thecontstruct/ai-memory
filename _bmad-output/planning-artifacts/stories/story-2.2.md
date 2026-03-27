---
id: "2.2"
title: "Update .claude/settings.json command paths to adapters/claude/"
epic: "Claude Code Adapter Migration"
sprint: 1
status: ready
effort: S
depends_on: ["2.1"]
traces_to: ["FR-101", "NFR-301"]
---

# Story 2.2: Update `.claude/settings.json` command paths to `adapters/claude/`

## 1. User Story
As a Claude Code user, I want the hook command paths in `.claude/settings.json` updated to reference the new `adapters/claude/` location, so that Claude Code loads the migrated adapter scripts without any manual path changes.

## 2. Acceptance Criteria
- [ ] All hook command strings in `.claude/settings.json` reference `$AI_MEMORY_INSTALL_DIR/adapters/claude/` paths
- [ ] No command string references `.claude/hooks/scripts/`
- [ ] The installer template that generates `.claude/settings.json` is updated to the new paths
- [ ] `pytest` invocation of the Claude Code hook path / migration integration suite (SC-07) exits 0 with zero failed tests after updating command paths
- [ ] `.claude/settings.json` JSON schema is unchanged (NFR-301)

## 3. Technical Context
### Files to Create/Modify
- `.claude/settings.json` — update all `command` string values referencing hook scripts
- Installer template or generation logic for `.claude/settings.json` — update to use `$AI_MEMORY_INSTALL_DIR/adapters/claude/<script>.py` paths

### Architecture References
- §2 Claude Code as Adapter — states `.claude/settings.json` command paths update to `$AI_MEMORY_INSTALL_DIR/adapters/claude/*.py`
- §5 Adapter Script Installation — confirms `adapters/claude/` is the canonical install path for Claude Code hook entry points

### Standards to Follow
- JSON schema of `.claude/settings.json` must not change — only `command` string values change (NFR-301)

## 4. Dependencies
- Story 2.1 must complete first because the scripts at `adapters/claude/` must exist before their paths are written into the config; the integration test suite (SC-07) must pass with the new paths pointing to real files

## 5. Out of Scope
- Any changes to the JSON structure or schema of `.claude/settings.json`
- Installer config generation for Gemini, Cursor, or Codex — Epic 6

## 6. Implementation Notes
- Only `command` string values change — the hook structure (event names, matchers, timeouts) is identical
- If the installer uses a template file to generate `.claude/settings.json`, update the template; if it generates inline, update the generation logic — do not patch both if only one is authoritative
- Command string format: `"$AI_MEMORY_INSTALL_DIR/.venv/bin/python" "$AI_MEMORY_INSTALL_DIR/adapters/claude/<script>.py"` per the architecture §4 example
- Run `pytest` with SC-07 marker or equivalent scope after the path update to confirm zero regressions before marking this story done

## 7. Definition of Done
- [ ] All acceptance criteria pass
- [ ] Unit tests written and passing
- [ ] No linter errors
- [ ] Code reviewed
