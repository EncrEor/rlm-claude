# Changelog

All notable changes to RLM are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Phase 6: Production-Ready (tests, CI/CD, PyPI distribution)

---

## [0.8.0] - 2026-01-24 - Hook PreCompact + Context-aware

### Added
- `pre_compact_chunk.py` - Hook PreCompact qui force chunk AVANT /compact ou auto-compact
- Context-awareness: Hook Stop ne se déclenche QUE si contexte >= 55%
- Seuils progressifs: 10 (📝 doux) / 20 (⚠️ insistant) / 30 (🛑 critique) tours
- Affichage du % de contexte dans les messages de reminder
- Documentation triggers manuels (décision, fin tâche, insight, changement sujet)

### Changed
- `auto_chunk_check.py` v3 - Lecture du contexte via stdin + seuils progressifs
- Architecture hooks: PreCompact (principal) + Stop (backup) + PostToolUse (reset)

### Configuration
```json
{
  "hooks": {
    "PreCompact": [
      {"matcher": "manual", "hooks": [...]},
      {"matcher": "auto", "hooks": [...]}
    ],
    "Stop": [...],
    "PostToolUse": [...]
  }
}
```

### Philosophy
- Chunk aux moments importants, pas sur des seuils arbitraires
- PreCompact garantit la sauvegarde avant perte de contexte
- Context-aware évite le bruit sur les petites conversations

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
