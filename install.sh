#!/bin/bash
# =============================================================================
# RLM Installation Script
# Infinite memory for Claude Code
# =============================================================================
#
# Usage:
#   ./install.sh                    # Auto-detect CLAUDE.md
#   ./install.sh --claude-md PATH   # Specify CLAUDE.md path
#   ./install.sh --no-claude-md     # Skip CLAUDE.md modification
#
# =============================================================================

set -e

echo ""
echo "=============================================="
echo "  RLM - Infinite Memory for Claude Code"
echo "=============================================="
echo ""

# =============================================================================
# Check Python version (3.10+ required)
# =============================================================================
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)
if [ -z "$PYTHON_VERSION" ]; then
    echo "ERROR: python3 not found."
    echo "  Install Python 3.10+ via one of:"
    echo "    brew install python@3.12"
    echo "    uv python install 3.12"
    echo "    https://www.python.org/downloads/"
    exit 1
fi
PY_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
    echo "ERROR: Python $PYTHON_VERSION found but RLM requires 3.10+."
    echo "  Install a newer version via one of:"
    echo "    brew install python@3.12"
    echo "    uv python install 3.12"
    echo "    https://www.python.org/downloads/"
    exit 1
fi
echo "  Python $PYTHON_VERSION OK"
echo ""

# =============================================================================
# Parse arguments
# =============================================================================
CLAUDE_MD_PATH=""
SKIP_CLAUDE_MD=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --claude-md)
            CLAUDE_MD_PATH="$2"
            shift 2
            ;;
        --no-claude-md)
            SKIP_CLAUDE_MD=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: ./install.sh [--claude-md PATH] [--no-claude-md]"
            exit 1
            ;;
    esac
done

# =============================================================================
# Paths
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RLM_DIR="$HOME/.claude/rlm"
SKILLS_DIR="$HOME/.claude/skills"
SETTINGS_FILE="$HOME/.claude/settings.json"

# =============================================================================
# Function: Find CLAUDE.md
# =============================================================================
find_claude_md() {
    local found_files=()

    # Check common locations
    local locations=(
        "$SCRIPT_DIR/../CLAUDE.md"           # Parent of RLM directory
        "$SCRIPT_DIR/../../CLAUDE.md"        # Two levels up
        "$HOME/.claude/CLAUDE.md"            # User's .claude directory
        "$(pwd)/CLAUDE.md"                   # Current directory
        "$SCRIPT_DIR/CLAUDE.md"              # Same directory as script
    )

    for loc in "${locations[@]}"; do
        if [ -f "$loc" ]; then
            # Resolve to absolute path
            local abs_path="$(cd "$(dirname "$loc")" && pwd)/$(basename "$loc")"
            # Avoid duplicates
            local is_dup=false
            for f in "${found_files[@]}"; do
                if [ "$f" = "$abs_path" ]; then
                    is_dup=true
                    break
                fi
            done
            if [ "$is_dup" = false ]; then
                found_files+=("$abs_path")
            fi
        fi
    done

    # Return results
    if [ ${#found_files[@]} -eq 0 ]; then
        echo ""
    elif [ ${#found_files[@]} -eq 1 ]; then
        echo "${found_files[0]}"
    else
        # Multiple found - list them
        echo "MULTIPLE:${found_files[*]}"
    fi
}

# =============================================================================
# 1. Create directories
# =============================================================================
echo "[1/7] Creating directories..."
mkdir -p "$RLM_DIR/hooks"
mkdir -p "$RLM_DIR/context/chunks"
mkdir -p "$SKILLS_DIR/rlm-analyze"
mkdir -p "$SKILLS_DIR/rlm-parallel"
echo "  OK - Directories created"

# =============================================================================
# 2. Copy hook scripts
# =============================================================================
echo "[2/7] Installing hooks..."
cp "$SCRIPT_DIR/hooks/pre_compact_chunk.py" "$RLM_DIR/hooks/"
cp "$SCRIPT_DIR/hooks/reset_chunk_counter.py" "$RLM_DIR/hooks/"
cp "$SCRIPT_DIR/hooks/i18n.py" "$RLM_DIR/hooks/"
chmod +x "$RLM_DIR/hooks/"*.py
echo "  OK - Hooks installed"

# =============================================================================
# 3. Copy skill
# =============================================================================
echo "[3/7] Installing RLM skills..."
cp "$SCRIPT_DIR/templates/skills/rlm-analyze/skill.md" "$SKILLS_DIR/rlm-analyze/"
cp "$SCRIPT_DIR/templates/skills/rlm-parallel/skill.md" "$SKILLS_DIR/rlm-parallel/"
echo "  OK - Skills /rlm-analyze and /rlm-parallel installed"

# =============================================================================
# 4. Configure MCP server
# =============================================================================
echo "[4/7] Configuring MCP server..."
if command -v claude &> /dev/null; then
    # Remove existing if any
    claude mcp remove rlm-server 2>/dev/null || true
    # Detect: pip install vs git clone
    if python3 -c "import mcp_server" 2>/dev/null; then
        MCP_CMD="python3 -m mcp_server"
    else
        MCP_CMD="python3 $SCRIPT_DIR/src/mcp_server/server.py"
    fi
    claude mcp add rlm-server -s user -- $MCP_CMD
    echo "  OK - MCP server configured ($MCP_CMD)"
else
    echo "  SKIP - Claude CLI not found (configure manually)"
fi

# =============================================================================
# 5. Initialize context files
# =============================================================================
echo "[5/7] Initializing context..."
if [ ! -f "$RLM_DIR/context/session_memory.json" ]; then
    cat > "$RLM_DIR/context/session_memory.json" << 'EOF'
{
  "version": "1.0.0",
  "insights": [],
  "created_at": null,
  "last_updated": null
}
EOF
fi
if [ ! -f "$RLM_DIR/context/index.json" ]; then
    cat > "$RLM_DIR/context/index.json" << 'EOF'
{
  "version": "2.0.0",
  "chunks": [],
  "total_tokens_estimate": 0
}
EOF
fi

# Initialize chunk state
cat > "$RLM_DIR/chunk_state.json" << 'EOF'
{
  "turns": 0,
  "last_chunk": 0
}
EOF
echo "  OK - Context initialized"

# =============================================================================
# 6. Merge hooks into settings.json
# =============================================================================
echo "[6/7] Configuring hooks in settings.json..."

python3 << 'PYTHON_SCRIPT'
import json
from pathlib import Path

settings_file = Path.home() / ".claude" / "settings.json"

# RLM hooks to add (matches templates/hooks_settings.json)
rlm_hooks = {
    "PreCompact": [
        {
            "matcher": "manual",
            "hooks": [{
                "type": "command",
                "command": "python3 ~/.claude/rlm/hooks/pre_compact_chunk.py"
            }]
        },
        {
            "matcher": "auto",
            "hooks": [{
                "type": "command",
                "command": "python3 ~/.claude/rlm/hooks/pre_compact_chunk.py"
            }]
        }
    ],
    "PostToolUse": [{
        "matcher": "mcp__rlm-server__rlm_chunk",
        "hooks": [{
            "type": "command",
            "command": "python3 ~/.claude/rlm/hooks/reset_chunk_counter.py"
        }]
    }]
}

# Load or create settings
if settings_file.exists():
    try:
        with open(settings_file) as f:
            settings = json.load(f)
    except:
        settings = {}
else:
    settings = {}

# Ensure hooks section exists
if "hooks" not in settings:
    settings["hooks"] = {}

# Clean up legacy Stop hook from older installs (replaced by PreCompact)
if "Stop" in settings["hooks"]:
    settings["hooks"]["Stop"] = [
        entry for entry in settings["hooks"]["Stop"]
        if not any(
            "auto_chunk_check.py" in h.get("command", "")
            for h in entry.get("hooks", [])
        )
    ]
    if not settings["hooks"]["Stop"]:
        del settings["hooks"]["Stop"]

# Merge RLM hooks (avoid duplicates by matcher+command pair)
for hook_type, hook_configs in rlm_hooks.items():
    if hook_type not in settings["hooks"]:
        settings["hooks"][hook_type] = []

    # Build set of existing (matcher, command) pairs
    existing_pairs = set()
    for existing in settings["hooks"][hook_type]:
        matcher = existing.get("matcher", "")
        for h in existing.get("hooks", []):
            if h.get("command"):
                existing_pairs.add((matcher, h["command"]))

    for config in hook_configs:
        matcher = config.get("matcher", "")
        for h in config.get("hooks", []):
            cmd = h.get("command", "")
            if cmd and (matcher, cmd) not in existing_pairs:
                settings["hooks"][hook_type].append(config)
                existing_pairs.add((matcher, cmd))
                break

# Save
settings_file.parent.mkdir(parents=True, exist_ok=True)
with open(settings_file, "w") as f:
    json.dump(settings, f, indent=2)

print("  OK - Hooks merged into settings.json")
PYTHON_SCRIPT

# =============================================================================
# 7. Add RLM instructions to CLAUDE.md
# =============================================================================
echo "[7/7] Configuring CLAUDE.md..."

if [ "$SKIP_CLAUDE_MD" = true ]; then
    echo "  SKIP - Option --no-claude-md"
else
    # If path not provided, try to find it
    if [ -z "$CLAUDE_MD_PATH" ]; then
        FOUND=$(find_claude_md)

        if [ -z "$FOUND" ]; then
            echo ""
            echo "  CLAUDE.md not found automatically."
            echo "  Checked locations:"
            echo "    - $SCRIPT_DIR/../CLAUDE.md"
            echo "    - $HOME/.claude/CLAUDE.md"
            echo "    - $(pwd)/CLAUDE.md"
            echo ""
            read -p "  Enter path to CLAUDE.md (or 'skip' to ignore): " CLAUDE_MD_PATH
            if [ "$CLAUDE_MD_PATH" = "skip" ] || [ -z "$CLAUDE_MD_PATH" ]; then
                echo "  SKIP - CLAUDE.md ignored"
                CLAUDE_MD_PATH=""
            fi
        elif [[ "$FOUND" == MULTIPLE:* ]]; then
            # Multiple files found
            FILES="${FOUND#MULTIPLE:}"
            echo ""
            echo "  Multiple CLAUDE.md files found:"
            IFS=' ' read -ra FILE_ARRAY <<< "$FILES"
            i=1
            for f in "${FILE_ARRAY[@]}"; do
                echo "    [$i] $f"
                ((i++))
            done
            echo ""
            read -p "  Choose a number (or 'skip' to ignore): " CHOICE
            if [ "$CHOICE" = "skip" ] || [ -z "$CHOICE" ]; then
                echo "  SKIP - CLAUDE.md ignored"
                CLAUDE_MD_PATH=""
            else
                # Get the chosen file
                idx=$((CHOICE - 1))
                CLAUDE_MD_PATH="${FILE_ARRAY[$idx]}"
            fi
        else
            # Single file found
            CLAUDE_MD_PATH="$FOUND"
            echo "  Found: $CLAUDE_MD_PATH"
        fi
    fi

    # Add RLM snippet if path is set
    if [ -n "$CLAUDE_MD_PATH" ] && [ -f "$CLAUDE_MD_PATH" ]; then
        RLM_MARKER="## RLM - MEMOIRE AUTOMATIQUE"
        if ! grep -q "$RLM_MARKER" "$CLAUDE_MD_PATH" 2>/dev/null; then
            # Backup first
            cp "$CLAUDE_MD_PATH" "$CLAUDE_MD_PATH.backup.$(date +%Y%m%d_%H%M%S)"
            # Append
            echo "" >> "$CLAUDE_MD_PATH"
            cat "$SCRIPT_DIR/templates/CLAUDE_RLM_SNIPPET.md" >> "$CLAUDE_MD_PATH"
            echo "  OK - RLM instructions added to $CLAUDE_MD_PATH"
            echo "  (Backup created: $CLAUDE_MD_PATH.backup.*)"
        else
            echo "  OK - RLM instructions already present in $CLAUDE_MD_PATH"
        fi
    elif [ -n "$CLAUDE_MD_PATH" ]; then
        echo "  ERROR - File not found: $CLAUDE_MD_PATH"
    fi
fi

# =============================================================================
# Done!
# =============================================================================
echo ""
echo "=============================================="
echo "  Installation completed successfully!"
echo "=============================================="
echo ""
echo "RLM is now installed with:"
echo "  - 14 MCP tools available"
echo "  - Auto-save before /compact (PreCompact hook)"
echo "  - Skills /rlm-analyze and /rlm-parallel installed"
echo ""
echo "NEXT STEP:"
echo "  Restart Claude Code to activate RLM"
echo ""
echo "VERIFY:"
echo "  claude mcp list    # List MCP servers"
echo "  rlm_status()       # Test inside Claude Code"
echo ""
echo "LANGUAGE:"
echo "  Hook messages are in English by default."
echo "  Set RLM_LANG=fr for French (see README)."
echo ""
echo "CUSTOMIZATION (optional):"
echo "  Edit $SCRIPT_DIR/context/domains.json"
echo "  (see domains.json.example for a complete example)"
echo ""
echo "=============================================="
