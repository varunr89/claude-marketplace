---
name: transcription
description: Use when the user wants to transcribe audio files (MP3, WAV, M4A) to text using MLX Whisper on Apple Silicon
---

# Audio Transcription

Fast local transcription using MLX Whisper with Apple Silicon GPU/Neural Engine acceleration.

## Requirements

- Apple Silicon Mac (M1+)
- Python 3.11+ with mlx-whisper package
- Model: mlx-community/whisper-large-v3-turbo (auto-downloaded on first use)

## Usage

The script at `${CLAUDE_PLUGIN_ROOT}/scripts/transcribe.py` processes MP3/WAV/M4A files:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/transcribe.py /path/to/audio/files/
```

- Processes all audio files in the given directory
- Outputs transcription text to stdout
- Reports timing statistics per file

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install mlx-whisper
```
