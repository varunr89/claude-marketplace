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

2. **Normalize the phone number** to E.164 format (+1XXXXXXXXXX). Strip parens, dashes, spaces. If 10 digits, prepend +1. If 11 digits starting with 1, prepend +.

3. **Generate voicemail message** from the purpose. Keep it under 30 seconds spoken. Always include the callback number from config.json `transfer_to` field. Be professional and concise.

4. **Generate IVR navigation goal** from the purpose (e.g., "reach enrollment department", "reach scheduling", "reach pharmacy")

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
${CLAUDE_PLUGIN_ROOT}/server/.venv/bin/python ${CLAUDE_PLUGIN_ROOT}/scripts/generate_tts.py ${CLAUDE_PLUGIN_ROOT}/config.json "voicemail message text here"
```
Capture the output path (last line of stdout). If this fails, note that Twilio Say will be used as fallback.

7. **Start ngrok tunnel** (if not already running):
```bash
${CLAUDE_PLUGIN_ROOT}/server/.venv/bin/python -c "
from pyngrok import ngrok, conf
import json
with open('${CLAUDE_PLUGIN_ROOT}/config.json') as f:
    cfg = json.load(f)
conf.get_default().auth_token = cfg['ngrok_auth_token']
tunnel = ngrok.connect(cfg.get('pipecat_port', 8765), 'http')
print(tunnel.public_url)
" &
```
Capture the public URL from stdout.

8. **Start the Pipecat call server** (if not already running):
```bash
CALL_CONFIG_PATH=${CLAUDE_PLUGIN_ROOT}/config.json \
VOICEMAIL_AUDIO=<path_from_step_6> \
PUBLIC_URL=<ngrok_url_from_step_7> \
${CLAUDE_PLUGIN_ROOT}/server/.venv/bin/python ${CLAUDE_PLUGIN_ROOT}/server/call_server.py &
```

9. **Wait for health check** (retry up to 10 times with 1s delay):
```bash
curl -sf http://localhost:8765/health
```

10. **Start the call:**
```bash
curl -s -X POST http://localhost:8765/call/start \
  -H 'Content-Type: application/json' \
  -d '{"to": "+1XXXXXXXXXX", "voicemail_audio": "/path/to/audio.wav"}'
```

11. **Poll for events** in a loop (every 2 seconds):
```bash
curl -s "http://localhost:8765/call/events?after=<last_event_id>"
```

Process each event:
- `state_change` → display status update
- `amd_result` with `result: "machine"` → wait for voicemail state, then send play
- `amd_result` with `result: "human"` → watch for transcript events
- `transcript` → analyze: is it an IVR menu? If yes, decide digit and send DTMF. If it sounds like a human greeting, send transfer.
- Terminal state (`completed` or `failed`) → stop polling

12. **For IVR navigation:** Read the transcript text. Determine which menu option matches the navigation goal. Send DTMF:
```bash
curl -s -X POST http://localhost:8765/call/dtmf \
  -H 'Content-Type: application/json' -d '{"digits": "1"}'
```
Track DTMF attempts (max 3). If stuck after 3, play voicemail and hang up.

13. **For voicemail playback:**
```bash
curl -s -X POST http://localhost:8765/call/play \
  -H 'Content-Type: application/json' -d '{"file": "/path/to/audio.wav"}'
```

14. **For human pickup -- warm transfer:**
```bash
curl -s -X POST http://localhost:8765/call/transfer \
  -H 'Content-Type: application/json' \
  -d '{"to": "+16083207152", "whisper": "Context about who answered"}'
```

15. **After call ends**, create call log at `call-logs/YYYY-MM-DD-xxxx<last4>.md`:
```markdown
# Call: (360) ***-5437
**Date:** 2026-03-23 2:34 PM
**Purpose:** Ask about enrollment for 2.5yo
**Outcome:** Voicemail left
**Duration:** 45 seconds
**State History:** requested → dialing → ringing → answered → voicemail → leaving_msg → completed

## Transcript
[timestamps and events from the call]

## Voicemail Message Left
"The message text that was played"
```

16. **Cleanup:** Stop the server process when done.

## Display during call

Show real-time status updates in the terminal:
```
Dialing (360) 676-5437...
Ringing...
Answered -- AMD detecting...
Machine detected (voicemail)
Playing voicemail message...
Message left. Hanging up.

Voicemail left at (360) ***-5437 (42s)
Log saved to call-logs/2026-03-23-xxxx5437.md
```

## Error handling

- If config.json is missing: tell user to run setup.sh
- If TTS generation fails: note fallback to Twilio Say verb
- If server fails to start: show the error
- If call fails: show the Twilio error message
- Always write a call log, even on failure
