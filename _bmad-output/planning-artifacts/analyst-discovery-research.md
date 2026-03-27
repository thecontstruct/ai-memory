# AI-Memory: Analyst Discovery Research

**Prepared by:** Mary (Senior Strategic Business Analyst)
**Date:** 2026-03-26
**Subject:** Discovery research for PRD creation — ai-memory v2.2.5/v2.2.6
**Codebase version audited:** v2.2.6 (pyproject.toml), architecture spec V3.4 (ROADMAP.md)

---

## Table of Contents

1. [User and Stakeholder Needs](#1-user-and-stakeholder-needs)
2. [Functional Requirements Surface](#2-functional-requirements-surface)
3. [Non-Functional Requirements](#3-non-functional-requirements)
4. [Integration Requirements](#4-integration-requirements)
5. [Constraints and Boundaries](#5-constraints-and-boundaries)
6. [Existing Behavior Documentation](#6-existing-behavior-documentation)

---

## 1. User and Stakeholder Needs

### Target Users

**Primary users** are software developers and development teams who use LLM agents — specifically Claude Code — to work on complex, multi-session projects. The `oversight/goals.md` characterizes the target as:

> "Developers and teams using LLM agents (primarily Claude Code) who need institutional memory across sessions, projects, and codebases."

The `docs/AI_MEMORY_ARCHITECTURE.md` extends this to include structured workflow users operating under the BMAD methodology (Analyst, PM, Architect, SM, DEV, UX, Tech Writer roles), each consuming memory from specific collections.

**Secondary users** are contributors to the open-source project itself (GitHub-based, community-driven per ROADMAP.md).

### Core Pain Point: Stateless LLM Sessions

The architecture document states the problem directly (`docs/AI_MEMORY_ARCHITECTURE.md:183-192`):

- Claude Code sessions are stateless — every new session starts from zero
- Developers waste 30%+ of tokens re-establishing context per session
- Complex multi-session work is impractical because Claude "forgets"
- Lessons learned are lost between sessions

### User Workflows Supported

[Verified — from `docs/AI_MEMORY_ARCHITECTURE.md` and `docs/HOOKS.md`]

| Workflow Moment | Pain Point Solved | Mechanism |
|---|---|---|
| New session start | Must re-explain project context | `SessionStart` hook bootstraps 2-3K tokens of relevant memories |
| Error occurs mid-session | Must manually recall past fixes | `error_detection` trigger retrieves past `error_pattern` memories |
| Creating a new file | Uncertainty about naming/structure conventions | `new_file` trigger fetches `naming` + `structure` memories |
| Editing an existing file | First edit has no prior pattern context | `first_edit` trigger fetches file-specific patterns |
| "Why did we..." question | No history of decisions | `decision_keywords` trigger fetches `decision` memories |
| "How should I..." question | No history of conventions | `best_practices_keywords` trigger fetches `guideline` memories |
| Session ends / compacts | Context lost on compaction | `PreCompact` hook saves a full session summary |

### Evidence of User Needs

[Informed — from ROADMAP.md community section and CHANGELOG.md]

The ROADMAP.md `Recently Implemented` section shows features driven by stated user needs:
- "Session History Trigger — Requested continuity for 'where were we' questions"
- "Backup/Restore Scripts — Production deployment requirements"
- "Five-Collection Architecture — Dedicated github and jira-data collections"

The community section is currently sparse (`Under Consideration: Submit a feature request to be the first!`), indicating the project is early in community adoption.

### OPEN QUESTIONS

- **OQ-1.1:** What is the current GitHub star count and active contributor count? (Adoption baseline not quantified in docs)
- **OQ-1.2:** Is the primary target an individual developer or a team? Multi-user team sharing a single Qdrant instance is mentioned (`v3.0 Enterprise Features`) but not implemented.
- **OQ-1.3:** What is the priority ordering across the three tracks: stabilization, new features, and adoption? (`oversight/goals.md` explicitly flags this as unresolved)
- **OQ-1.4:** Are there production deployments in use today, and what is the observed session token savings?

---

## 2. Functional Requirements Surface

### 2.1 Currently Implemented Features

[Verified — from direct source code inspection]

#### Memory Storage

- **Five-collection architecture** (`src/memory/config.py:51-70`): `code-patterns`, `conventions`, `discussions`, `github`, `jira-data`
- **31 memory types** (`src/memory/models.py:22-85`): covers implementation, error_pattern, refactor, file_pattern, rule, guideline, naming, structure, decision, session, jira_issue, github_code_blob, agent_handoff, etc.
- **Zero-truncation storage**: content is chunked into multiple vectors rather than truncated (`ROADMAP.md:50`, confirmed in `src/memory/chunking/__init__.py`)
- **Dual embedding model routing** (`src/memory/config.py:78-83`): code content uses `jina-embeddings-v2-base-code`, prose uses `jina-embeddings-v2-base-en` (both 768-dim)
- **Dual-stage deduplication** (`src/memory/deduplication.py`): Stage 1 is SHA256 hash exact-match; Stage 2 is semantic similarity via ANN search
- **Content-hash based supersede** for GitHub code blobs with partial-batch rollback (`CHANGELOG.md v2.2.5`)
- **Batched code blob sync** with bounded concurrency, sub-batch upserts (64-point cap to avoid Qdrant gRPC 64MB limit) (`src/memory/storage.py`, `CHANGELOG.md v2.2.5`)

#### Memory Retrieval and Search

- **Triple Fusion Hybrid Search** (`ROADMAP.md:9`): Dense + BM25 sparse + ColBERT late interaction, fused via Qdrant RRF
- **4-path search composition**: The `MemorySearch` class supports multiple query paths (`src/memory/search.py`)
- **Semantic decay scoring** (`src/memory/decay.py`): `final_score = (0.7 * semantic_similarity) + (0.3 * temporal_score)`, computed server-side via Qdrant FormulaQuery API. Type-specific half-lives: code 14 days, discussions 21 days, conventions 60 days
- **Intent detection** (`src/memory/intent.py`): Routes HOW/WHAT/WHY queries to `code-patterns`, `conventions`, or `discussions` collections respectively
- **HNSW configuration** (`src/memory/config.py:172-185`): Dual ef values — `hnsw_ef_fast=64` for trigger mode, `hnsw_ef_accurate=128` for user search mode
- **Progressive context injection** (`src/memory/injection.py`): Tier 1 (bootstrap, 2-3K tokens) + Tier 2 (per-turn, 500-1500 tokens); greedy fill with no individual truncation; topic drift detection via cosine distance
- **Confidence gating**: injection skipped when retrieval score falls below threshold
- **Cascading search**: falls back across collections for comprehensive results

#### Automatic Triggers

[Verified — from `src/memory/triggers.py` and `.claude/hooks/scripts/`]

Six triggers are defined in `TRIGGER_CONFIG` (`src/memory/triggers.py:38-120`):

| Trigger | Signal | Status |
|---|---|---|
| `error_detection` | Structured error strings (`Error:`, `Exception:`, `Traceback`) | Enabled — `error_detection.py` |
| `new_file` | File creation in PreToolUse | Enabled — `new_file_trigger.py` |
| `first_edit` | First edit per file per session | Enabled — `first_edit_trigger.py` |
| `decision_keywords` | "why did we", "what was decided", etc. | **Disabled** — `decision_keyword_trigger.py.disabled` |
| `best_practices_keywords` | "how should I...", etc. | **Disabled** — `best_practices_keyword_trigger.py.disabled` |
| `session_history_keywords` | "what have we done..." | **Disabled** — `session_history_trigger.py.disabled` |

Three of six triggers are disabled via file extension in the current codebase.

#### Hook System

[Verified — from `.claude/hooks/scripts/` and `docs/HOOKS.md`]

Active hooks:
- `session_start.py` — SessionStart (startup/resume/compact)
- `post_tool_capture.py` — PostToolUse (pattern capture, forks to background)
- `agent_response_capture.py` — agent response capture
- `pre_compact_save.py` — PreCompact session summary
- `context_injection_tier2.py` — UserPromptSubmit per-turn injection
- `error_detection.py`, `error_pattern_capture.py`, `error_store_async.py` — error pipeline
- `langfuse_stop_hook.py` — Langfuse session tracing on Stop

Async store path: `store_async.py`, `user_prompt_store_async.py`, `agent_response_store_async.py` — PostToolUse forks to background to stay under 500ms NFR.

#### Security Scanning

[Verified — from `src/memory/security_scanner.py:1-82`]

Three-layer pipeline runs before any content is stored:
- Layer 1: Regex (~1ms) — email, phone, IP, SSN, credit card, API keys, tokens
- Layer 2: `detect-secrets` entropy scanning (~10ms)
- Layer 3: SpaCy NER (~50-100ms, optional) — named entity PII detection

PII is **masked** with placeholders; secrets are **blocked** entirely.

#### LLM Classification

[Verified — from `src/memory/classifier/`]

- Primary classifier: Anthropic Claude SDK (`src/memory/classifier/llm_classifier.py`)
- Fallback chain: Ollama → OpenRouter → OpenAI (`src/memory/classifier/config.py`)
- Rule-based pre-classifier (`src/memory/classifier/rules.py`) for deterministic cases
- Significance check (`src/memory/classifier/significance.py`) before classification
- Circuit breaker (`src/memory/classifier/circuit_breaker.py`): 3 states (CLOSED/OPEN/HALF_OPEN), configurable failure threshold and reset timeout
- Rate limiter (`src/memory/classifier/rate_limiter.py`)

#### Observability and Monitoring

- Prometheus metrics (`src/memory/metrics.py`): 6 NFR-aligned histograms + counters for captures, retrievals, embeddings, dedup, queue size
- Prometheus Pushgateway for hook-fired metrics (hooks can't scrape)
- Grafana dashboards (`docker/grafana/`)
- Langfuse V3 integration (`src/memory/trace_buffer.py`, `src/memory/trace_flush_worker.py`): OTel-based tracing with dual-path architecture — file-based buffer (~5ms overhead) for hooks, direct SDK for services
- Streamlit dashboard for memory inspection (`docker/streamlit/`)

#### Parzival Agent

[Informed — from `README.md:69-110`]

Parzival is an AI project manager persona (a `.claude/` skill set, not a separate process) that orchestrates BMAD workflow phases: Init → Discovery → Architecture → Planning → Execution → Integration → Release → Maintenance. It uses 20-constraint enforcement to prevent behavioral drift. Implemented as skill shims in `.claude/skills/`.

#### GitHub Integration

[Verified — from `src/memory/connectors/github/`]

Syncs: issues, PRs, PR diffs, PR reviews, commits, CI results, code blobs, releases into the `github` collection. Batched code blob sync with path-level include/exclude overrides (`GITHUB_CODE_BLOB_INCLUDE`). AST chunking via tree-sitter for 5 languages (Python, JS, TS, Go, Rust).

#### Jira Integration

[Verified — from `src/memory/connectors/jira/`]

Syncs: issues and comments into `jira-data` collection. ADF → plain text conversion. Full + incremental sync via JQL. Tenant isolation via `group_id` based on Jira instance hostname.

#### Multi-Project Support

- `group_id` filtering in all Qdrant queries (`src/memory/config.py`, `src/memory/project.py`)
- Project auto-detection from working directory path (`src/memory/project.py`)
- `projects.d/` YAML config directory for per-project GitHub/Jira settings
- Multi-project sync via `github_sync_service.py`

#### Backup/Restore

- `scripts/backup_qdrant.py` and `scripts/restore_qdrant.py`

### 2.2 Planned Features Not Yet Built

[Informed — from ROADMAP.md]

#### v2.3 (target: June 2026)

- ColBERT production hardening (memory optimization, model caching) — ColBERT is shipped but flagged `COLBERT_ENABLED=false` by default in docker-compose
- Search accuracy benchmarking and regression testing
- BM25 index maintenance and vocabulary tuning
- Test reorganization (unit/integration/e2e separation)
- Type hints for mypy strict mode
- Async migration to `asyncio.TaskGroup` (Python 3.11+)
- Circuit breaker pattern for Qdrant/embedding services (currently only in classifier)
- Automatic queue processor (background thread in classifier-worker)

#### v3.0 (target: TBD, Q3-Q4 2026)

- Multi-modal memory (image, diagram embeddings, cross-modal retrieval)
- Natural language query API with structured query builder
- Team collaboration with shared memory pools
- Access control and permissions
- Plugin system for custom extractors

### 2.3 Edge Cases and Gaps

[Verified + Inferred]

- **Three of six triggers are disabled** (`.claude/hooks/scripts/`): `decision_keyword_trigger`, `best_practices_keyword_trigger`, `session_history_trigger` all have `.disabled` extension. The reason for disabling is not documented in the files.
- **Streamlit auth deferred**: `TECH-DEBT-076` comment in `docker-compose.yml:276` — "Authentication: Deferred to Phase 2" — the Streamlit dashboard is unauthenticated and bound to localhost only.
- **Qdrant not in COLLECTION_NAMES** for jira-data: `src/memory/config.py:59` notes `COLLECTION_JIRA_DATA` is excluded from the `COLLECTION_NAMES` list to avoid breaking existing iteration logic. This is a known inconsistency.
- **ColBERT opt-in but not hardened**: `COLBERT_ENABLED=false` default with a `~400MB download` note in docker-compose — memory optimization and model caching are v2.3 scope.
- **No inline freshness at query time**: `src/memory/freshness.py:7` — "Tier 2 (inline freshness at query time) is Phase 3 scope." Only on-demand freshness report exists.
- **Token budget ceiling commented**: `src/memory/config.py:164` — "Can increase to 6000 if needed (TECH-DEBT-116)" — current default is 4000, ceiling is configurable but unvalidated at scale.

### OPEN QUESTIONS

- **OQ-2.1:** Why are three triggers disabled? Is this a known behavioral regression, a deliberate performance choice, or an incomplete feature state?
- **OQ-2.2:** Is there a prioritized list of TECH-DEBT items? The codebase has 30+ TECH-DEBT-xxx markers.
- **OQ-2.3:** What is the expected behavior when ColBERT is enabled in production — is it recommended for end users today?

---

## 3. Non-Functional Requirements

### 3.1 Performance Characteristics

[Verified — from `src/memory/metrics.py:1-25` and `docs/HOOKS.md:46-51`]

Six explicit NFR targets are instrumented with Prometheus histograms:

| NFR ID | Target | Metric | What it measures |
|--------|--------|--------|-----------------|
| NFR-P1 | <500ms | `aimemory_hook_duration_seconds` | PostToolUse hook total execution |
| NFR-P2 | <2s | `aimemory_embedding_batch_duration_seconds` | Batch embedding generation |
| NFR-P3 | <3s | `aimemory_session_injection_duration_seconds` | SessionStart bootstrap injection |
| NFR-P4 | <100ms | `aimemory_dedup_check_duration_seconds` | Deduplication check |
| NFR-P5 | <500ms | `aimemory_retrieval_query_duration_seconds` | Qdrant retrieval query |
| NFR-P6 | <500ms | `aimemory_embedding_realtime_duration_seconds` | Real-time single embedding |

Security scanning layer latencies are documented inline: Layer 1 ~1ms, Layer 2 ~10ms, Layer 3 (SpaCy) ~50-100ms (`src/memory/security_scanner.py:7-9`).

The `SessionStart` hook is synchronous and **blocks** Claude startup — the 3s NFR-P3 target reflects this user-visible constraint. All PostToolUse capture hooks fork to background (`store_async.py`) to stay within 500ms.

### 3.2 Scale Expectations

[Informed — from config defaults and architecture docs]

- `max_retrievals` default: 10 (range 1-50) per session (`src/memory/config.py:158-160`)
- `token_budget` default: 4000 tokens (range 100-100000) (`src/memory/config.py:165-170`)
- `collection_size_warning` and `collection_size_critical` thresholds exist in `MemoryConfig` but specific values not inspected
- Embedding memory limit: 4GB per container for dual ONNX models (`docker/docker-compose.yml:71`)
- GitHub code blob sub-batch upsert cap: 64 points to avoid Qdrant gRPC 64MB limit (`CHANGELOG.md v2.2.5`)
- Queue retry backoff: 1min, 5min, 15min capped (`src/memory/queue.py`)
- Session trigger state: max 100 concurrent sessions, 24h TTL (`src/memory/triggers.py:33-34`)
- Prometheus retention: 30 days (`docker/docker-compose.yml:156`)

**Concurrent user model:** The system is primarily designed for single-developer use per Qdrant instance. Multi-team shared memory pools are explicitly v3.0 scope. `group_id` filtering provides project isolation on a shared instance.

### 3.3 Security Model

[Verified — from `src/memory/security_scanner.py`, `docker/docker-compose.yml`, `oversight/project-context.md`]

**3-Layer Content Security Pipeline** (SPEC-009):

- **Layer 1 — Regex pattern detection** (`src/memory/security_scanner.py:88-140`): Catches emails, phone numbers, IPs, credit cards, SSNs, GitHub handles, internal URLs, API keys, tokens, passwords. Action: PII → MASKED with placeholder; secrets → BLOCKED. Latency: ~1ms.
- **Layer 2 — detect-secrets entropy scanning** (`src/memory/security_scanner.py:28-31`): Lazy-loaded (`TD-162`) to avoid hook startup overhead. Catches high-entropy strings that bypass regex. Action: BLOCKED. Latency: ~10ms.
- **Layer 3 — SpaCy NER** (`src/memory/security_scanner.py:25-26`): Lazy-loaded to avoid import overhead. Named entity recognition for person names, organizations. Action: MASKED. Latency: ~50-100ms, optional.

`ScanAction` outcomes: `PASSED`, `MASKED`, `BLOCKED` — blocked content is never stored, original text is never persisted to Qdrant (`src/memory/security_scanner.py:67`).

**Infrastructure Security:**
- Qdrant API key authentication (`docker/docker-compose.yml:29`)
- All services bound to `127.0.0.1` — no external exposure
- Container security hardening: `no-new-privileges:true`, `cap_drop: ALL`, `read_only: true` on monitoring-api, prometheus, grafana containers
- SOPS+age encryption support for secrets config (`docs/` references `setup-secrets.sh`)
- Prometheus basic auth with bcrypt-hashed passwords (init container pattern)
- Structured logging redacts `SENSITIVE_KEYS` (`oversight/project-context.md:99-103`)

**Gaps noted:**
- Streamlit dashboard has no authentication (`TECH-DEBT-076`, Phase 2 deferred)
- Qdrant `QDRANT_USE_HTTPS=false` default — API key without TLS provides limited protection in non-localhost deployments (noted in config)

### 3.4 Reliability and Resilience

[Verified — from `src/memory/graceful.py`, `src/memory/classifier/circuit_breaker.py`, `src/memory/queue.py`]

**Graceful degradation** (`src/memory/graceful.py`): `@graceful_hook` decorator wraps all hook entry points. Any unhandled exception exits with code 1 (non-blocking) — Claude continues working without memory context rather than crashing. Exit codes: 0 (success), 1 (non-blocking error), 2 (blocking — rarely used).

**Circuit breaker** for LLM classifier providers (`src/memory/classifier/circuit_breaker.py`): 3-state CLOSED/OPEN/HALF_OPEN. Configurable `failure_threshold=5`, `reset_timeout=60s`, `half_open_max_attempts=3`. Thread-safe with `RLock`. Currently only protects the classifier provider chain — circuit breakers for Qdrant and embedding services are **planned in v2.3**.

**File-based retry queue** (`src/memory/queue.py`): Failed memory operations (embedding unavailable, Qdrant down) are queued to `pending_queue.jsonl`. Retry with exponential backoff: 1min, 5min, 15min. Uses `fcntl.flock` for concurrency safety and atomic `os.replace()` writes. Background processor for this queue is v2.3 scope (currently manual/on-demand).

**Null vector fallback**: embedding failure results in `EmbeddingStatus.PENDING` rather than storage failure (`src/memory/storage.py` docstring).

**Tenacity retry** (`pyproject.toml:46`): `tenacity>=8.0` for HTTP retries with exponential backoff in client calls.

---

## 4. Integration Requirements

### 4.1 External System Integrations

[Verified — from `src/memory/connectors/`, `oversight/project-context.md`, `docker/docker-compose.yml`]

#### GitHub

- **API version:** REST (GitHub API via `src/memory/connectors/github/client.py`)
- **Auth:** GitHub Personal Access Token (env var `GITHUB_TOKEN`)
- **Data synced:** issues, PRs, PR diffs, PR reviews, commits, CI results, code blobs, releases
- **Sync modes:** full backfill + incremental (delta via last-synced timestamp)
- **Code indexing:** AST chunking via tree-sitter (Python, JS, TS, Go, Rust)
- **Include overrides:** `GITHUB_CODE_BLOB_INCLUDE` env var for path-level force-include
- **Multi-project:** `projects.d/` per-project config, github-sync restarts on new project add

#### Jira Cloud

- **API:** Jira REST API v3 (`src/memory/connectors/jira/client.py`)
- **Auth:** Basic Auth (email + API token via `JIRA_EMAIL`, `JIRA_API_TOKEN` as SecretStr)
- **Data synced:** issues and comments
- **Content transform:** ADF (Atlassian Document Format) → plain text (`src/memory/connectors/jira/adf_converter.py`)
- **Sync modes:** full + incremental via JQL
- **Tenant isolation:** `group_id` derived from Jira instance hostname

#### Langfuse (optional)

- **SDK:** Langfuse v3 only — V2 SDK usage is explicitly prohibited in comments across multiple files
- **Architecture:** dual-path — trace buffer (file-based, ~5ms) for hooks (Path A), direct SDK with `@observe` decorator for services (Path B) (`src/memory/trace_buffer.py`, `src/memory/trace_flush_worker.py`)
- **OTel:** `opentelemetry-instrumentation-anthropic` for Anthropic SDK auto-instrumentation
- **Opt-in:** `LANGFUSE_ENABLED=true` kill-switch; inactive hooks remain <500ms
- **Docker:** 7 additional services via `--profile langfuse` (`docker/docker-compose.langfuse.yml`)

#### Prometheus + Grafana (optional)

- **Prometheus:** v2.55.1, 30-day retention, basic auth, `--profile monitoring`
- **Pushgateway:** v1.9.0 for hook-fired metrics (hooks can't be scraped)
- **Grafana:** v12.0.0, pre-provisioned dashboards, anonymous Viewer access by default
- **Metrics namespace:** `aimemory_*` (BP-045)

### 4.2 Qdrant (Core Dependency)

- **Version:** v1.16.3 (pinned in `docker-compose.yml`)
- **Client:** `qdrant-client>=1.17.0,<2.0.0` (`pyproject.toml:31`)
- **FormulaQuery API:** required for decay scoring — `qdrant-client>=1.14.0` hard requirement (`src/memory/decay.py:29-34`)
- **Hybrid search:** dense vectors + sparse BM25 vectors + ColBERT late interaction, fused via RRF
- **8-bit scalar quantization:** per BP-038 (confirmed in ROADMAP.md best practices table)
- **gRPC transport:** used for batch operations; 64MB limit requires sub-batching
- **Auth:** API key via `QDRANT__SERVICE__API_KEY` env var

### 4.3 LLM Classification Providers

[Verified — from `src/memory/classifier/providers/`]

Primary: Anthropic Claude SDK (`anthropic>=0.61.0,<1.0.0`)
Fallback chain (in order): Ollama → OpenRouter → OpenAI
- Ollama URL auto-detected (WSL2 gateway, Docker host.docker.internal, or localhost)
- Custom model registration for Langfuse cost tracking

### 4.4 Embedding Service

- Self-hosted FastEmbed service (`docker/embedding/`)
- Two ONNX models loaded: `jina-embeddings-v2-base-en` + `jina-embeddings-v2-base-code`
- HTTP API, 768-dimensional vectors
- Memory: 4GB container limit (two ONNX models ~3GB combined)
- Startup: up to 12.5min first-run (model download, ~500MB/model)
- ColBERT model: opt-in (`COLBERT_ENABLED=false` default), ~400MB additional download

### 4.5 Authentication / Configuration Model

[Verified — from `src/memory/config.py:87-248` and `oversight/project-context.md:55-59`]

- **Primary config source:** environment variables loaded from `~/.ai-memory/docker/.env`
- **Pydantic BaseSettings** with `SettingsConfigDict`: env vars override `.env`, `.env` overrides defaults
- **315 configurable env vars** documented in `docker/.env.example`
- **Frozen config** (immutable after load, thread-safe)
- **LRU cache** on `get_config()` — single instance per process
- **SecretStr** used for `JIRA_API_TOKEN` and similar sensitive fields
- **SOPS+age** encryption available for secrets file (`scripts/setup-secrets.sh`)

### 4.6 Deployment Requirements

[Verified — from `docker/docker-compose.yml`, `docker/docker-compose.langfuse.yml`, `scripts/install.sh`]

**Core stack** (always required):
- `qdrant` — vector database
- `embedding` — FastEmbed service

**Optional profiles:**
- `--profile monitoring` — adds: prometheus-init, prometheus, pushgateway, grafana, streamlit, monitoring-api
- `--profile langfuse` — adds: Langfuse web, worker, PostgreSQL, ClickHouse, Redis, MinIO, trace-flush-worker
- `--profile testing` — adds: monitoring-api only

**Installer:** `scripts/install.sh` — Bash script for macOS/Linux. Handles: new install, add-project to existing, updates. Auto-detects GitHub repo from `.git/config`. Manages `projects.d/` per-project YAML. Requires Docker 20.10+ and Python 3.10+.

**Install directory:** `~/.ai-memory/` (configurable via `AI_MEMORY_INSTALL_DIR`)

**No cloud requirement:** entirely self-hosted. Qdrant runs locally via Docker.

---

## 5. Constraints and Boundaries

### 5.1 Explicit Out of Scope

[Informed — from `oversight/goals.md` and ROADMAP.md]

From `oversight/goals.md:21-22`: "Out of Scope (Initial): TBD — to be determined during Discovery phase"

The goals doc explicitly defers out-of-scope definition to Discovery. However, from roadmap and architecture signals:

- **Team collaboration / multi-user shared pools** — deferred to v3.0
- **Access control / permissions** — deferred to v3.0
- **Plugin system for custom extractors** — deferred to v3.0
- **Multi-modal memory (images, diagrams)** — deferred to v3.0
- **Natural language query API** — deferred to v3.0
- **Cloud-hosted SaaS offering** — no mention anywhere in docs; entirely self-hosted model

### 5.2 Technical Constraints

[Verified — from `pyproject.toml`, `oversight/project-context.md`, `src/memory/decay.py`]

- **Python 3.10+** required — uses `match` statements, union types (`X | Y`), `StrEnum` workaround for 3.10 compatibility (`src/memory/models.py:28-30`)
- **Qdrant v1.16.3** pinned in Docker — `qdrant-client>=1.14.0` minimum for FormulaQuery/decay scoring
- **qdrant-client** must be `>=1.17.0,<2.0.0` (`pyproject.toml:31`)
- **FastEmbed ONNX models** — ~500MB per model, first-run download required; no GPU requirement but CPU inference
- **Docker** required for Qdrant and embedding service — no native install path for core services
- **768 vector dimensions** — fixed by Jina embeddings v2; changing models requires full re-embedding
- **ColBERT late interaction** — opt-in, not hardened for production (v2.3 scope)
- **Linux/macOS only** for installer — WSL2 supported; native Windows not mentioned
- **`asyncio.TaskGroup`** migration deferred to Python 3.11+ (currently uses older async patterns)

### 5.3 Backward Compatibility

[Informed — from ROADMAP.md:175 and CHANGELOG.md migration scripts]

ROADMAP principle: "Breaking changes only in major versions (x.0.0)."

Migration scripts exist for past breaking changes:
- `scripts/migrate_v205_to_v206.py` — v2.0.5 → v2.0.6
- `scripts/migrate_v209_github_collection.py` — github collection separation
- `scripts/migrate_v221_hybrid_vectors.py` — v2.2.1 hybrid search vector schema

The `EMBEDDING_MODEL` constant is kept in `config.py:79-80` with a "Legacy constant, kept for backward compat" comment.

The `COLLECTION_NAMES` list intentionally excludes `jira-data` for backward compatibility with existing iteration logic (`src/memory/config.py:65-70`).

### 5.4 Known Limitations

[Verified + Inferred]

1. **Three keyword triggers disabled**: `decision_keyword_trigger`, `best_practices_keyword_trigger`, `session_history_trigger` are not running in default installations (`.claude/hooks/scripts/*.disabled`)
2. **No Streamlit auth**: dashboard accessible to any local process (`TECH-DEBT-076`)
3. **No circuit breakers for Qdrant/embedding**: only the LLM classifier has circuit breakers; Qdrant/embedding failures use graceful degradation (queue fallback) rather than circuit breaking — planned v2.3
4. **Queue processor is manual**: failed operations queue to `pending_queue.jsonl` but automatic background retry is v2.3 scope; current workflow requires user or cron to drain the queue
5. **Freshness detection is on-demand only**: no inline freshness at query time; only available via `/aim-freshness-report` skill
6. **ColBERT not production-ready**: enabled via opt-in flag, but memory optimization and model caching are v2.3 scope
7. **mypy strict mode not enforced**: type hints incomplete; mypy strict migration is v2.3 scope
8. **Test reorganization pending**: unit/integration/e2e separation is v2.3 scope; current structure mixes test types
9. **Intent detection is keyword-only**: `src/memory/intent.py` uses simple keyword matching, not semantic classification — "why did", "what port", "how do" keywords only
10. **Success criteria undefined**: `oversight/goals.md:14` — "Success Criteria: TBD — to be refined during Discovery phase"

---

## 6. Existing Behavior Documentation

### 6.1 End-to-End System Flow

[Verified — from `.claude/hooks/scripts/`, `src/memory/`, `docs/HOOKS.md`, `docs/AI_MEMORY_ARCHITECTURE.md`]

#### Full Flow: Hook → Embed → Store → Retrieve → Inject

```
CAPTURE PATH (write side):
1. Claude Code event fires (PostToolUse, Stop, PreCompact)
2. Hook script executes (.claude/hooks/scripts/post_tool_capture.py)
3. Security scan runs (3-layer pipeline in security_scanner.py)
   - BLOCKED content: dropped, never stored
   - MASKED content: PII replaced with placeholders
4. Deduplication check (deduplication.py)
   - Stage 1: SHA256 hash match (fast path)
   - Stage 2: Semantic similarity via Qdrant ANN (if hash misses)
5. Chunking (chunking/__init__.py → ast_chunker.py or prose_chunker.py)
   - Code: tree-sitter AST chunking (256-512 token chunks, 10-20% overlap)
   - Prose: prose chunker with topical segmentation
6. Embedding generation (embeddings.py → HTTP to embedding service)
   - Code content → jina-embeddings-v2-base-code (768-dim)
   - Prose → jina-embeddings-v2-base-en (768-dim)
   - Failure: sets EmbeddingStatus.PENDING, queues to pending_queue.jsonl
7. Storage (storage.py → qdrant_client.py)
   - Upsert to target collection with payload (group_id, memory_type, content, timestamp, etc.)
   - For GitHub code blobs: batched sub-upserts ≤64 points to avoid gRPC limit
8. Classification (async, classifier-worker container)
   - Rule-based pre-classification
   - LLM classification if rules don't match (Claude primary, fallback chain)
   - Circuit breaker protects against provider failures
9. Langfuse tracing (if enabled)
   - Hook side: emit_trace_event() writes to trace buffer file (~5ms)
   - trace_flush_worker container flushes buffer to Langfuse SDK asynchronously
   - Prometheus metrics pushed to Pushgateway async

RETRIEVAL PATH (read side):
1. SessionStart hook fires (session_start.py)
2. Bootstrap retrieval (injection.py: retrieve_bootstrap_context())
   - Intent detection on context (intent.py: detect_intent())
   - Search target collection (search.py: MemorySearch)
   - Hybrid search: dense + BM25 sparse + ColBERT RRF fusion
   - Decay scoring: FormulaQuery in Qdrant (0.7*semantic + 0.3*temporal)
   - Confidence gating: results below threshold dropped
   - Greedy fill within token budget (no individual truncation)
3. Context injected to Claude as text output from SessionStart hook (Tier 1, 2-3K tokens)
4. Per-turn injection (context_injection_tier2.py via UserPromptSubmit)
   - Topic drift detection vs. prior query embedding
   - Adaptive budget (500-1500 tokens)
   - Dedup against already-injected content this session (InjectionSessionState)
5. Automatic triggers fire in parallel with tool use (PreToolUse/UserPromptSubmit)
   - Active: error_detection, new_file, first_edit
   - Inactive: decision_keywords, best_practices_keywords, session_history_keywords
```

### 6.2 What Is Complete

[Verified]

- Full capture pipeline (hook → security scan → dedup → chunk → embed → store)
- Full retrieval pipeline (search → decay score → intent route → greedy inject)
- Triple fusion hybrid search (dense + BM25 + ColBERT via RRF)
- 5-collection architecture with 31 memory types
- GitHub integration (issues, PRs, commits, CI, code blobs) with batched sync
- Jira integration (issues, comments, ADF conversion)
- Multi-project isolation via `group_id`
- 3-layer security pipeline
- Dual-stage deduplication
- Semantic decay scoring
- Progressive context injection (Tier 1 bootstrap + Tier 2 per-turn)
- Parzival AI project manager (skill-based)
- Langfuse V3 observability (optional, dual-path architecture)
- Prometheus + Grafana monitoring (optional)
- File-based retry queue
- Circuit breaker for LLM classifier providers
- Installer script with multi-project support
- Backup/restore scripts
- Streamlit memory inspection dashboard

### 6.3 What Is Partial or Incomplete

[Verified]

- **Trigger system**: 6 triggers defined, 3 active, 3 disabled — the disabled triggers represent partial functionality
- **ColBERT**: shipped in embedding service (`COLBERT_ENABLED=false` default) — production hardening (memory optimization, model caching) is v2.3 scope
- **Queue processor**: queue exists and persists, but background auto-processing is v2.3 scope
- **Freshness detection**: on-demand Tier 1 only; inline Tier 2 at query time is deferred
- **Streamlit auth**: UI shipped without authentication (`TECH-DEBT-076`)
- **mypy strict**: type coverage incomplete, strict enforcement deferred to v2.3
- **Async migration**: partial — 6+ modules use async/await, but `asyncio.TaskGroup` migration (Python 3.11+) is v2.3

### 6.4 Known Issues and Technical Debt

[Verified — from inline TECH-DEBT markers and CHANGELOG bug references]

Representative items from source code markers (not exhaustive):

| ID | Module | Description |
|---|---|---|
| TECH-DEBT-012 | `models.py`, `storage.py` | `created_at` timestamp handling has 3+ rounds of patches |
| TECH-DEBT-035 | `agent_sdk_wrapper.py` | Claude Agent SDK wrapper — Phase 3 of incremental build |
| TECH-DEBT-066 | `config.py` | HNSW search performance tuning in config |
| TECH-DEBT-076 | `docker-compose.yml` | Streamlit auth deferred to Phase 2 |
| TECH-DEBT-089 | `deduplication.py`, `chunking/` | Metrics push for NFR-P4 dedup timing — partially complete |
| TECH-DEBT-113 | `triggers.py` | Trigger validation runs at module load (dev check) |
| TECH-DEBT-115 | `session_start.py` | `<retrieved_context>` delimiters per BP-039 §1 not yet applied |
| TECH-DEBT-116 | `config.py` | Token budget ceiling may need increase to 6000 |
| TECH-DEBT-123 | `metrics.py` | Deprecated Grafana V2 metrics pending removal |
| BUG-040 | `docker-compose.yml` | Embedding healthcheck start_period increased to 12.5min for model download |

The `storage.py` module at 2,045 lines is the largest module, with multiple TECH-DEBT markers suggesting organic growth. The `search.py` module (2,002 lines) is similarly large.

### 6.5 Test Coverage Assessment

[Verified — from `oversight/project-context.md:73-78` and file counts]

- **Test-to-code ratio:** 2.1x (69K LOC tests / 32K LOC source)
- **Coverage threshold:** 70% (enforced via pytest-cov)
- **Test structure:** ~50 unit test files in `tests/unit/`, ~46 integration test files in `tests/integration/`
- **E2E:** Playwright-based TypeScript in `tests/e2e/`
- **Performance tests:** dedicated directory
- **Markers:** `integration`, `slow`, `performance`, `requires_qdrant`, `requires_docker_stack`, `regression`, `quarantine`
- **Test reorganization** (unit/integration/e2e clean separation) is explicitly v2.3 scope, implying current structure has mixed or overlapping test types
- **9 pytest plugins**: asyncio, cov, mock, timeout, randomly, rerunfailures, hypothesis, playwright — mature test infrastructure
- **Known gap:** `session_history_trigger.py.disabled` and other disabled scripts have no active code path to test

### OPEN QUESTIONS

- **OQ-6.1:** What is the actual measured coverage percentage? The 70% threshold is enforced but the current figure is unknown.
- **OQ-6.2:** Why are three triggers disabled? If they were working and then disabled, what regression caused it? If they were never completed, what is the remaining work?
- **OQ-6.3:** Is the `pending_queue.jsonl` file growing unbounded in production installations without a background processor? What is the operational guidance for queue drain today?
- **OQ-6.4:** Are there any known data corruption or data loss issues that have been observed in production?

---

## Summary of Open Questions

| ID | Section | Question | Priority |
|---|---|---|---|
| OQ-1.1 | Users | Current star count and active contributor count? | Low |
| OQ-1.2 | Users | Individual developer vs. team as primary target? | High |
| OQ-1.3 | Users | Priority ordering: stabilization vs. features vs. adoption? | Critical |
| OQ-1.4 | Users | Production deployments today + observed token savings? | Medium |
| OQ-2.1 | Functional | Why are three triggers disabled? | High |
| OQ-2.2 | Functional | Prioritized TECH-DEBT backlog? | Medium |
| OQ-2.3 | Functional | Is ColBERT recommended for end users today? | Medium |
| OQ-6.1 | Testing | Current actual coverage percentage? | Low |
| OQ-6.2 | Testing | Disabled trigger status: regression, incomplete, or deliberate? | High |
| OQ-6.3 | Testing | Queue drain operational guidance for production? | High |
| OQ-6.4 | Testing | Known data loss or corruption issues in production? | High |

---

*This document is based on direct inspection of the ai-memory v2.2.6 codebase and associated documentation. All [Verified] findings were confirmed by reading source code. All [Informed] findings derive from project documentation. [Inferred] findings are pattern-based and should be validated before use in PRD drafting.*
