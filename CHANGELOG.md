# Changelog

All notable changes to RLM are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.1] - 2026-02-01

### Changed — Phase 6: PyPI Distribution
- Migrated to **src/ layout** (PyPA best practice)
- Added `main()` entry point in `server.py`
- Added `__init__.py` and `__main__.py` for `python -m mcp_server` support
- Updated `install.sh` with pip vs git clone detection
- CI: Enabled Trusted Publishers (OIDC) for PyPI publish on tag push
- Removed redundant `mcp_server/requirements.txt` (pyproject.toml is source of truth)
- Fixed all internal imports: `from tools.X` → `from mcp_server.tools.X`
- Fixed test imports: removed `sys.path` hacks, use proper package imports
- Added `dist/`, `build/`, `*.egg-info` to `.gitignore`

### Backward compatibility
- **Symlink** `mcp_server/server.py` → `src/mcp_server/server.py` for existing users
- Existing installations keep working after `git pull` (no immediate breakage)
- Recommended: re-run `./install.sh` to update the MCP server path

### Install
```bash
# New install
pip install mcp-rlm-server[all]

# Upgrade from v0.9.0 (git users)
cd rlm-claude && git pull && ./install.sh
```

## [Unreleased]

### Added — Phase 7.2: Entity Extraction (COMPLETE)
- `_extract_entities(content)` — regex-based extraction of files, versions, modules, tickets, functions
- `_entity_matches(chunk_info, entity)` — case-insensitive substring matching across all entity types
- `entity` param on `rlm_grep` — filter grep/fuzzy results by entity
- `entity` param on `rlm_search` — filter BM25 results by entity
- Auto-extraction at `rlm_chunk()` time — entities stored in index.json and YAML frontmatter
- Typed storage: `{"files": [...], "versions": [...], "modules": [...], "tickets": [...], "functions": [...]}`
- 36 tests in `tests/test_entity_extraction.py` (extraction, matching, grep filter, search filter)
- Zero external dependencies (regex-only, MAGMA-inspired lightweight approach)
- Backward compatible: existing chunks without entities treated as `{}`

### Added — Phase 7.1: Temporal Filtering (COMPLETE)
- `date_from`/`date_to` params on `rlm_search` — filter BM25 results by date range
- `date_from`/`date_to` params on `rlm_grep` — filter regex/fuzzy results by date range
- `_parse_date_from_chunk()` helper — extracts date from `created_at` or chunk ID fallback
- `_chunk_in_date_range()` helper — lexicographic YYYY-MM-DD comparison (no datetime parsing)
- 28 tests in `tests/test_temporal_filter.py` (helpers, grep, fuzzy+date, search, legacy, edge cases)
- Backward compatible: legacy format 1.0 chunks supported via ID-based date extraction

### Added — Phase 6: Production-Ready (in progress)
- `mcp_server/tools/fileutil.py` - Shared security utilities (atomic writes, path traversal prevention, file locking)
- `SECURITY.md` - Vulnerability reporting policy
- GitHub Actions CI: ruff lint + ruff format
- `tests/` directory with pytest infrastructure

### Security (Phase 6)
- **Path traversal prevention** — Chunk IDs validated against strict allowlist `[a-zA-Z0-9_.-&]`, resolved paths checked
- **Atomic writes** — All JSON and chunk files written via write-to-temp-then-rename (POSIX atomic)
- **File locking** — `fcntl.flock` exclusive locks for concurrent read-modify-write on shared indexes
- **Content size limits** — 2 MB chunks, 10 MB decompression cap (gzip bomb protection)
- **SHA-256 hashing** — Content deduplication uses SHA-256 (not MD5)

### Changed
- Duplicate detection upgraded from MD5 to SHA-256
- All I/O operations consolidated into `fileutil.py`
- Import ordering fixed for ruff compliance

---

## [0.9.0] - 2026-01-24 - Système Simplifié (User-Driven + Auto-Compact)

### Changed
- **BREAKING**: Suppression des reminders automatiques 10/20/30 tours
- Hook Stop désactivé (plus de reminders intrusifs)
- Hook PreCompact crée un chunk automatique AVANT /compact
- Philosophie: L'utilisateur décide quand chunker, le système sauvegarde avant perte

### Architecture Simplifiée

| Moment | Action | Déclencheur |
|--------|--------|-------------|
| Instruction explicite | `rlm_chunk()` ou `rlm_remember()` | Utilisateur ("garde ça", "chunk") |
| Moment clé | Claude propose de chunker | Réflexe Claude (décision, fin tâche) |
| `/compact` | Chunk automatique minimal | Hook PreCompact |
| Post-compact | Claude lit et enrichit si besoin | Réflexe Claude |

### Removed
- Seuils 10/20/30 tours
- Reminders "AUTO-CHUNK REQUIS"
- Context-awareness (plus nécessaire sans reminders)

### Why
- Les hooks PreCompact ne peuvent PAS injecter de message dans le contexte Claude
- Les reminders étaient souvent ignorés
- Approche user-driven + sauvegarde automatique = plus simple et plus efficace

---

## [0.8.0] - 2026-01-24 - Hook PreCompact + Context-aware (DEPRECATED)

> **Note**: Cette version a été remplacée par v0.9.0 le même jour après découverte
> que les hooks PreCompact ne peuvent pas injecter de messages dans le contexte Claude.

### Added
- `pre_compact_chunk.py` - Hook PreCompact (message seulement, pas d'injection)
- Context-awareness: Hook Stop ne se déclenche QUE si contexte >= 55%
- Seuils progressifs: 10/20/30 tours

### Deprecated
- Cette approche ne fonctionne pas comme prévu

---

## [0.7.0] - 2026-01-19 - Phase 5.6 Retention

### Added
- `rlm_retention_preview` tool - Preview what would be archived/purged (dry-run)
- `rlm_retention_run` tool - Execute archiving and/or purging
- `rlm_restore` tool - Restore archived chunks to active storage
- `mcp_server/tools/retention.py` - Core retention logic (400+ LOC)
- 3-zone architecture: ACTIVE → ARCHIVE → PURGE
- Gzip compression for archives (~70% size reduction)
- Auto-restore on `peek()` - Archived chunks are transparently restored
- Immunity system - Protected tags, access count, keywords
- `context/archive/` directory for compressed chunks
- `archive_index.json` - Index of archived chunks
- `purge_log.json` - Log of purged chunks (metadata only)
- 20 new tests in `tests/test_retention.py`

### Retention Rules
- **Archive after 30 days** if: `access_count == 0` AND not immune
- **Purge after 180 days** in archive if: still unused AND not immune
- **Immunity conditions**:
  - Tags: `critical`, `decision`, `keep`, `important`
  - `access_count >= 3` (frequently accessed)
  - Keywords in content: `DECISION:`, `IMPORTANT:`, `A RETENIR:`

### Examples
```python
# Preview actions (dry-run)
rlm_retention_preview()

# Archive old unused chunks
rlm_retention_run(archive=True)

# Archive AND purge (explicit)
rlm_retention_run(archive=True, purge=True)

# Manually restore an archived chunk
rlm_restore("2025-12-01_001")
```

### Technical
- Atomic file operations (temp + rename)
- Backward compatible index format
- Purge log preserves metadata, never content

---

## [0.6.1] - 2026-01-19 - Phase 5.2 Grep++ (Fuzzy Search)

### Added
- `grep_fuzzy()` function - Fuzzy matching with thefuzz library
- `rlm_grep(..., fuzzy=True, fuzzy_threshold=80)` - Tolerates typos in searches
- Score-based ranking - Best matches first
- 16 new tests in `tests/test_grep_fuzzy.py`

### Examples
- `rlm_grep("buisness", fuzzy=True)` finds "business"
- `rlm_grep("validaton", fuzzy=True)` finds "validation"
- `rlm_grep("senario", fuzzy=True)` finds "scenario"

### Dependencies
- Added `thefuzz>=0.22.1` as optional dependency (`pip install mcp-rlm-server[fuzzy]`)
- Graceful degradation: Returns error message if thefuzz not installed

### Technical
- Uses `fuzz.partial_ratio` for substring matching
- Default threshold: 80 (adjustable 0-100)
- Integrates with existing project/domain filters

---

## [0.6.0] - 2026-01-18 - Phase 5.5 Multi-sessions COMPLETE

### Added
- `rlm_sessions` tool - List sessions by project/domain
- `rlm_domains` tool - List available domains (31 default)
- New chunk ID format: `{date}_{project}_{seq}[_{ticket}][_{domain}]`
- Project auto-detection via `RLM_PROJECT` env, git root, or cwd
- `domains.json.example` - Template with Joy Juice domains
- Cross-session filtering: `rlm_grep(..., project="X", domain="Y")`
- Cross-session filtering: `rlm_search(..., project="X", domain="Y")`
- `sessions.json` - Session index (auto-created, git-ignored)
- `domains.json` - Domain suggestions (auto-created, git-ignored)

### Fixed
- **Bugfix b691d9f**: `chunk()` now properly calls `register_session()` and `add_chunk_to_session()`

### Changed
- Backward compatibility: Chunks in format 1.0 (`YYYY-MM-DD_NNN`) remain accessible

---

## [0.5.1] - 2026-01-18 - Phase 5.1 BM25 Search

### Added
- `rlm_search` tool - BM25 ranking search (FR/EN)
- `mcp_server/tools/search.py` - BM25S implementation (500x faster than rank_bm25)
- `mcp_server/tools/tokenizer_fr.py` - Zero-dependency FR/EN tokenization
- Accent normalization: `realiste` matches `réaliste`
- Stopwords filtering (French + English)
- Compound word splitting: `jus-de-fruits` → `[jus, fruits]`

### Dependencies
- Added `bm25s>=0.2.0` (optional, for search feature)

---

## [0.5.0] - 2026-01-18 - Phase 5.3 Sub-agents

### Added
- Skill `/rlm-parallel` - Parallel chunk analysis (Partition + Map pattern)
- 3 parallel Task tools (Sonnet) + 1 merger
- Automatic contradiction detection
- Citation format with `[chunk_id]` references

### Notes
- MCP Sampling not supported by Claude Code (issue #1785) → Skill = only option
- Cost: $0 (Task tools included in Claude Code Pro/Max)

---

## [0.4.0] - 2026-01-18 - Phase 4 Production

### Added
- Auto-summarization when no summary provided (first line extraction)
- Duplicate detection via MD5 content hash
- Access counting for chunks (`access_count`, `last_accessed`)
- Most-accessed chunks display in `rlm_status()`

### Fixed
- Hook `Stop` format: Use `systemMessage` (not `hookSpecificOutput.additionalContext`)
- Removed unsupported `"matcher": "*"` from Stop hook

### Changed
- `index.json` upgraded to v2.0.0 with extended metadata

---

## [0.3.0] - 2026-01-18 - Phase 3 Auto-chunking

### Added
- Hook `auto_chunk_check.py` - Detects when chunking is needed
- Hook `reset_chunk_counter.py` - Resets counter after `rlm_chunk`
- Skill `/rlm-analyze` - Analyze single chunk with sub-agent
- `install.sh` - One-command installation script
- `templates/hooks_settings.json` - Hook configuration template
- `templates/CLAUDE_RLM_SNIPPET.md` - CLAUDE.md instructions

### Configuration
- Turns threshold: 10 (configurable)
- Time threshold: 30 minutes (configurable)

---

## [0.2.0] - 2026-01-18 - Phase 2 Navigation

### Added
- `rlm_chunk` tool - Save content to external chunk file
- `rlm_peek` tool - Read chunk content (with optional line range)
- `rlm_grep` tool - Search regex patterns across all chunks
- `rlm_list_chunks` tool - List chunks with metadata
- `context/chunks/` directory for chunk storage
- `context/index.json` for chunk indexing

### Format
- Chunk ID format v1.0: `YYYY-MM-DD_NNN`
- Chunk files: Markdown with YAML frontmatter

---

## [0.1.0] - 2026-01-18 - Phase 1 Memory

### Added
- `rlm_remember` tool - Save insights (decision, fact, preference, finding, todo, general)
- `rlm_recall` tool - Retrieve insights by query, category, or importance
- `rlm_forget` tool - Delete insight by ID
- `rlm_status` tool - System status (insights count, categories, importance levels)
- `context/session_memory.json` for insight storage
- MCP server with stdio transport (FastMCP)

### Importance Levels
- `low`, `medium`, `high`, `critical`

### Categories
- `decision`, `fact`, `preference`, `finding`, `todo`, `general`

---

## References

- [RLM Paper (MIT CSAIL)](https://arxiv.org/abs/2512.24601) - Zhang et al., Dec 2025
- [MCP Specification](https://modelcontextprotocol.io/specification)
- [Letta Benchmark](https://www.letta.com/blog/benchmarking-ai-agent-memory)

---

**Repository**: https://github.com/EncrEor/rlm-claude
**Authors**: Ahmed MAKNI, Claude Opus 4.5
