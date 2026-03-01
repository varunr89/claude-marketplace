---
name: video-ocr
description: "Extract text from video files by sampling frames and running Apple Vision OCR, with optional perceptual deduplication"
---

# Video OCR

Extracts frames from a video at a configurable FPS using ffmpeg, optionally deduplicates visually similar frames using perceptual hashing (aHash), then runs Apple Vision OCR on each kept frame in parallel.

## When to use

Use this skill when the user wants to extract text from a video -- for example lecture recordings, tutorial screencasts, or presentation recordings where on-screen text changes over time.

## Usage

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/video_ocr.py <video_file> \
  [-o output.jsonl] \
  [--fps 3.0] \
  [--workers 8] \
  [--dedupe] [--dedupe-threshold 0.15] [--hash-size 8] \
  [--frames-out <dir>] \
  [--markdown <output.md>] [--markdown-images]
```

## Key arguments

| Argument | Default | Description |
|---|---|---|
| `video` (positional) | required | Input video file path |
| `-o, --output` | `ocr_output.jsonl` | Output JSONL file path |
| `--fps` | 3.0 | Frames per second to extract |
| `--workers` | 8 | Number of parallel OCR workers |
| `--dedupe` | false | Deduplicate visually similar frames |
| `--dedupe-threshold` | 0.15 | Max visual difference ratio (0-1) to treat as similar |
| `--hash-size` | 8 | Perceptual hash size (hash_size x hash_size bits) |
| `--frames-out` | None | Directory to save kept frames as JPGs |
| `--markdown` | None | Optional Markdown output path |
| `--markdown-images` | false | Embed frame images in Markdown (requires --frames-out) |

## Pipeline

1. ffmpeg extracts frames from the video at the specified FPS
2. If `--dedupe` is enabled, frames are compared using average perceptual hash (aHash) and similar consecutive frames are dropped
3. Apple Vision OCR runs in parallel on all kept frames
4. Results are sorted by frame number and written to JSONL (one JSON object per frame with `frame`, `time_sec`, and `text` fields)
5. Optionally, a Markdown file is generated with frame headings and OCR text blocks

## Deduplication

The deduplication feature uses average perceptual hashing (aHash):
- Each frame is resized to `hash_size x hash_size` grayscale
- Pixels above the mean are mapped to 1, below to 0
- Consecutive frames whose Hamming distance ratio is below `--dedupe-threshold` are dropped
- This efficiently removes near-duplicate frames (e.g., static slides)

## Dependencies

- ffmpeg (brew install ffmpeg) -- frame extraction
- macOS + PyObjC (pip install pyobjc-core pyobjc-framework-Vision pyobjc-framework-Cocoa) -- Vision OCR
- Pillow (pip install pillow) -- required for --dedupe
