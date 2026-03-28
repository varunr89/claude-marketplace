#!/bin/bash
# Integration tests for desktop CLI
# Requires: cliclick, screencapture, Accessibility + Screen Recording permissions
# Note: NOT using set -e because arithmetic ((PASS++)) returns 1 when PASS is 0
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DESKTOP="$SCRIPT_DIR/desktop"
PASS=0
FAIL=0

assert_ok() {
  local desc="$1"; shift
  if "$@" > /dev/null 2>&1; then
    echo "PASS: $desc"
    PASS=$((PASS + 1))
  else
    echo "FAIL: $desc"
    FAIL=$((FAIL + 1))
  fi
}

assert_json_field() {
  local desc="$1"
  local output="$2"
  local field="$3"
  if echo "$output" | python3 -c "import sys,json; d=json.load(sys.stdin); assert '$field' in d" 2>/dev/null; then
    echo "PASS: $desc"
    PASS=$((PASS + 1))
  else
    echo "FAIL: $desc ($field not in output)"
    FAIL=$((FAIL + 1))
  fi
}

# Test: screenshot returns JSON with path, dimensions, scale
echo "--- screenshot ---"
OUTPUT=$("$DESKTOP" screenshot)
assert_json_field "screenshot returns path" "$OUTPUT" "path"
assert_json_field "screenshot returns dimensions" "$OUTPUT" "dimensions"
assert_json_field "screenshot returns scale" "$OUTPUT" "scale"

# Verify file exists
SPATH=$(echo "$OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['path'])")
if [ -f "$SPATH" ]; then
  echo "PASS: screenshot file exists at $SPATH"
  PASS=$((PASS + 1))
  rm -f "$SPATH"
else
  echo "FAIL: screenshot file missing at $SPATH"
  FAIL=$((FAIL + 1))
fi

# Test: screenshot with custom path
CUSTOM_PATH="/tmp/test-desktop-screenshot.png"
OUTPUT=$("$DESKTOP" screenshot "$CUSTOM_PATH")
if [ -f "$CUSTOM_PATH" ]; then
  echo "PASS: custom path screenshot exists"
  PASS=$((PASS + 1))
  rm -f "$CUSTOM_PATH"
else
  echo "FAIL: custom path screenshot missing"
  FAIL=$((FAIL + 1))
fi

# Test: click (just verify it doesn't error -- click at 0,0 is safe)
echo "--- click ---"
assert_ok "click at 1 1" "$DESKTOP" click 1 1

# Test: move
echo "--- move ---"
assert_ok "move to 100 100" "$DESKTOP" move 100 100

# Test: type (type into void -- no harm)
echo "--- type ---"
assert_ok "type hello" "$DESKTOP" type "hello"

# Test: key
echo "--- key ---"
assert_ok "key esc" "$DESKTOP" key esc

# Summary
echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
