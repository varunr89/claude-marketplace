#!/usr/bin/env bash
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$PLUGIN_ROOT/server/.venv"
CONFIG="$PLUGIN_ROOT/config.json"

echo "=== /call plugin setup ==="

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating Python venv..."
    python3 -m venv "$VENV_DIR"
fi

echo "Installing dependencies..."
"$VENV_DIR/bin/pip" install -q -r "$PLUGIN_ROOT/server/requirements.txt"

if [ -f "$CONFIG" ]; then
    echo "Config already exists at $CONFIG"
    exit 0
fi

echo ""
echo "--- Twilio ---"
read -rp "Account SID: " TWILIO_SID
read -rp "Auth Token: " TWILIO_TOKEN
read -rp "Phone Number (E.164, e.g. +12065551234): " TWILIO_FROM

echo ""
echo "--- Azure OpenAI ---"
read -rp "Endpoint (e.g. https://xxx.openai.azure.com): " AZURE_ENDPOINT
read -rp "API Key: " AZURE_KEY

echo ""
echo "--- Your Phone ---"
read -rp "Transfer-to number (E.164, e.g. +16083207152): " TRANSFER_TO

echo ""
echo "--- ngrok ---"
read -rp "Auth token: " NGROK_TOKEN

cat > "$CONFIG" << EOF
{
  "twilio": {
    "account_sid": "$TWILIO_SID",
    "auth_token": "$TWILIO_TOKEN",
    "from_number": "$TWILIO_FROM"
  },
  "azure_openai": {
    "endpoint": "$AZURE_ENDPOINT",
    "api_key": "$AZURE_KEY",
    "tts_model": "tts-hd",
    "tts_voice": "onyx",
    "stt_model": "gpt-4o-mini-transcribe"
  },
  "transfer_to": "$TRANSFER_TO",
  "ngrok_auth_token": "$NGROK_TOKEN",
  "pipecat_port": 8765
}
EOF

echo ""
echo "Config saved to $CONFIG"
echo "Setup complete."
