#!/bin/bash
set -Eeuo pipefail
umask 077

# Claude Code Configuration Sync - SessionEnd Hook
# Auto-syncs configuration when Claude Code exits

LOG_FILE="$HOME/.claude-sync.log"
REPO_DIR="$HOME/projects/claude-config"
CLAUDE_DIR="$HOME/.claude"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Acquire lock to prevent concurrent syncs (if flock is available)
if command -v flock &> /dev/null; then
    exec 9>"$REPO_DIR/.sync.lock"
    if ! flock -n 9; then
        log "Another sync in progress, skipping"
        exit 0
    fi
fi

log "SessionEnd: Starting sync..."

# Check if repo exists
if [ ! -d "$REPO_DIR/.git" ]; then
    log "ERROR: Config repo not found at $REPO_DIR"
    exit 0
fi

# Define rsync excludes for runtime/cache files
# Note: Can't use --filter=':- .gitignore' because .gitignore isn't in ~/.claude
RSYNC_FILTER=(
    --exclude='.git'
    --exclude='plugins/cache/'
    --exclude='plugins/marketplaces/'
    --exclude='ide/'
    --exclude='statsig/'
    --exclude='history.jsonl'
    --exclude='debug/'
    --exclude='session-env/'
    --exclude='shell-snapshots/'
    --exclude='todos/'
    --exclude='file-history/'
    --exclude='projects/'
    --exclude='.DS_Store'
    --exclude='.claude-sync.log'
)

# Pull latest changes BEFORE copying local files
git -C "$REPO_DIR" pull --rebase --autostash origin main >> "$LOG_FILE" 2>&1 || {
    log "ERROR: Pull failed (conflict or network issue). Resolve manually."
    exit 0
}

# Copy everything from ~/.claude to repo with filters
# --delete removes files deleted locally
# --delete-excluded purges previously-copied caches from repo
rsync -a --delete --delete-excluded "${RSYNC_FILTER[@]}" "$CLAUDE_DIR/" "$REPO_DIR/"
log "  ✓ Synced all files from ~/.claude (filters applied)"

# Check if there are changes
cd "$REPO_DIR"
git add -A
if git diff --cached --quiet; then
    log "No changes to sync"
    exit 0
fi

# Commit changes with hostname for traceability
git commit -m "Auto-sync: $(date '+%F %T') [$HOSTNAME]" >> "$LOG_FILE" 2>&1

# Push to remote
git push -u origin main >> "$LOG_FILE" 2>&1 || {
    log "ERROR: Push failed (network issue). Will retry on next sync."
    exit 0
}

log "SessionEnd: Sync complete ✓"
