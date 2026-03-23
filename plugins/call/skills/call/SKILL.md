---
name: call
description: >
  Use when the user wants to make a phone call, leave a voicemail,
  call a business, reach someone by phone, or navigate a phone menu.
  Triggered by "/call" followed by a phone number and purpose.
version: 0.1.0
argument-hint: "<phone_number> <purpose>"
allowed-tools:
  - Bash
  - Read
  - Write
---

# /call -- Automated Phone Calls from Claude Code

Make phone calls that leave voicemails, navigate IVR menus, and warm-transfer live humans to your phone.

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

## How It Works

1. You provide a phone number and purpose
2. Claude Code generates a voicemail message and IVR navigation goal
3. You confirm before the call is placed
4. Azure OpenAI TTS HD pre-generates the voicemail audio
5. Pipecat server starts and dials via Twilio
6. Twilio's AMD detects human vs machine:
   - **Voicemail**: plays pre-generated message, hangs up
   - **IVR Menu**: Azure Whisper transcribes options, Claude decides which button to press
   - **Human answers**: warm-transfers to your phone with a context whisper
7. Call log saved to `call-logs/` in current project

## Architecture

```
Claude Code (brain, makes all decisions)
  + Pipecat Server (sandboxed voice worker, FastAPI + Twilio WebSocket)
  + Twilio (telephony, AMD, DTMF, call transfer)
  + Azure OpenAI gpt-4o-mini-transcribe (STT, segmented)
  + Azure OpenAI TTS HD (voicemail audio, pre-generated)
```

**Security boundary**: Pipecat is a sandboxed low-privilege process. It handles audio only. Claude Code never receives raw call audio -- only text transcripts. This prevents caller prompt injection from reaching Claude Code's privileged tools.

## Call States

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
```

Terminal reasons: `voicemail_left`, `transferred`, `no_answer`, `busy`, `ivr_failed`, `call_dropped`, `transfer_failed`, `timeout`, `error`

## Setup (First Time)

Run the setup script:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/setup.sh
```

This will:
1. Create a Python venv and install dependencies (pipecat-ai, twilio, openai, fastapi)
2. Prompt for Twilio account SID, auth token, and phone number
3. Prompt for Azure OpenAI endpoint and API key
4. Prompt for your phone number (for warm transfers)
5. Prompt for ngrok auth token
6. Save config to `${CLAUDE_PLUGIN_ROOT}/config.json`

### Required External Services
- **Twilio account** with a US phone number (~$1/mo + $0.014/min)
- **Azure OpenAI** endpoint with gpt-4o-mini-transcribe and TTS HD deployed
- **ngrok** account (free tier is sufficient)

## Configuration

Config stored at `${CLAUDE_PLUGIN_ROOT}/config.json`:

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
    "tts_model": "tts-hd",
    "tts_voice": "onyx",
    "stt_model": "gpt-4o-mini-transcribe"
  },
  "transfer_to": "+16083207152",
  "ngrok_auth_token": "xxxxx",
  "pipecat_port": 8765
}
```

## Call Log Format

Saved to `<project>/call-logs/YYYY-MM-DD-xxxx<last4>.md`:

```markdown
# Call: (360) ***-5437
**Date:** 2026-03-22 2:34 PM
**Purpose:** Ask about enrollment for 2.5yo
**Outcome:** Voicemail left
**Duration:** 45 seconds

## Transcript
[0:00] IVR: "Thank you for calling..."
[0:08] Agent: Sent DTMF 1 (enrollment)
[0:15] Voicemail: "Please leave a message after the tone"
[0:18] Agent: Played voicemail message
```

## Error Handling

- **TTS fails**: Falls back to Twilio `<Say>` (robotic but works)
- **STT fails**: Cannot navigate IVR. Leaves voicemail instead.
- **Your phone doesn't answer transfer**: Apologizes to center, hangs up
- **IVR stuck (3 attempts)**: Leaves voicemail and hangs up
- **Config missing**: Shows setup instructions

Every call produces a log. No call ends silently.

## Cost

~$0.03-0.05 per call (Twilio minutes + AMD + Azure OpenAI tokens).

## Implementation

The skill logic is in `$ARGUMENTS`:

1. Parse phone number (first token) and purpose (remaining text)
2. Normalize number to E.164 format
3. Read config from `${CLAUDE_PLUGIN_ROOT}/config.json`
4. Generate voicemail message text from purpose
5. Show confirmation prompt
6. On confirm: generate TTS audio, start Pipecat server, orchestrate call
7. Poll events, make IVR/transfer/voicemail decisions
8. Write call log on completion
