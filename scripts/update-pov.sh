#!/usr/bin/env bash
#
# update-pov.sh — Update Parzival (POV) module for existing installations.
# Copies agent definitions, workflows, constraints, loader shims, and oversight
# templates. Preserves _memory/ (user data) and config.yaml user values.
#
# Usage:
#   ./scripts/update-pov.sh <target-project-dir>
#   ./scripts/update-pov.sh --dry-run /path/to/project
#   ./scripts/update-pov.sh --yes --source ~/my-source /path/to/project
#
# Options: --dry-run, --yes (-y), --source <path>, --help (-h)
# Exit: 0=success, 1=error

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_SOURCE="/home/parzival/projects/agent-skills/dev-program/pov-dev-manager/Parzival"
SOURCE_DIR="" TARGET_DIR="" DRY_RUN=false AUTO_YES=false
FILES_COPIED=0 FILES_PRESERVED=0 DIRS_CREATED=0

info()  { echo -e "${CYAN}  $*${NC}"; }
ok()    { echo -e "${GREEN}  [OK] $*${NC}"; }
warn()  { echo -e "${YELLOW}  [!]  $*${NC}"; }
die()   { echo -e "${RED}  [ERR] $*${NC}" >&2; exit 1; }
run()   { if $DRY_RUN; then echo -e "  ${YELLOW}[dry-run]${NC} $*"; else "$@"; fi; }

resolve_source() {
    [[ -n "$SOURCE_DIR" ]] && return
    local c="$(cd "$SCRIPT_DIR/.." && pwd)/../Parzival"
    if [[ -d "$c/_ai-memory/pov" ]]; then SOURCE_DIR="$(cd "$c" && pwd)"; return; fi
    SOURCE_DIR="$DEFAULT_SOURCE"
}

validate() {
    [[ -d "$TARGET_DIR" ]] || die "Target does not exist: $TARGET_DIR"
    [[ -d "$TARGET_DIR/_ai-memory" ]] || die "No _ai-memory/ in target — use install.sh for fresh installs."
    [[ -d "$SOURCE_DIR/_ai-memory/pov" ]] || die "Source missing _ai-memory/pov/: $SOURCE_DIR"
    ok "Validation passed"; info "Source: $SOURCE_DIR"; info "Target: $TARGET_DIR"
}

confirm() {
    $AUTO_YES && return 0
    echo ""; warn "This will update Parzival files. Make sure you have backed up any customizations."
    read -rp "  Continue? [y/N] " ans; [[ "$ans" =~ ^[Yy]$ ]] || { echo "  Aborted."; exit 0; }
}

copy_dir() {
    local src="$1" dst="$2" label="$3"
    [[ -d "$src" ]] || { warn "Source not found, skipping: $label"; return; }
    info "Copying $label ..."
    run mkdir -p "$dst"
    local count; count=$(find "$src" -type f 2>/dev/null | wc -l)
    if $DRY_RUN; then
        echo -e "  ${YELLOW}[dry-run]${NC} Would copy $count files -> $dst"
    else
        cp -a "$src/." "$dst/"
    fi
    FILES_COPIED=$((FILES_COPIED + count))
}

copy_oversight_templates() {
    local src="$SOURCE_DIR/oversight" dst="$TARGET_DIR/oversight"
    [[ -d "$src" ]] || { warn "No oversight/ in source, skipping"; return; }
    info "Copying oversight templates (skip-existing for user data) ..."
    run mkdir -p "$dst"
    while IFS= read -r -d '' file; do
        local rel="${file#"$src"/}" tf="$dst/${file#"$src"/}" bn; bn="$(basename "$file")"
        if [[ "$bn" == *TEMPLATE* || "$bn" == *.yaml || "$bn" == README* ]]; then
            run mkdir -p "$(dirname "$tf")"
            $DRY_RUN && echo -e "  ${YELLOW}[dry-run]${NC} Update: oversight/$rel" || cp -a "$file" "$tf"
            FILES_COPIED=$((FILES_COPIED + 1))
        elif [[ -f "$tf" ]]; then
            FILES_PRESERVED=$((FILES_PRESERVED + 1))
        else
            run mkdir -p "$(dirname "$tf")"
            $DRY_RUN && echo -e "  ${YELLOW}[dry-run]${NC} New: oversight/$rel" || cp -a "$file" "$tf"
            FILES_COPIED=$((FILES_COPIED + 1))
        fi
    done < <(find "$src" -type f -print0 2>/dev/null)
}

preserve_config() {
    local cfg="$TARGET_DIR/_ai-memory/pov/config.yaml"
    [[ -f "$cfg" ]] || return 1
    info "Backing up config.yaml ..."
    $DRY_RUN && echo -e "  ${YELLOW}[dry-run]${NC} Would backup config.yaml" || cp -a "$cfg" "${cfg}.bak"
    FILES_PRESERVED=$((FILES_PRESERVED + 1)); return 0
}

restore_config() {
    local cfg="$TARGET_DIR/_ai-memory/pov/config.yaml" bak="$TARGET_DIR/_ai-memory/pov/config.yaml.bak"
    [[ -f "$bak" ]] || return 0
    info "Restoring user config values ..."
    if $DRY_RUN; then echo -e "  ${YELLOW}[dry-run]${NC} Would restore user config values"; return; fi
    for key in user_name communication_language document_output_language pov_output_folder output_folder teams_enabled; do
        local v; v=$(grep "^${key}:" "$bak" 2>/dev/null | head -1 | sed "s/^${key}: *//") || true
        [[ -n "$v" ]] && grep -q "^${key}:" "$cfg" 2>/dev/null && { local ev; ev=$(printf '%s\n' "$v" | sed 's/[&|\\]/\\&/g'); sed -i "s|^${key}:.*|${key}: ${ev}|" "$cfg"; }
    done
    ok "User config values restored"
}

update_version() {
    local sm="$SOURCE_DIR/_ai-memory/_config/manifest.yaml" dm="$TARGET_DIR/_ai-memory/_config/manifest.yaml"
    [[ -f "$sm" ]] || { warn "No source manifest.yaml, skipping version update"; return; }
    local ver; ver=$(grep 'version:' "$sm" | head -1 | sed 's/.*version: *//' | tr -d "\"'")
    info "Version: ${ver:-unknown}"
    run mkdir -p "$(dirname "$dm")"
    if $DRY_RUN; then echo -e "  ${YELLOW}[dry-run]${NC} Would set manifest version to $ver"; return; fi
    cp -a "$sm" "$dm"
    sed -i "s|lastUpdated:.*|lastUpdated: $(date -u +"%Y-%m-%dT%H:%M:%S.000Z")|g" "$dm"
}

ensure_dirs() {
    for d in "$TARGET_DIR/.audit/logs" "$TARGET_DIR/_ai-memory/.audit/logs"; do
        [[ -d "$d" ]] && continue; run mkdir -p "$d"; DIRS_CREATED=$((DIRS_CREATED + 1))
    done
}

print_summary() {
    echo ""
    echo "============================================================"
    $DRY_RUN && echo -e "  ${YELLOW}DRY RUN SUMMARY (no changes made)${NC}" || echo -e "  ${GREEN}UPDATE COMPLETE${NC}"
    echo "============================================================"
    echo "  Files copied/updated:  $FILES_COPIED"
    echo "  Files preserved:       $FILES_PRESERVED"
    echo "  Directories created:   $DIRS_CREATED"
    local sm="$SOURCE_DIR/_ai-memory/_config/manifest.yaml"
    [[ -f "$sm" ]] && echo "  Version installed:     $(grep 'version:' "$sm" | head -1 | sed "s/.*version: *//" | tr -d "\"'")"
    echo "============================================================"
    echo ""
}

# --- Argument parsing -------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)  DRY_RUN=true; shift ;;
        --yes|-y)   AUTO_YES=true; shift ;;
        --source)   SOURCE_DIR="${2:-}"; [[ -n "$SOURCE_DIR" ]] || die "--source needs a path"; shift 2 ;;
        --help|-h)  sed -n '3,13p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'; exit 0 ;;
        -*)         die "Unknown option: $1" ;;
        *)          [[ -z "$TARGET_DIR" ]] || die "Multiple targets specified"; TARGET_DIR="$1"; shift ;;
    esac
done
[[ -n "$TARGET_DIR" ]] || die "Usage: $0 [--dry-run] [--yes] [--source <path>] <target-project-dir>"

# --- Main -------------------------------------------------------------------
echo -e "\n============================================================"
echo "  Parzival (POV) Module Update"
echo -e "============================================================\n"

resolve_source; validate; confirm
$DRY_RUN && echo -e "\n  ${YELLOW}*** DRY RUN MODE ***${NC}\n"

HAS_CONFIG=false; preserve_config && HAS_CONFIG=true
copy_dir "$SOURCE_DIR/_ai-memory/pov" "$TARGET_DIR/_ai-memory/pov" "_ai-memory/pov"
$HAS_CONFIG && restore_config
copy_dir "$SOURCE_DIR/.claude/agents/pov" "$TARGET_DIR/.claude/agents/pov" ".claude/agents/pov"
copy_dir "$SOURCE_DIR/.claude/commands/pov" "$TARGET_DIR/.claude/commands/pov" ".claude/commands/pov"
copy_oversight_templates; ensure_dirs; update_version; print_summary
