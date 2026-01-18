#!/bin/bash
# =============================================================================
# RLM Installation Script
# Memoire infinie pour Claude Code
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
echo "  RLM - Memoire infinie pour Claude Code"
echo "=============================================="
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
            echo "Option inconnue: $1"
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
echo "[1/7] Creation des repertoires..."
mkdir -p "$RLM_DIR/hooks"
mkdir -p "$RLM_DIR/context/chunks"
mkdir -p "$SKILLS_DIR/rlm-analyze"
mkdir -p "$SKILLS_DIR/rlm-parallel"
echo "  OK - Repertoires crees"

# =============================================================================
# 2. Copy hook scripts
# =============================================================================
echo "[2/7] Installation des hooks..."
cp "$SCRIPT_DIR/hooks/auto_chunk_check.py" "$RLM_DIR/hooks/"
cp "$SCRIPT_DIR/hooks/reset_chunk_counter.py" "$RLM_DIR/hooks/"
chmod +x "$RLM_DIR/hooks/"*.py
echo "  OK - Hooks installes"

# =============================================================================
# 3. Copy skill
# =============================================================================
echo "[3/7] Installation des skills RLM..."
cp "$SCRIPT_DIR/templates/skills/rlm-analyze/skill.md" "$SKILLS_DIR/rlm-analyze/"
cp "$SCRIPT_DIR/templates/skills/rlm-parallel/skill.md" "$SKILLS_DIR/rlm-parallel/"
echo "  OK - Skills /rlm-analyze et /rlm-parallel installes"

# =============================================================================
# 4. Configure MCP server
# =============================================================================
echo "[4/7] Configuration du serveur MCP..."
if command -v claude &> /dev/null; then
    # Remove existing if any
    claude mcp remove rlm-server 2>/dev/null || true
    # Add new
    claude mcp add rlm-server -s user -- python3 "$SCRIPT_DIR/mcp_server/server.py"
    echo "  OK - Serveur MCP configure"
else
    echo "  SKIP - Claude CLI non trouve (configurer manuellement)"
fi

# =============================================================================
# 5. Initialize context files
# =============================================================================
echo "[5/7] Initialisation du contexte..."
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
echo "  OK - Contexte initialise"

# =============================================================================
# 6. Merge hooks into settings.json
# =============================================================================
echo "[6/7] Configuration des hooks dans settings.json..."

python3 << 'PYTHON_SCRIPT'
import json
from pathlib import Path

settings_file = Path.home() / ".claude" / "settings.json"

# RLM hooks to add
rlm_hooks = {
    "Stop": [{
        "matcher": "*",
        "hooks": [{
            "type": "command",
            "command": "python3 ~/.claude/rlm/hooks/auto_chunk_check.py"
        }]
    }],
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

# Merge RLM hooks (avoid duplicates)
for hook_type, hook_configs in rlm_hooks.items():
    if hook_type not in settings["hooks"]:
        settings["hooks"][hook_type] = []

    existing_cmds = []
    for existing in settings["hooks"][hook_type]:
        for h in existing.get("hooks", []):
            if h.get("command"):
                existing_cmds.append(h["command"])

    for config in hook_configs:
        for h in config.get("hooks", []):
            cmd = h.get("command", "")
            if cmd and cmd not in existing_cmds:
                settings["hooks"][hook_type].append(config)
                break

# Save
settings_file.parent.mkdir(parents=True, exist_ok=True)
with open(settings_file, "w") as f:
    json.dump(settings, f, indent=2)

print("  OK - Hooks merges dans settings.json")
PYTHON_SCRIPT

# =============================================================================
# 7. Add RLM instructions to CLAUDE.md
# =============================================================================
echo "[7/7] Configuration CLAUDE.md..."

if [ "$SKIP_CLAUDE_MD" = true ]; then
    echo "  SKIP - Option --no-claude-md"
else
    # If path not provided, try to find it
    if [ -z "$CLAUDE_MD_PATH" ]; then
        FOUND=$(find_claude_md)

        if [ -z "$FOUND" ]; then
            echo ""
            echo "  CLAUDE.md non trouve automatiquement."
            echo "  Emplacements verifies:"
            echo "    - $SCRIPT_DIR/../CLAUDE.md"
            echo "    - $HOME/.claude/CLAUDE.md"
            echo "    - $(pwd)/CLAUDE.md"
            echo ""
            read -p "  Entrez le chemin vers CLAUDE.md (ou 'skip' pour ignorer): " CLAUDE_MD_PATH
            if [ "$CLAUDE_MD_PATH" = "skip" ] || [ -z "$CLAUDE_MD_PATH" ]; then
                echo "  SKIP - CLAUDE.md ignore"
                CLAUDE_MD_PATH=""
            fi
        elif [[ "$FOUND" == MULTIPLE:* ]]; then
            # Multiple files found
            FILES="${FOUND#MULTIPLE:}"
            echo ""
            echo "  Plusieurs CLAUDE.md trouves:"
            IFS=' ' read -ra FILE_ARRAY <<< "$FILES"
            i=1
            for f in "${FILE_ARRAY[@]}"; do
                echo "    [$i] $f"
                ((i++))
            done
            echo ""
            read -p "  Choisissez un numero (ou 'skip' pour ignorer): " CHOICE
            if [ "$CHOICE" = "skip" ] || [ -z "$CHOICE" ]; then
                echo "  SKIP - CLAUDE.md ignore"
                CLAUDE_MD_PATH=""
            else
                # Get the chosen file
                idx=$((CHOICE - 1))
                CLAUDE_MD_PATH="${FILE_ARRAY[$idx]}"
            fi
        else
            # Single file found
            CLAUDE_MD_PATH="$FOUND"
            echo "  Trouve: $CLAUDE_MD_PATH"
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
            echo "  OK - Instructions RLM ajoutees a $CLAUDE_MD_PATH"
            echo "  (Backup cree: $CLAUDE_MD_PATH.backup.*)"
        else
            echo "  OK - Instructions RLM deja presentes dans $CLAUDE_MD_PATH"
        fi
    elif [ -n "$CLAUDE_MD_PATH" ]; then
        echo "  ERREUR - Fichier non trouve: $CLAUDE_MD_PATH"
    fi
fi

# =============================================================================
# Done!
# =============================================================================
echo ""
echo "=============================================="
echo "  Installation terminee avec succes!"
echo "=============================================="
echo ""
echo "RLM est maintenant installe avec :"
echo "  - 9 tools MCP disponibles"
echo "  - Auto-chunking active (hook Stop)"
echo "  - Skills /rlm-analyze et /rlm-parallel installes"
echo ""
echo "PROCHAINE ETAPE:"
echo "  Relancez Claude Code pour activer RLM"
echo ""
echo "VERIFICATION:"
echo "  claude mcp list    # Voir les serveurs MCP"
echo "  rlm_status()       # Tester dans Claude Code"
echo ""
echo "=============================================="
