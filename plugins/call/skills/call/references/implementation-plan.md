# /call Skill Implementation Plan

Based on: `docs/specs/2026-03-23-call-skill-design.md` (v2)

## Phase 1: Foundation (Setup & Config)

### Step 1.1: Create skill directory structure
- Create `~/.claude/skills/call/`
- Create `server/` subdirectory
- Create `audio/` subdirectory
- Write `setup.sh` that creates Python venv and installs deps

### Step 1.2: Write SKILL.md
- Frontmatter with name, description, user-invocable, allowed-tools
- Invocation docs and examples
- Setup instructions for first-time users

### Step 1.3: Config management
- Write config.json template with placeholders
- Add config validation function (checks all required keys)
- Clear error messages with setup instructions when keys missing
- Ensure config.json is gitignored

### Step 1.4: Setup script
- `setup.sh`: creates venv, installs requirements, prompts for API keys
- `requirements.txt` for the Pipecat server dependencies

**Deliverable:** Running `/call` shows setup instructions if not configured, or "Ready" if configured.

---

## Phase 2: Pre-Call Pipeline

### Step 2.1: Argument parsing
- Parse phone number (first arg) and purpose (remaining text)
- Normalize phone number to E.164 (+1XXXXXXXXXX)
- Handle common formats: 3606765437, (360) 676-5437, +13606765437

### Step 2.2: Voicemail message generation
- Claude Code generates voicemail text from the purpose
- Always includes callback number from config
- Shows confirmation prompt: message + IVR goal + proceed? (y/n)

### Step 2.3: TTS audio generation
- Call Azure OpenAI TTS HD API to render voicemail .wav
- Cache in `~/.claude/skills/call/audio/` with content hash filename
- Fallback: if TTS fails, note to use Twilio `<Say>` during call

**Deliverable:** `/call 3606765437 enrollment inquiry` shows confirmation with voicemail text and generates .wav file.

---

## Phase 3: Pipecat Voice Server

### Step 3.1: FastAPI skeleton
- `call_server.py`: FastAPI app with uvicorn
- Endpoints: `/call/start`, `/call/dtmf`, `/call/play`, `/call/transfer`, `/call/hangup`, `/call/events`
- In-memory event queue for Claude Code to poll
- Health check endpoint

### Step 3.2: Twilio webhook handler
- `twilio_handler.py`: handles Twilio callback webhooks
- X-Twilio-Signature validation on every request
- AMD result webhook handler
- Call status webhook handler
- Returns TwiML for Media Streams connection

### Step 3.3: Pipecat pipeline
- Twilio Media Streams WebSocket transport (using `TwilioSerializer`)
- Audio buffer with VAD silence detection
- On silence: send buffered audio to Azure OpenAI gpt-4o-mini-transcribe
- Post transcript to event queue
- DTMF sending via Twilio REST API
- Audio playback (pre-generated .wav files)

### Step 3.4: Ngrok tunnel
- Start ngrok tunnel on server startup
- Expose the webhook URL to Twilio
- Auto-configure Twilio webhook URLs

**Deliverable:** Pipecat server starts, accepts Twilio WebSocket connection, transcribes audio, exposes HTTP API.

---

## Phase 4: Call Orchestration (Claude Code side)

### Step 4.1: Call state machine
- Implement state tracking: requested → dialing → ringing → answered → ...
- Log every state transition
- Enforce terminal states (completed/failed/canceled) with reasons

### Step 4.2: Server lifecycle management
- Launch Pipecat server as subprocess
- Wait for health check to pass
- Monitor process, detect crashes
- Clean shutdown on call end

### Step 4.3: Event polling loop
- Poll `GET /call/events` during active call
- Display real-time status in terminal
- Route events to decision handlers:
  - `amd_result` → voicemail path or human path
  - `transcript` → IVR decision or human detection
  - `state_change` → update state machine

### Step 4.4: IVR navigation
- When transcript looks like an IVR menu, Claude Code decides which option
- Sends `POST /call/dtmf` with the digit
- Tracks DTMF attempt count (max 3)
- If stuck, falls back to voicemail

### Step 4.5: Warm transfer
- When human detected, sends `POST /call/transfer`
- Pipecat calls user's phone, whispers context
- Claude Code monitors transfer events
- On transfer failure, graceful hangup with apology

### Step 4.6: Voicemail delivery
- On voicemail detection (AMD or timeout), sends `POST /call/play`
- Waits for playback complete event
- Sends `POST /call/hangup`

**Deliverable:** Full call flow works end-to-end: dial → AMD → IVR/voicemail/human → log.

---

## Phase 5: Post-Call & Logging

### Step 5.1: Call log generation
- Generate markdown log file from event history
- Redact phone numbers in filenames (last 4 digits)
- Include: date, purpose, outcome, duration, state history, transcript, voicemail text

### Step 5.2: Terminal output
- Display concise outcome summary after call ends
- e.g., "Voicemail left at Little Darling School (45s)"

**Deliverable:** Every call produces a markdown log file and terminal summary.

---

## Phase 6: Error Handling & Hardening

### Step 6.1: Graceful degradation
- TTS failure → Twilio `<Say>` fallback
- STT failure → play voicemail and hang up
- Ngrok failure → clear error message
- Server crash → detect and log

### Step 6.2: Config validation
- Validate all keys on skill invocation
- Test Twilio credentials with a ping
- Test Azure endpoint reachability

### Step 6.3: Timeout and safety limits
- 60s ring timeout
- 30s silence timeout
- 3 DTMF attempt limit
- 5 minute max call duration
- 30s warm transfer pickup timeout

**Deliverable:** Skill handles all error scenarios from the spec without crashing.

---

## Phase 7: Testing

### Step 7.1: Unit tests
- Config validation
- Phone number normalization
- State machine transitions
- Event parsing

### Step 7.2: Integration test with Twilio
- Make a test call to Twilio's test number
- Verify AMD detection works
- Verify DTMF sending works

### Step 7.3: End-to-end test
- Call a real voicemail and verify message is left
- Call user's own phone to verify warm transfer whisper

**Deliverable:** Confidence that the skill works before using on real childcare centers.

---

## Implementation Order

```
Phase 1 (Foundation)     → Can run /call, sees setup flow
Phase 2 (Pre-Call)       → Generates voicemail audio
Phase 3 (Pipecat Server) → Voice pipeline works
Phase 4 (Orchestration)  → Full call flow
Phase 5 (Logging)        → Call logs generated
Phase 6 (Hardening)      → Error handling
Phase 7 (Testing)        → Verified working
```

Estimated implementation: Phases 1-4 are the core. Phases 5-7 are polish. The skill is usable after Phase 4.
