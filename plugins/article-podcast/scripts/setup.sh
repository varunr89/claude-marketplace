#!/usr/bin/env bash
# Setup script for article-podcast plugin.
# Creates a virtual environment and installs Python dependencies.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/venv"
DATA_DIR="${PODCAST_DATA_DIR:-$HOME/.article-podcast}"

echo "=== Article Podcast Plugin Setup ==="

# Create virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
else
    echo "Virtual environment already exists at $VENV_DIR"
fi

# Install dependencies
echo "Installing Python dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/../requirements.txt" -q

# Create data directory
mkdir -p "$DATA_DIR"

# Create config template if none exists
CONFIG_FILE="$DATA_DIR/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Creating config template at $CONFIG_FILE..."
    cat > "$CONFIG_FILE" << 'EOF'
{
  "azure_storage_account": "REPLACE_ME",
  "azure_container": "podcasts",
  "feed_url": "https://REPLACE_ME.blob.core.windows.net/podcasts/feed.xml",
  "feed_title": "My Reading List",
  "feed_author": "Your Name",
  "feed_description": "AI-generated podcast episodes from articles and papers",
  "tts_fallback_order": ["gemini", "azure-openai", "edge"]
}
EOF
    echo "  -> Edit $CONFIG_FILE with your Azure Storage details"
else
    echo "Config already exists at $CONFIG_FILE"
fi

# Check for required tools
echo ""
echo "Checking dependencies..."
command -v ffmpeg >/dev/null 2>&1 && echo "  ffmpeg: OK" || echo "  ffmpeg: MISSING (install via: brew install ffmpeg)"
command -v ffprobe >/dev/null 2>&1 && echo "  ffprobe: OK" || echo "  ffprobe: MISSING (included with ffmpeg)"

# Check environment variables
echo ""
echo "Checking environment variables..."
[ -n "${GEMINI_API_KEY:-}" ] && echo "  GEMINI_API_KEY: set" || echo "  GEMINI_API_KEY: NOT SET (required for Gemini TTS)"
[ -n "${AZURE_STORAGE_CONNECTION_STRING:-}" ] && echo "  AZURE_STORAGE_CONNECTION_STRING: set" || echo "  AZURE_STORAGE_CONNECTION_STRING: NOT SET (required for publishing)"
[ -n "${AZURE_API_KEY:-}" ] && echo "  AZURE_API_KEY: set" || echo "  AZURE_API_KEY: not set (optional, for Azure OpenAI TTS fallback)"

echo ""
echo "Setup complete! Edit $CONFIG_FILE and set required environment variables."
echo "Then use '/podcast <url>' in Claude Code to generate your first episode."
