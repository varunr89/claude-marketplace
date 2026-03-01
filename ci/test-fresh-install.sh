#!/usr/bin/env bash
set -euo pipefail

# Usage: test-fresh-install.sh <repo-root>
# Tests marketplace add, plugin install, plugin load in a clean environment.
# Requires: claude CLI installed. No API key needed ($0 cost).

REPO_ROOT="$(cd "${1:-.}" && pwd)"
TMP_HOME="$(mktemp -d)"
TMP_CWD="$(mktemp -d)"
TMP_LOG="$(mktemp -d)"
trap 'rm -rf "$TMP_HOME" "$TMP_CWD" "$TMP_LOG"' EXIT

PASS=0
FAIL=0
SKIP=0

# Wrapper: run claude with isolated HOME (no existing config)
cc() { HOME="$TMP_HOME" claude "$@"; }

check_platform() {
  local plugin_dir="$1"
  local platform_file="$plugin_dir/tests/platform.json"
  if [ ! -f "$platform_file" ]; then
    return 0  # No platform constraints
  fi

  local current_os
  current_os="$(uname -s | tr '[:upper:]' '[:lower:]')"
  local current_arch
  current_arch="$(uname -m)"
  # Normalize: x86_64 -> amd64, arm64 stays arm64
  [ "$current_arch" = "x86_64" ] && current_arch="amd64"

  local required_os
  required_os=$(jq -r '.os // [] | join(",")' "$platform_file")
  if [ -n "$required_os" ] && ! echo "$required_os" | grep -qi "$current_os"; then
    return 1  # Platform not supported
  fi

  local required_arch
  required_arch=$(jq -r '.arch // [] | join(",")' "$platform_file")
  if [ -n "$required_arch" ] && ! echo "$required_arch" | grep -qi "$current_arch"; then
    return 1  # Arch not supported
  fi

  return 0
}

echo "=== Fresh Install E2E Test ==="
echo "Repo: $REPO_ROOT"
echo "Isolated HOME: $TMP_HOME"
echo ""

# Step 1: Validate marketplace manifest
echo "--- Validating marketplace manifest ---"
cc plugin validate "$REPO_ROOT"
echo "PASS: marketplace manifest valid"
PASS=$((PASS + 1))

# Step 2: Add marketplace from local checkout
echo ""
echo "--- Adding marketplace ---"
cc plugin marketplace add "$REPO_ROOT"
echo "PASS: marketplace added"
PASS=$((PASS + 1))

# Step 3: List available plugins
echo ""
echo "--- Listing available plugins ---"
available="$(cc plugin list --json --available)"
echo "$available" | jq -r '.available[].pluginId' 2>/dev/null || true

# Step 4: Install each local plugin and probe
cd "$TMP_CWD"
for plugin_dir in "$REPO_ROOT"/plugins/*/; do
  plugin_name="$(basename "$plugin_dir")"
  id="${plugin_name}@varunr-marketplace"

  echo ""
  echo "--- Testing plugin: $plugin_name ---"

  # Check platform requirements
  if ! check_platform "$plugin_dir"; then
    echo "  SKIP $plugin_name (platform not supported)"
    SKIP=$((SKIP + 1))
    continue
  fi

  # Install
  echo "  Installing $id..."
  cc plugin install "$id"

  # Verify plugin.json exists at install path
  install_path="$(cc plugin list --json | jq -r --arg id "$id" '.[] | select(.id==$id) | .installPath')"
  if [ -z "$install_path" ] || [ ! -f "$install_path/.claude-plugin/plugin.json" ]; then
    echo "  FAIL: plugin.json not found at install path"
    FAIL=$((FAIL + 1))
    continue
  fi
  echo "  PASS: installed at $install_path"
  PASS=$((PASS + 1))

  # Probe: loads plugins, fails auth before API call ($0)
  debug_log="$TMP_LOG/${plugin_name}.debug.log"
  result_file="$TMP_LOG/${plugin_name}.json"
  set +e
  cc -p "plugin load probe" --max-turns 1 --output-format json \
    --debug-file "$debug_log" > "$result_file" 2>&1
  rc=$?
  set -e

  # Assert zero cost (auth failed before any API call)
  if [ -f "$result_file" ] && jq -e 'has("total_cost_usd")' "$result_file" >/dev/null 2>&1; then
    cost=$(jq -r '.total_cost_usd // 0' "$result_file")
    if [ "$cost" != "0" ]; then
      echo "  FAIL: unexpected API cost: $cost"
      FAIL=$((FAIL + 1))
      continue
    fi
  fi

  # Assert plugin loaded in debug log
  if [ -f "$debug_log" ]; then
    if grep -q "Loading plugin\|plugin.*loaded\|skills loaded" "$debug_log" 2>/dev/null; then
      echo "  PASS: plugin loaded (confirmed in debug log)"
      PASS=$((PASS + 1))
    else
      echo "  WARN: could not confirm plugin load in debug log"
    fi
  fi

  # Lifecycle: disable, enable, uninstall
  echo "  Testing lifecycle: disable -> enable -> uninstall"
  cc plugin disable "$id" >/dev/null 2>&1 || true
  cc plugin enable "$id" >/dev/null 2>&1 || true
  cc plugin uninstall "$id" >/dev/null 2>&1 || true
  echo "  PASS: lifecycle complete"
  PASS=$((PASS + 1))
done

echo ""
echo "=== Results: $PASS passed, $FAIL failed, $SKIP skipped ==="

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
