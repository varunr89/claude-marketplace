---
name: config-sync
description: Sync ~/.claude/ configuration to a git repo automatically on session start/end
---

# Config Sync

Automatically pulls config from a git repo on session start and pushes changes on session end. Keeps your Claude Code settings, commands, and skills synchronized across machines.

## Setup

1. Create a git repo for your config (e.g., `~/projects/claude-config`)
2. Set `REPO_DIR` in the hook scripts to point to your config repo
3. The hooks use rsync to sync, excluding runtime files (plugins/cache, session state, etc.)

## What Gets Synced

- `settings.json`, `settings.local.json`
- `commands/` directory
- `skills/` directory
- `hooks/` directory
- `CLAUDE.md`

## What Gets Excluded

- `plugins/cache/`, `plugins/marketplaces/`
- `session-env/`, `todos/`, `debug/`
- `history.jsonl`
- `*.local.md` state files
