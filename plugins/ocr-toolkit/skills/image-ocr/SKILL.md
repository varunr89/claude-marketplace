---
name: image-ocr
description: "Extract text from a directory of JPG/JPEG images into a single Markdown file using Apple Vision, tesseract, or MLX OCR"
---

# Image OCR

Batch-processes a directory of JPG/JPEG images and produces a combined Markdown file containing the OCR text from each image.

## When to use

Use this skill when the user wants to extract text from one or more JPG/JPEG images -- for example scanned documents, photos of whiteboards, or screenshots.

## Backends

- **vision** (default on macOS/Apple Silicon) -- Uses Apple's Vision framework via PyObjC. Fast, on-device, GPU-accelerated. Requires `pyobjc-core` and `pyobjc-framework-Vision`.
- **tesseract** -- Uses the `tesseract` CLI binary. Cross-platform. Optional preprocessing (grayscale, autocontrast, upscale) via Pillow.
- **mlx_ocr** -- Uses MLX-based OCR on Apple Silicon. Runs in a subprocess to isolate potential Metal crashes. Requires Python 3.10+ and `mlx-ocr`.
- **auto** -- Tries vision first, falls back to tesseract.

## Usage

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ocr_jpgs_to_markdown.py \
  --input <directory-of-jpgs> \
  --output <output.md> \
  [--backend auto|vision|tesseract|mlx_ocr] \
  [--start N] [--limit N] \
  [--languages en-US] \
  [--fast] \
  [--workers N] \
  [--tesseract-lang eng] [--tesseract-psm 6] [--tesseract-oem 1] \
  [--preprocess] [--preprocess-scale 2.0] \
  [--det-lang eng] [--rec-lang lat] \
  [--mlx-worker-python /path/to/python3.11]
```

## Key arguments

| Argument | Default | Description |
|---|---|---|
| `--input` | `ezgif-...` | Directory containing .jpg/.jpeg files |
| `--output` | `training_plan_ocr.md` | Output Markdown file path |
| `--backend` | `auto` | OCR backend: auto, vision, tesseract, mlx_ocr |
| `--start` | 0 | Start index (0-based) within sorted file list |
| `--limit` | None | Max files to process |
| `--languages` | `en-US` | Comma-separated recognition languages (Vision) |
| `--fast` | false | Use faster, less accurate recognition level (Vision) |
| `--workers` | CPU count | Number of parallel workers |
| `--preprocess` | false | Grayscale/autocontrast/upscale before tesseract |
| `--preprocess-scale` | 2.0 | Upscale factor for preprocessing |

## Dependencies

- macOS + PyObjC for Vision backend (pip install pyobjc-core pyobjc-framework-Vision)
- tesseract binary for tesseract backend (brew install tesseract)
- mlx-ocr + Python 3.10+ for MLX backend
- Pillow for preprocessing and MLX
