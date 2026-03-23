# /call Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Claude Code plugin that makes automated phone calls -- leaving voicemails, navigating IVR menus, and warm-transferring humans to the user's phone.

**Architecture:** Claude Code (brain) communicates with a Pipecat FastAPI server (voice worker) over localhost HTTP. Pipecat handles Twilio WebSocket Media Streams for real-time audio. Azure OpenAI provides pre-call TTS and in-call STT. Twilio handles PSTN, AMD, and DTMF.

**Tech Stack:** Python 3.12, Pipecat (`pipecat-ai[twilio]`), FastAPI, Twilio REST + Media Streams, Azure OpenAI (gpt-4o-mini-transcribe, tts-hd), pyngrok, uvicorn

**Plugin root:** `~/.claude/plugins/marketplaces/varunr-marketplace/plugins/call/`
**Spec:** `skills/call/references/design-spec.md`

---

## File Structure

```
plugins/call/
├── .claude-plugin/plugin.json        # Already exists
├── skills/call/SKILL.md              # Already exists
├── scripts/
│   ├── setup.sh                      # One-time setup: venv, deps, config
│   └── generate_tts.py               # Pre-generate voicemail .wav via Azure TTS
├── server/
│   ├── requirements.txt              # Python deps for the Pipecat server
│   ├── call_server.py                # FastAPI app: /dialout, /twiml, /ws, /call/*
│   ├── call_state.py                 # Call state machine + event queue
│   └── twilio_handler.py             # Twilio webhook signature validation
├── commands/
│   └── call.md                       # /call command definition
├── tests/
│   ├── platform.json                 # Already exists
│   ├── test_phone_utils.py           # Phone number normalization tests
│   ├── test_call_state.py            # State machine tests
│   └── test_config.py                # Config validation tests
├── audio/                            # Cached .wav files (gitignored)
├── config.json                       # API keys (gitignored)
└── .gitignore
```

---

### Task 1: Setup Script & Dependencies

**Files:**
- Create: `plugins/call/scripts/setup.sh`
- Create: `plugins/call/server/requirements.txt`
- Create: `plugins/call/.gitignore`

- [ ] **Step 1: Create .gitignore**

```bash
cat > ~/.claude/plugins/marketplaces/varunr-marketplace/plugins/call/.gitignore << 'GITIGNORE'
config.json
audio/*.wav
server/.venv/
__pycache__/
*.pyc
GITIGNORE
```

- [ ] **Step 2: Create requirements.txt**

```bash
cat > ~/.claude/plugins/marketplaces/varunr-marketplace/plugins/call/server/requirements.txt << 'REQS'
pipecat-ai[twilio,silero]==0.0.74
fastapi==0.115.12
uvicorn[standard]==0.34.2
openai==1.82.0
twilio==9.6.1
pyngrok==7.2.4
REQS
```

- [ ] **Step 3: Create setup.sh**

```bash
cat > ~/.claude/plugins/marketplaces/varunr-marketplace/plugins/call/scripts/setup.sh << 'SETUP'
#!/usr/bin/env bash
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$PLUGIN_ROOT/server/.venv"
CONFIG="$PLUGIN_ROOT/config.json"

echo "=== /call plugin setup ==="

# Create venv
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating Python venv..."
    python3 -m venv "$VENV_DIR"
fi

echo "Installing dependencies..."
"$VENV_DIR/bin/pip" install -q -r "$PLUGIN_ROOT/server/requirements.txt"

# Config
if [ -f "$CONFIG" ]; then
    echo "Config already exists at $CONFIG"
    exit 0
fi

echo ""
echo "--- Twilio ---"
read -p "Account SID: " TWILIO_SID
read -p "Auth Token: " TWILIO_TOKEN
read -p "Phone Number (E.164, e.g. +12065551234): " TWILIO_FROM

echo ""
echo "--- Azure OpenAI ---"
read -p "Endpoint (e.g. https://xxx.openai.azure.com): " AZURE_ENDPOINT
read -p "API Key: " AZURE_KEY

echo ""
echo "--- Your Phone ---"
read -p "Transfer-to number (E.164, e.g. +16083207152): " TRANSFER_TO

echo ""
echo "--- ngrok ---"
read -p "Auth token: " NGROK_TOKEN

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
echo "Setup complete. You can now use /call."
SETUP
chmod +x ~/.claude/plugins/marketplaces/varunr-marketplace/plugins/call/scripts/setup.sh
```

- [ ] **Step 4: Run setup to create venv and verify deps install**

Run: `~/.claude/plugins/marketplaces/varunr-marketplace/plugins/call/scripts/setup.sh`
Expected: venv created, deps installed, config prompts shown

- [ ] **Step 5: Commit**

```bash
cd ~/.claude/plugins/marketplaces/varunr-marketplace
git add plugins/call/.gitignore plugins/call/scripts/setup.sh plugins/call/server/requirements.txt
git commit -m "feat(call): add setup script and dependencies"
```

---

### Task 2: Config Validation & Phone Utils

**Files:**
- Create: `plugins/call/server/config.py`
- Create: `plugins/call/server/phone_utils.py`
- Create: `plugins/call/tests/test_config.py`
- Create: `plugins/call/tests/test_phone_utils.py`

- [ ] **Step 1: Write failing tests for phone number normalization**

```python
# plugins/call/tests/test_phone_utils.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))
from phone_utils import normalize_phone, redact_phone

def test_ten_digit():
    assert normalize_phone("3606765437") == "+13606765437"

def test_with_country_code():
    assert normalize_phone("+13606765437") == "+13606765437"

def test_with_parens():
    assert normalize_phone("(360) 676-5437") == "+13606765437"

def test_with_dashes():
    assert normalize_phone("360-676-5437") == "+13606765437"

def test_eleven_digit():
    assert normalize_phone("13606765437") == "+13606765437"

def test_invalid_short():
    try:
        normalize_phone("12345")
        assert False, "Should have raised"
    except ValueError:
        pass

def test_redact():
    assert redact_phone("+13606765437") == "(360) ***-5437"

def test_redact_filename():
    assert redact_phone("+13606765437", for_filename=True) == "xxxx5437"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/.claude/plugins/marketplaces/varunr-marketplace && plugins/call/server/.venv/bin/python -m pytest plugins/call/tests/test_phone_utils.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement phone_utils.py**

```python
# plugins/call/server/phone_utils.py
import re

def normalize_phone(number: str) -> str:
    digits = re.sub(r'[^\d+]', '', number)
    if digits.startswith('+'):
        if len(digits) == 12 and digits.startswith('+1'):
            return digits
        raise ValueError(f"Unsupported country code: {digits}")
    if len(digits) == 11 and digits.startswith('1'):
        return f"+{digits}"
    if len(digits) == 10:
        return f"+1{digits}"
    raise ValueError(f"Invalid phone number: {number} ({len(digits)} digits)")

def redact_phone(e164: str, for_filename: bool = False) -> str:
    if for_filename:
        return f"xxxx{e164[-4:]}"
    area = e164[2:5]
    last4 = e164[-4:]
    return f"({area}) ***-{last4}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/.claude/plugins/marketplaces/varunr-marketplace && plugins/call/server/.venv/bin/python -m pytest plugins/call/tests/test_phone_utils.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Write failing tests for config validation**

```python
# plugins/call/tests/test_config.py
import sys, os, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))
from config import load_config, validate_config, ConfigError

def test_missing_file():
    try:
        load_config("/nonexistent/config.json")
        assert False
    except ConfigError as e:
        assert "not found" in str(e).lower()

def test_valid_config():
    cfg = {
        "twilio": {"account_sid": "AC123", "auth_token": "tok", "from_number": "+11234567890"},
        "azure_openai": {"endpoint": "https://x.openai.azure.com", "api_key": "k", "tts_model": "tts-hd", "tts_voice": "onyx", "stt_model": "gpt-4o-mini-transcribe"},
        "transfer_to": "+16083207152",
        "ngrok_auth_token": "ngrok_tok",
        "pipecat_port": 8765
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(cfg, f)
        f.flush()
        result = load_config(f.name)
        assert result["twilio"]["account_sid"] == "AC123"
    os.unlink(f.name)

def test_missing_twilio_key():
    cfg = {"twilio": {"account_sid": "AC123"}, "azure_openai": {}, "transfer_to": "", "ngrok_auth_token": "", "pipecat_port": 8765}
    try:
        validate_config(cfg)
        assert False
    except ConfigError as e:
        assert "auth_token" in str(e)
```

- [ ] **Step 6: Implement config.py**

```python
# plugins/call/server/config.py
import json
import os

class ConfigError(Exception):
    pass

REQUIRED_KEYS = {
    "twilio": ["account_sid", "auth_token", "from_number"],
    "azure_openai": ["endpoint", "api_key", "tts_model", "tts_voice", "stt_model"],
}

def load_config(path: str) -> dict:
    if not os.path.exists(path):
        raise ConfigError(
            f"Config not found at {path}.\n"
            "Run the setup script first:\n"
            "  bash ~/.claude/plugins/marketplaces/varunr-marketplace/plugins/call/scripts/setup.sh"
        )
    with open(path) as f:
        cfg = json.load(f)
    validate_config(cfg)
    return cfg

def validate_config(cfg: dict) -> None:
    for section, keys in REQUIRED_KEYS.items():
        if section not in cfg:
            raise ConfigError(f"Missing config section: {section}")
        for key in keys:
            if key not in cfg[section] or not cfg[section][key]:
                raise ConfigError(f"Missing config key: {section}.{key}")
    if "transfer_to" not in cfg or not cfg["transfer_to"]:
        raise ConfigError("Missing config key: transfer_to")
    if "ngrok_auth_token" not in cfg or not cfg["ngrok_auth_token"]:
        raise ConfigError("Missing config key: ngrok_auth_token")
```

- [ ] **Step 7: Run all tests**

Run: `cd ~/.claude/plugins/marketplaces/varunr-marketplace && plugins/call/server/.venv/bin/python -m pytest plugins/call/tests/ -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
cd ~/.claude/plugins/marketplaces/varunr-marketplace
git add plugins/call/server/phone_utils.py plugins/call/server/config.py plugins/call/tests/
git commit -m "feat(call): add config validation and phone number utils"
```

---

### Task 3: Call State Machine

**Files:**
- Create: `plugins/call/server/call_state.py`
- Create: `plugins/call/tests/test_call_state.py`

- [ ] **Step 1: Write failing tests for state machine**

```python
# plugins/call/tests/test_call_state.py
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))
from call_state import CallState, CallEvent, InvalidTransition

def test_initial_state():
    cs = CallState()
    assert cs.state == "requested"

def test_valid_transition():
    cs = CallState()
    cs.transition("dialing")
    assert cs.state == "dialing"

def test_invalid_transition():
    cs = CallState()
    try:
        cs.transition("completed")
        assert False
    except InvalidTransition:
        pass

def test_full_voicemail_flow():
    cs = CallState()
    cs.transition("dialing")
    cs.transition("ringing")
    cs.transition("answered")
    cs.transition("voicemail")
    cs.transition("leaving_msg")
    cs.transition("completed", reason="voicemail_left")
    assert cs.state == "completed"
    assert cs.reason == "voicemail_left"
    assert cs.is_terminal()

def test_event_queue():
    cs = CallState()
    cs.add_event("amd_result", {"result": "human"})
    cs.add_event("transcript", {"text": "Press 1 for enrollment"})
    events = cs.get_events(after=0)
    assert len(events) == 2
    assert events[0]["event"] == "amd_result"

def test_event_cursor():
    cs = CallState()
    cs.add_event("amd_result", {"result": "human"})
    cs.add_event("transcript", {"text": "Hello"})
    events = cs.get_events(after=1)
    assert len(events) == 1
    assert events[0]["event"] == "transcript"

def test_state_history():
    cs = CallState()
    cs.transition("dialing")
    cs.transition("ringing")
    assert cs.history == ["requested", "dialing", "ringing"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `plugins/call/server/.venv/bin/python -m pytest plugins/call/tests/test_call_state.py -v`
Expected: FAIL

- [ ] **Step 3: Implement call_state.py**

```python
# plugins/call/server/call_state.py
import time
from threading import Lock

VALID_TRANSITIONS = {
    "requested": ["dialing", "failed"],
    "dialing": ["ringing", "failed"],
    "ringing": ["answered", "completed", "failed"],
    "answered": ["voicemail", "ivr_nav", "human", "completed", "failed"],
    "voicemail": ["leaving_msg", "failed"],
    "leaving_msg": ["completed", "failed"],
    "ivr_nav": ["navigating", "voicemail", "human", "completed", "failed"],
    "navigating": ["ivr_nav", "voicemail", "human", "completed", "failed"],
    "human": ["transferring", "completed", "failed"],
    "transferring": ["completed", "failed"],
    "completed": [],
    "failed": [],
    "canceled": [],
}

class InvalidTransition(Exception):
    pass

class CallEvent:
    def __init__(self, event_id: int, event: str, data: dict):
        self.event_id = event_id
        self.event = event
        self.data = data
        self.ts = time.time()

    def to_dict(self) -> dict:
        return {"id": self.event_id, "event": self.event, "ts": self.ts, **self.data}

class CallState:
    def __init__(self):
        self.state = "requested"
        self.reason = None
        self.duration = None
        self.history = ["requested"]
        self._events: list[CallEvent] = []
        self._event_counter = 0
        self._lock = Lock()

    def transition(self, new_state: str, reason: str = None, duration: float = None):
        if new_state not in VALID_TRANSITIONS.get(self.state, []):
            raise InvalidTransition(f"Cannot go from '{self.state}' to '{new_state}'")
        self.state = new_state
        self.history.append(new_state)
        if reason:
            self.reason = reason
        if duration is not None:
            self.duration = duration
        self.add_event("state_change", {"state": new_state, "reason": reason})

    def is_terminal(self) -> bool:
        return self.state in ("completed", "failed", "canceled")

    def add_event(self, event: str, data: dict = None):
        with self._lock:
            self._event_counter += 1
            self._events.append(CallEvent(self._event_counter, event, data or {}))

    def get_events(self, after: int = 0) -> list[dict]:
        with self._lock:
            return [e.to_dict() for e in self._events if e.event_id > after]

    def state_history_str(self) -> str:
        return " → ".join(self.history)
```

- [ ] **Step 4: Run tests**

Run: `plugins/call/server/.venv/bin/python -m pytest plugins/call/tests/test_call_state.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/call/server/call_state.py plugins/call/tests/test_call_state.py
git commit -m "feat(call): add call state machine with event queue"
```

---

### Task 4: TTS Audio Generation Script

**Files:**
- Create: `plugins/call/scripts/generate_tts.py`
- Create: `plugins/call/audio/` (directory, gitignored)

- [ ] **Step 1: Implement generate_tts.py**

```python
# plugins/call/scripts/generate_tts.py
"""Generate voicemail .wav file via Azure OpenAI TTS HD."""
import hashlib
import json
import os
import sys
from pathlib import Path

def generate_tts(config_path: str, text: str, output_dir: str) -> str:
    """Generate TTS audio, return path to .wav file. Uses content-hash caching."""
    from openai import AzureOpenAI

    with open(config_path) as f:
        cfg = json.load(f)

    az = cfg["azure_openai"]
    content_hash = hashlib.sha256(text.encode()).hexdigest()[:12]
    output_path = os.path.join(output_dir, f"vm_{content_hash}.wav")

    if os.path.exists(output_path):
        print(f"Using cached audio: {output_path}", file=sys.stderr)
        return output_path

    client = AzureOpenAI(
        azure_endpoint=az["endpoint"],
        api_key=az["api_key"],
        api_version="2025-01-01",
    )

    response = client.audio.speech.create(
        model=az["tts_model"],
        voice=az["tts_voice"],
        input=text,
        response_format="wav",
    )

    os.makedirs(output_dir, exist_ok=True)
    response.write_to_file(output_path)
    print(f"Generated audio: {output_path}", file=sys.stderr)
    return output_path

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: generate_tts.py <config_path> <text>", file=sys.stderr)
        sys.exit(1)

    plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    audio_dir = os.path.join(plugin_root, "audio")
    path = generate_tts(sys.argv[1], sys.argv[2], audio_dir)
    print(path)
```

- [ ] **Step 2: Verify script loads without errors**

Run: `plugins/call/server/.venv/bin/python -c "import plugins.call.scripts.generate_tts" 2>&1 || plugins/call/server/.venv/bin/python plugins/call/scripts/generate_tts.py --help 2>&1 || echo "Module loads checked"`
Expected: No import errors (actual TTS call requires valid Azure creds)

- [ ] **Step 3: Commit**

```bash
git add plugins/call/scripts/generate_tts.py
git commit -m "feat(call): add Azure OpenAI TTS HD audio generation"
```

---

### Task 5: Pipecat Call Server -- Core FastAPI App

**Files:**
- Create: `plugins/call/server/call_server.py`
- Create: `plugins/call/server/twilio_handler.py`

- [ ] **Step 1: Implement twilio_handler.py**

```python
# plugins/call/server/twilio_handler.py
"""Twilio webhook signature validation."""
from twilio.request_validator import RequestValidator

class TwilioValidator:
    def __init__(self, auth_token: str):
        self.validator = RequestValidator(auth_token)

    def validate(self, url: str, params: dict, signature: str) -> bool:
        return self.validator.validate(url, params, signature)
```

- [ ] **Step 2: Implement call_server.py -- the FastAPI + Pipecat server**

```python
# plugins/call/server/call_server.py
"""Pipecat call server -- FastAPI app with Twilio WebSocket transport."""
import asyncio
import json
import os
import sys
import wave
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, WebSocket, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import Connect, Stream, VoiceResponse

from call_state import CallState
from config import load_config, ConfigError
from twilio_handler import TwilioValidator

# --- Globals ---
call_state: CallState | None = None
twilio_client: TwilioClient | None = None
twilio_validator: TwilioValidator | None = None
config: dict = {}
active_call_sid: str | None = None
active_task = None
PUBLIC_URL: str = ""

# --- Models ---
class StartCallRequest(BaseModel):
    to: str
    voicemail_audio: str | None = None

class DTMFRequest(BaseModel):
    digits: str

class PlayRequest(BaseModel):
    file: str

class TransferRequest(BaseModel):
    to: str
    whisper: str = ""

# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global config, twilio_client, twilio_validator, PUBLIC_URL
    config_path = os.environ.get("CALL_CONFIG_PATH", "")
    if not config_path:
        raise RuntimeError("CALL_CONFIG_PATH env var required")
    config = load_config(config_path)
    twilio_client = TwilioClient(config["twilio"]["account_sid"], config["twilio"]["auth_token"])
    twilio_validator = TwilioValidator(config["twilio"]["auth_token"])
    PUBLIC_URL = os.environ.get("PUBLIC_URL", "")
    yield

app = FastAPI(lifespan=lifespan)

# --- Health ---
@app.get("/health")
async def health():
    return {"status": "ok", "call_active": call_state is not None and not call_state.is_terminal()}

# --- Start Call ---
@app.post("/call/start")
async def start_call(req: StartCallRequest):
    global call_state, active_call_sid

    if call_state and not call_state.is_terminal():
        raise HTTPException(400, "A call is already active")

    call_state = CallState()
    call_state.transition("dialing")

    twiml_url = f"{PUBLIC_URL}/twiml"
    status_url = f"{PUBLIC_URL}/call/status"

    try:
        call = twilio_client.calls.create(
            to=req.to,
            from_=config["twilio"]["from_number"],
            url=twiml_url,
            method="POST",
            machine_detection="DetectMessageEnd",
            async_amd=True,
            async_amd_status_callback=f"{PUBLIC_URL}/call/amd",
            async_amd_status_callback_method="POST",
            status_callback=status_url,
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            status_callback_method="POST",
        )
        active_call_sid = call.sid
        call_state.add_event("call_started", {"call_sid": call.sid})
        return {"call_sid": call.sid, "status": "dialing"}
    except Exception as e:
        call_state.transition("failed", reason="error")
        call_state.add_event("error", {"message": str(e)})
        raise HTTPException(500, str(e))

# --- TwiML (Twilio calls this to get instructions) ---
@app.post("/twiml")
async def get_twiml(request: Request):
    form_data = await request.form()
    ws_url = PUBLIC_URL.replace("https://", "wss://").replace("http://", "ws://") + "/ws"

    response = VoiceResponse()
    connect = Connect()
    stream = Stream(url=ws_url)
    stream.parameter(name="voicemail_audio", value=os.environ.get("VOICEMAIL_AUDIO", ""))
    connect.append(stream)
    response.append(connect)
    response.pause(length=300)  # Keep call alive up to 5 min

    return HTMLResponse(content=str(response), media_type="application/xml")

# --- AMD Result Callback ---
@app.post("/call/amd")
async def amd_callback(request: Request):
    form_data = await request.form()
    amd_status = form_data.get("AnsweredBy", "unknown")

    if call_state:
        result = "machine" if "machine" in amd_status.lower() else "human"
        call_state.add_event("amd_result", {"result": result, "raw": amd_status})

        if result == "machine":
            call_state.transition("answered")
            call_state.transition("voicemail")
        else:
            call_state.transition("answered")

    return JSONResponse({"status": "ok"})

# --- Call Status Callback ---
@app.post("/call/status")
async def status_callback(request: Request):
    form_data = await request.form()
    status = form_data.get("CallStatus", "")

    if call_state:
        if status == "ringing" and call_state.state == "dialing":
            call_state.transition("ringing")
        elif status == "busy":
            call_state.transition("completed", reason="busy")
        elif status == "no-answer":
            call_state.transition("completed", reason="no_answer")
        elif status == "failed":
            call_state.transition("failed", reason="error")
        elif status == "completed" and not call_state.is_terminal():
            call_state.transition("completed", reason="call_ended")

        call_state.add_event("twilio_status", {"status": status})

    return JSONResponse({"status": "ok"})

# --- Events (Claude Code polls this) ---
@app.get("/call/events")
async def get_events(after: int = 0):
    if not call_state:
        return {"events": [], "state": None}
    return {
        "events": call_state.get_events(after=after),
        "state": call_state.state,
        "reason": call_state.reason,
    }

# --- DTMF ---
@app.post("/call/dtmf")
async def send_dtmf(req: DTMFRequest):
    if not active_call_sid:
        raise HTTPException(400, "No active call")
    try:
        twilio_client.calls(active_call_sid).update(
            twiml=f'<Response><Play digits="{req.digits}"/><Pause length="300"/></Response>'
        )
        if call_state:
            call_state.add_event("dtmf_sent", {"digits": req.digits})
        return {"status": "sent", "digits": req.digits}
    except Exception as e:
        raise HTTPException(500, str(e))

# --- Play Audio ---
@app.post("/call/play")
async def play_audio(req: PlayRequest):
    if not active_call_sid:
        raise HTTPException(400, "No active call")
    try:
        # Upload audio to Twilio and play it
        file_url = f"{PUBLIC_URL}/audio/{os.path.basename(req.file)}"
        twilio_client.calls(active_call_sid).update(
            twiml=f'<Response><Play>{file_url}</Play><Pause length="2"/><Hangup/></Response>'
        )
        if call_state:
            call_state.transition("leaving_msg")
            call_state.add_event("playing_audio", {"file": req.file})
        return {"status": "playing"}
    except Exception as e:
        raise HTTPException(500, str(e))

# --- Serve audio files ---
from fastapi.responses import FileResponse

@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    filepath = os.path.join(plugin_root, "audio", filename)
    if not os.path.exists(filepath):
        raise HTTPException(404, "Audio file not found")
    return FileResponse(filepath, media_type="audio/wav")

# --- Warm Transfer ---
@app.post("/call/transfer")
async def warm_transfer(req: TransferRequest):
    if not active_call_sid:
        raise HTTPException(400, "No active call")
    try:
        # Put center on hold, call user's phone with whisper
        twiml = f'''<Response>
            <Say>Please hold one moment while I connect you.</Say>
            <Dial timeout="30" callerId="{config['twilio']['from_number']}">
                <Number url="{PUBLIC_URL}/whisper?msg={req.whisper}">{req.to}</Number>
            </Dial>
            <Say>I apologize, I was unable to connect. I will call back. Goodbye.</Say>
            <Hangup/>
        </Response>'''
        twilio_client.calls(active_call_sid).update(twiml=twiml)
        if call_state:
            call_state.transition("human")
            call_state.transition("transferring")
            call_state.add_event("transfer_initiated", {"to": req.to})
        return {"status": "transferring"}
    except Exception as e:
        raise HTTPException(500, str(e))

# --- Whisper (plays context to user before bridging) ---
@app.post("/whisper")
async def whisper(request: Request):
    form_data = await request.form()
    msg = request.query_params.get("msg", "Incoming call")
    response = VoiceResponse()
    response.say(f"Connecting you now. Context: {msg}")
    response.pause(length=1)
    return HTMLResponse(content=str(response), media_type="application/xml")

# --- Hangup ---
@app.post("/call/hangup")
async def hangup():
    if active_call_sid:
        try:
            twilio_client.calls(active_call_sid).update(status="completed")
        except Exception:
            pass
    if call_state and not call_state.is_terminal():
        call_state.transition("completed", reason="hangup")
    return {"status": "hung_up"}

# --- WebSocket (Pipecat pipeline for STT) ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handle Twilio Media Stream WebSocket for real-time STT."""
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineParams, PipelineTask
    from pipecat.runner.types import WebSocketRunnerArguments
    from pipecat.runner.utils import parse_telephony_websocket
    from pipecat.serializers.twilio import TwilioFrameSerializer
    from pipecat.services.openai.stt import OpenAISTTService
    from pipecat.transports.websocket.fastapi import (
        FastAPIWebsocketParams,
        FastAPIWebsocketTransport,
    )
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import (
        LLMContextAggregatorPair,
        LLMUserAggregatorParams,
    )

    await websocket.accept()

    transport_type, call_data = await parse_telephony_websocket(websocket)

    serializer = TwilioFrameSerializer(
        stream_sid=call_data["stream_id"],
        call_sid=call_data.get("call_id"),
        account_sid=config["twilio"]["account_sid"],
        auth_token=config["twilio"]["auth_token"],
    )

    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            serializer=serializer,
        ),
    )

    az = config["azure_openai"]
    stt = OpenAISTTService(
        api_key=az["api_key"],
        base_url=f"{az['endpoint']}/openai",
        settings=OpenAISTTService.Settings(model=az["stt_model"]),
    )

    # Simple pipeline: audio in → STT → post transcripts to event queue
    class TranscriptForwarder:
        """Receives transcription frames and posts them to call_state events."""
        async def process_frame(self, frame, direction):
            from pipecat.frames.frames import TranscriptionFrame
            if isinstance(frame, TranscriptionFrame) and frame.text.strip():
                if call_state:
                    call_state.add_event("transcript", {"text": frame.text})

    pipeline = Pipeline([
        transport.input(),
        stt,
    ])

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=8000,
            audio_out_sample_rate=8000,
        ),
    )

    @transport.event_handler("on_client_disconnected")
    async def on_disconnect(transport, client):
        await task.cancel()

    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)

# --- Main ---
if __name__ == "__main__":
    port = int(os.environ.get("PIPECAT_PORT", "8765"))
    uvicorn.run(app, host="127.0.0.1", port=port)
```

- [ ] **Step 3: Verify server imports load**

Run: `cd plugins/call/server && ../.venv/bin/python -c "from call_server import app; print('Server imports OK')"`
Expected: "Server imports OK" (may warn about missing env vars, that's fine)

- [ ] **Step 4: Commit**

```bash
git add plugins/call/server/call_server.py plugins/call/server/twilio_handler.py
git commit -m "feat(call): add Pipecat FastAPI call server with Twilio integration"
```

---

### Task 6: /call Command Definition

**Files:**
- Create: `plugins/call/commands/call.md`

- [ ] **Step 1: Create the command markdown**

```markdown
---
description: "Make a phone call -- leave voicemail, navigate IVR, or warm-transfer to your phone"
argument-hint: "<phone_number> <purpose>"
allowed-tools:
  - Bash
  - Read
  - Write
---

# /call

Make an automated phone call.

## Usage

```
/call <phone_number> <purpose in natural language>
```

## What to do with $ARGUMENTS

Parse the arguments: first token is the phone number, rest is the purpose.

1. **Validate config exists** at `${CLAUDE_PLUGIN_ROOT}/config.json`. If missing, tell user to run: `bash ${CLAUDE_PLUGIN_ROOT}/scripts/setup.sh`

2. **Normalize the phone number** to E.164 format (+1XXXXXXXXXX)

3. **Generate voicemail message** from the purpose. Keep it under 30 seconds spoken. Always include the callback number from config.json `transfer_to` field.

4. **Generate IVR navigation goal** from the purpose (e.g., "reach enrollment department")

5. **Show confirmation:**
   ```
   Ready to call (360) 676-5437

   Voicemail message:
     "Hi, this is Varun Ramesh calling about..."

   IVR goal: Reach enrollment/admissions

   Proceed? (y/n)
   ```

6. **On confirm, generate TTS audio:**
   ```bash
   ${CLAUDE_PLUGIN_ROOT}/server/.venv/bin/python ${CLAUDE_PLUGIN_ROOT}/scripts/generate_tts.py ${CLAUDE_PLUGIN_ROOT}/config.json "voicemail message text"
   ```
   Capture the output path (stdout).

7. **Start the Pipecat server** (if not running):
   ```bash
   CALL_CONFIG_PATH=${CLAUDE_PLUGIN_ROOT}/config.json \
   VOICEMAIL_AUDIO=<path_from_step_6> \
   PUBLIC_URL=<ngrok_url> \
   ${CLAUDE_PLUGIN_ROOT}/server/.venv/bin/python ${CLAUDE_PLUGIN_ROOT}/server/call_server.py &
   ```
   Start ngrok first: `ngrok http 8765` and capture the public URL.

8. **Wait for health check:** `curl -s http://localhost:8765/health`

9. **Start the call:**
   ```bash
   curl -s -X POST http://localhost:8765/call/start \
     -H 'Content-Type: application/json' \
     -d '{"to": "+13606765437", "voicemail_audio": "/path/to/audio.wav"}'
   ```

10. **Poll for events** in a loop:
    ```bash
    curl -s "http://localhost:8765/call/events?after=0"
    ```
    Process each event:
    - `amd_result` with `result: "machine"` → wait, then send play command
    - `amd_result` with `result: "human"` → watch for transcripts
    - `transcript` → decide: IVR menu? Send DTMF. Human? Send transfer.
    - `state_change` to terminal state → stop polling

11. **For IVR navigation:** Read the transcript. Decide which digit to press. Send:
    ```bash
    curl -s -X POST http://localhost:8765/call/dtmf \
      -H 'Content-Type: application/json' -d '{"digits": "1"}'
    ```
    Max 3 DTMF attempts. If stuck, play voicemail and hang up.

12. **For voicemail:** Send play command:
    ```bash
    curl -s -X POST http://localhost:8765/call/play \
      -H 'Content-Type: application/json' -d '{"file": "/path/to/audio.wav"}'
    ```

13. **For human pickup:** Send transfer:
    ```bash
    curl -s -X POST http://localhost:8765/call/transfer \
      -H 'Content-Type: application/json' \
      -d '{"to": "+16083207152", "whisper": "Little Darling School, enrollment dept"}'
    ```

14. **After call ends**, write call log to `call-logs/` in current working directory.

15. **Stop the server** when done.

## Display during call

Show real-time status updates:
```
Dialing (360) 676-5437...
Ringing...
Answered -- AMD detecting...
Machine detected (voicemail)
Playing voicemail message...
Message left. Hanging up.

✓ Voicemail left at (360) ***-5437 (42s)
Log saved to call-logs/2026-03-23-xxxx5437.md
```
```

- [ ] **Step 2: Commit**

```bash
git add plugins/call/commands/call.md
git commit -m "feat(call): add /call command definition"
```

---

### Task 7: Integration Test with Ngrok

**Files:** No new files -- manual verification

- [ ] **Step 1: Run setup.sh with real credentials**

Run: `bash ~/.claude/plugins/marketplaces/varunr-marketplace/plugins/call/scripts/setup.sh`
Enter real Twilio, Azure, ngrok credentials when prompted.

- [ ] **Step 2: Start ngrok**

Run: `ngrok http 8765` (in a separate terminal or background)
Note the public URL (e.g., `https://abc123.ngrok.io`)

- [ ] **Step 3: Start the call server**

```bash
CALL_CONFIG_PATH=~/.claude/plugins/marketplaces/varunr-marketplace/plugins/call/config.json \
PUBLIC_URL=https://abc123.ngrok.io \
~/.claude/plugins/marketplaces/varunr-marketplace/plugins/call/server/.venv/bin/python \
~/.claude/plugins/marketplaces/varunr-marketplace/plugins/call/server/call_server.py
```

- [ ] **Step 4: Verify health check**

Run: `curl -s http://localhost:8765/health`
Expected: `{"status":"ok","call_active":false}`

- [ ] **Step 5: Test a real call to your own phone**

```bash
curl -s -X POST http://localhost:8765/call/start \
  -H 'Content-Type: application/json' \
  -d '{"to": "+16083207152"}'
```
Expected: Your phone rings. Check `/call/events` for AMD result.

- [ ] **Step 6: Commit final state**

```bash
git add -A plugins/call/
git commit -m "feat(call): complete core implementation (phases 1-4)"
```

---

## Execution Order

```
Task 1 (Setup)         → venv, deps, config
Task 2 (Config+Utils)  → validation, phone normalization, tests
Task 3 (State Machine) → call states, event queue, tests
Task 4 (TTS Script)    → Azure OpenAI audio generation
Task 5 (Call Server)    → FastAPI + Pipecat + Twilio (the big one)
Task 6 (Command)        → /call command definition
Task 7 (Integration)    → real call test with ngrok
```

Tasks 1-3 can be done without any external service credentials. Task 4 needs Azure creds. Tasks 5-7 need all credentials.
