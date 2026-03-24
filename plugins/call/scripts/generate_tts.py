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
        api_version="2024-12-01-preview",
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
    # Print path to stdout for the caller to capture
    print(path)
