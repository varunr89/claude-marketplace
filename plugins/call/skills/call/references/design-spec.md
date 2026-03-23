# /call Skill Design Spec (v2)

*Updated after GPT 5.4 xhigh architectural review*

## Overview

A general-purpose Claude Code skill that makes automated phone calls. Claude Code acts as the brain (decision-making), Pipecat runs the call pipeline as a standalone FastAPI/WebSocket server, Twilio handles telephony, and Azure OpenAI provides STT and TTS.

The skill handles three scenarios: leaving voicemails, navigating IVR menus, and warm-transferring live humans to the user's phone with context.

## Invocation

```
/call <phone_number> <purpose in natural language>
```

**Examples:**
```
/call 3606765437 ask about enrollment for my 2.5yo daughter
/call 2065551234 schedule a dentist appointment for next week
/call 8005551234 cancel my internet service
```

## Architecture

```
Claude Code (brain + orchestrator)
  + Pipecat Server (call pipeline, FastAPI + WebSocket, runs as subprocess)
  + Twilio (telephony, AMD, DTMF, call transfer, Media Streams WebSocket)
  + Azure OpenAI gpt-4o-mini-transcribe (STT, segmented after VAD silence)
  + Azure OpenAI TTS HD (voicemail audio, pre-generated before call)
```

### Separation of Concerns

- **Claude Code** makes all decisions: what voicemail message to craft, which IVR option to select, when to transfer. It communicates with the Pipecat server over a local HTTP API. Claude Code has full tool access (shell, files, git) but never receives raw call audio.
- **Pipecat Server** is a sandboxed, low-privilege voice worker. It runs as a FastAPI process with Twilio WebSocket transport (Pipecat's native `TwilioSerializer`). It handles real-time audio, STT buffering, TTS playback, DTMF, and call transfer. It exposes a local HTTP API for Claude Code to send commands and receive events. It has NO shell, filesystem write, or git access.
- **Twilio** is the phone line: PSTN connectivity, Answering Machine Detection, DTMF transmission, call bridging, Media Streams WebSocket for audio. Webhook signatures (`X-Twilio-Signature`) are validated on all callbacks.
- **Azure OpenAI** provides voice services: `gpt-4o-mini-transcribe` for STT (segmented after VAD silence, $0.003/min), TTS HD for natural-sounding pre-generated voicemail audio.

### Security Boundary

```
┌─────────────────────────────┐     ┌──────────────────────────────┐
│     CLAUDE CODE (privileged) │     │   PIPECAT SERVER (sandboxed)  │
│                             │     │                              │
│  • Shell access             │     │  • NO shell access           │
│  • File read/write          │ HTTP│  • NO filesystem write       │
│  • Git operations           │◄───►│  • Audio processing only     │
│  • Decision making          │ API │  • Twilio WebSocket          │
│  • Reads transcripts (text) │     │  • Azure OpenAI STT/TTS     │
│  • Never sees raw audio     │     │  • Local HTTP API exposed    │
└─────────────────────────────┘     └──────────────────────────────┘
```

This separation prevents a caller from injecting prompts that reach Claude Code's privileged tools. The Pipecat server only forwards text transcripts to Claude Code, never raw audio or unvalidated caller input piped to a tool-bearing LLM.

## Communication Protocol: Claude Code ↔ Pipecat Server

**Local HTTP API (not stdio)** -- Pipecat runs a FastAPI server on `localhost:<port>`.

**Claude Code → Pipecat (HTTP POST requests):**
```
POST /call/start    {"to": "+13606765437", "voicemail_audio": "/path/to.wav"}
POST /call/dtmf     {"digits": "1"}
POST /call/play     {"file": "/path/to/voicemail.wav"}
POST /call/transfer {"to": "+16083207152", "whisper": "Little Darling, enrollment"}
POST /call/hangup   {}
```

**Pipecat → Claude Code (HTTP GET polling or SSE):**
```
GET /call/events

[
  {"event": "state_change", "state": "ringing", "ts": 1711148400},
  {"event": "amd_result", "result": "human", "ts": 1711148405},
  {"event": "transcript", "text": "Press 1 for enrollment...", "ts": 1711148408},
  {"event": "state_change", "state": "completed", "reason": "voicemail_left", "duration": 45, "ts": 1711148445}
]
```

This uses Pipecat's native FastAPI runner and avoids inventing a custom transport.

## Call State Machine

```
requested → dialing → ringing → answered
                                    │
                        ┌───────────┼───────────┐
                        ▼           ▼           ▼
                    voicemail    ivr_nav      human
                        │           │           │
                        ▼           ▼           ▼
                  leaving_msg   navigating   transferring
                        │           │           │
                        └───────────┼───────────┘
                                    ▼
                               completed
                              (with reason)

Terminal states: completed, failed, canceled
Reasons: voicemail_left, transferred, no_answer, busy, ivr_failed,
         call_dropped, transfer_failed, timeout, error
```

Every state transition is logged. The call never ends without a terminal state + reason.

## Call Flow

### Pre-Call Phase
1. Claude Code parses phone number and purpose from arguments
2. Normalizes phone number to E.164 format (+1XXXXXXXXXX)
3. Generates voicemail message text (concise, includes callback number)
4. Generates IVR navigation goal (e.g., "reach enrollment department")
5. Shows user confirmation prompt with message and goal
6. User confirms (y/n)
7. Azure OpenAI TTS HD renders voicemail message to .wav file (cached)
8. Pipecat server subprocess starts on localhost, ngrok tunnel opens

### Dialing Phase
9. Claude Code sends `POST /call/start` to Pipecat
10. Twilio places outbound call with AMD enabled (`DetectMessageEnd` mode)
11. Claude Code polls `GET /call/events` for status updates
12. Terminal shows: "Dialing...", "Ringing..."

### AMD Detection Phase
13. Twilio AMD classifies the answer:

**Path A: Machine/Voicemail**
- Twilio waits for beep (`DetectMessageEnd`)
- Pipecat plays pre-generated .wav file
- Hangs up → state: `completed`, reason: `voicemail_left`

**Path B: Human/IVR**
- Pipecat buffers audio, segments after VAD silence
- Each segment sent to Azure OpenAI `gpt-4o-mini-transcribe`
- Transcript posted as event for Claude Code to read

**Path B1: IVR Menu Detected**
- Claude Code reads transcript, decides which option
- Sends `POST /call/dtmf` with digits
- Loop: continue until reaching human or voicemail
- Safety: after 3 DTMF attempts, play voicemail and hang up

**Path B2: Human Detected**
- Pipecat plays brief hold message
- Claude Code sends `POST /call/transfer`
- Pipecat calls user's phone, whispers context when answered
- User says ready → calls bridged → Pipecat drops out

**Path C: No Answer / Busy**
- 60s timeout → `completed`, reason: `no_answer`
- Busy → `completed`, reason: `busy`

**Path D: Timeout**
- Human/IVR answered but 30s silence → play voicemail, hang up

### Post-Call Phase
- Full transcript saved to `call-logs/YYYY-MM-DD-<sanitized>.md`
- Phone numbers redacted in log filenames (last 4 digits only)
- Outcome summary displayed in Claude Code terminal
- Audio file cached for potential re-use

## File Structure

```
~/.claude/skills/call/
├── SKILL.md              # Skill definition, triggers, documentation
├── config.json            # Twilio creds, Azure keys, transfer number (gitignored)
├── server/
│   ├── call_server.py     # Pipecat FastAPI server (the voice worker)
│   ├── twilio_handler.py  # Twilio webhook handler with signature validation
│   └── requirements.txt   # Python dependencies for the server
├── audio/                 # Cached pre-generated .wav files
└── setup.sh              # One-time setup: venv, deps, config prompts

<current_project>/call-logs/
├── 2026-03-22-xxxx5437.md   # Phone number redacted (last 4 digits)
├── 2026-03-22-xxxx1234.md
└── ...
```

## Configuration

**config.json:**
```json
{
  "twilio": {
    "account_sid": "ACxxxxxxxx",
    "auth_token": "xxxxx",
    "from_number": "+1XXXXXXXXXX"
  },
  "azure_openai": {
    "endpoint": "https://xxx.openai.azure.com",
    "api_key": "xxxxx",
    "tts_model": "tts-1-hd",
    "tts_voice": "onyx",
    "stt_model": "gpt-4o-mini-transcribe"
  },
  "transfer_to": "+16083207152",
  "ngrok_auth_token": "xxxxx",
  "pipecat_port": 8765
}
```

All secrets in config.json, gitignored. Skill validates config on startup with clear setup instructions if keys are missing. Secrets never passed through LLM-visible prompts.

## Call Log Format

```markdown
# Call: (360) ***-5437
**Date:** 2026-03-22 2:34 PM
**Purpose:** Ask about enrollment for 2.5yo
**Outcome:** Voicemail left
**Duration:** 45 seconds
**State History:** requested → dialing → ringing → answered → voicemail → leaving_msg → completed

## Transcript
[0:00] IVR: "Thank you for calling Little Darling School..."
[0:08] Agent: Sent DTMF 1 (enrollment)
[0:15] Voicemail: "Please leave a message after the tone"
[0:18] Agent: Played voicemail message
[0:42] Agent: Hung up

## Voicemail Message Left
"Hi, this is Varun Ramesh calling about enrolling my
2.5 year old daughter Anicca. We're looking for 2-3 days
per week. Please call me back at 608-320-7152. Thank you."
```

## Error Handling

| Scenario | Behavior | Terminal State |
|----------|----------|----------------|
| Twilio creds missing/invalid | Check config on startup, clear error with setup instructions | N/A (pre-call) |
| Azure OpenAI TTS fails | Fall back to Twilio `<Say>` verb (free, robotic but functional) | Continues |
| Azure STT fails | Cannot navigate IVR. Play voicemail and hang up | completed: ivr_failed |
| Ngrok tunnel fails | Error with instructions to check auth token | failed: error |
| User's phone doesn't answer transfer | Wait 30s, tell center "let me call back", hang up | completed: transfer_failed |
| Call drops mid-IVR | Log partial transcript | failed: call_dropped |
| Invalid phone number | Twilio returns error immediately | failed: error |
| No answer after 60s | Hang up | completed: no_answer |
| Busy signal | Log | completed: busy |
| IVR loop (3 DTMF attempts) | Play voicemail and hang up | completed: ivr_failed |
| Pipecat server crashes | Claude Code detects process exit, logs error | failed: error |
| Invalid Twilio webhook signature | Request rejected, logged as security event | N/A |

**Principle:** Every call ends with a log entry and a terminal state. No call ends silently. Degrade gracefully.

## Dependencies

### Python (in skill's own venv at `~/.claude/skills/call/server/.venv`)
- `pipecat-ai` (orchestration)
- `pipecat-ai[twilio]` (Twilio WebSocket transport + serializer)
- `fastapi` + `uvicorn` (local HTTP API)
- `openai` (Azure OpenAI STT + TTS)
- `twilio` (Twilio REST API + webhook signature validation)
- `pyngrok` (ngrok tunnel management)

### External Services
- **Twilio account** with a US phone number (~$1/mo + $0.014/min + $0.0075/call AMD)
- **Azure OpenAI** endpoint with gpt-4o-mini-transcribe and TTS HD models deployed
- **ngrok** account (free tier sufficient) for Twilio webhook callbacks

### Estimated Cost Per Call
- Twilio: $0.014/min + $0.0075 AMD = ~$0.02 for 1-min call
- Azure OpenAI gpt-4o-mini-transcribe: ~$0.003/min of audio
- Azure OpenAI TTS HD: ~$0.030 per 1K chars (one-time per message)
- **Total: ~$0.03-0.05 per call**
- Hidden costs: number rental ($1/mo), failed attempts, ngrok (free tier)

## SKILL.md Frontmatter

```yaml
---
name: call
description: Use when the user wants to make a phone call, leave a voicemail, call a business, or reach someone by phone. Triggered by "/call" followed by a phone number and purpose.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
---
```

## Review Changelog (v2)

Changes from v1 based on GPT 5.4 xhigh review:

| Issue | v1 | v2 |
|-------|----|----|
| Security boundary | Claude Code received raw call data | Pipecat is sandboxed voice worker; Claude Code only sees text transcripts |
| Pipecat transport | Custom stdio JSON protocol | Native FastAPI + Twilio WebSocket (documented Pipecat pattern) |
| STT model | whisper-1 ($0.006/min) | gpt-4o-mini-transcribe ($0.003/min, cheaper) |
| Communication | stdin/stdout JSON | Local HTTP API (POST commands, GET/SSE events) |
| Call state machine | Informal | Formal states with terminal states + reasons |
| Webhook security | Not mentioned | X-Twilio-Signature validation required |
| PII in logs | Full phone numbers in filenames | Redacted (last 4 digits only) |
| Cost analysis | Missing hidden costs | Added number rental, failed attempts |
| Prompt injection | Not addressed | Threat model: caller audio never reaches privileged agent |
