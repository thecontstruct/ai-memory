---
project_name: ai-memory
feature: "FEATURE-001: Multi-IDE Support"
author: Architect
date: 2026-03-26
version: "1.0-draft"
status: draft
prd_version: "1.1"
---

# Architecture Document — FEATURE-001: Multi-IDE Support

## Table of Contents

1. [Technology Stack](#1-technology-stack)
2. [System Design](#2-system-design)
3. [Data Architecture](#3-data-architecture)
4. [Security Architecture](#4-security-architecture)
5. [Infrastructure and Deployment](#5-infrastructure-and-deployment)
6. [Code Organization](#6-code-organization)
7. [Performance and Scale](#7-performance-and-scale)
8. [Technical Constraints and Trade-offs](#8-technical-constraints-and-trade-offs)

---

## 1. Technology Stack

### Existing Stack (No Changes)

| Component | Version | Notes |
|-----------|---------|-------|
| Python | 3.10+ | All adapter scripts |
| Qdrant | 1.16.3 | Vector DB, unchanged schema |
| FastEmbed | jina-embeddings-v2-base-en/code | 768-dim embeddings |
| Pydantic v2 | 2.0+ | Config validation |
| structlog | 24+ | Structured logging |
| httpx | 0.27+ | HTTP client with explicit timeouts |

**Rationale:** All four IDEs — including Claude Code — normalize through the canonical event schema in `adapters/schema.py`. Claude Code hooks are refactored to call `normalize_claude_event()` (~5 lines per hook), making the canonical schema the single interface to the pipeline. Every adapter reuses the existing Python runtime, `hooks_common.py` utilities, `MemoryStorage` class, `MemorySearch` class, and 3-layer security pipeline. No new runtime is introduced.

### New Dependencies

None. All adapter scripts are standard-library Python plus existing `src/memory/` imports. No new pip packages are required.

**Rationale:** The PRD scope is thin translation scripts. The existing `subprocess.Popen`, `json`, `sys`, `os`, and `pathlib` stdlib modules, combined with the already-installed `memory.*` package, provide everything the adapters need. Adding dependencies would increase the install surface for a solo-developer, self-hosted project with no benefit.

### Language Choice

All adapter scripts are Python 3.10+. Shell wrappers are not used for adapter logic.

**Rationale (NFR-201):** Python's `subprocess.Popen(args=[...])` avoids shell interpolation risks that Bash string-concatenated commands would introduce. The existing `post_tool_capture.py` fork pattern is Python-native. Keeping adapters in the same language means `hooks_common.py` functions (`setup_python_path`, `setup_hook_logging`, `log_to_activity`, `get_hook_timeout`, `extract_error_signature`) are directly importable.

---

## 2. System Design

### Component Diagram

```
+------------------+   +------------------+   +------------------+   +------------------+
|   Claude Code    |   |   Gemini CLI     |   |   Cursor IDE     |   |   Codex CLI      |
|                  |   |                  |   |                  |   |                  |
| .claude/         |   | .gemini/         |   | .cursor/         |   | .codex/          |
| settings.json    |   | settings.json    |   | hooks.json       |   | hooks.json       |
+--------+---------+   +--------+---------+   +--------+---------+   +--------+---------+
         |                       |                       |                       |
         | stdin JSON            | stdin JSON            | stdin JSON            | stdin JSON
         | (Claude schema)       | (Gemini schema)       | (Cursor schema)       | (Codex schema)
         v                       v                       v                       v
+--------+---------+   +--------+---------+   +--------+---------+   +--------+---------+
| Claude Adapter   |   | Gemini Adapter   |   | Cursor Adapter   |   | Codex Adapter    |
| (normalize_      |   | (normalize_      |   | (normalize_      |   | (normalize_      |
|  claude_event)   |   |  gemini_event)   |   |  cursor_event)   |   |  codex_event)    |
| adapters/claude/ |   | adapters/gemini/ |   | adapters/cursor/ |   | adapters/codex/  |
| *.py             |   | *.py             |   | *.py             |   | *.py             |
+--------+---------+   +--------+---------+   +--------+---------+   +--------+---------+
         |                       |                       |                       |
         | (translates to)       | (translates to)       | (translates to)       | (translates to)
         |                       |                       |                       |
         +-------+-------+-------+-------+-------+-------+-------+------+
                 |            Canonical Event Schema (dict)               |
                 | session_id, cwd, hook_event_name, tool_name,          |
                 | tool_input, tool_response, transcript_path,           |
                 | ide_source                                             |
                 +---------------------------+---------------------------+
                                             |
                                             v
                               +-------------+-------------+
                               |   Pipeline (accepts       |
                               |   canonical events only)  |
                               |                           |
                               |  hooks_common.py          |
                               |  store_async.py           |
                               |  error_store_async.py     |
                               |  MemoryStorage            |
                               |  MemorySearch             |
                               |  security scan (3-layer)  |
                               |  injection.py             |
                               +-------------+-------------+
                                             |
                                             v
                               +-------------+-------------+
                               |   Qdrant (unchanged)      |
                               |                           |
                               |  code-patterns            |
                               |  conventions              |
                               |  discussions              |
                               |  github                   |
                               |  jira-data                |
                               +---------------------------+
```

**Key design decision:** All four IDEs — including Claude Code — normalize through the canonical event schema. Claude Code hooks are refactored to call `normalize_claude_event()` from `adapters/schema.py` before invoking the pipeline. This makes the canonical schema the single interface between any IDE and the storage/retrieval pipeline. No IDE gets a "direct call" bypass.

### Data Flow: Capture Path (All IDEs — Unified)

```
Any IDE fires capture event (PostToolUse / AfterTool / postToolUse)
         |
         v
stdin JSON --> Hook/adapter script reads sys.stdin.read()
         |
         v
Script calls normalize_<ide>_event(raw_input):
  - Claude: normalize_claude_event() — maps existing fields, sets ide_source="claude"
  - Gemini: normalize_gemini_event() — maps AfterTool fields
  - Cursor: normalize_cursor_event() — maps postToolUse fields
  - Codex:  normalize_codex_event()  — maps PostToolUse fields
  Each normalizer:
    - Maps tool_name to canonical (e.g. Gemini "write_file" -> "Write")
    - Resolves session_id via fallback chain (FR-601)
    - Resolves cwd via fallback chain (FR-602)
    - Normalizes MCP tool names via normalize_mcp_tool_name() (FR-101)
    - Sets ide_source (FR-102)
    - Returns canonical event dict
         |
         v
validate_canonical_event(event) — shared validation (schema.py)
         |
         v
fork_to_background(canonical_event):
  - Sets CLAUDE_SESSION_ID in subprocess env
  - subprocess.Popen([python, store_async.py], stdin=PIPE, start_new_session=True)
  - Writes canonical event JSON to subprocess stdin
         |
         v
Script exits 0 immediately (<500ms per NFR-102)
         |
         v
Background store_async.py runs pipeline:
  - extract_patterns()
  - IntelligentChunker
  - 3-layer security scan
  - MemoryStorage.store_memory() -> Qdrant upsert
  - ide_source added as payload metadata
```

**Claude Code as adapter:** Existing `.claude/hooks/scripts/*.py` files are migrated to
`adapters/claude/*.py` and refactored to normalize through `normalize_claude_event()`.
Background pipeline scripts (`store_async.py` etc.) move to `adapters/pipeline/`.
`.claude/settings.json` command paths update to `$AI_MEMORY_INSTALL_DIR/adapters/claude/*.py`.
All four IDEs follow the identical adapter → canonical schema → pipeline path.

### Data Flow: Retrieval Path (All IDEs — Unified)

```
Any IDE fires SessionStart / BeforeAgent / sessionStart event
         |
         v
stdin JSON --> Hook/adapter script reads sys.stdin.read()
         |
         v
Script calls normalize_<ide>_event(raw_input):
  - Returns canonical event dict with session_id, cwd, ide_source resolved
         |
         v
validate_canonical_event(event) — shared validation
         |
         v
Script resolves project via detect_project(canonical_event["cwd"])
         |
         v
Adapter calls existing retrieval pipeline:
  - get_qdrant_client(config)
  - check_qdrant_health(client)
         |
         +-- Failure / empty results (non-blocking; sys.exit(0); IDE continues without memory context):
         |     1. Qdrant unreachable / unhealthy (check_qdrant_health returns false):
         |        log reason=qdrant_unavailable; empty context per IDE contract below
         |     2. Search exception (MemorySearch.search() raises): log error; empty context per IDE contract below
         |     3. Empty results (zero hits): empty context per IDE contract below
         |     Per-IDE empty-context payloads:
         |     - Gemini: {"hookSpecificOutput": {"additionalContext": ""}}
         |     - Cursor: {"additional_context": ""}
         |     - Codex:  {"hookSpecificOutput": {"systemMessage": ""}}
         |
         +-- Success path -->
  - MemorySearch.search() across collections
  - inject_with_priority() for formatting
         |
         v
Script formats stdout per IDE contract:
  - Claude: plain markdown text to stdout (existing behavior preserved)
  - Gemini: {"hookSpecificOutput": {"additionalContext": "<markdown>"}}
  - Cursor: {"additional_context": "<markdown>"}
  - Codex:  {"hookSpecificOutput": {"systemMessage": "<markdown>"}}
         |
         v
print(json.dumps(output)); sys.stdout.flush(); sys.exit(0)
```

### Canonical Event Schema (FR-101)

The canonical event schema is a plain Python `dict`, not a Pydantic model. This matches the existing pattern in `post_tool_capture.py` where hook input is a raw dict passed through `json.loads()` and validated by `validate_hook_input()`. A Pydantic model would add import overhead in the critical path of every hook invocation with no benefit for internal-only data.

```python
canonical_event = {
    # Required fields
    "session_id": str,        # Resolved via FR-601 fallback chain
    "cwd": str,               # Resolved via FR-602 fallback chain
    "hook_event_name": str,   # Canonical name: "SessionStart", "PostToolUse",
                              #   "PreCompact", "UserPromptSubmit", "Stop"
    "tool_name": str | None,  # Canonical name: "Write", "Edit", "Bash",
                              #   "NotebookEdit", or "mcp:<server>:<tool>"
    "tool_input": dict | None,   # IDE-normalized tool input
    "tool_response": dict | None, # IDE-normalized tool response
    "transcript_path": str | None, # Path to session transcript file
    "ide_source": str,        # One of: "claude", "gemini", "cursor", "codex"
}
```

**Validation function** (shared across all adapters):

```python
# In src/memory/adapters/schema.py

VALID_IDE_SOURCES = {"claude", "gemini", "cursor", "codex"}
VALID_HOOK_EVENTS = {
    "SessionStart", "PostToolUse", "PreCompact",
    "UserPromptSubmit", "Stop"
}

def validate_canonical_event(event: dict) -> None:
    """Validate canonical event dict. Raises ValueError on invalid input."""
    required = ["session_id", "cwd", "hook_event_name", "ide_source"]
    for field in required:
        if field not in event or not isinstance(event[field], str):
            raise ValueError(f"Missing or invalid required field: {field}")
    if event["ide_source"] not in VALID_IDE_SOURCES:
        raise ValueError(f"Invalid ide_source: {event['ide_source']}")
    if event["hook_event_name"] not in VALID_HOOK_EVENTS:
        raise ValueError(f"Invalid hook_event_name: {event['hook_event_name']}")
    optional_str_or_none = ["tool_name", "transcript_path"]
    for field in optional_str_or_none:
        if field in event and event[field] is not None and not isinstance(event[field], str):
            raise ValueError(f"{field} must be str or None, got {type(event[field]).__name__}")
    optional_dict_or_none = ["tool_input", "tool_response"]
    for field in optional_dict_or_none:
        if field in event and event[field] is not None and not isinstance(event[field], dict):
            raise ValueError(f"{field} must be dict or None, got {type(event[field]).__name__}")
```

### Claude Code Normalizer

Claude Code hooks are refactored to normalize through the same canonical schema. The
normalizer is in `adapters/schema.py` alongside the other normalizers:

```python
# In src/memory/adapters/schema.py

def normalize_claude_event(raw: dict, hook_event_name: str) -> dict:
    """Normalize Claude Code native stdin to canonical event schema.

    Claude Code stdin already contains most canonical fields natively.
    This normalizer standardizes naming and adds ide_source.
    """
    tool_name = raw.get("tool_name")
    mcp_name = normalize_mcp_tool_name(tool_name) if tool_name else None

    return {
        "session_id": raw.get("session_id", ""),
        "cwd": raw.get("cwd", os.getcwd()),
        "hook_event_name": hook_event_name,
        "tool_name": mcp_name or tool_name,
        "tool_input": raw.get("tool_input"),
        "tool_response": raw.get("tool_response"),
        "transcript_path": raw.get("transcript_path"),
        "ide_source": "claude",
    }
```

**Impact on existing Claude Code hooks:** Each hook's stdin parsing changes from:
```python
# Before
hook_input = json.loads(sys.stdin.read())
tool_name = hook_input.get("tool_name", "")
```
to:
```python
# After
from memory.adapters.schema import normalize_claude_event, validate_canonical_event
raw = json.loads(sys.stdin.read())
event = normalize_claude_event(raw, "PostToolUse")  # or "SessionStart", etc.
validate_canonical_event(event)
tool_name = event["tool_name"]
```

This is a ~5-line change per hook. All downstream logic is unchanged because the
canonical dict contains the same keys the hooks already expected — the normalizer
just makes the contract explicit and adds `ide_source`.

### MCP Tool Name Normalization (FR-101 Amendment)

```python
# In src/memory/adapters/schema.py

import re

def normalize_mcp_tool_name(raw_name: str) -> str | None:
    """Normalize IDE-specific MCP tool names to canonical format.

    Gemini format: mcp_<server>_<tool> -> mcp:<server>:<tool>
    Cursor format: MCP:<name>          -> mcp:unknown:<name>

    Returns None if the name is not an MCP tool name.
    """
    # Gemini: mcp_postgres_query -> mcp:postgres:query
    gemini_match = re.match(r"^mcp_([^_]+)_(.+)$", raw_name)
    if gemini_match:
        server = gemini_match.group(1)
        tool = gemini_match.group(2)
        return f"mcp:{server}:{tool}"

    # Cursor: MCP:postgres_query -> mcp:unknown:postgres_query
    cursor_match = re.match(r"^MCP:(.+)$", raw_name)
    if cursor_match:
        tool = cursor_match.group(1)
        return f"mcp:unknown:{tool}"

    return None
```

### How Adapters Plug In Without Modifying Claude Code Hooks

All adapters — including Claude Code — live under `$AI_MEMORY_INSTALL_DIR/adapters/<ide>/`. They call into the existing `src/memory/` pipeline code via Python imports after adding `$AI_MEMORY_INSTALL_DIR/src` to `sys.path`. Every IDE's config file references `$AI_MEMORY_INSTALL_DIR/adapters/<ide>/<script>.py` as the hook command.

**The boundary:** Adapters translate IDE-native payloads into the canonical event dict, then either:
- **Capture path:** Call `fork_to_background()` which spawns `store_async.py` -- the same background script Claude Code uses.
- **Retrieval path:** Call into `MemorySearch` and `inject_with_priority()` directly -- the same functions `session_start.py` uses.

No new intermediate layer or abstraction is introduced between the adapters and the pipeline. The adapters ARE the translation layer.

---

## 3. Data Architecture

### `ide_source` Metadata Field (FR-102)

**Where stored:** As a top-level key in the Qdrant point payload, alongside existing fields like `type`, `group_id`, `source_hook`, `session_id`.

**How added:** There are two persistence paths:

1. **`store_async.py` (PostToolUse background path):** The script (moved to `adapters/pipeline/store_async.py`) builds a `payload` dict for each chunked memory before upserting to Qdrant. **`ide_source` is not in that dict today** — FEATURE-001 must add: `"ide_source": hook_input.get("ide_source", "claude")`.

2. **`storage.py` `store_memory()`:** Callers pass `**extra_fields`. The implementation routes keys that are not `MemoryPayload` dataclass fields into an `extra_payload` dict and merges them into the Qdrant `PointStruct.payload` via `**extra_payload` together with `payload.to_dict()`. Unknown fields (including `ide_source` when passed this way) therefore still appear in the stored JSON payload.

**Implementation (`store_async.py` chunk payload; `ide_source` line to add):**

```python
            payload = {
                "content": chunk.content,
                "content_hash": content_hash,
                "group_id": group_id,
                "type": "implementation",
                "source_hook": "PostToolUse",
                "session_id": session_id,
                "created_at": now,
                "stored_at": now,
                "embedding_status": "pending",
                "tool_name": tool_name,
                "file_path": patterns["file_path"],
                "language": patterns["language"],
                "framework": patterns["framework"],
                "importance": patterns["importance"],
                "tags": patterns["tags"],
                "domain": patterns["domain"],
                "chunk_type": chunk.metadata.chunk_type,
                "chunk_index": chunk.metadata.chunk_index,
                "total_chunks": chunk.metadata.total_chunks,
                "chunk_size_tokens": chunk.metadata.chunk_size_tokens,
                "is_classified": False,
                "timestamp": now,
                "decay_score": 1.0,
                "freshness_status": "unverified",
                "source_authority": 0.4,
                "is_current": True,
                "version": 1,
                "agent_id": os.environ.get(
                    "PARZIVAL_AGENT_ID", os.environ.get("AI_MEMORY_AGENT_ID", "default")
                ),
                "ide_source": hook_input.get("ide_source", "claude"),
            }
```

**How queried:** The retrieval pipeline does not filter by `ide_source` -- all memories from all IDEs are returned for a given project (same `group_id`). The `ide_source` field is for observability and audit only (e.g., Streamlit dashboard can show memory provenance).

**Existing points:** Points stored by Claude Code before FEATURE-001 will lack `ide_source`. This is acceptable per NFR-302: "Existing points without this field must remain valid and retrievable." No backfill migration.

### Session ID Resolution Strategy (FR-601)

Each IDE adapter resolves `session_id` using this fallback chain:

| Priority | Source | Gemini CLI | Cursor IDE | Codex CLI |
|----------|--------|-----------|------------|-----------|
| 1 | Native `session_id` field | `session_id` | `session_id` | `session_id` |
| 2 | Alternate ID field | -- | `conversation_id` | -- |
| 3 | Transcript path basename | `os.path.splitext(os.path.basename(transcript_path))[0]` | same | same |
| 4 | Generated fallback | `hashlib.sha256(f"{cwd}:{timestamp}".encode()).hexdigest()[:16]` | same | same |

The resolved `session_id` is set as `os.environ["CLAUDE_SESSION_ID"]` before any pipeline call, maintaining compatibility with existing code that reads this env var (e.g., `store_async.py`, `InjectionSessionState`).

```python
# In src/memory/adapters/schema.py

def resolve_session_id(payload: dict) -> str:
    """Resolve session_id from IDE payload using fallback chain (FR-601)."""
    # Priority 1: native session_id
    sid = payload.get("session_id")
    if sid and isinstance(sid, str) and sid.strip():
        return sid.strip()

    # Priority 2: conversation_id (Cursor)
    cid = payload.get("conversation_id")
    if cid and isinstance(cid, str) and cid.strip():
        return cid.strip()

    # Priority 3: transcript_path basename
    tp = payload.get("transcript_path")
    if tp and isinstance(tp, str) and tp.strip():
        return os.path.splitext(os.path.basename(tp))[0]

    # Priority 4: generated from cwd + timestamp
    import hashlib
    from datetime import datetime, timezone
    cwd = payload.get("cwd", os.getcwd())
    ts = datetime.now(tz=timezone.utc).isoformat()
    return hashlib.sha256(f"{cwd}:{ts}".encode()).hexdigest()[:16]
```

### CWD Resolution Strategy (FR-602)

| Priority | Source | Gemini CLI | Cursor IDE | Codex CLI |
|----------|--------|-----------|------------|-----------|
| 1 | Native `cwd` field | `cwd` | `cwd` | `cwd` |
| 2 | Workspace roots | -- | `workspace_roots[0]` | -- |
| 3 | IDE env var | `GEMINI_CWD` | `CURSOR_PROJECT_DIR` | -- |
| 4 | Process cwd | `os.getcwd()` | `os.getcwd()` | `os.getcwd()` |

```python
# In src/memory/adapters/schema.py

def resolve_cwd(payload: dict, ide_source: str) -> str:
    """Resolve cwd from IDE payload using fallback chain (FR-602)."""
    cwd = payload.get("cwd")
    if cwd and isinstance(cwd, str) and cwd.strip():
        return cwd.strip()

    if ide_source == "cursor":
        roots = payload.get("workspace_roots", [])
        if roots and isinstance(roots[0], str):
            return roots[0]
        cursor_dir = os.environ.get("CURSOR_PROJECT_DIR")
        if cursor_dir:
            return cursor_dir

    if ide_source == "gemini":
        gemini_cwd = os.environ.get("GEMINI_CWD")
        if gemini_cwd:
            return gemini_cwd

    return os.getcwd()
```

### Qdrant Schema: No Changes (NFR-302)

No collection schema changes. No new collections. No new indexed fields. The `ide_source` field is additive metadata stored in the point payload -- Qdrant stores arbitrary JSON payloads without schema enforcement.

### MCP Tool Name Storage

MCP tool names are normalized before storage (FR-101). The `tool_name` field in the Qdrant payload will contain the canonical `mcp:<server>:<tool>` format. This means cross-IDE recall of MCP tool events works via content similarity search (Cursor-captured MCP events use `mcp:unknown:<tool>` because Cursor does not expose the server name; see Known Limitation 3 / FR-101).

---

## 4. Security Architecture

### No Shell Interpolation (NFR-201)

**How adapters receive paths:** All file paths come from the hook stdin JSON payload parsed via `json.loads()`. No path is ever interpolated into a shell command string.

**How adapters pass paths to subprocesses:**

```python
# CORRECT: args list, no shell=True
subprocess.Popen(
    [sys.executable, str(store_async_script)],
    stdin=subprocess.PIPE,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    start_new_session=True,
)
```

This is the identical pattern from `post_tool_capture.py:fork_to_background()`. Adapters reuse this exact function.

**IDE config command strings:** The installer writes command strings in IDE config files. These commands reference `$AI_MEMORY_INSTALL_DIR` (an env var set by the installer itself, not user input), fixed script paths, and — where the IDE format requires it — inline propagation of runtime env vars (`AI_MEMORY_PROJECT_ID`, `QDRANT_HOST`, `QDRANT_PORT`, `EMBEDDING_HOST`, `EMBEDDING_PORT`, `SIMILARITY_THRESHOLD`, `LOG_LEVEL`, etc.). The generated config must supply those values the same way as in the Gemini `env` example so hook processes can reach Qdrant, embeddings, and retrieval thresholds.

```
"$AI_MEMORY_INSTALL_DIR/.venv/bin/python" "$AI_MEMORY_INSTALL_DIR/adapters/gemini/session_start.py"
```

No user-supplied input is interpolated into these command strings.

### Security Scan Parity (NFR-202)

All adapters route capture through the same background pipeline:
1. Adapter calls `fork_to_background()` which spawns `store_async.py`
2. `store_async.py` calls `MemoryStorage.store_memory()`
3. `store_memory()` invokes the 3-layer security scan:
   - Layer 1: Regex pattern detection (`security.py`)
   - Layer 2: detect-secrets library scan
   - Layer 3: SpaCy NER-based PII detection

There is no alternative code path for any IDE. The security scan runs identically because the same `store_async.py` -> `MemoryStorage.store_memory()` call chain is used by all IDEs.

### Config File Security (NFR-203)

IDE config files written by the installer contain only:
- Fixed env vars: `AI_MEMORY_INSTALL_DIR`, `AI_MEMORY_PROJECT_ID`, `QDRANT_HOST`, `QDRANT_PORT`, `EMBEDDING_HOST`, `EMBEDDING_PORT`, `SIMILARITY_THRESHOLD`, `LOG_LEVEL`
- Hook command strings referencing `$AI_MEMORY_INSTALL_DIR` and fixed script names

No credentials, API keys, or user-identifiable information beyond `AI_MEMORY_PROJECT_ID` (derived from directory name per FR-503). The `ANTHROPIC_API_KEY`, `LANGFUSE_SECRET_KEY`, and similar secrets are loaded from `~/.ai-memory/docker/.env` by the pipeline at runtime, never written to IDE configs.

---

## 5. Infrastructure and Deployment

### Adapter Script Installation

All adapter and pipeline scripts are installed to a single location:

```
$AI_MEMORY_INSTALL_DIR/
  adapters/
    schema.py                # Shared: normalizers, validation, fork
    pipeline/                # Shared: IDE-agnostic background processors
      store_async.py
      error_store_async.py
      user_prompt_store_async.py
      agent_response_store_async.py
    claude/                  # Claude Code adapter entry points
      session_start.py
      post_tool_capture.py
      context_injection_tier2.py
      error_detection.py
      error_pattern_capture.py
      first_edit_trigger.py
      new_file_trigger.py
      pre_compact_save.py
      user_prompt_capture.py
      agent_response_capture.py
      best_practices_retrieval.py
      langfuse_stop_hook.py
      manual_save_memory.py
    gemini/                  # Gemini CLI (full parity — 12 scripts)
      session_start.py       after_tool_capture.py
      error_detection.py     error_pattern_capture.py
      before_tool_first_edit.py  before_tool_new_file.py
      context_injection.py   user_prompt_capture.py
      best_practices_retrieval.py  pre_compress.py
      session_end.py         langfuse_stop.py
    cursor/                  # Cursor IDE (full parity — 12 scripts)
      session_start.py       post_tool_capture.py
      error_detection.py     error_pattern_capture.py
      pre_tool_first_edit.py pre_tool_new_file.py
      context_injection.py   user_prompt_capture.py
      best_practices_retrieval.py  pre_compact.py
      stop.py                langfuse_stop.py
    codex/                   # Codex CLI (9 scripts — 3 platform gaps)
      session_start.py       error_detection.py
      error_pattern_capture.py  context_injection.py
      user_prompt_capture.py best_practices_retrieval.py
      stop.py                langfuse_stop.py
      # Gaps: no post_tool_capture, first_edit, new_file (Bash-only)
      # Gap: no pre_compact (no PreCompact hook)
```

**Rationale:** All four IDEs — including Claude Code — follow the same directory structure under `adapters/`. Claude Code is not special-cased. The `.claude/hooks/scripts/` directory is eliminated; `.claude/settings.json` command paths point to `$AI_MEMORY_INSTALL_DIR/adapters/claude/*.py` just as `.gemini/settings.json` points to `adapters/gemini/*.py`. Background pipeline scripts (`store_async.py` etc.) move to `adapters/pipeline/` because they accept canonical events and are IDE-agnostic — every adapter's `fork_to_background()` spawns the same pipeline script.

### IDE Config File Generation

The installer generates these per-project config files:

**Gemini CLI** (`.gemini/settings.json`):
```json
{
  "env": {
    "AI_MEMORY_INSTALL_DIR": "/home/user/.ai-memory",
    "AI_MEMORY_PROJECT_ID": "my-project",
    "QDRANT_HOST": "localhost",
    "QDRANT_PORT": "26350",
    "EMBEDDING_HOST": "localhost",
    "EMBEDDING_PORT": "28080",
    "SIMILARITY_THRESHOLD": "0.4",
    "LOG_LEVEL": "INFO"
  },
  "hooks": {
    "SessionStart": [
      { "matcher": ".*", "hooks": [
        { "type": "command", "command": "\"$PY\" \"$AD/gemini/session_start.py\"", "timeout": 30000 }
      ]}
    ],
    "AfterTool": [
      { "matcher": "edit_file|write_file|create_file", "hooks": [
        { "type": "command", "command": "\"$PY\" \"$AD/gemini/after_tool_capture.py\"", "timeout": 5000 }
      ]},
      { "matcher": "run_shell_command", "sequential": true, "hooks": [
        { "type": "command", "command": "\"$PY\" \"$AD/gemini/error_detection.py\"", "timeout": 5000 },
        { "type": "command", "command": "\"$PY\" \"$AD/gemini/error_pattern_capture.py\"", "timeout": 5000 }
      ]},
      { "matcher": "mcp_.*", "hooks": [
        { "type": "command", "command": "\"$PY\" \"$AD/gemini/after_tool_capture.py\"", "timeout": 5000 }
      ]}
    ],
    "BeforeTool": [
      { "matcher": "edit_file", "hooks": [
        { "type": "command", "command": "\"$PY\" \"$AD/gemini/before_tool_first_edit.py\"", "timeout": 2000 }
      ]},
      { "matcher": "write_file|create_file", "hooks": [
        { "type": "command", "command": "\"$PY\" \"$AD/gemini/before_tool_new_file.py\"", "timeout": 2000 }
      ]}
    ],
    "BeforeAgent": [
      { "matcher": ".*", "sequential": true, "hooks": [
        { "type": "command", "command": "\"$PY\" \"$AD/gemini/context_injection.py\"", "timeout": 5000 },
        { "type": "command", "command": "\"$PY\" \"$AD/gemini/user_prompt_capture.py\"", "timeout": 5000 },
        { "type": "command", "command": "\"$PY\" \"$AD/gemini/best_practices_retrieval.py\"", "timeout": 5000 }
      ]}
    ],
    "PreCompress": [
      { "matcher": ".*", "hooks": [
        { "type": "command", "command": "\"$PY\" \"$AD/gemini/pre_compress.py\"", "timeout": 60000 }
      ]}
    ],
    "SessionEnd": [
      { "matcher": ".*", "sequential": true, "hooks": [
        { "type": "command", "command": "\"$PY\" \"$AD/gemini/session_end.py\"", "timeout": 10000 },
        { "type": "command", "command": "\"$PY\" \"$AD/gemini/langfuse_stop.py\"", "timeout": 5000 }
      ]}
    ]
  }

  // Note: $PY = "$AI_MEMORY_INSTALL_DIR/.venv/bin/python"
  //       $AD = "$AI_MEMORY_INSTALL_DIR/adapters"
  // Installer expands these to absolute paths at write time.
}
```

**Cursor IDE** (`.cursor/hooks.json`):
```json
{
  "version": 1,
  "hooks": {
    "sessionStart": [
      { "command": "$ENV \"$PY\" \"$AD/cursor/session_start.py\"", "timeout": 30 }
    ],
    "postToolUse": [
      { "matcher": "Write|Edit", "command": "$ENV \"$PY\" \"$AD/cursor/post_tool_capture.py\"", "timeout": 5 },
      { "matcher": "Shell", "command": "$ENV \"$PY\" \"$AD/cursor/error_detection.py\"", "timeout": 5 },
      { "matcher": "Shell", "command": "$ENV \"$PY\" \"$AD/cursor/error_pattern_capture.py\"", "timeout": 5 },
      { "matcher": "MCP:.*", "command": "$ENV \"$PY\" \"$AD/cursor/post_tool_capture.py\"", "timeout": 5 }
    ],
    "preToolUse": [
      { "matcher": "Edit", "command": "$ENV \"$PY\" \"$AD/cursor/pre_tool_first_edit.py\"", "timeout": 2 },
      { "matcher": "Write", "command": "$ENV \"$PY\" \"$AD/cursor/pre_tool_new_file.py\"", "timeout": 2 }
    ],
    "beforeSubmitPrompt": [
      { "command": "$ENV \"$PY\" \"$AD/cursor/context_injection.py\"", "timeout": 5 },
      { "command": "$ENV \"$PY\" \"$AD/cursor/user_prompt_capture.py\"", "timeout": 5 },
      { "command": "$ENV \"$PY\" \"$AD/cursor/best_practices_retrieval.py\"", "timeout": 5 }
    ],
    "preCompact": [
      { "command": "$ENV \"$PY\" \"$AD/cursor/pre_compact.py\"", "timeout": 30 }
    ],
    "stop": [
      { "command": "$ENV \"$PY\" \"$AD/cursor/stop.py\"", "timeout": 10 }
    ],
    "sessionEnd": [
      { "command": "$ENV \"$PY\" \"$AD/cursor/langfuse_stop.py\"", "timeout": 5 }
    ]
  }
}

// $ENV = inline env var assignments (AI_MEMORY_INSTALL_DIR, AI_MEMORY_PROJECT_ID, etc.)
// $PY  = "$AI_MEMORY_INSTALL_DIR/.venv/bin/python"
// $AD  = "$AI_MEMORY_INSTALL_DIR/adapters"
// Installer expands all placeholders to absolute values at write time.
```

**Note on Cursor env propagation:** Cursor’s `.cursor/hooks.json` schema does not support a top-level `env` block. The installer inlines env var assignments in every `command` string: `AI_MEMORY_INSTALL_DIR`, `AI_MEMORY_PROJECT_ID`, `QDRANT_HOST`, `QDRANT_PORT`, `EMBEDDING_HOST`, `EMBEDDING_PORT`, `SIMILARITY_THRESHOLD`, `LOG_LEVEL`. `CURSOR_PROJECT_DIR` is provided by the Cursor process environment and is not set by the installer.

**Codex CLI** (`.codex/hooks.json`):
```json
{
  "hooks": {
    "SessionStart": [
      { "matcher": ".*", "hooks": [
        { "type": "command", "command": "$ENV \"$PY\" \"$AD/codex/session_start.py\"", "timeout": 30 }
      ]}
    ],
    "PostToolUse": [
      { "matcher": "Bash", "hooks": [
        { "type": "command", "command": "$ENV \"$PY\" \"$AD/codex/error_detection.py\"", "timeout": 10 },
        { "type": "command", "command": "$ENV \"$PY\" \"$AD/codex/error_pattern_capture.py\"", "timeout": 10 }
      ]}
    ],
    "UserPromptSubmit": [
      { "hooks": [
        { "type": "command", "command": "$ENV \"$PY\" \"$AD/codex/context_injection.py\"", "timeout": 5 },
        { "type": "command", "command": "$ENV \"$PY\" \"$AD/codex/user_prompt_capture.py\"", "timeout": 5 },
        { "type": "command", "command": "$ENV \"$PY\" \"$AD/codex/best_practices_retrieval.py\"", "timeout": 5 }
      ]}
    ],
    "Stop": [
      { "hooks": [
        { "type": "command", "command": "$ENV \"$PY\" \"$AD/codex/stop.py\"", "timeout": 30 },
        { "type": "command", "command": "$ENV \"$PY\" \"$AD/codex/langfuse_stop.py\"", "timeout": 5 }
      ]}
    ]
  }
}

// Codex platform gaps: no post_tool_capture (Bash-only PostToolUse),
// no first_edit/new_file triggers (Bash-only PreToolUse), no pre_compact (no hook).
// $ENV/$PY/$AD expanded by installer at write time. Inline env needed (no env block).
```

**Note on Codex env propagation:** Codex hooks use inline env var assignments in all command strings. This is the canonical pattern — no install-time detection of `env` block support is required.

### Skill / Command Deployment

**Gemini CLI commands** (`.gemini/commands/`):

```
.gemini/
  commands/
    search-memory.toml      # FR-205
    memory-status.toml      # FR-206
    save-memory.toml        # FR-207
```

Example `search-memory.toml`:
```toml
description = "Search ai-memory for relevant stored memories"
prompt = "Search ai-memory for: {{args}}. Execute the command [$AI_MEMORY_INSTALL_DIR/.venv/bin/python, $AI_MEMORY_INSTALL_DIR/src/memory/search.py, --query, {{args}}, --project, <current directory basename>] without shell interpolation. Present the results clearly."
```

The query text MUST be passed as a discrete argv element, not interpolated into a shell string, per NFR-201.

**Cursor IDE skills** (`.cursor/skills/`):

```
.cursor/
  skills/
    search-memory/
      SKILL.md              # FR-305
    memory-status/
      SKILL.md              # FR-306
    save-memory/
      SKILL.md              # FR-307
```

Example `.cursor/skills/search-memory/SKILL.md`:
```markdown
---
name: search-memory
description: Search ai-memory for relevant stored memories
allowed-tools: Bash
---

Search ai-memory for relevant stored memories matching the user's query.

## Instructions

1. Invoke the search script with **no shell**: pass a discrete argv array (e.g. Cursor Shell tool argument list, or equivalent) — executable path, then `$AI_MEMORY_INSTALL_DIR/src/memory/search.py`, then `--query`, then the user query string as its **own** token, then `--project`, then the current directory basename as its **own** token. Do not embed the query inside a single quoted shell string.
2. Present the ranked results clearly to the user.
```

The query text MUST be passed as a discrete argv element, not interpolated into a shell string, per NFR-201.

**Codex CLI skills** (`.agents/skills/`):

```
.agents/
  skills/
    search-memory/
      SKILL.md              # FR-406
    memory-status/
      SKILL.md              # FR-407
```

Codex SKILL.md files use the same format as Cursor, with `allowed-tools: shell` instead of `allowed-tools: Bash`.

### Installer Changes (`scripts/install.sh`)

The installer gains the following new capabilities:

**1. IDE Detection Functions:**

```bash
detect_gemini_cli() {
    command -v gemini >/dev/null 2>&1
}

detect_cursor_ide() {
    command -v agent >/dev/null 2>&1 || command -v cursor-agent >/dev/null 2>&1
}

detect_codex_cli() {
    command -v codex >/dev/null 2>&1
}
```

**2. `--ide` Flag Parsing (FR-502):**

The installer accepts `--ide gemini,cursor,codex` to explicitly include IDEs. `--ide none` skips all IDE config. When `--ide` is not specified, the installer auto-detects.

**3. Config Generation Functions:**

Each IDE gets a `write_<ide>_config()` function that:
- If the config file exists and contains `AI_MEMORY_INSTALL_DIR`: skip (FR-504, already installed)
- If `--force` is set: overwrite the entire file (FR-505)
- If the config file exists but does NOT contain `AI_MEMORY_INSTALL_DIR`: read the existing JSON, merge ai-memory keys into the existing object (preserving all unrelated keys), and write the merged result back. If the file is not valid JSON, abort with a non-zero exit and log the path and parse error — do not overwrite.
- If no config file exists: write a new file with only ai-memory keys
- Writes skill/command files (these are ai-memory-owned paths; no merge needed)
- Logs what was written and whether it was a fresh write or a merge

**4. Adapter Installation:**

During installation, the installer copies only the per-IDE adapter script trees (`gemini/`, `cursor/`, `codex/`) and `templates/` from `src/memory/adapters/` into `$AI_MEMORY_INSTALL_DIR/adapters/` — not the entire `src/memory/adapters/` tree (e.g. `schema.py` is not duplicated under `adapters/`). `schema.py` remains importable as `memory.adapters.schema` via the existing copy of `src/memory/` to `$AI_MEMORY_INSTALL_DIR/src/memory/`.

**5. Skill Template Installation:**

Skill/command templates are stored in `src/memory/adapters/templates/` and copied to the project directory during `add-project`. The templates use `$AI_MEMORY_INSTALL_DIR` as a placeholder that the installer resolves at write time.

**6. New Step in Installation Flow:**

The existing 8-step flow gains IDE detection and config generation as part of the existing "configure hooks" step (no new top-level step needed). The `add-project` mode is extended similarly.

---

## 6. Code Organization

### Directory Structure for New Code

```
src/memory/
  adapters/                          # Adapter package — ALL IDEs live here
    __init__.py                      # Package marker
    schema.py                        # Canonical event schema, validation,
                                     #   normalize_mcp_tool_name(),
                                     #   normalize_claude_event(),
                                     #   normalize_gemini_event(),
                                     #   normalize_cursor_event(),
                                     #   normalize_codex_event(),
                                     #   resolve_session_id(),
                                     #   resolve_cwd(),
                                     #   fork_to_background()
    pipeline/                        # IDE-agnostic background processors
      __init__.py
      store_async.py                 # Moved from .claude/hooks/scripts/
      error_store_async.py           # Moved from .claude/hooks/scripts/
      user_prompt_store_async.py     # Moved from .claude/hooks/scripts/
      agent_response_store_async.py  # Moved from .claude/hooks/scripts/
    claude/                          # Claude Code adapter (same structure as others)
      __init__.py
      session_start.py               # SessionStart hook entry point
      post_tool_capture.py           # PostToolUse capture (Edit/Write/NotebookEdit)
      context_injection_tier2.py     # UserPromptSubmit per-turn injection
      error_detection.py             # PostToolUse(Bash) error retrieval
      error_pattern_capture.py       # PostToolUse(Bash) error capture
      first_edit_trigger.py          # PreToolUse(Edit) trigger
      new_file_trigger.py            # PreToolUse(Write) trigger
      pre_compact_save.py            # PreCompact session summary
      user_prompt_capture.py         # UserPromptSubmit capture
      agent_response_capture.py      # Stop session summary
      best_practices_retrieval.py    # UserPromptSubmit best practices
      langfuse_stop_hook.py          # Stop tracing
      manual_save_memory.py          # Manual save trigger
    gemini/                          # Gemini CLI adapter (full parity)
      __init__.py
      session_start.py               # SessionStart → retrieval bootstrap
      after_tool_capture.py          # AfterTool(edit/write/create) → code pattern capture
      error_detection.py             # AfterTool(run_shell_command) → error retrieval
      error_pattern_capture.py       # AfterTool(run_shell_command) → error capture
      before_tool_first_edit.py      # BeforeTool(edit_file) → first edit trigger
      before_tool_new_file.py        # BeforeTool(write_file/create_file) → new file trigger
      context_injection.py           # BeforeAgent → per-turn injection
      user_prompt_capture.py         # BeforeAgent → user prompt capture
      best_practices_retrieval.py    # BeforeAgent → best practices retrieval
      pre_compress.py                # PreCompress → session summary
      session_end.py                 # SessionEnd → agent response capture
      langfuse_stop.py               # SessionEnd → Langfuse tracing
    cursor/                          # Cursor IDE adapter (full parity)
      __init__.py
      session_start.py               # sessionStart → retrieval bootstrap
      post_tool_capture.py           # postToolUse(Write/Edit) → code pattern capture
      error_detection.py             # postToolUse(Shell) → error retrieval
      error_pattern_capture.py       # postToolUse(Shell) → error capture
      pre_tool_first_edit.py         # preToolUse(Edit) → first edit trigger
      pre_tool_new_file.py           # preToolUse(Write) → new file trigger
      context_injection.py           # beforeSubmitPrompt → per-turn injection
      user_prompt_capture.py         # beforeSubmitPrompt → user prompt capture
      best_practices_retrieval.py    # beforeSubmitPrompt → best practices retrieval
      pre_compact.py                 # preCompact → session summary
      stop.py                        # stop → agent response capture
      langfuse_stop.py               # sessionEnd → Langfuse tracing
    codex/                           # Codex CLI adapter (parity minus platform gaps)
      __init__.py
      session_start.py               # SessionStart → retrieval bootstrap
      error_detection.py             # PostToolUse(Bash) → error retrieval
      error_pattern_capture.py       # PostToolUse(Bash) → error capture
      context_injection.py           # UserPromptSubmit → per-turn injection
      user_prompt_capture.py         # UserPromptSubmit → user prompt capture
      best_practices_retrieval.py    # UserPromptSubmit → best practices retrieval
      stop.py                        # Stop → agent response capture
      langfuse_stop.py               # Stop → Langfuse tracing
      # PLATFORM GAPS (Codex PreToolUse is Bash-only, no PreCompact):
      # - No post_tool_capture (Edit/Write not supported in PostToolUse)
      # - No first_edit_trigger (PreToolUse is Bash-only)
      # - No new_file_trigger (PreToolUse is Bash-only)
      # - No pre_compact (no PreCompact hook in Codex)
    templates/                       # Skill/command templates per IDE
      claude/
        search-memory/
          SKILL.md                   # Existing aim-search equivalent
        memory-status/
          SKILL.md                   # Existing aim-status equivalent
        save-memory/
          SKILL.md                   # Existing aim-save equivalent
      gemini/
        search-memory.toml           # FR-205
        memory-status.toml           # FR-206
        save-memory.toml             # FR-207
      cursor/
        search-memory/
          SKILL.md                   # FR-305
        memory-status/
          SKILL.md                   # FR-306
        save-memory/
          SKILL.md                   # FR-307
      codex/
        search-memory/
          SKILL.md                   # FR-406
        memory-status/
          SKILL.md                   # FR-407
```

**Migration from `.claude/hooks/scripts/`:** The existing 18 hook scripts move from
`.claude/hooks/scripts/*.py` to `src/memory/adapters/claude/*.py` and
`src/memory/adapters/pipeline/*.py`. The `.claude/settings.json` command paths update
from `.claude/hooks/scripts/<script>.py` to
`$AI_MEMORY_INSTALL_DIR/adapters/claude/<script>.py`. The installer generates these
paths identically for all four IDEs. The old `.claude/hooks/scripts/` directory is
removed after migration.

### Module Boundaries

| Location | Responsibility | Imports From |
|----------|---------------|-------------|
| `src/memory/adapters/schema.py` | Canonical schema, all 4 IDE normalizers, validation, MCP normalization, session/cwd resolution, `fork_to_background()` | `os`, `re`, `hashlib`, `json`, `subprocess`, `sys` (stdlib only) |
| `src/memory/adapters/pipeline/*.py` | IDE-agnostic background processors (store, error store, user prompt store, agent response store) | `memory.*` (storage, search, security, config) |
| `src/memory/adapters/<ide>/*.py` | IDE-specific hook entry points: parse stdin, normalize, call pipeline or retrieval, format stdout | `memory.adapters.schema`, `memory.hooks_common`, `memory.config`, `memory.search`, `memory.project`, `memory.health`, `memory.injection` |
| `src/memory/hooks_common.py` | Shared hook utilities (UNCHANGED) | stdlib |
| `scripts/install.sh` | Installer (EXTENDED): IDE detection, config generation for all 4 IDEs, adapter + pipeline script installation | N/A (Bash) |

### Naming Conventions

- **Adapter Python files:** `snake_case.py` (e.g., `session_start.py`, `after_tool.py`, `post_tool_use.py`)
- **Adapter directories:** `snake_case` IDE names (e.g., `gemini/`, `cursor/`, `codex/`)
- **Template skill directories:** `kebab-case` (e.g., `search-memory/`, `memory-status/`)
- **Functions:** `snake_case` (e.g., `normalize_mcp_tool_name`, `resolve_session_id`)
- **Constants:** `UPPER_SNAKE` (e.g., `VALID_IDE_SOURCES`, `VALID_HOOK_EVENTS`)
- **Classes:** None planned -- adapters use functions, not classes (matching the existing hook pattern)

---

## 7. Performance and Scale

### Adapter Overhead Budget

| Hook Type | PRD Requirement | Budget Allocation |
|-----------|----------------|-------------------|
| SessionStart (retrieval) | p95 < 3000ms (NFR-101) | est. ~50ms adapter overhead + ~2950ms for Qdrant search + formatting |
| PostToolUse (capture) | p95 < 500ms (NFR-102) | est. ~30ms adapter overhead + fork; background process unconstrained |
| UserPromptSubmit (injection) | < 2000ms (NFR-104) | est. ~50ms adapter overhead + ~1950ms for search + inject |
| Stop (session summary) | No strict budget (end of session) | Synchronous, up to 30s |

**How the budget is met:** Adapter overhead is minimal -- it's `json.loads()` on stdin, a few dict key lookups for field mapping, and a `json.dumps()` on stdout (or a `subprocess.Popen` call for capture). The actual time is spent in the existing pipeline (Qdrant search, embedding generation, security scan). Acceptance criteria: for each adapter (Gemini, Cursor, Codex), run the adapter's hook entry point 20 times against a local Qdrant instance seeded with at least 100 points; measure wall-clock time from stdin write to process exit for capture hooks and from stdin write to stdout flush for retrieval/injection hooks; p95 must remain below the threshold in the table above. Failure of any single adapter blocks story acceptance.

### Fork-to-Background Pattern for Capture Hooks

All capture adapters (PostToolUse/AfterTool/postToolUse) use the same fork pattern as `post_tool_capture.py`:

```python
def fork_to_background(canonical_event: dict) -> None:
    """Fork storage to background. Adapter exits immediately after this call."""
    store_async_script = Path(INSTALL_DIR) / "adapters" / "pipeline" / "store_async.py"
    subprocess_env = os.environ.copy()
    sid = canonical_event.get("session_id", "")
    if sid:
        subprocess_env["CLAUDE_SESSION_ID"] = sid

    process = subprocess.Popen(
        [sys.executable, str(store_async_script)],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=subprocess_env,
        start_new_session=True,
    )
    if process.stdin:
        process.stdin.write(json.dumps(canonical_event).encode("utf-8"))
        process.stdin.close()
```

**Key detail:** The adapters fork to the EXISTING `store_async.py` script, not a new one. This ensures the same pipeline, security scan, and storage logic is used regardless of IDE. `validate_canonical_event` raises `ValueError` before `store_async.py` receives any event whose optional fields violate the type constraints declared in the schema above; `store_async.py` therefore only processes events where `tool_input` and `tool_response` are `dict | None` and `tool_name` and `transcript_path` are `str | None`.

### Gemini JSON-Only stdout Constraint (FR-603)

Gemini CLI warns and may suppress non-JSON stdout from hooks. All Gemini adapter scripts must:
1. Log exclusively to stderr (using `logging.StreamHandler(sys.stderr)`)
2. Produce exactly one `json.dumps()` call to stdout, followed by `sys.stdout.flush()`
3. Never use `print()` without `json.dumps()` wrapping

The existing Claude Code `session_start.py` already follows this pattern (logs to stderr, structured JSON to stdout), so the Gemini adapter mirrors it directly.

### Codex Timeout Overrides (FR-403)

Codex CLI defaults to a 600s hook timeout. The installer overrides this in the generated config:
- `SessionStart`: 30s (matches Claude Code)
- `PostToolUse`: 10s (generous for fork + exit)
- `UserPromptSubmit`: 5s (per-turn, must be fast)
- `Stop`: 30s (session end, less latency-sensitive)

---

## 8. Technical Constraints and Trade-offs

### Alternatives Considered and Rejected

**1. Unified adapter dispatcher (single entry point for all IDEs)**

Considered: A single `adapter_dispatch.py` that detects the IDE from the payload structure and routes internally.

Rejected: Each IDE's config file must reference a specific script path. A dispatcher would still need per-IDE entry points. It adds a layer of indirection with no benefit -- each adapter is ~100 lines of straightforward translation code. Separate scripts are easier to debug, test, and maintain independently.

**2. Pydantic models for canonical event schema**

Considered: Define `CanonicalEvent(BaseModel)` with strict field types.

Rejected: Pydantic import is estimated to add ~100ms cold-start overhead (based on typical v2 import cost). The existing Claude Code hooks use raw dicts validated with simple `if field not in data` checks (see `validate_hook_input()` in `post_tool_capture.py`). Adapters follow the same pattern for consistency and performance. Unit tests validate the schema; runtime validation is a function call on a dict.

**3. Shared adapter base class**

Considered: `class BaseAdapter` with abstract methods `parse_stdin()`, `normalize()`, `format_stdout()`.

Rejected: Over-engineering for a solo-developer project with 3 adapters. Each adapter is a standalone script with a `main()` function -- the same pattern as every existing Claude Code hook. Shared logic lives in `schema.py` as importable functions. Classes add no value when there's no polymorphic dispatch.

**4. Modifying `store_async.py` to accept `ide_source` explicitly**

Considered: Adding `--ide-source gemini` as a CLI argument to `store_async.py`.

Rejected: `store_async.py` reads its input from stdin JSON. The `ide_source` field is simply included in the JSON payload. No CLI argument changes needed. This maintains backward compatibility -- Claude Code hooks that don't set `ide_source` continue to work unchanged.

### Known Limitations

**1. Codex CLI Bash-Only PostToolUse (FR-402)**

Codex CLI's `PostToolUse` hook currently fires only for Bash tool events. File write/edit events do not trigger hooks. This means Codex sessions capture error patterns (from Bash failures) but not implementation patterns (from Edit/Write). This is a platform limitation documented in the PRD. The adapter is designed so that if Codex expands `PostToolUse` to more tools, the adapter handles them without code changes (the tool name mapping is extensible).

**2. Cursor Symlink Issue (FR-302)**

Cursor has known issues resolving symlinks in `.claude/` directories. All Cursor adapter script paths are resolved via `$AI_MEMORY_INSTALL_DIR` env var, never via relative symlinks from the project directory. The installer does not create symlinks.

**3. MCP Tool Name Ambiguity in Cursor (FR-101)**

Cursor's `MCP:<name>` format does not include the MCP server name. The normalization function maps `MCP:<name>` to `mcp:unknown:<name>`. This means a Cursor-captured MCP event and a Gemini-captured MCP event for the same tool will have different `tool_name` values (`mcp:unknown:query` vs `mcp:postgres:query`). Cross-IDE MCP recall depends on content similarity search, not tool name matching, so this is acceptable. A future enhancement could add server name resolution from the IDE's MCP config file.

**4. No Langfuse Tracing for Non-Claude Adapters (Out of Scope)**

Per PRD Section 7, Langfuse tracing instrumentation is excluded from FEATURE-001 adapters. The adapters import `emit_trace_event` defensively (try/except ImportError) but do not call it. This can be added in a follow-on without adapter redesign.

**5. Codex MCP Event Capture Gap (FR-408)**

It is not confirmed whether Codex CLI fires `PostToolUse` for MCP tool invocations. The adapter logs a structured warning for unrecognized tool names that may indicate MCP tools, but does not attempt to capture them. This gap will be revisited when Codex documentation clarifies MCP hook behavior.

### Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| IDE hook protocol changes in future releases | Medium | Adapter scripts break for that IDE | Each adapter is isolated; a protocol change affects only one IDE's adapter. Adapters log structured warnings for unexpected payload shapes, enabling fast diagnosis. |
| `store_async.py` rejects canonical events with unfamiliar fields | Low | Memories not stored for non-Claude IDEs | `store_async.py` uses `dict.get()` with defaults throughout. `ide_source` is **not** in the hardcoded payload today (see FR-102); FEATURE-001 must add it explicitly. Test with a synthetic event whose `ide_source` is not "claude" and assert the stored Qdrant point payload contains the expected `ide_source` value. |
| Gemini/Cursor/Codex stdin schema differs from documentation | Medium | Adapter fails to parse payload | Each adapter's `main()` has a try/except catching `json.JSONDecodeError` and `KeyError`, returning exit 0 with valid empty output. Graceful degradation means the IDE session continues unaffected. |
| Performance regression from adapter overhead | Low | Hook exceeds latency budget | Each story's acceptance tests must include the per-IDE latency measurement defined in Adapter Overhead Budget; p95 exceeding the relevant NFR threshold blocks story acceptance. |
| Installer writes conflicting config when IDE already has hooks | Medium | User's existing hooks overwritten | FR-504: skip if already installed. FR-505: `--force` overwrites. Default: JSON-level merge preserving unrelated keys; aborts on unparseable files. |
