[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/encreor-rlm-claude-badge.png)](https://mseep.ai/app/encreor-rlm-claude)

# RLM - Infinite Memory for Claude Code

> Your Claude Code sessions forget everything after `/compact`. RLM fixes that.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP Server](https://img.shields.io/badge/MCP-Server-green.svg)](https://modelcontextprotocol.io)
[![CI](https://github.com/EncrEor/rlm-claude/actions/workflows/ci.yml/badge.svg)](https://github.com/EncrEor/rlm-claude/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/EncrEor/rlm-claude/branch/main/graph/badge.svg)](https://codecov.io/gh/EncrEor/rlm-claude)
[![PyPI version](https://img.shields.io/pypi/v/mcp-rlm-server.svg)](https://pypi.org/project/mcp-rlm-server/)

[Fran&ccedil;ais](README.fr.md) | English | [日本語](README.ja.md)

---

## The Problem

Claude Code has a **context window limit**. When it fills up:
- `/compact` wipes your conversation history
- Previous decisions, insights, and context are **lost**
- You repeat yourself. Claude makes the same mistakes. Productivity drops.

## The Solution

**RLM** is an MCP server that gives Claude Code **persistent memory across sessions**:

```
You: "Remember that the client prefers 500ml bottles"
     → Saved. Forever. Across all sessions.

You: "What did we decide about the API architecture?"
     → Claude searches its memory and finds the answer.
```

**3 lines to install. 14 tools. Zero configuration.**

---

## Quick Install

> **Requirements**: Python 3.10+ ([download](https://www.python.org/downloads/)), Claude Code CLI

### Via PyPI (recommended)

```bash
pip install mcp-rlm-server[all]
```

The hooks and templates ship inside the package. Since a pip install gives you
no repo checkout, ask the package where they landed:

```bash
python -m mcp_server --hooks-dir       # e.g. .../site-packages/mcp_server/hooks
python -m mcp_server --templates-dir
```

Point your `~/.claude/settings.json` hook commands at that path (see
[Hook Configuration](#hook-configuration)), or copy them to `~/.claude/rlm/hooks/`.

### Via uv (fast, no global pollution)

```bash
uv tool install mcp-rlm-server[all] --python 3.12
```

### Via Git (full install with hooks)

```bash
git clone https://github.com/EncrEor/rlm-claude.git
cd rlm-claude
./install.sh
```

### Via Docker

```bash
docker build -t rlm-server .
# Or pull from registry (when published):
# docker pull ghcr.io/encreor/rlm-claude
```

Then configure Claude Code to use the Docker container (see [Docker setup](#docker-setup) below).

Restart Claude Code. Done.

### Upgrading from v0.9.0 or earlier

v0.9.1 moved the source code from `mcp_server/` to `src/mcp_server/` (PyPA best practice). A compatibility symlink is included so existing installations keep working, but we recommend re-running the installer:

```bash
cd rlm-claude
git pull
./install.sh          # reconfigures the MCP server path
```

Your data (`~/.claude/rlm/`) is untouched. Only the server path is updated.

---

## How It Works

```
                    ┌─────────────────────────┐
                    │     Claude Code CLI      │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │    RLM MCP Server        │
                    │    (14 tools)            │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                   │
    ┌─────────▼────────┐ ┌──────▼──────┐ ┌──────────▼─────────┐
    │    Insights       │ │   Chunks    │ │    Retention        │
    │ (key decisions,   │ │ (full conv  │ │ (auto-archive,      │
    │  facts, prefs)    │ │  history)   │ │  restore, purge)    │
    └──────────────────┘ └─────────────┘ └────────────────────┘
```

### Nothing Lost Silently

Chunking is a deliberate act: RLM never writes a chunk on its own. What it does is make sure an unsaved session cannot go unnoticed:

- **Before `/compact`**: a manual `/compact` is blocked when nothing was chunked in the last 15 minutes. Chunk, re-run it, it passes. Auto-compact is never blocked (that would strand a full session), only warned.
- **After a session**: a hook traces what each session touched (file paths and allow-listed program names, never command lines). At the next start, a session that changed things and ended without a chunk is listed with its transcript, so it can still be recovered. Crashes and closed terminals are covered too: it is the missing chunk that is detected, not a clean exit.

### Two Memory Systems

| System | What it stores | How to use |
|--------|---------------|------------|
| **Insights** | Key decisions, facts, preferences | `rlm_remember()` / `rlm_recall()` |
| **Chunks** | Full conversation segments | `rlm_chunk()` / `rlm_peek()` / `rlm_grep()` |

---

## Features

### Memory & Insights
- **`rlm_remember`** - Save decisions, facts, preferences with categories and importance levels
- **`rlm_recall`** - Search insights by keyword (multi-word tokenized), category, or importance
  - Without a query, results rank by **importance first**, then recency — a settled `critical` rule outranks today's `medium` note
  - **Truncated results say so**: the reply reports how many matched, so a capped recall can't pass for a complete one
- **`rlm_forget`** - Remove an insight
- **`rlm_status`** - System overview (insight count, chunk stats, access metrics)

### Conversation History
- **`rlm_chunk`** - Save conversation segments with typed categorization (`snapshot`, `session`, `debug`; `insight` redirects to `rlm_remember`)
- **`rlm_peek`** - Read a chunk (full or partial by line range)
- **`rlm_grep`** - Regex search across all chunks (+ fuzzy matching for typo tolerance)
- **`rlm_search`** - Hybrid search: BM25 + semantic cosine similarity (FR/EN, accent-normalized, chunks + insights)
- **`rlm_list_chunks`** - List all chunks with metadata

### Multi-Project Organization
- **`rlm_sessions`** - Browse sessions by project or domain
- **`rlm_domains`** - List available domains for categorization
- Auto-detection of project from git or working directory
- Cross-project filtering on all search tools

### Smart Retention
- **`rlm_retention_preview`** - Preview what would be archived (dry-run)
- **`rlm_retention_run`** - Archive old unused chunks, purge ancient ones
- **`rlm_restore`** - Bring back archived chunks
- 3-zone lifecycle: **Active** &rarr; **Archive** (.gz) &rarr; **Purge**
- Immunity system: critical tags, frequent access, and keywords protect chunks
- **Archiving is a demotion, not a deletion**: archived chunks leave the active index, but `rlm_search` still matches them by summary and tags and returns them under `archived_matches` — `rlm_peek(chunk_id)` restores one in full
- **Every retrieval counts as an access** (peek, grep and search alike), so a chunk your searches keep surfacing reaches immunity instead of being archived as idle

### Safety Nets & Memory Routing (Hooks)
- **PreCompact hook**: blocks a manual `/compact` with no chunk in the last 15 minutes; warns (never blocks) on auto-compact. It never creates a chunk itself
- **PostToolUse hook (rlm_chunk)**: records when the last chunk happened (read by the PreCompact hook) and ties the chunk to its session (`session_id` and `transcript_path` in the index)
- **PostToolUse hook (Edit/Write/Bash)** — *session trace*: appends to `~/.claude/rlm/sessions/<session_id>.jsonl` the paths a session edits and the basenames of allow-listed programs it runs. Never a command line: it can carry passwords
- **SessionStart hook** — *unsaved sessions*: lists past sessions that changed things and ended with neither a chunk nor an acknowledgement, with their transcript path. Acknowledge one with `python3 ~/.claude/rlm/hooks/session_orphans.py --ack <session_id> "reason"`
- **PostToolUse hook (Write/Edit)**: Detects writes to Claude Code's auto-memory and nudges toward RLM for decisions, insights, and session logs
- User-driven philosophy: you decide when to chunk, the system saves before loss

### Semantic Search (optional)
- **Hybrid BM25 + cosine** - Combines keyword matching with vector similarity for better relevance
- **Auto-embedding** - New chunks are automatically embedded at creation time
- **Two providers** - Model2Vec (fast, 256d) or FastEmbed (accurate, 384d)
- **Graceful degradation** - Falls back to pure BM25 when semantic deps are not installed

#### Provider comparison (benchmark on 108 chunks)

| | Model2Vec (default) | FastEmbed |
|---|---|---|
| **Model** | `potion-multilingual-128M` | `paraphrase-multilingual-MiniLM-L12-v2` |
| **Dimensions** | 256 | 384 |
| **Embed 108 chunks** | 0.06s | 1.30s |
| **Search latency** | 0.1ms/query | 1.5ms/query |
| **Memory** | 0.1 MB | 0.3 MB |
| **Disk (model)** | ~35 MB | ~230 MB |
| **Semantic quality** | Good (keyword-biased) | Better (true semantic) |
| **Speed** | **21x faster** | Baseline |

Top-5 result overlap between providers: ~1.6/5 (different results in 7/8 queries). FastEmbed captures more semantic meaning while Model2Vec leans toward keyword similarity. The hybrid BM25 + cosine fusion compensates for both weaknesses.

**Recommendation**: Start with Model2Vec (default). Switch to FastEmbed only if you need better semantic accuracy and can afford the slower startup.

```bash
# Model2Vec (default) — fast, ~35 MB
pip install mcp-rlm-server[semantic]

# FastEmbed — more accurate, ~230 MB, slower
pip install mcp-rlm-server[semantic-fastembed]
export RLM_EMBEDDING_PROVIDER=fastembed

# Compare both providers on your data
python3 scripts/benchmark_providers.py

# Backfill existing chunks (run once after install)
python3 scripts/backfill_embeddings.py
```

#### Checking embedding coverage

Embedding is best-effort: a chunk is always written, even when the provider is
unavailable. That chunk is then invisible to semantic search until it gets a
vector, so the gap is reported rather than left to be discovered later.

`rlm_status` warns whenever coverage is incomplete, names the reason when the
provider failed to load, and echoes the most recent entries of `rlm.log` (an
append-only log in your context directory). To heal a gap:

```bash
# Dry-run first: lists chunks that would be embedded
python3 scripts/reconcile_stores.py

# Re-embed everything missing, with timestamped backups
python3 scripts/reconcile_stores.py --apply
```

Both honour `RLM_CONTEXT_DIR`. Use the same `RLM_EMBEDDING_PROVIDER` as your
server — the script refuses to mix vector dimensions.

### Sub-Agent Skills
- **`/rlm-analyze`** - Analyze a single chunk with an isolated sub-agent
- **`/rlm-parallel`** - Analyze multiple chunks in parallel (Map-Reduce pattern from MIT RLM paper)

---

## Comparison

| Feature | Raw Context | Letta/MemGPT | claude-mem | **RLM** |
|---------|-------------|--------------|------------|---------|
| Persistent memory | No | Yes | Yes | **Yes** |
| Works with Claude Code | N/A | No (own runtime) | Plugin (hooks + worker) | **Native MCP + hooks** |
| What gets saved | Nothing | Agent-managed | Every tool call, compressed by an LLM | **What you chunk; unsaved sessions are flagged** |
| Background LLM calls | No | Yes | Yes (per observation) | **None** |
| Guard before compact | No | N/A | N/A (captures continuously) | **Yes (manual `/compact` blocked without a chunk)** |
| Search (regex + BM25 + semantic) | No | Basic | Full-text + optional vector | **Yes** |
| Fuzzy search (typo-tolerant) | No | No | — | **Yes** |
| Multi-project support | No | No | Yes | **Yes** |
| Smart retention (archive/purge) | No | Basic | — | **Yes** |
| Sub-agent analysis | No | No | — | **Yes** |
| Zero config install | N/A | Complex | One command | **3 lines** |
| FR/EN/JA support | N/A | EN only | Multi-language modes | **3 languages** |
| Cost | Free | Self-hosted | LLM usage or hosted plan | **Free** |

— = not assessed. The claude-mem column reflects its documentation as of October 2026.

claude-mem and RLM make opposite bets. claude-mem records everything automatically and spends model calls to compress it; RLM stores only what you decide to keep, at no model cost, and makes sure a session you forgot to save is pointed out to you instead of silently lost.

---

## Usage Examples

### Session startup (recommended)

```python
# Load universal rules (apply regardless of topic).
# Pass a limit above your critical count — the default is 10, and a recall
# that returns 10 of 34 rules looks exactly like a complete one.
rlm_recall(importance="critical", limit=50)

# Load context for current topic
rlm_recall(query="deployment")

# Check memory status
rlm_status()
```

### Save and recall insights

```python
# Save a universal rule (loaded every session)
rlm_remember("Always deploy LOCAL → VPS, never direct",
             category="decision", importance="critical",
             tags="deploy,workflow")

# Save a topic-specific insight
rlm_remember("WeasyPrint requires inline CSS for PDF rendering",
             category="finding", importance="high",
             tags="weasyprint,pdf")

# Find insights later
rlm_recall(query="source of truth")
rlm_recall(category="decision")
rlm_recall(importance="critical", limit=50)   # all universal rules (mind the default limit of 10)
```

### Importance levels

| Level | When to use | Loaded |
|-------|------------|--------|
| `critical` | Universal rules (apply regardless of topic) | Every session |
| `high` | Topic-specific rules | When working on that topic |
| `medium` | Useful info, not blocking | On explicit search |

**Test**: "Does this rule apply even when working on a completely different topic?" If yes → `critical`.

### Manage conversation history

```python
# Save important discussion (typed)
rlm_chunk("Discussion about API redesign... [long content]",
          summary="API v2 architecture decisions",
          tags="api,architecture",
          chunk_type="session")        # or "snapshot", "debug"

# Search across all history
rlm_search("API architecture decisions")      # BM25 ranked
rlm_grep("authentication", fuzzy=True)         # Typo-tolerant

# Read a specific chunk
rlm_peek("2026-01-18_MyProject_001")
```

### Multi-project organization

```python
# Filter by project
rlm_search("deployment issues", project="MyApp")
rlm_grep("database", project="MyApp", domain="infra")

# Browse sessions
rlm_sessions(project="MyApp")
```

---

## Project Structure

```
rlm-claude/
├── src/mcp_server/
│   ├── server.py              # MCP server (14 tools)
│   └── tools/
│       ├── memory.py          # Insights (remember/recall/forget)
│       ├── navigation.py      # Chunks (chunk/peek/grep/list)
│       ├── search.py          # BM25 search engine
│       ├── tokenizer_fr.py    # FR/EN tokenization
│       ├── sessions.py        # Multi-session management
│       ├── retention.py       # Archive/restore/purge lifecycle
│       ├── embeddings.py      # Embedding providers (Model2Vec, FastEmbed)
│       ├── vecstore.py        # Vector store (.npz) for semantic search
│       ├── diagnostics.py     # Warning log (rlm.log) — degraded ops stay visible
│       └── fileutil.py        # Safe I/O (atomic writes, path validation, locking)
│
├── hooks/                     # Claude Code hooks
│   ├── i18n.py                # Translations (EN/FR/JA) for hook messages
│   ├── pre_compact_chunk.py   # Guard before /compact (PreCompact hook)
│   ├── memory_write_redirect.py # Redirect auto-memory writes to RLM (PostToolUse hook)
│   ├── reset_chunk_counter.py # Last-chunk time + chunk ↔ session link (PostToolUse hook)
│   ├── session_trace.py       # What a session touches, metadata only (PostToolUse hook)
│   ├── session_orphans.py     # Unsaved past sessions at startup, --ack (SessionStart hook)
│   └── session_common.py      # Shared paths, config and lock-safe index update
│
├── templates/
│   ├── hooks_settings.json    # Hook config template
│   ├── CLAUDE_RLM_SNIPPET.md  # CLAUDE.md instructions
│   └── skills/                # Sub-agent skills
│
├── context/                   # Storage (created at install, git-ignored)
│   ├── session_memory.json    # Insights
│   ├── index.json             # Chunk index
│   ├── chunks/                # Conversation history
│   ├── archive/               # Compressed archives (.gz)
│   ├── embeddings.npz         # Semantic vectors (Phase 8)
│   └── sessions.json          # Session index
│
├── install.sh                 # One-command installer
└── README.md
```

---

## Configuration

### Hook Configuration

The installer automatically configures hooks in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreCompact": [
      {
        "matcher": "manual",
        "hooks": [{ "type": "command", "command": "python3 ~/.claude/rlm/hooks/pre_compact_chunk.py" }]
      },
      {
        "matcher": "auto",
        "hooks": [{ "type": "command", "command": "python3 ~/.claude/rlm/hooks/pre_compact_chunk.py" }]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "mcp__rlm-server__rlm_chunk",
        "hooks": [{ "type": "command", "command": "python3 ~/.claude/rlm/hooks/reset_chunk_counter.py" }]
      },
      {
        "matcher": "Write",
        "hooks": [{ "type": "command", "command": "python3 ~/.claude/rlm/hooks/memory_write_redirect.py" }]
      },
      {
        "matcher": "Edit",
        "hooks": [{ "type": "command", "command": "python3 ~/.claude/rlm/hooks/memory_write_redirect.py" }]
      },
      {
        "matcher": "Edit|Write|MultiEdit|NotebookEdit|Bash",
        "hooks": [{ "type": "command", "command": "python3 ~/.claude/rlm/hooks/session_trace.py" }]
      }
    ],
    "SessionStart": [{
      "matcher": "",
      "hooks": [{ "type": "command", "command": "python3 ~/.claude/rlm/hooks/session_orphans.py" }]
    }]
  }
}
```

The same block lives in `templates/hooks_settings.json`, which the installer reads.

### Session Trace

Optional `~/.claude/rlm/session_trace.json` (every key optional):

```json
{
  "notable_commands": ["ssh", "scp", "rsync", "psql", "kubectl", "terraform", "ansible-playbook", "deploy.sh"],
  "min_edits": 5,
  "idle_hours": 2,
  "retention_days": 30,
  "max_listed": 5
}
```

- `notable_commands`: programs whose **basename** is recorded when a session runs them (arguments never are). One notable run is enough for a session to count.
- `min_edits`: a session with more Edit/Write than this counts.
- `idle_hours`: a session idle for less than this is presumed still running (parallel sessions are left alone).
- `retention_days`: traces older than this are deleted. Keep it aligned with Claude Code's `cleanupPeriodDays` (30 by default): past it the transcript is gone and the session cannot be recovered anyway.

### Language

Hook messages default to English. Set `RLM_LANG=fr` for French or `RLM_LANG=ja` for Japanese:

```bash
# Option 1: Set globally in your shell profile (~/.zshrc, ~/.bashrc)
export RLM_LANG=fr   # or ja

# Option 2: Set per-hook in ~/.claude/settings.json
# Replace the command with:
"command": "RLM_LANG=fr python3 ~/.claude/rlm/hooks/pre_compact_chunk.py"
```

Supported languages: `en` (default), `fr`, `ja`.

### Storage Directory

RLM stores data in `~/.claude/rlm/context/` by default. Override with `RLM_CONTEXT_DIR`:

```bash
export RLM_CONTEXT_DIR=/path/to/custom/storage
```

This is particularly useful for Docker deployments (see below).

### Custom Domains

Organize chunks by topic with custom domains:

```json
{
  "domains": {
    "my_project": {
      "description": "Domains for my project",
      "list": ["feature", "bugfix", "infra", "docs"]
    }
  }
}
```

Edit `context/domains.json` after installation.

---

## Manual Installation

### Via pip

```bash
pip install -e ".[all]"
claude mcp add rlm-server -- python3 -m mcp_server
```

### Via uv

```bash
uv tool install mcp-rlm-server[all] --python 3.12
claude mcp add rlm-server -- ~/.local/bin/mcp-rlm-server
```

### Hook Setup (required for pip and uv installs)

The `./install.sh` script handles this automatically. For manual installs:

```bash
# Get hook scripts from the repo
git clone https://github.com/EncrEor/rlm-claude.git /tmp/rlm-setup

# Install hooks and i18n
mkdir -p ~/.claude/rlm/hooks
cp /tmp/rlm-setup/hooks/*.py ~/.claude/rlm/hooks/
chmod +x ~/.claude/rlm/hooks/*.py

# Install skills (optional)
mkdir -p ~/.claude/skills/rlm-analyze ~/.claude/skills/rlm-parallel
cp /tmp/rlm-setup/templates/skills/rlm-analyze/skill.md ~/.claude/skills/rlm-analyze/
cp /tmp/rlm-setup/templates/skills/rlm-parallel/skill.md ~/.claude/skills/rlm-parallel/

# Cleanup
rm -rf /tmp/rlm-setup
```

Then configure hooks in `~/.claude/settings.json` (see [Hook Configuration](#hook-configuration) above).

### Docker Setup

Build the image:

```bash
git clone https://github.com/EncrEor/rlm-claude.git
cd rlm-claude
docker build -t rlm-server .
```

Configure Claude Code MCP to use Docker:

```bash
claude mcp add rlm-server -- docker run -i --rm -v ~/.claude/rlm/context:/data rlm-server
```

Or manually in `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "rlm-server": {
      "type": "stdio",
      "command": "docker",
      "args": ["run", "-i", "--rm", "-v", "~/.claude/rlm/context:/data", "rlm-server"]
    }
  }
}
```

The Docker image uses `RLM_CONTEXT_DIR=/data` internally, and the volume mount maps it to your local storage.

## Uninstall

```bash
./uninstall.sh              # Interactive (choose to keep or delete data)
./uninstall.sh --keep-data  # Remove RLM config, keep your chunks/insights
./uninstall.sh --all        # Remove everything
./uninstall.sh --dry-run    # Preview what would be removed
```

---

## Security

RLM includes built-in protections for safe operation:

- **Path traversal prevention** - Chunk IDs are validated against a strict allowlist (`[a-zA-Z0-9_.-&]`), and resolved paths are verified to stay within the storage directory
- **Atomic writes** - All JSON and chunk files are written using write-to-temp-then-rename, preventing corruption from interrupted writes or crashes
- **File locking** - Concurrent read-modify-write operations on shared indexes use `fcntl.flock` exclusive locks
- **Content size limits** - Chunks are limited to 2 MB, and gzip decompression (archive restore) is capped at 10 MB to prevent resource exhaustion
- **SHA-256 hashing** - Content deduplication uses SHA-256 (not MD5)

All I/O safety primitives are centralized in `mcp_server/tools/fileutil.py`.

---

## Troubleshooting

### "MCP server not found"

```bash
claude mcp list                    # Check servers
claude mcp remove rlm-server       # Remove if exists
claude mcp add rlm-server -- python3 -m mcp_server
```

### "Hooks not working"

```bash
cat ~/.claude/settings.json | grep -A 10 "PreCompact"  # Verify hooks config
ls ~/.claude/rlm/hooks/                                  # Check installed hooks
```

---

## Roadmap

- [x] **Phase 1**: Memory tools (remember/recall/forget/status)
- [x] **Phase 2**: Navigation tools (chunk/peek/grep/list)
- [x] **Phase 3**: Auto-chunking + sub-agent skills
- [x] **Phase 4**: Production (auto-summary, dedup, access tracking)
- [x] **Phase 5**: Advanced (BM25 search, fuzzy grep, multi-sessions, retention)
- [x] **Phase 6**: Production-ready (tests, CI/CD, PyPI)
- [x] **Phase 7**: MAGMA-inspired (temporal filtering, entity extraction)
- [x] **Phase 8**: Hybrid semantic search (BM25 + cosine, Model2Vec)
- [x] **Phase 9**: Typed chunking — `chunk_type` parameter (snapshot/session/debug/insight redirect)
- [x] **Phase 10**: Auto-memory/RLM cohabitation — Write/Edit hook redirects auto-memory to RLM + Japanese i18n
- [x] **Phase 11**: Safety nets — PreCompact guard v2, recall ranked by importance with truncation reported, session trace + unsaved-session report

---

## Inspired By

### Research Papers
- [RLM Paper (MIT CSAIL)](https://arxiv.org/abs/2512.24601) - Zhang et al., Dec 2025 - "Recursive Language Models" — foundational architecture (chunk/peek/grep, sub-agent analysis)
- [MAGMA (arXiv:2601.03236)](https://arxiv.org/abs/2601.03236) - Jan 2026 - "Memory-Augmented Generation with Memory Agents" — temporal filtering, entity extraction (Phase 7)

### Libraries & Tools
- [Model2Vec](https://github.com/MinishLab/model2vec) - Static word embeddings for fast semantic search (Phase 8)
- [BM25S](https://github.com/xhluca/bm25s) - Fast BM25 implementation in pure Python (Phase 5)
- [FastEmbed](https://github.com/qdrant/fastembed) - ONNX-based embeddings, optional provider (Phase 8)
- [Letta/MemGPT](https://github.com/letta-ai/letta) - AI agent memory framework — early inspiration

### Standards & Platform
- [MCP Specification](https://modelcontextprotocol.io/specification) - Model Context Protocol
- [Claude Code Hooks](https://docs.anthropic.com/claude-code/hooks) - PreCompact / PostToolUse hooks

---

## Contributing

### Translations

The repository is maintained in English. User-facing files can be translated to your language:

| File | Purpose | Translations welcome |
|------|---------|---------------------|
| `README.md` | Main documentation | `README.xx.md` (e.g., `README.fr.md`, `README.ja.md`) |
| `templates/CLAUDE_RLM_SNIPPET.md` | CLAUDE.md instructions | `CLAUDE_RLM_SNIPPET.xx.md` |

Code, comments, and commit messages stay in English.

---

## Authors

- Ahmed MAKNI ([@EncrEor](https://github.com/EncrEor))
- Claude Opus 4.6 (joint R&D)

## License

MIT License - see [LICENSE](LICENSE)
