# Varun's Claude Marketplace

Claude Code plugins for OCR, scheduling, flight search, transcription, and developer workflows.

## Installation

```bash
claude plugin marketplace add varunr89/claude-marketplace
```

Then install individual plugins:

```bash
claude plugin install <plugin-name>
```

## Available Plugins

| Plugin | Description |
|--------|-------------|
| codex-collab | Automated Codex CLI reviews during design and implementation |
| copilot-collab (recommended) | Automated GitHub Copilot CLI reviews and interactive consultations via Stop hooks |
| ocr-toolkit | Extract text from images, PDFs, and videos |
| when2meet | Create When2Meet events and pre-fill availability |
| safari-archiver | Archive Safari pages to Obsidian as clean markdown |
| transcription | Fast audio transcription using MLX Whisper |
| flight-optimizer | Multi-leg flight search with scoring and batch sweep |
| scenario-test | Azure infrastructure scenario testing |
| config-sync | Sync ~/.claude/ config via git |
| phone-a-friend (deprecated) | Consult other AI models for second opinions |
| resume-tailoring | Tailored resumes with company research and branching experience discovery |
| devlog | Auto-generate daily dev log blog posts from Claude Code insights |
| paper-banana | Generate publication-ready academic diagrams and plots from paper methodology |
| paper-shepherd | AI-guided deep paper understanding using Keshav's three-pass method |
| computer-use | Unified browser and desktop automation using Playwright CDP and macOS screencapture |
| progressive-learning | Domain-agnostic progressive learning framework with Socratic teaching |
| call (untested) | Automated phone calls from Claude Code — voicemail, IVR navigation, and warm transfer |

## Testing

**CI (every PR):** Static validation + fresh install E2E on `macos-14` ($0 API cost)

```bash
# Run locally
bash ci/test-fresh-install.sh "$PWD"
```

## Contributing

1. Create plugin directory under `plugins/`
2. Add `.claude-plugin/plugin.json` with name, version, description
3. Add skills in `skills/*/SKILL.md` with YAML frontmatter
4. Add `tests/platform.json` if plugin has OS/arch requirements
5. Update `.claude-plugin/marketplace.json` to register the plugin
