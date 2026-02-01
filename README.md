# RLM - Infinite Memory for Claude Code

> Your Claude Code sessions forget everything after `/compact`. RLM fixes that.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP Server](https://img.shields.io/badge/MCP-Server-green.svg)](https://modelcontextprotocol.io)

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

### Via PyPI (recommended)

```bash
pip install mcp-rlm-server[all]
```

### Via Git

```bash
git clone https://github.com/EncrEor/rlm-claude.git
cd rlm-claude
./install.sh
```

Restart Claude Code. Done.

**Requirements**: Python 3.10+, Claude Code CLI

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

### Auto-Save Before Context Loss

RLM hooks into Claude Code's `/compact` event. Before your context is wiped, RLM **automatically saves a snapshot**. No action needed.

### Two Memory Systems

| System | What it stores | How to use |
|--------|---------------|------------|
| **Insights** | Key decisions, facts, preferences | `rlm_remember()` / `rlm_recall()` |
| **Chunks** | Full conversation segments | `rlm_chunk()` / `rlm_peek()` / `rlm_grep()` |

---

## Features

### Memory & Insights
- **`rlm_remember`** - Save decisions, facts, preferences with categories and importance levels
- **`rlm_recall`** - Search insights by keyword, category, or importance
- **`rlm_forget`** - Remove an insight
- **`rlm_status`** - System overview (insight count, chunk stats, access metrics)

### Conversation History
- **`rlm_chunk`** - Save conversation segments to persistent storage
- **`rlm_peek`** - Read a chunk (full or partial by line range)
- **`rlm_grep`** - Regex search across all chunks (+ fuzzy matching for typo tolerance)
- **`rlm_search`** - BM25 ranked search (FR/EN, accent-normalized)
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

### Auto-Chunking (Hooks)
- **PreCompact hook**: Automatic snapshot before `/compact` or auto-compact
- **PostToolUse hook**: Stats tracking after chunk operations
- User-driven philosophy: you decide when to chunk, the system saves before loss

### Sub-Agent Skills
- **`/rlm-analyze`** - Analyze a single chunk with an isolated sub-agent
- **`/rlm-parallel`** - Analyze multiple chunks in parallel (Map-Reduce pattern from MIT RLM paper)

---

## Comparison

| Feature | Raw Context | Letta/MemGPT | **RLM** |
|---------|-------------|--------------|---------|
| Persistent memory | No | Yes | **Yes** |
| Works with Claude Code | N/A | No (own runtime) | **Native MCP** |
| Auto-save before compact | No | N/A | **Yes (hooks)** |
| Search (regex + BM25) | No | Basic | **Yes** |
| Fuzzy search (typo-tolerant) | No | No | **Yes** |
| Multi-project support | No | No | **Yes** |
| Smart retention (archive/purge) | No | Basic | **Yes** |
| Sub-agent analysis | No | No | **Yes** |
| Zero config install | N/A | Complex | **3 lines** |
| FR/EN support | N/A | EN only | **Both** |
| Cost | Free | Self-hosted | **Free** |

---

## Usage Examples

### Save and recall insights

```python
# Save a key decision
rlm_remember("Backend is the source of truth for all data",
             category="decision", importance="high",
             tags="architecture,backend")

# Find it later
rlm_recall(query="source of truth")
rlm_recall(category="decision")
```

### Manage conversation history

```python
# Save important discussion
rlm_chunk("Discussion about API redesign... [long content]",
          summary="API v2 architecture decisions",
          tags="api,architecture")

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
│       └── fileutil.py        # Safe I/O (atomic writes, path validation, locking)
│
├── hooks/                     # Claude Code hooks
│   ├── pre_compact_chunk.py   # Auto-save before /compact (PreCompact hook)
│   └── reset_chunk_counter.py # Stats reset after chunk (PostToolUse hook)
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
    "PostToolUse": [{
      "matcher": "mcp__rlm-server__rlm_chunk",
      "hooks": [{ "type": "command", "command": "python3 ~/.claude/rlm/hooks/reset_chunk_counter.py" }]
    }]
  }
}
```

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

If you prefer to install manually:

```bash
pip install -e ".[all]"
claude mcp add rlm-server -- python3 -m mcp_server
mkdir -p ~/.claude/rlm/hooks
cp hooks/*.py ~/.claude/rlm/hooks/
chmod +x ~/.claude/rlm/hooks/*.py
mkdir -p ~/.claude/skills/rlm-analyze ~/.claude/skills/rlm-parallel
cp templates/skills/rlm-analyze/skill.md ~/.claude/skills/rlm-analyze/
cp templates/skills/rlm-parallel/skill.md ~/.claude/skills/rlm-parallel/
```

Then configure hooks in `~/.claude/settings.json` (see above).

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

---

## Inspired By

- [RLM Paper (MIT CSAIL)](https://arxiv.org/abs/2512.24601) - Zhang et al., Dec 2025 - "Recursive Language Models"
- [Letta/MemGPT](https://github.com/letta-ai/letta) - AI agent memory framework
- [MCP Specification](https://modelcontextprotocol.io/specification)
- [Claude Code Hooks](https://docs.anthropic.com/claude-code/hooks)

---

## Authors

- Ahmed MAKNI ([@EncrEor](https://github.com/EncrEor))
- Claude Opus 4.5 (joint R&D)

## License

MIT License - see [LICENSE](LICENSE)
