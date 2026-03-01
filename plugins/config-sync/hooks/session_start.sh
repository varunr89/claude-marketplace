#!/bin/bash
set -Eeuo pipefail
umask 077

# Claude Code Configuration Sync - SessionStart Hook
# Auto-pulls latest configuration when Claude Code starts

LOG_FILE="$HOME/.claude-sync.log"
REPO_DIR="$HOME/projects/claude-config"
CLAUDE_DIR="$HOME/.claude"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

log "SessionStart: Pulling latest config..."

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

# Pull latest changes
git -C "$REPO_DIR" pull --rebase origin main >> "$LOG_FILE" 2>&1 || {
    log "ERROR: Pull failed (network issue or conflict)"
    exit 0
}

# Copy everything from repo to ~/.claude
# --delete WITH filters: deletes tracked files removed on other devices,
# preserves local-only ignored files (history, caches, logs)
rsync -a --delete "${RSYNC_FILTER[@]}" "$REPO_DIR/" "$CLAUDE_DIR/"
log "  ✓ Synced all config files to ~/.claude"

log "SessionStart: Pull complete ✓"
