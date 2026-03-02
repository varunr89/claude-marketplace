# paper-banana

A Claude Code plugin that generates publication-ready scientific diagrams and statistical plots from paper methodology sections and figure captions.

Based on the [PaperBanana/PaperVizAgent](https://github.com/dwzhu-pku/PaperBanana) framework.

## How It Works

The plugin implements a multi-agent pipeline where Claude handles text reasoning (planning, styling, critiquing) while the Gemini API handles native image generation (Nano Banana):

1. **Retrieve** (optional): Find relevant reference examples from PaperBananaBench
2. **Plan**: Claude generates a detailed figure description from methodology + caption
3. **Style**: Claude refines the description using NeurIPS 2025 style guidelines
4. **Visualize**: Gemini API generates the image (diagrams) or matplotlib code (plots)
5. **Critique**: Claude reviews the result and suggests improvements (interactive loop)

## Prerequisites

```bash
pip install google-genai Pillow
export GOOGLE_API_KEY="your-key-here"  # Free from https://aistudio.google.com/apikey
```

The Gemini API free tier includes 500 images/day at no cost (no credit card required).

## Features

- **Diagrams**: Architecture overviews, framework pipelines, module breakdowns (native image gen)
- **Plots**: Bar charts, line charts, scatter plots, heatmaps (matplotlib code gen)
- **Style-aware**: Applies NeurIPS 2025 aesthetic conventions automatically
- **Interactive critique**: Review and iteratively improve generated figures
- **Reference-driven**: Optionally use PaperBananaBench examples for higher quality

## Usage

Ask Claude to generate a figure for your paper:

> "Generate a diagram for my paper. Here's the methodology section: [paste text]. The figure caption is: Figure 1: Overview of our multi-agent framework."

> "Create a bar chart plot for my paper. Here's the raw data: [paste data]. Visual intent: Figure 3: Performance comparison across baselines."

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_API_KEY` | Yes | Free Gemini API key |
| `GEMINI_IMAGE_MODEL` | No | Override image model (default: `nano-banana-pro-preview`) |
| `GEMINI_TEXT_MODEL` | No | Override text model (default: `nano-banana-pro-preview`) |

## Dataset Setup (Optional)

For reference-driven generation with higher quality:

```bash
python scripts/paper_banana.py setup --data-dir ./data
```
