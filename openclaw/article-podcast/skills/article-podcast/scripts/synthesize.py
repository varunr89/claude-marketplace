#!/usr/bin/env python3
"""Stage 2: Multi-backend TTS audio synthesis with chunking and fallback."""

import io
import os
import sys
import tempfile
import time
import wave
from typing import Optional

import requests

TTS_BACKENDS = ["gemini", "azure-openai", "edge"]

# Speaker name mapping for Gemini prompts
_SPEAKER_NAMES = {
    "interview": {"S1": "Host", "S2": "Expert"},
    "discussion": {"S1": "Alex", "S2": "Sam"},
    "narrator": {"S1": "Narrator"},
}

# Backend-specific limits
GEMINI_MAX_WORDS_PER_CHUNK = 650       # ~4.3 min of speech (safety margin for 5:27 hard cutoff)
AZURE_MAX_CHARS_PER_REQUEST = 4096     # Hard API limit
EDGE_MAX_CHARS_PER_REQUEST = 10000     # Conservative safe limit
AZURE_RPM_LIMIT = 3                    # Default Azure rate limit
CROSSFADE_MS = 30                      # Crossfade between same-speaker chunks
SPEAKER_CHANGE_SILENCE_MS = 300        # Silence at speaker changes


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# --- Chunking utilities ---

def _split_oversized_text(text: str, max_chars: int) -> list[str]:
    """Split text that exceeds max_chars at sentence boundaries.

    Falls back to splitting at word boundaries if no sentence break fits.
    """
    if len(text) <= max_chars:
        return [text]

    import re
    # Split on sentence boundaries (period/exclamation/question followed by space)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = ""
    for sentence in sentences:
        if not current:
            current = sentence
        elif len(current) + 1 + len(sentence) <= max_chars:
            current += " " + sentence
        else:
            chunks.append(current)
            current = sentence

    # If a single sentence is still too long, split at word boundaries
    if current:
        if len(current) <= max_chars:
            chunks.append(current)
        else:
            words = current.split()
            buf = ""
            for word in words:
                if not buf:
                    buf = word
                elif len(buf) + 1 + len(word) <= max_chars:
                    buf += " " + word
                else:
                    chunks.append(buf)
                    buf = word
            if buf:
                chunks.append(buf)

    return chunks


def batch_segments(
    segments: list[dict], max_chars: int
) -> list[dict]:
    """Batch consecutive same-speaker segments into chunks up to max_chars.

    Returns a list of {"speaker": str, "text": str} dicts where consecutive
    same-speaker segments are merged, respecting the character limit.
    Handles oversized single segments by splitting at sentence boundaries.
    """
    if not segments:
        return []

    batches = []
    current_speaker = segments[0]["speaker"]
    current_text = segments[0]["text"]

    for seg in segments[1:]:
        if seg["speaker"] == current_speaker:
            combined = current_text + " " + seg["text"]
            if len(combined) <= max_chars:
                current_text = combined
                continue
        # Speaker changed or char limit reached: flush current batch
        # Split oversized text if needed
        for chunk in _split_oversized_text(current_text, max_chars):
            batches.append({"speaker": current_speaker, "text": chunk})
        current_speaker = seg["speaker"]
        current_text = seg["text"]

    # Flush last batch (also handle oversized)
    for chunk in _split_oversized_text(current_text, max_chars):
        batches.append({"speaker": current_speaker, "text": chunk})
    return batches


def chunk_for_gemini(
    segments: list[dict], max_words: int = GEMINI_MAX_WORDS_PER_CHUNK
) -> list[list[dict]]:
    """Split transcript segments into ~5-min chunks for Gemini TTS.

    Each chunk is a list of segments that together contain <= max_words words.
    Chunks never split mid-segment.
    """
    chunks = []
    current_chunk = []
    current_words = 0

    for seg in segments:
        seg_words = len(seg["text"].split())
        if current_words + seg_words > max_words and current_chunk:
            chunks.append(current_chunk)
            current_chunk = []
            current_words = 0
        current_chunk.append(seg)
        current_words += seg_words

    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def build_gemini_prompt(segments: list[dict], fmt: str) -> str:
    """Build a TTS prompt for Gemini from a list of segments.

    Gemini expects conversational text with speaker names matching the
    speaker_voice_configs.
    """
    names = _SPEAKER_NAMES.get(fmt, {"S1": "Speaker1", "S2": "Speaker2"})
    is_multi = len(set(seg["speaker"] for seg in segments)) > 1

    lines = []
    lines.append(f"TTS the following {'conversation' if is_multi else 'narration'}:")
    lines.append("")
    for seg in segments:
        name = names.get(seg["speaker"], seg["speaker"])
        lines.append(f"{name}: {seg['text']}")
    return "\n".join(lines)


def _wave_bytes(
    pcm_data: bytes, channels: int = 1, rate: int = 24000, sample_width: int = 2
) -> bytes:
    """Convert raw PCM data to WAV bytes."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


def _stitch_audio_segments(
    audio_segments: list, speaker_changes: list[bool]
) -> "AudioSegment":
    """Stitch pydub AudioSegments with crossfade or silence at boundaries.

    Args:
        audio_segments: list of pydub AudioSegment objects
        speaker_changes: list of bools, same length as audio_segments.
            True if this segment starts a new speaker turn.
    """
    from pydub import AudioSegment as AS

    if not audio_segments:
        return AS.silent(duration=0)

    combined = audio_segments[0]
    for i in range(1, len(audio_segments)):
        if speaker_changes[i]:
            # Speaker change: insert silence gap
            combined += AS.silent(duration=SPEAKER_CHANGE_SILENCE_MS)
            combined += audio_segments[i]
        else:
            # Same speaker continuation: crossfade for smooth join
            if len(combined) > CROSSFADE_MS and len(audio_segments[i]) > CROSSFADE_MS:
                combined = combined.append(audio_segments[i], crossfade=CROSSFADE_MS)
            else:
                combined += audio_segments[i]
    return combined


# --- Error classification and retries ---

_FATAL_ERRORS = (
    "authentication", "unauthorized", "forbidden", "api key",
    "invalid_api_key", "permission",
)


def _is_fatal_error(error: Exception) -> bool:
    """Check if an error is fatal (no point retrying)."""
    msg = str(error).lower()
    return any(term in msg for term in _FATAL_ERRORS)


def _retry_with_backoff(fn, max_retries: int = 2, initial_wait: float = 2.0):
    """Call fn() with exponential backoff retries on transient errors."""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as e:
            last_error = e
            if _is_fatal_error(e):
                raise  # Don't retry auth/permission errors
            if attempt < max_retries:
                wait = initial_wait * (2 ** attempt)
                _log(f"  Retry {attempt + 1}/{max_retries} after {wait:.1f}s: {e}")
                time.sleep(wait)
    raise last_error


# --- Backend implementations ---

def synthesize_gemini(transcript: dict, voices: list[str], config: dict) -> str:
    """Generate audio using Gemini 2.5 Flash TTS with chunking.

    Splits transcript into ~5-min chunks, generates each chunk separately
    with consistent voice assignments, then stitches with crossfade.
    """
    from google import genai
    from google.genai import types
    from pydub import AudioSegment

    _log(f"Gemini TTS: synthesizing with voices {voices}")

    api_key = os.environ.get(config.get("gemini_api_key_env", "GEMINI_API_KEY"), "")
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY", "")
    client = genai.Client(api_key=api_key)

    fmt = transcript["format"]
    names = _SPEAKER_NAMES.get(fmt, {"S1": "Speaker1", "S2": "Speaker2"})

    # Build speaker voice configs (same for all chunks)
    speaker_configs = []
    for i, speaker in enumerate(transcript["speakers"]):
        voice_name = voices[i] if i < len(voices) else voices[0]
        name = names.get(speaker["id"], speaker["id"])
        speaker_configs.append(
            types.SpeakerVoiceConfig(
                speaker=name,
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice_name,
                    )
                ),
            )
        )

    if len(speaker_configs) == 1:
        speech_config = types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=voices[0],
                )
            )
        )
    else:
        speech_config = types.SpeechConfig(
            multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                speaker_voice_configs=speaker_configs,
            )
        )

    # Chunk the transcript into ~5-min blocks
    chunks = chunk_for_gemini(transcript["segments"])
    _log(f"Gemini TTS: split into {len(chunks)} chunks")

    audio_parts = []
    for ci, chunk_segments in enumerate(chunks):
        prompt = build_gemini_prompt(chunk_segments, fmt)
        _log(f"Gemini TTS: generating chunk {ci + 1}/{len(chunks)} "
             f"({len(chunk_segments)} segments, {len(prompt)} chars)")

        def _gemini_call():
            resp = client.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=speech_config,
                ),
            )
            return resp.candidates[0].content.parts[0].inline_data.data

        pcm_data = _retry_with_backoff(_gemini_call)
        wav_bytes = _wave_bytes(pcm_data)
        segment = AudioSegment.from_wav(io.BytesIO(wav_bytes))
        audio_parts.append(segment)

        # Rate limiting: 10 RPM free tier = 6s between requests
        if ci < len(chunks) - 1:
            time.sleep(7)  # Stay safely under 10 RPM free tier

    # Determine speaker changes at chunk boundaries by checking
    # the last segment of each chunk vs the first segment of the next
    speaker_changes = [True]  # First chunk always starts fresh
    for ci in range(1, len(chunks)):
        prev_last_speaker = chunks[ci - 1][-1]["speaker"]
        curr_first_speaker = chunks[ci][0]["speaker"]
        speaker_changes.append(prev_last_speaker != curr_first_speaker)
    combined = _stitch_audio_segments(audio_parts, speaker_changes)

    tmp_dir = tempfile.mkdtemp(prefix="podcast-")
    mp3_path = os.path.join(tmp_dir, "episode.mp3")
    combined.export(mp3_path, format="mp3", bitrate="192k")

    _log(f"Gemini TTS: wrote {os.path.getsize(mp3_path)} bytes, "
         f"duration {len(combined) / 1000:.1f}s")
    return mp3_path


def synthesize_azure_openai(transcript: dict, voices: list[str], config: dict) -> str:
    """Generate audio using Azure OpenAI TTS-HD with batching and rate limiting.

    Batches consecutive same-speaker segments up to 4,096 chars per request.
    Respects Azure's 3 RPM default rate limit with sleep between calls.
    """
    from pydub import AudioSegment

    endpoint = config.get(
        "azure_tts_endpoint",
        "https://varun-mmbhqa1x-swedencentral.cognitiveservices.azure.com"
        "/openai/deployments/tts-hd/audio/speech",
    )
    api_version = config.get("azure_tts_api_version", "2025-03-01-preview")
    api_key_env = config.get("azure_tts_api_key_env", "AZURE_API_KEY")
    api_key = os.environ.get(api_key_env, "")
    if not api_key:
        raise RuntimeError(f"Environment variable {api_key_env} not set")

    url = f"{endpoint}?api-version={api_version}"
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key,
    }

    # Map speaker IDs to voices
    speaker_voice_map = {}
    for i, speaker in enumerate(transcript["speakers"]):
        speaker_voice_map[speaker["id"]] = voices[i] if i < len(voices) else voices[0]

    # Batch segments to minimize API calls
    batches = batch_segments(transcript["segments"], max_chars=AZURE_MAX_CHARS_PER_REQUEST)
    _log(f"Azure TTS: {len(transcript['segments'])} segments -> {len(batches)} batches "
         f"(voices: {voices})")

    audio_parts = []
    speaker_changes = []
    prev_speaker = None
    request_times = []  # Track timestamps for rate limiting

    for idx, batch in enumerate(batches):
        voice = speaker_voice_map.get(batch["speaker"], voices[0])
        speaker_changes.append(batch["speaker"] != prev_speaker)
        prev_speaker = batch["speaker"]

        # Rate limiting: ensure we don't exceed 3 RPM
        now = time.time()
        request_times = [t for t in request_times if now - t < 60]
        if len(request_times) >= AZURE_RPM_LIMIT:
            wait = 60 - (now - request_times[0]) + 0.5
            _log(f"Azure TTS: rate limit hit, waiting {wait:.1f}s")
            time.sleep(wait)

        payload = {
            "model": "tts-hd",
            "input": batch["text"],
            "voice": voice,
        }

        def _azure_call():
            r = requests.post(url, headers=headers, json=payload, timeout=120)
            r.raise_for_status()
            return r

        resp = _retry_with_backoff(_azure_call)
        request_times.append(time.time())

        segment_audio = AudioSegment.from_mp3(io.BytesIO(resp.content))
        audio_parts.append(segment_audio)

        if (idx + 1) % 5 == 0 or idx == len(batches) - 1:
            _log(f"Azure TTS: completed batch {idx + 1}/{len(batches)}")

    combined = _stitch_audio_segments(audio_parts, speaker_changes)

    tmp_dir = tempfile.mkdtemp(prefix="podcast-")
    mp3_path = os.path.join(tmp_dir, "episode.mp3")
    combined.export(mp3_path, format="mp3", bitrate="192k")

    _log(f"Azure TTS: wrote {os.path.getsize(mp3_path)} bytes, "
         f"duration {len(combined) / 1000:.1f}s")
    return mp3_path


async def _synthesize_edge_async(transcript: dict, voices: list[str]) -> str:
    """Internal async implementation for Edge TTS with batching."""
    import edge_tts
    from pydub import AudioSegment

    speaker_voice_map = {}
    for i, speaker in enumerate(transcript["speakers"]):
        speaker_voice_map[speaker["id"]] = voices[i] if i < len(voices) else voices[0]

    # Batch segments (Edge can handle larger chunks)
    batches = batch_segments(transcript["segments"], max_chars=EDGE_MAX_CHARS_PER_REQUEST)
    _log(f"Edge TTS: {len(transcript['segments'])} segments -> {len(batches)} batches "
         f"(voices: {voices})")

    audio_parts = []
    speaker_changes = []
    prev_speaker = None

    for idx, batch in enumerate(batches):
        voice = speaker_voice_map.get(batch["speaker"], voices[0])
        speaker_changes.append(batch["speaker"] != prev_speaker)
        prev_speaker = batch["speaker"]

        communicate = edge_tts.Communicate(batch["text"], voice)

        audio_bytes = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes.write(chunk["data"])

        audio_bytes.seek(0)
        segment_audio = AudioSegment.from_mp3(audio_bytes)
        audio_parts.append(segment_audio)

        if (idx + 1) % 5 == 0 or idx == len(batches) - 1:
            _log(f"Edge TTS: completed batch {idx + 1}/{len(batches)}")

    combined = _stitch_audio_segments(audio_parts, speaker_changes)

    tmp_dir = tempfile.mkdtemp(prefix="podcast-")
    mp3_path = os.path.join(tmp_dir, "episode.mp3")
    combined.export(mp3_path, format="mp3", bitrate="192k")

    _log(f"Edge TTS: wrote {os.path.getsize(mp3_path)} bytes, "
         f"duration {len(combined) / 1000:.1f}s")
    return mp3_path


def synthesize_edge(transcript: dict, voices: list[str], config: dict) -> str:
    """Generate audio using Microsoft Edge TTS (free) with batching."""
    import asyncio
    return asyncio.run(_synthesize_edge_async(transcript, voices))


# --- Main synthesis entry point ---

def synthesize(
    transcript: dict,
    voices: list[str],
    backend: str,
    config: dict,
    fallback_order: Optional[list[str]] = None,
) -> tuple[str, str]:
    """Synthesize audio with fallback chain.

    Args:
        transcript: structured transcript dict
        voices: voice names for primary backend
        backend: primary backend ("gemini", "azure-openai", "edge")
        config: plugin config dict
        fallback_order: ordered list of backends to try

    Returns:
        Tuple of (audio_file_path, backend_used, voices_used)
    """
    from voices import pick_voices

    if fallback_order is None:
        fallback_order = [backend]

    backends = {
        "gemini": synthesize_gemini,
        "azure-openai": synthesize_azure_openai,
        "edge": synthesize_edge,
    }

    num_speakers = len(transcript["speakers"])
    last_error = None

    for be in fallback_order:
        fn = backends.get(be)
        if not fn:
            _log(f"Unknown backend: {be}, skipping")
            continue

        # Pick voices for this backend (primary voices are for the first backend)
        if be == fallback_order[0]:
            be_voices = voices
        else:
            be_voices = pick_voices(be, num_speakers)

        try:
            _log(f"Trying TTS backend: {be}")
            audio_path = fn(transcript, be_voices, config)
            return audio_path, be, be_voices
        except Exception as e:
            if _is_fatal_error(e):
                _log(f"Backend {be} fatal error (skipping retries): {e}")
            else:
                _log(f"Backend {be} failed: {e}")
            last_error = e
            continue

    raise RuntimeError(f"All TTS backends failed. Last error: {last_error}")
