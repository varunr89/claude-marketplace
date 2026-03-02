---
name: paper-banana
description: >
  This skill should be used when the user asks to "generate a scientific diagram",
  "create an academic illustration", "make a figure for my paper", "generate a plot
  for my paper", "create a publication-ready diagram", "illustrate my methodology",
  "visualize my paper's architecture", "draw a pipeline diagram", "visualize my method",
  or "create a chart for my research". Also triggers when the user mentions
  "PaperBanana", "paper figure", "NeurIPS diagram", "conference figure", or
  "academic figure".
---

# PaperBanana: Academic Illustration Generator

Generate publication-ready scientific diagrams and statistical plots from paper
methodology sections and figure captions using a multi-agent pipeline.

## Overview

PaperBanana adapts the PaperVizAgent framework into a Claude-orchestrated pipeline.
Claude handles the text reasoning roles (planning, styling, critiquing) while a
Python script calls the Gemini API for native image generation (Nano Banana).

The pipeline follows five stages: **Retrieve** (optional) -> **Plan** -> **Style** -> **Visualize** -> **Critique** (iterative).

## Prerequisites

Ensure the following before starting:

1. **Python packages**: `pip install google-genai Pillow`
2. **API key**: Set `GOOGLE_API_KEY` env var (free from https://aistudio.google.com/apikey, no credit card needed, 500 images/day)
3. **Dataset** (optional): Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/paper_banana.py setup` to download PaperBananaBench for reference-driven generation

## Core Workflow

### Step 1: Gather Input

Collect two pieces of information from the user:
- **Methodology text**: The paper's method section describing the approach
- **Figure caption**: What the figure should depict (e.g., "Figure 1: Overview of our framework")

Also determine:
- **Task type**: `diagram` (architectural/framework figures) or `plot` (statistical charts)
- **Aspect ratio**: `1:1`, `3:2`, `16:9`, or `21:9` (default: `16:9` for diagrams, `1:1` for plots)

### Step 2: Retrieve References (Optional)

If the PaperBananaBench dataset is available, retrieve relevant reference examples:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/paper_banana.py retrieve \
  --task diagram \
  --content "methodology text here" \
  --intent "Figure 1: caption here" \
  --data-dir ./data \
  --output refs.json
```

Read the returned reference images using the Read tool to use as in-context examples for the planning step.

### Step 3: Plan (Claude as Planner Agent)

Generate a detailed figure description. This is the most critical step.

**For diagrams**, produce a description that covers:
- Every visual element and their connections
- Background style (typically pure white or very light pastel)
- Colors with specific hex codes, line thickness, icon styles
- Layout direction (typically left-to-right flow)
- Typography choices (sans-serif for labels, serif for math variables)
- Do NOT include figure titles/captions in the description

Use this system context for planning:

> Given the methodology section and figure caption, produce a detailed description
> of an illustrative diagram. The description must be extremely detailed:
> semantically describe each element and their connections; formally specify
> background style, colors, line thickness, icon styles. Vague specifications
> produce worse figures.

**For plots**, the description must include:
- Precise mapping of variables to visual channels (x, y, hue)
- Every raw data point's coordinates
- Exact aesthetic parameters: specific HEX color codes, font sizes, line widths,
  marker dimensions, legend placement, grid styles

If reference examples were retrieved, use them as few-shot examples to guide the
description style and level of detail.

### Step 4: Style (Claude as Stylist Agent)

Refine the planned description using the NeurIPS style guidelines.

Read the appropriate style guide:
- **Diagrams**: `${CLAUDE_PLUGIN_ROOT}/skills/paper-banana/references/neurips2025-diagram-style-guide.md`
- **Plots**: `${CLAUDE_PLUGIN_ROOT}/skills/paper-banana/references/neurips2025-plot-style-guide.md`

Apply these styling rules:
1. **Preserve semantic content**: do not alter logic, structure, or data
2. **Preserve existing high-quality aesthetics**: only intervene when the description lacks detail or looks outdated
3. **Respect domain diversity**: agent papers use illustrative styles, CV papers use spatial styles, theory papers use minimalist styles
4. **Enrich missing details**: add specific colors, fonts, line styles from the guidelines
5. **Handle icons carefully**: snowflake = frozen/non-trainable, flame = trainable; verify intent before changing

Output only the refined description with no commentary.

### Step 5: Visualize (Script)

Save the styled description to a temp file and generate the image:

**For diagrams:**
```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/paper_banana.py generate \
  --description-file /tmp/description.txt \
  --output figure.png \
  --aspect-ratio 16:9
```

**For plots:**
```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/paper_banana.py plot \
  --description-file /tmp/description.txt \
  --output plot.png
```

The script calls the Gemini API with `response_modalities=["IMAGE"]` for native image generation
(diagrams) or generates and executes matplotlib code (plots).

### Step 6: Critique (Claude as Critic Agent, Interactive)

After the image is generated, read it with the Read tool (Claude can view images) and perform a critique.

**For diagrams**, check:
1. **Fidelity**: Does the diagram accurately reflect the methodology? No hallucinated content.
2. **Text QA**: Check for typos, nonsensical text, unclear labels
3. **Example validation**: Verify molecular formulas, math expressions, etc.
4. **Caption exclusion**: The figure caption must NOT appear inside the image
5. **Clarity**: Is the flow confusing or layout cluttered?
6. **Legend management**: Remove redundant text-based legends

**For plots**, check:
1. **Data fidelity**: All quantitative values must be correct, no hallucinated data
2. **Text QA**: Check axis labels, legend entries, annotations
3. **Value validation**: Verify axis scales and data points against raw data
4. **Overlap**: Check for obscured labels, elements overlapping
5. **Generation failures**: If the plot failed to render, simplify the description

Present the critique to the user and ask whether to:
- **Accept** the current image
- **Revise** with suggested improvements (loop back to Step 5 with revised description)
- **Regenerate** from scratch

If revising, produce a JSON critique:
```json
{
  "critic_suggestions": "specific issues found...",
  "revised_description": "the full revised description..."
}
```

The revised description should primarily modify the original, not rewrite from scratch.
Run up to 3 critique rounds maximum.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_API_KEY` | Yes | Free Gemini API key (https://aistudio.google.com/apikey) |
| `GEMINI_IMAGE_MODEL` | No | Image model (default: `nano-banana-pro-preview`) |
| `GEMINI_TEXT_MODEL` | No | Text model for plot code (default: `nano-banana-pro-preview`) |

## Key Tips

- **More detail = better output**. Vague descriptions produce poor figures. Always specify exact colors, positions, and relationships.
- **Diagrams vs plots**: Diagrams use Gemini's native image generation; plots generate matplotlib code and execute it.
- **Aspect ratios**: Use `16:9` for wide pipeline/framework diagrams, `1:1` for square module diagrams, `3:2` for balanced layouts.
- **Domain awareness**: Match the visual style to the paper's domain (see style guides for agent, CV, and theory paper conventions).
- **Timeout**: The default timeout is 300s. For complex diagrams, increase with `--timeout 600`.

## Additional Resources

### Reference Files

For detailed styling guidelines, consult:
- **`${CLAUDE_PLUGIN_ROOT}/skills/paper-banana/references/neurips2025-diagram-style-guide.md`**: Color palettes, shapes, arrows, typography, domain-specific styles for diagrams
- **`${CLAUDE_PLUGIN_ROOT}/skills/paper-banana/references/neurips2025-plot-style-guide.md`**: Color palettes, axes, typography, chart-type-specific guidelines for plots

### Script Reference

The main script at `${CLAUDE_PLUGIN_ROOT}/scripts/paper_banana.py` supports:
- `generate`: Render a diagram via Gemini image generation
- `plot`: Generate and execute matplotlib code for plots
- `retrieve`: Search PaperBananaBench for relevant reference examples
- `setup`: Download the PaperBananaBench dataset
