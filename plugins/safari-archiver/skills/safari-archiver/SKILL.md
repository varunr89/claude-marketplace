---
name: safari-archiver
description: "Archive the current Safari page or PDF to Obsidian as clean markdown with images, frontmatter, and domain-based folder structure"
---

# Safari Archiver

Archives web pages and PDFs from Safari into an Obsidian vault as clean Markdown files. Two variants are provided: a Python-backed AppleScript (full-featured) and a pure JavaScript AppleScript (no Python dependency, but no PDF support).

## When to use

Use this skill when the user wants to save the current Safari page to Obsidian, export a web page as markdown, or archive a PDF from Safari.

## Components

### 1. safari-markdown-exporter.py -- Python content extractor

The core extraction engine. Called by the AppleScript wrappers.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/safari-markdown-exporter.py <input_file> <url> [title] [--pdf]
```

**How it works:**
- For **web pages**: Uses trafilatura to extract the main article content as Markdown. Downloads images locally, rewrites image links to Obsidian wiki-link format (`![[folder/image.jpg]]`). Handles both trafilatura-found images and raw HTML-extracted figures/standalone images.
- For **PDFs**: Uses PyMuPDF (fitz) to extract text. Copies the source PDF into an asset folder. Links the PDF in YAML frontmatter.

**Output structure:**
```
Obsidian Vault/Saved Pages/
  <domain>/
    001 - 2026-01-15 - Article Title.md      # Markdown with frontmatter
    001 - 2026-01-15 - Article Title/         # Asset folder
      image1.jpg
      image2.png
```

**YAML frontmatter** includes: title, url, domain, date_saved, and optionally source_pdf.

### 2. safari-markdown-exporter.scpt -- AppleScript (Python variant)

Triggered via keyboard shortcut (Automator Quick Action). Workflow:
1. Gets URL and title from the active Safari tab
2. For PDFs: downloads via curl, calls Python with `--pdf` flag
3. For web pages: toggles Safari Reader Mode for cleaner content, extracts full HTML via JavaScript, writes to temp file, calls Python
4. Shows macOS notification on success

**NOTE:** The `.scpt` file contains hardcoded paths that must be updated for your environment:
- `pythonScript` property -- path to safari-markdown-exporter.py
- `pythonPath` property -- path to Python 3.11+ interpreter

### 3. safari-markdown-exporter-js.scpt -- AppleScript (JavaScript variant)

A self-contained version that embeds an HTML-to-Markdown converter in JavaScript. No Python dependency, but does not support PDF archival. Handles image downloading via curl and Obsidian wiki-link rewriting natively in AppleScript.

### 4. safari-pdf-exporter.scpt -- PDF export with auto-scroll

A simpler utility that exports the current Safari page as PDF using Safari's "Export as PDF" menu, auto-increments a counter for sequential filenames, scrolls to the bottom of the page, and navigates to the next page. Useful for batch-exporting multi-page courseware.

## Dependencies

- trafilatura (pip install trafilatura) -- article content extraction
- PyMuPDF (pip install pymupdf) -- PDF text extraction (optional)
- macOS with Safari -- AppleScript automation
- Obsidian vault configured at the expected iCloud path

## Setup

1. Update the `pythonScript` and `pythonPath` properties in the `.scpt` files to match your local paths
2. Create an Automator Quick Action to run the desired `.scpt` file
3. Assign a keyboard shortcut in System Settings > Keyboard > Keyboard Shortcuts > Services
