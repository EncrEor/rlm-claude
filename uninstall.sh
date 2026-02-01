#!/bin/bash
# =============================================================================
# RLM Uninstall Script
# Cleanly removes RLM from Claude Code
# =============================================================================
#
# Usage:
#   ./uninstall.sh                    # Interactive (prompts before removing data)
#   ./uninstall.sh --keep-data        # Remove config but keep chunks/insights
#   ./uninstall.sh --all              # Remove everything including data
#   ./uninstall.sh --dry-run          # Show what would be removed without doing it
#
# =============================================================================

set -e

# =============================================================================
# Colors (with fallback for non-interactive terminals)
# =============================================================================
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    RED='' GREEN='' YELLOW='' CYAN='' BOLD='' NC=''
fi

# =============================================================================
# Parse arguments
# =============================================================================
KEEP_DATA=false
REMOVE_ALL=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --keep-data)
            KEEP_DATA=true
            shift
            ;;
        --all)
            REMOVE_ALL=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            echo "Usage: ./uninstall.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --keep-data   Remove RLM config but keep your chunks and insights"
            echo "  --all         Remove everything including all stored data"
            echo "  --dry-run     Preview what would be removed (no changes made)"
            echo "  -h, --help    Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run ./uninstall.sh --help for usage"
            exit 1
            ;;
    esac
done

# =============================================================================
# Paths
# =============================================================================
RLM_DIR="$HOME/.claude/rlm"
SKILLS_DIR="$HOME/.claude/skills"
SETTINGS_FILE="$HOME/.claude/settings.json"
CONTEXT_DIR="$RLM_DIR/context"
CHUNKS_DIR="$CONTEXT_DIR/chunks"

# =============================================================================
# Helper functions
# =============================================================================
info()    { echo -e "${CYAN}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC}   $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
skip()    { echo -e "${YELLOW}[SKIP]${NC} $1"; }
dry()     { echo -e "${BOLD}[DRY]${NC}  $1"; }

run_or_dry() {
    if [ "$DRY_RUN" = true ]; then
        dry "Would run: $*"
    else
        "$@"
    fi
}

count_chunks() {
    if [ -d "$CHUNKS_DIR" ]; then
        find "$CHUNKS_DIR" -name "*.md" 2>/dev/null | wc -l | tr -d ' '
    else
        echo "0"
    fi
}

count_insights() {
    if [ -f "$CONTEXT_DIR/session_memory.json" ]; then
        python3 -c "
import json, sys
try:
    with open('$CONTEXT_DIR/session_memory.json') as f:
        data = json.load(f)
    print(len(data.get('insights', [])))
except:
    print('0')
" 2>/dev/null || echo "0"
    else
        echo "0"
    fi
}

# =============================================================================
# Header
# =============================================================================
echo ""
echo -e "${BOLD}=============================================="
echo "  RLM - Uninstall"
echo -e "==============================================${NC}"
echo ""

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}--- DRY RUN MODE (no changes will be made) ---${NC}"
    echo ""
fi

# =============================================================================
# 1. Inventory - show what exists
# =============================================================================
info "Scanning RLM installation..."

CHUNK_COUNT=$(count_chunks)
INSIGHT_COUNT=$(count_insights)

echo ""
echo "  Found:"
[ -d "$RLM_DIR" ]                     && echo "    - RLM directory:    $RLM_DIR" || echo "    - RLM directory:    (not found)"
[ -d "$SKILLS_DIR/rlm-analyze" ]      && echo "    - Skill rlm-analyze" || true
[ -d "$SKILLS_DIR/rlm-parallel" ]     && echo "    - Skill rlm-parallel" || true
[ -f "$SETTINGS_FILE" ]               && echo "    - Settings hooks:   $SETTINGS_FILE" || true
echo "    - Chunks stored:    $CHUNK_COUNT"
echo "    - Insights stored:  $INSIGHT_COUNT"
echo ""

# =============================================================================
# 2. Determine data removal strategy
# =============================================================================
REMOVE_DATA=false

if [ "$REMOVE_ALL" = true ]; then
    REMOVE_DATA=true
elif [ "$KEEP_DATA" = true ]; then
    REMOVE_DATA=false
elif [ "$DRY_RUN" = true ]; then
    # In dry-run without explicit flag, show both scenarios
    REMOVE_DATA=false
else
    # Interactive prompt (only if there's data to lose)
    if [ "$CHUNK_COUNT" -gt 0 ] || [ "$INSIGHT_COUNT" -gt 0 ]; then
        echo -e "${YELLOW}You have $CHUNK_COUNT chunks and $INSIGHT_COUNT insights stored.${NC}"
        echo ""
        echo "  [1] Keep data   - Remove RLM config only, preserve chunks/insights"
        echo "  [2] Remove all  - Delete everything including stored data"
        echo "  [3] Cancel      - Abort uninstall"
        echo ""
        read -p "  Choose [1/2/3]: " CHOICE
        case $CHOICE in
            1) REMOVE_DATA=false ;;
            2) REMOVE_DATA=true ;;
            *)
                echo ""
                echo "Uninstall cancelled."
                exit 0
                ;;
        esac
        echo ""
    fi
fi

# =============================================================================
# 3. Remove MCP server
# =============================================================================
info "Removing MCP server..."

if command -v claude &> /dev/null; then
    if [ "$DRY_RUN" = true ]; then
        dry "Would run: claude mcp remove rlm-server"
    else
        claude mcp remove rlm-server 2>/dev/null && success "MCP server removed" || skip "MCP server not found (already removed)"
    fi
else
    skip "Claude CLI not found (MCP server not removed)"
fi

# =============================================================================
# 4. Remove hooks from settings.json
# =============================================================================
info "Cleaning hooks from settings.json..."

if [ -f "$SETTINGS_FILE" ]; then
    if [ "$DRY_RUN" = true ]; then
        dry "Would remove RLM hooks from $SETTINGS_FILE"
    else
        # Backup settings.json
        cp "$SETTINGS_FILE" "$SETTINGS_FILE.backup.$(date +%Y%m%d_%H%M%S)"

        python3 << 'PYTHON_SCRIPT'
import json
import sys
from pathlib import Path

settings_file = Path.home() / ".claude" / "settings.json"

try:
    with open(settings_file) as f:
        settings = json.load(f)
except (json.JSONDecodeError, FileNotFoundError):
    print("  Could not parse settings.json, skipping hook removal")
    sys.exit(0)

hooks = settings.get("hooks", {})
removed = 0

# RLM hook commands to match (covers all versions)
rlm_patterns = [
    "rlm/hooks/auto_chunk_check.py",
    "rlm/hooks/reset_chunk_counter.py",
    "rlm/hooks/pre_compact_chunk.py",
]

for hook_type in list(hooks.keys()):
    original_count = len(hooks[hook_type])
    hooks[hook_type] = [
        entry for entry in hooks[hook_type]
        if not any(
            pattern in h.get("command", "")
            for h in entry.get("hooks", [])
            for pattern in rlm_patterns
        )
    ]
    removed += original_count - len(hooks[hook_type])

    # Remove empty hook type arrays
    if not hooks[hook_type]:
        del hooks[hook_type]

# Remove empty hooks object
if not hooks:
    del settings["hooks"]
else:
    settings["hooks"] = hooks

with open(settings_file, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")

print(f"  Removed {removed} RLM hook(s) from settings.json")
PYTHON_SCRIPT
        success "Hooks cleaned (backup: settings.json.backup.*)"
    fi
else
    skip "settings.json not found"
fi

# =============================================================================
# 5. Remove skills
# =============================================================================
info "Removing skills..."

for skill in rlm-analyze rlm-parallel; do
    skill_dir="$SKILLS_DIR/$skill"
    if [ -d "$skill_dir" ]; then
        run_or_dry rm -rf "$skill_dir"
        if [ "$DRY_RUN" = true ]; then
            dry "Would remove $skill_dir"
        else
            success "Removed skill /$skill"
        fi
    else
        skip "Skill /$skill not found"
    fi
done

# =============================================================================
# 6. Remove RLM snippet from CLAUDE.md
# =============================================================================
info "Cleaning CLAUDE.md..."

# Search for CLAUDE.md in common locations
CLAUDE_MD_FOUND=""
for loc in \
    "$(cd "$(dirname "$0")" 2>/dev/null && pwd)/../CLAUDE.md" \
    "$(cd "$(dirname "$0")" 2>/dev/null && pwd)/../../CLAUDE.md" \
    "$HOME/.claude/CLAUDE.md" \
    "$(pwd)/CLAUDE.md"; do
    if [ -f "$loc" ]; then
        # Resolve absolute path
        abs="$(cd "$(dirname "$loc")" && pwd)/$(basename "$loc")"
        if grep -q "## RLM - M" "$abs" 2>/dev/null; then
            CLAUDE_MD_FOUND="$abs"
            break
        fi
    fi
done

if [ -n "$CLAUDE_MD_FOUND" ]; then
    if [ "$DRY_RUN" = true ]; then
        dry "Would remove RLM section from $CLAUDE_MD_FOUND"
    else
        cp "$CLAUDE_MD_FOUND" "$CLAUDE_MD_FOUND.backup.$(date +%Y%m%d_%H%M%S)"

        python3 << PYTHON_SCRIPT
import re

path = "$CLAUDE_MD_FOUND"
with open(path, encoding="utf-8") as f:
    content = f.read()

# Remove the RLM section: from "## RLM - " to the next "## " heading or EOF
# Match both "## RLM - MÉMOIRE PERSISTANTE" and "## RLM - MEMOIRE AUTOMATIQUE"
pattern = r'\n*## RLM - M[^\n]*\n(?:(?!## ).|\n)*'
new_content = re.sub(pattern, '\n', content).rstrip() + '\n'

if new_content != content:
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"  Removed RLM section from {path}")
else:
    print(f"  No RLM section found in {path}")
PYTHON_SCRIPT
        success "CLAUDE.md cleaned (backup created)"
    fi
else
    skip "No CLAUDE.md with RLM section found"
fi

# =============================================================================
# 7. Remove RLM files
# =============================================================================
if [ "$REMOVE_DATA" = true ]; then
    info "Removing all RLM files (including data)..."
    if [ -d "$RLM_DIR" ]; then
        run_or_dry rm -rf "$RLM_DIR"
        if [ "$DRY_RUN" != true ]; then
            success "Removed $RLM_DIR ($CHUNK_COUNT chunks, $INSIGHT_COUNT insights deleted)"
        fi
    else
        skip "RLM directory not found"
    fi
else
    info "Removing RLM config files (keeping data)..."

    # Remove hooks directory
    if [ -d "$RLM_DIR/hooks" ]; then
        run_or_dry rm -rf "$RLM_DIR/hooks"
        if [ "$DRY_RUN" != true ]; then
            success "Removed hooks directory"
        fi
    fi

    # Remove chunk_state.json (runtime state, not user data)
    if [ -f "$RLM_DIR/chunk_state.json" ]; then
        run_or_dry rm -f "$RLM_DIR/chunk_state.json"
        if [ "$DRY_RUN" != true ]; then
            success "Removed chunk_state.json"
        fi
    fi

    if [ -d "$CONTEXT_DIR" ]; then
        echo ""
        info "Data preserved at: $CONTEXT_DIR"
        echo "    - $CHUNK_COUNT chunks in $CHUNKS_DIR"
        echo "    - $INSIGHT_COUNT insights in session_memory.json"
        echo "    - To remove later: rm -rf $RLM_DIR"
    fi
fi

# =============================================================================
# Done
# =============================================================================
echo ""
echo -e "${BOLD}=============================================="
if [ "$DRY_RUN" = true ]; then
    echo "  Dry run complete (no changes made)"
else
    echo "  RLM uninstalled successfully"
fi
echo -e "==============================================${NC}"
echo ""

if [ "$DRY_RUN" != true ]; then
    echo "What was removed:"
    echo "  - MCP server (rlm-server)"
    echo "  - Hooks from settings.json"
    echo "  - Skills (/rlm-analyze, /rlm-parallel)"
    echo "  - RLM section from CLAUDE.md"
    if [ "$REMOVE_DATA" = true ]; then
        echo "  - All chunks and insights"
    else
        echo ""
        echo "Your data was preserved at:"
        echo "  $CONTEXT_DIR"
    fi
    echo ""
    echo "Restart Claude Code to complete the removal."
fi
echo ""
