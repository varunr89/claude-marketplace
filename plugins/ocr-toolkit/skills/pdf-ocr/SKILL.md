---
name: pdf-ocr
description: "Extract text from PDF files using Apple Vision OCR, optimized for Apple Silicon"
---

# PDF OCR

Converts PDF pages to images using PyMuPDF, then runs Apple Vision OCR on each page in parallel. Produces Markdown, plain text, or JSONL output.

## When to use

Use this skill when the user wants to extract text from a PDF file -- especially scanned PDFs, image-based PDFs, or PDFs where copy-paste produces garbled text.

## Usage

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/pdf_ocr.py <input.pdf> \
  [-o output_file] \
  [-f markdown|text|jsonl] \
  [--dpi 200] \
  [--workers N] \
  [--languages en-US] \
  [--fast] \
  [--keep-images] [--images-dir <dir>] \
  [--stdout]
```

## Key arguments

| Argument | Default | Description |
|---|---|---|
| `pdf` (positional) | required | Input PDF file path |
| `-o, --output` | `<pdf_name>.md` | Output file path |
| `-f, --format` | `markdown` | Output format: markdown, text, or jsonl |
| `--dpi` | 200 | Resolution for rendering PDF pages (higher = better quality, slower) |
| `--workers` | CPU count | Number of parallel OCR workers |
| `--languages` | `en-US` | Comma-separated recognition languages |
| `--fast` | false | Use faster, less accurate recognition |
| `--keep-images` | false | Keep the extracted page images after OCR |
| `--images-dir` | temp dir | Directory to save page images (requires --keep-images) |
| `--stdout` | false | Print extracted text to stdout instead of writing to file |

## Pipeline

1. PDF pages are rendered to PNG images at the specified DPI using PyMuPDF (fitz)
2. Apple Vision OCR runs in parallel across pages using ThreadPoolExecutor
3. Results are assembled in page order and written to the chosen output format

## Output formats

- **markdown** -- Each page becomes a `## Page N` section with the OCR text
- **text** -- Plain text with `=== Page N ===` separators
- **jsonl** -- One JSON object per line with `page`, `text`, and `backend` fields

## Dependencies

- PyMuPDF (pip install pymupdf) -- PDF to image conversion
- macOS + PyObjC (pip install pyobjc-core pyobjc-framework-Vision pyobjc-framework-Cocoa) -- Vision OCR
