# Changelog

All notable changes to RLM are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.11.0] - 2026-10-07

### Added — Unsaved sessions are reported, not silently lost
- Chunking stays deliberate, so a session that ends without `rlm_chunk()` — closed terminal, crash, auto-compact, plain forgetting — used to leave no trace at all. Nothing told the next session that work had gone unsaved.
- **`hooks/session_trace.py`** (PostToolUse on `Edit|Write|MultiEdit|NotebookEdit|Bash`) appends to `~/.claude/rlm/sessions/<session_id>.jsonl` the paths a session edits and, for Bash, only the **basenames of allow-listed programs** (`notable_commands`). The command line is never recorded: it can carry passwords and tokens. A test feeds it `sshpass -p <secret> …` and checks the secret never reaches the trace.
- **`hooks/session_orphans.py`** (SessionStart) lists past sessions that are over (idle for `idle_hours`), mattered (more than `min_edits` edits, or one notable program run) and carry neither a chunk nor an acknowledgement — with their transcript path and the date until which Claude Code keeps it. It detects the *missing chunk*, not a clean exit, so crashes are covered. Sessions of the current project are detailed, others only counted; the current session and sessions possibly still running in parallel are skipped. `--ack <session_id> "reason"` records that a session holds nothing worth keeping. Traces older than `retention_days` (30, Claude Code's default transcript retention) are deleted.
- **`hooks/reset_chunk_counter.py`** now also ties each chunk to its session: a `chunk` event in the trace, and `session_id` + `transcript_path` on the chunk in `index.json` (same flock protocol as the server; a duplicate chunk keeps its first session). The `last_chunk` timestamp read by the PreCompact guard is still written first and unconditionally.
- Thresholds and the allow-list live in an optional `~/.claude/rlm/session_trace.json`. Messages in EN/FR/JA. 19 tests run the real hook scripts against a throwaway `HOME`.

### Fixed — Installer and docs
- `install.sh` copied three hooks out of four (`memory_write_redirect.py` was registered but never installed) and kept its own hand-written copy of the hook config, which had drifted from `templates/hooks_settings.json`. It now copies every hook and reads the template.
- `uninstall.sh` removes every hook under `~/.claude/rlm/hooks/` instead of a fixed list that missed `memory_write_redirect.py`, and the session traces with the other runtime files.
- The READMEs (EN/FR/JA) and `templates/CLAUDE_RLM_SNIPPET.md` still promised that RLM "automatically saves a snapshot" before `/compact`. It never did since the PreCompact v2 guard: rewritten to describe what the hooks actually do. claude-mem added to the comparison table.


### Fixed — FastEmbed model cache no longer lives in the temp directory
- fastembed defaults to `tempfile.gettempdir()/fastembed_cache`. macOS sweeps that directory: the ~235 MB model blob disappeared while the snapshot symlinks stayed, the load failed with `NO_SUCHFILE` instead of re-downloading, and every chunk written meanwhile was stored without a vector (4 chunks on 26-27 Sept. 2026, found by `rlm_status`). `FastEmbedProvider` now passes a persistent `cache_dir` (`~/.cache/fastembed`); `FASTEMBED_CACHE_PATH` still overrides it.
- `scripts/reconcile_stores.py` is safe to run while sessions are live: vectors are computed outside the lock and written inside `VectorStore.locked()` on a fresh load, and `index.json` goes through `locked_json_update()` instead of rewriting the snapshot read at startup (which would have dropped any chunk indexed by another session meanwhile). A healed chunk also loses the `embedded: false` flag set at write time.
- The test suite no longer runs against the developer's real context: `tests/conftest.py` binds `RLM_CONTEXT_DIR` to a throwaway directory before any `mcp_server` import. `CONTEXT_DIR` is resolved at import time, so the suite used to append fake warnings to the live `rlm.log` (surfaced by `rlm_status` as real ones) and to attempt writes of test vectors into the live store — stopped only by a dimension mismatch. A guard test fails if the redirection ever stops. An inherited `RLM_EMBEDDING_PROVIDER` is dropped as well: three provider tests assume the default provider and failed under `fastembed`.

### Added — Review-driven archiving (`scripts/retire_chunks.py`)
- `rlm_retention_run()` archives by age and use; it cannot tell a stale state from a valid old decision. `scripts/retire_chunks.py` archives from a **reviewed manifest**: each chunk carries why it is obsolete, what supersedes it, and whether it is cleared for a later purge.
- The archive entry is annotated (`archive_reason`, `superseded_by`, `purge_ok`, `review`) and its summary prefixed (`[OBSOLETE → <superseded_by>]`). `rlm_search` lists archived matches by summary, so a reader who meets the archive is told it is obsolete and where the current state lives, instead of restoring it as if it were true.
- `purge_ok: false` adds the protected tag `keep`: that archive is never a purge candidate, whatever its age. A later run with `purge_ok: true` lifts the hold the tool placed (never a tag the chunk already had).
- Dry-run by default; `--apply` requires `--expect N` and aborts before the first write on any other count, on an unknown id, or on an ambiguous manifest. Re-running is idempotent. Nothing is ever deleted.
- `scripts/purge_reviewed.py` is the matching final step: it purges only archives carrying `purge_ok: true` (optionally of one review label), never a held or never-reviewed entry, dry-run by default, `--apply --expect N`. Purging stays a decision of the person who owns the memory.

### Fixed — The server accepts the chunk IDs it generates
- `rlm_chunk(ticket="#364")` builds the ID `…_#364_…`, but `validate_chunk_id()` rejected `#`: 29 real chunks could neither be peeked, archived nor restored — the tool answered "Invalid chunk ID format" to its own IDs. `#` is now allowed (it is harmless in a file name; slashes and `..` stay blocked), and a test pins the contract that any generated ID passes validation.

### Fixed — Retention no longer races with live sessions
- `archive_chunk()`, `restore_chunk()` and `purge_chunk()` rewrote `index.json`, `archive_index.json` and `purge_log.json` with a plain load → modify → save, while chunk creation and access bookkeeping rewrite the same index under `locked_json_update()`. With several sessions open, an archive could drop the chunk another session had just indexed, or have its own removal undone when that session wrote back what it had read — leaving an index entry with no file behind it. All three now go through `locked_json_update()`. A regression test holds the lock from a second writer and checks that the archive waits and that both changes survive.
- `rlm_remember()` and `rlm_forget()` had the same flaw on `session_memory.json`: load → append → save with no lock, so of two sessions saving an insight at the same moment, the slower one erased the other's. Both now run inside `locked_json_update()`, with the same kind of regression test.

### Changed — PreCompact hook v2
- **A manual `/compact` is now blocked (`exit 2`) when no `rlm_chunk()` happened in the last 15 minutes**, with the reason written to stderr so it reaches the model, not just the terminal. Chunk, then re-run `/compact` — it passes. The previous version emitted a `systemMessage` and `exit 0`: the reminder was displayed to the user but never reached Claude, and nothing was blocked, so the documented "auto-save before compact" did not exist.
- **Auto-compact is never blocked** — only warned. Blocking there would strand a session at context saturation with no way out.
- Neither branch ever creates a chunk on its own: chunking stays a deliberate act. Freshness is read from `chunk_state.json`, written by the `reset_chunk_counter.py` PostToolUse hook on every `rlm_chunk` call.
- New i18n keys in EN/FR/JA: `compact_blocked_header`, `compact_relaunch`, `compact_auto_warning`, `compact_age_never`.

### Added — Phase 10: Auto-memory/RLM Cohabitation
- New `memory_write_redirect.py` hook — detects writes to Claude Code's auto-memory directory and injects a reminder to use RLM instead
  - Fires on `Write` and `Edit` PostToolUse events
  - Only triggers when file path matches `/.claude/projects/*/memory/`
  - Silently passes through for all other file operations
- Japanese (`ja`) language support in `hooks/i18n.py` — all hook messages now available in EN/FR/JA
- New i18n keys: `memory_redirect_title`, `memory_redirect_body` (3 languages)
- Updated `templates/hooks_settings.json` with Write/Edit hook entries

### Why (Phase 10)
- With 1M context windows, `/compact` events are rare, reducing the PreCompact hook's effectiveness as an RLM trigger
- Claude Code's built-in auto-memory system (MEMORY.md files) intercepts "remember this" requests at system prompt level, bypassing RLM
- The new hook acts as a mechanical guardrail: even when auto-memory fires first, the hook redirects toward RLM for structured, searchable, cross-session storage
- Auto-memory remains useful as a quick-reference cheat sheet (patterns, ports, shortcuts)

## [0.10.4] - 2026-08-01

### Fixed
- **The wheel now ships the hooks and templates.** `pip install` installs the wheel, and the wheel contained neither — only the sdist did. So the auto-save-before-compact behaviour documented in the README did not exist for anyone who installed the recommended way; the feature was described, shipped in the repo, and absent from the package. They are force-included under `mcp_server/hooks` and `mcp_server/templates` rather than at the top level, since a bare `hooks` package in site-packages would squat a very common import name.

### Added
- `python -m mcp_server --hooks-dir` and `--templates-dir` print where the bundled files landed, which is otherwise unknowable for a pip install (no repo checkout). Falls back to the repo root for editable/source installs. `--help` documents both.
- Install instructions in the three READMEs now show how to point `settings.json` at the bundled hooks.

## [0.10.3] - 2026-08-01

### Fixed
- **A query-less `rlm_recall` now ranks by importance before recency.** It sorted by date alone, so with 34 `critical` insights and the default `limit=10`, the 24 oldest never surfaced — and the oldest are the most settled rules, exactly what a start-of-session recall exists to reload. `critical` now outranks `high` outranks `medium`, newest first within a level. An unrecognised importance sorts last instead of raising, so memories written by earlier versions still rank (`memory.py`).

### Added
- **Truncated recalls say so.** `recall()` returns `total_matching` alongside `count`, plus `truncated` and a message when results were cut, and `rlm_recall` prints a warning line above the list. A recall that looks complete but isn't is worse than an empty one: that is how two thirds of a six-month-old rule set stayed invisible.
- Tests: `tests/test_recall_ordering.py` — importance ranking, recency within a level, truncation reporting, no false alarm on complete results, relevance still winning when a query is given, unknown importance tolerated (+6 tests, 169 total).

## [0.10.2] - 2026-08-01

Five weeks of chunks had been stored without vectors, unnoticed. Everything
below comes from tracking that down: the failures were real, silent, and each
one is now either impossible or loud.

### Fixed
- **A transient embedding-provider failure no longer disables embeddings for the lifetime of the process.** `_get_cached_provider()` set its "already loaded" flag *before* attempting the load and cached `None` on any exception. Since loading may reach the HuggingFace Hub, one network hiccup meant every chunk created by that server process was stored without a vector — invisible to semantic search, with no error anywhere. A missing library is still cached (permanent), but any other failure is now retried after a cooldown, and the reason is retained (`get_provider_error()`) (`embeddings.py`).
- **Concurrent sessions no longer overwrite each other's chunks.** ID generation counted same-day chunks in the index, then the file and index entry were written in separate unlocked steps: two sessions computed the same sequence number and the later write replaced the earlier chunk. Reproduced: 18 parallel writes produced 16 chunks. Reservation, file write and index registration now happen under a single exclusive lock, and an ID already present on disk is never reused (`navigation.py`).
- **The file lock now actually excludes.** `locked_json_update()` deleted its `.lock` file on release, so the next writer created a *new inode* and locked that, while a waiter blocked on the old inode was released at the same moment — two writers inside the critical section at once. Surfaced by the concurrency test on Linux CI (15 files written, only 13 index entries). The lock file is now left in place (`fileutil.py`, `vecstore.py`).
- **Vector writes are no longer lost under concurrency.** `save()` wrote to a shared `embeddings_tmp.npz`: two writers clobbered each other's temp file, one crashing on rename after its vector was already gone. The temp name is now per-process, and `VectorStore.locked()` guards the read-modify-write cycle used by chunk creation and retention (`vecstore.py`).
- **Retention no longer archives chunks that search surfaces daily.** `access_count` drives archiving, but only `rlm_peek` ever incremented it — chunks returned by `rlm_search` and `rlm_grep` stayed at zero and became archive candidates. Every retrieval path now records access, batched into one locked update per query (`navigation.py`, `search.py`).
- **`scripts/reconcile_stores.py` honours `RLM_CONTEXT_DIR`.** It resolved `<repo>/context` unconditionally, so it silently targeted a stale directory for anyone who moved their data out of the checkout (the recommended setup).

### Added
- **Archived chunks are discoverable again.** Archiving removes a chunk from the active index *and* the vector store, leaving `rlm_peek(exact_id)` as the only way back — an ID that can no longer be searched for. `rlm_search` now also matches archived chunks by summary and tags, returning them under `archived_matches` (metadata only; nothing is decompressed) (`retention.search_archives`).
- **Degraded operation is now visible.** `rlm_status` reports missing vectors as a problem with its remedy instead of a bare ratio, names the reason when the provider is unavailable, and surfaces recent warnings. New `diagnostics.py` writes an append-only, size-capped `rlm.log`; the `except: pass` around embedding is now a logged warning, and chunks stored without a vector are flagged `embedded: false` in the index.
- Tests: `tests/test_resilience.py` — provider retry/permanence/cooldown, concurrent chunk writes, ID collision with on-disk files, access counting, archive discoverability (+8 tests, 163 total).

## [0.10.1] - 2026-06-26

### Fixed
- **`grep` now returns the most *recent* matches instead of the oldest.** It iterated chunks in index insertion order (oldest first) and stopped at `limit`, so any recurring term surfaced only its oldest occurrences and hid recent context. Chunks are now scanned newest-first (`navigation.py`).
- **The vector store now stays in sync with the active chunk set.** Archiving or purging a chunk now removes its embedding from `embeddings.npz`; restoring re-embeds it. Previously, archived/purged chunks left orphan vectors that polluted semantic search with empty-summary results and let the store grow unbounded (`retention.py`). All sync is best-effort and never blocks a retention operation.

### Added
- `scripts/reconcile_stores.py` — maintenance tool that reconciles the four stores (active chunks / archive / `index.json` / `embeddings.npz`) against the source of truth (the active `.md` files): drops orphan index entries and vectors, re-embeds missing chunks. Dry-run by default, timestamped backups, embedding-dimension guard.
- Tests: `tests/test_retention_semantic.py` (archive/purge/restore sync, fail-safe) and `tests/test_grep_ordering.py` (recency ordering) — +6 tests (155 total).

## [0.10.0] - 2026-02-04

### Added — Phase 9: Chunking Typé
- New `chunk_type` parameter in `rlm_chunk()` to categorize chunks at creation time
  - `snapshot` — Current state of a topic (will be replaced by next snapshot)
  - `session` — Work session log (default, backward compatible)
  - `debug` — Bug + fix for future reference
  - `insight` — Redirects to `rlm_remember()` with helpful message
- Validation: invalid `chunk_type` returns explicit error with valid types list
- `chunk_type` stored in YAML frontmatter header and `index.json` metadata
- Updated `rlm-chunk-triggers.md` with types documentation, examples, and anti-patterns
- 9 unit tests in `tests/test_chunk_type.py`

### Added — Phase 7.2: Entity Extraction
- `_extract_entities(content)` — regex-based extraction of files, versions, modules, tickets, functions
- `_entity_matches(chunk_info, entity)` — case-insensitive substring matching across all entity types
- `entity` param on `rlm_grep` — filter grep/fuzzy results by entity
- `entity` param on `rlm_search` — filter BM25 results by entity
- Auto-extraction at `rlm_chunk()` time — entities stored in index.json and YAML frontmatter
- Typed storage: `{"files": [...], "versions": [...], "modules": [...], "tickets": [...], "functions": [...]}`
- 36 tests in `tests/test_entity_extraction.py`
- Zero external dependencies (regex-only, MAGMA-inspired lightweight approach)

### Added — Phase 7.1: Temporal Filtering
- `date_from`/`date_to` params on `rlm_search` — filter BM25 results by date range
- `date_from`/`date_to` params on `rlm_grep` — filter regex/fuzzy results by date range
- `_parse_date_from_chunk()` helper — extracts date from `created_at` or chunk ID fallback
- `_chunk_in_date_range()` helper — lexicographic YYYY-MM-DD comparison (no datetime parsing)
- 28 tests in `tests/test_temporal_filter.py`
- Backward compatible: legacy format 1.0 chunks supported via ID-based date extraction

### Added — Phase 6: Security Hardening
- `mcp_server/tools/fileutil.py` — Shared security utilities (atomic writes, path traversal prevention, file locking)
- `SECURITY.md` — Vulnerability reporting policy
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

### Why (Phase 9)
- Chunks mixed permanent insights ("WeasyPrint CSS must be inline") with temporal snapshots ("catalogue has 8 pages")
- When topics evolve, old chunks become partially obsolete with no mechanism to manage this
- `chunk_type` forces separation at the source: permanent facts go to `rlm_remember()`, temporal state goes to typed chunks

### Backward compatibility
- **100% backward compatible** — default `chunk_type` is `session`
- Existing 128+ chunks without `chunk_type` continue to work (treated as `session`)
- Existing chunks without entities treated as `{}`
- No migration needed

## [0.9.3] - 2026-02-03

### Added — Unified search across insights and chunks
- `rlm_recall` now uses `tokenize_fr()` for multi-word tokenized search instead of exact substring matching
  - `rlm_recall("SIRET auto-entrepreneur")` now finds insights containing any of those tokens (previously: 0 results)
  - Results ranked by relevance (matching token ratio) then by date
  - Stopword-only queries fall back to raw lowercase match
- `rlm_search` BM25 index now includes insights from `session_memory.json` alongside chunks
  - Results include `type` field: `"chunk"` or `"insight"` for disambiguation
  - New `include_insights` parameter (default: `True`) to opt out of insight indexing

### Backward compatibility
- **100% backward compatible** — single-word queries behave identically (1 token = same substring match)
- Empty/null queries still return all insights sorted by date
- `rlm_search` without `include_insights` param defaults to `True` (no change for existing callers)

## [0.9.2] - 2026-02-02

### Fixed — Phase 8.1: Metadata-boosted search
- `search.py` `_extract_content()` now prepends summary, tags, project, domain to indexed text
  so BM25 matches on metadata keywords (e.g. query "BP" finds chunks tagged `domain: bp`)
- `navigation.py` `chunk()` enriches text with summary + tags before embedding
- `backfill_embeddings.py` applies the same metadata enrichment when re-embedding existing chunks
- 3 new tests in `test_semantic.py` (`TestMetadataBoostedSearch`)

### Added — Phase 8: Hybrid Semantic Search (COMPLETE)
- `embeddings.py` — Abstract `EmbeddingProvider` with two implementations:
  - `Model2VecProvider`: `minishlab/potion-multilingual-128M` (256 dim, fast)
  - `FastEmbedProvider`: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dim, accurate)
- `vecstore.py` — Numpy-based vector store (`.npz`), brute-force cosine similarity
- Hybrid fusion in `search.py` — BM25 scores normalized [0,1] + cosine scores, alpha=0.6
- Auto-embedding on `rlm_chunk()` — embedding generated at creation time (silent fail if unavailable)
- Semantic status in `rlm_status()` — shows provider name and embedded/total counts
- `scripts/backfill_embeddings.py` — retroactively embed existing chunks (`--dry-run` support)
- 18 tests in `tests/test_semantic.py` (VectorStore, normalization, fusion, graceful degradation)
- Provider selection via `RLM_EMBEDDING_PROVIDER` env var (default: `model2vec`)

### Changed
- `pyproject.toml` version bump to 0.9.2
- New optional dependencies: `semantic` (model2vec+numpy), `semantic-fastembed` (fastembed+numpy)
- `all` extra now includes `semantic`

### Backward compatibility
- **100% backward compatible** — without `model2vec` installed, search falls back to pure BM25
- No changes to existing tool signatures or behavior
- Existing chunks work unchanged; run `backfill_embeddings.py` to add vectors

### Install
```bash
# New install (with semantic)
pip install mcp-rlm-server[all]

# Add semantic to existing install
pip install mcp-rlm-server[semantic]

# Backfill existing chunks
python3 scripts/backfill_embeddings.py
```

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
- `domains.json.example` - Template with example domains
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
