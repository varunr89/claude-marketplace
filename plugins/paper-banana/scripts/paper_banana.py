#!/usr/bin/env python3
"""
PaperBanana - Academic illustration generator.

Generates publication-ready scientific diagrams and statistical plots
using Google Gemini's native image generation (Nano Banana).

Based on the PaperBanana/PaperVizAgent framework by dwzhu-pku.

Usage:
    # Generate a diagram from a detailed description
    python paper_banana.py generate --description "..." --output diagram.jpg

    # Generate a diagram with aspect ratio
    python paper_banana.py generate --description "..." --output diagram.jpg --aspect-ratio 16:9

    # Generate a plot (produces matplotlib code, executes it)
    python paper_banana.py plot --description "..." --output plot.jpg

    # Retrieve similar references from PaperBananaBench
    python paper_banana.py retrieve --task diagram --content "..." --intent "..."

    # Download PaperBananaBench dataset
    python paper_banana.py setup --data-dir ./data

Environment variables:
    GOOGLE_API_KEY          - Required. Free from https://aistudio.google.com/apikey
    GEMINI_IMAGE_MODEL      - Image generation model (default: nano-banana-pro-preview).
    GEMINI_TEXT_MODEL        - Text model for plots/retrieval (default: gemini-3.1-pro).
"""

import argparse
import asyncio
import base64
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def check_dependencies():
    """Check and report missing dependencies."""
    missing = []
    try:
        from google import genai  # noqa: F401
    except ImportError:
        missing.append("google-genai")
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        missing.append("Pillow")

    if missing:
        print(f"ERROR: Missing dependencies: {', '.join(missing)}")
        print(f"Install with: pip install {' '.join(missing)}")
        sys.exit(1)


def get_gemini_client():
    """Create a Gemini API client."""
    from google import genai

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_API_KEY environment variable is required.")
        print("Get a free key at: https://aistudio.google.com/apikey")
        sys.exit(1)
    return genai.Client(api_key=api_key)


async def call_gemini_with_retry(client, model_name, contents, config,
                                  max_attempts=5, retry_delay=10):
    """Call Gemini API with exponential backoff retry."""
    from google.genai import types

    # Convert content list to Gemini format
    gemini_parts = []
    for item in contents:
        if item["type"] == "text":
            gemini_parts.append(types.Part.from_text(text=item["text"]))
        elif item["type"] == "image":
            image_data = item.get("image_base64", item.get("data", ""))
            media_type = item.get("media_type", "image/jpeg")
            gemini_parts.append(types.Part.from_bytes(
                data=base64.b64decode(image_data),
                mime_type=media_type,
            ))

    gemini_contents = [types.Content(role="user", parts=gemini_parts)]

    for attempt in range(max_attempts):
        try:
            response = await client.aio.models.generate_content(
                model=model_name,
                contents=gemini_contents,
                config=config,
            )

            if not response.candidates:
                raise ValueError("No candidates in response")

            results = []
            for candidate in response.candidates:
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, "inline_data") and part.inline_data:
                            img_bytes = part.inline_data.data
                            if isinstance(img_bytes, bytes):
                                results.append(
                                    base64.b64encode(img_bytes).decode("utf-8")
                                )
                            else:
                                results.append(img_bytes)
                        elif hasattr(part, "text") and part.text:
                            results.append(part.text)
            return results

        except Exception as e:
            if attempt < max_attempts - 1:
                wait = retry_delay * (2 ** attempt)
                print(
                    f"Attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {wait}s..."
                )
                await asyncio.sleep(wait)
            else:
                raise RuntimeError(
                    f"All {max_attempts} attempts failed. Last error: {e}"
                )


def convert_png_b64_to_jpg_b64(png_b64: str) -> str:
    """Convert a base64 PNG to base64 JPEG."""
    from PIL import Image

    try:
        img_bytes = base64.b64decode(png_b64)
        img = Image.open(io.BytesIO(img_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")
    except Exception as e:
        print(f"Warning: Image conversion failed: {e}")
        return png_b64


def execute_plot_code(code_text: str, output_path: str) -> bool:
    """
    Execute matplotlib code safely by writing to a temp file and
    running it as a subprocess. Returns True on success.
    """
    match = re.search(r"```python(.*?)```", code_text, re.DOTALL)
    code_clean = match.group(1).strip() if match else code_text.strip()

    # Inject save-to-file logic instead of plt.show()
    code_clean = code_clean.replace("plt.show()", "")
    save_line = (
        f"\nimport matplotlib.pyplot as plt\n"
        f"plt.savefig(r'{output_path}', format='jpeg', "
        f"bbox_inches='tight', dpi=300)\n"
        f"plt.close('all')\n"
    )
    code_clean += save_line

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False
    ) as tmp:
        tmp.write(code_clean)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            print(f"Plot code stderr: {result.stderr}")
            return False
        return Path(output_path).exists()
    except subprocess.TimeoutExpired:
        print("ERROR: Plot code execution timed out (60s)")
        return False
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


async def generate_diagram(args):
    """Generate a diagram image via Gemini native image generation."""
    from google.genai import types

    client = get_gemini_client()
    model = args.model or os.environ.get(
        "GEMINI_IMAGE_MODEL", "nano-banana-pro-preview"
    )
    aspect_ratio = args.aspect_ratio or "1:1"

    description = args.description
    if args.description_file:
        description = Path(args.description_file).read_text()

    prompt = (
        "Render an image based on the following detailed description: "
        f"{description}\n"
        "Note that do not include figure titles in the image. Diagram: "
    )
    contents = [{"type": "text", "text": prompt}]

    config = types.GenerateContentConfig(
        system_instruction=(
            "You are an expert scientific diagram illustrator. "
            "Generate high-quality scientific diagrams based on "
            "user requests."
        ),
        temperature=1.0,
        candidate_count=1,
        max_output_tokens=50000,
        response_modalities=["IMAGE"],
        image_config=types.ImageConfig(
            aspect_ratio=aspect_ratio,
        ),
    )

    print(
        f"Generating diagram with {model} "
        f"(aspect ratio: {aspect_ratio})..."
    )
    results = await call_gemini_with_retry(client, model, contents, config)

    if not results:
        print("ERROR: No image generated.")
        sys.exit(1)

    img_b64 = convert_png_b64_to_jpg_b64(results[0])
    img_bytes = base64.b64decode(img_b64)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(img_bytes)
    print(f"Diagram saved to: {output_path.resolve()}")
    return str(output_path.resolve())


async def generate_plot(args):
    """Generate a plot by having Gemini write matplotlib code, then run it."""
    from google.genai import types

    client = get_gemini_client()
    model = args.model or os.environ.get(
        "GEMINI_TEXT_MODEL", "nano-banana-pro-preview"
    )

    description = args.description
    if args.description_file:
        description = Path(args.description_file).read_text()

    prompt = (
        "Use python matplotlib to generate a statistical plot based on "
        f"the following detailed description: {description}\n"
        "Only provide the code without any explanations. Code:"
    )
    contents = [{"type": "text", "text": prompt}]

    config = types.GenerateContentConfig(
        system_instruction=(
            "You are an expert statistical plot illustrator. "
            "Write code to generate high-quality statistical plots "
            "based on user requests."
        ),
        temperature=1.0,
        candidate_count=1,
        max_output_tokens=50000,
    )

    print(f"Generating plot code with {model}...")
    results = await call_gemini_with_retry(client, model, contents, config)

    if not results:
        print("ERROR: No code generated.")
        sys.exit(1)

    code_text = results[0]
    print("Executing matplotlib code...")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    success = execute_plot_code(code_text, str(output_path))

    if not success:
        code_path = output_path.with_suffix(".py")
        code_path.write_text(code_text)
        print(
            f"ERROR: Plot code execution failed. "
            f"Code saved to: {code_path}"
        )
        sys.exit(1)

    print(f"Plot saved to: {output_path.resolve()}")

    code_path = output_path.with_suffix(".py")
    code_path.write_text(code_text)
    print(f"Plot code saved to: {code_path.resolve()}")
    return str(output_path.resolve())


async def retrieve_references(args):
    """Retrieve relevant references from PaperBananaBench dataset."""
    from google.genai import types

    data_dir = Path(args.data_dir)
    task = args.task

    ref_path = data_dir / "PaperBananaBench" / task / "ref.json"
    if not ref_path.exists():
        print(f"ERROR: Reference file not found: {ref_path}")
        print("Run 'paper_banana.py setup' first to download the dataset.")
        sys.exit(1)

    with open(ref_path, "r", encoding="utf-8") as f:
        candidates = json.load(f)

    client = get_gemini_client()
    model = args.model or os.environ.get(
        "GEMINI_TEXT_MODEL", "nano-banana-pro-preview"
    )

    if task == "diagram":
        candidate_text = ""
        for item in candidates[:200]:
            candidate_text += (
                f"ID: {item['id']}\n"
                f"Caption: "
                f"{item.get('visual_intent', item.get('caption', ''))}\n"
                f"Content: {item.get('content', '')[:300]}\n\n"
            )
        system_prompt = (
            "You are the Retrieval Agent. Select the Top 10 most "
            "relevant reference diagrams from the candidate pool. "
            "Match by Research Topic, Visual Intent (Framework, "
            "Pipeline, Module), and Structural Similarity.\n"
            'Output JSON: {"top10_diagrams": ["ref_1", "ref_2", ...]}'
        )
        output_key = "top10_diagrams"
    else:
        candidate_text = ""
        for item in candidates:
            raw_data = item.get("content", "")
            if isinstance(raw_data, (dict, list)):
                raw_data = json.dumps(raw_data)[:300]
            candidate_text += (
                f"ID: {item['id']}\n"
                f"Visual Intent: {item.get('visual_intent', '')}\n"
                f"Data: {raw_data}\n\n"
            )
        system_prompt = (
            "You are the Retrieval Agent. Select the Top 10 most "
            "relevant reference plots from the candidate pool. "
            "Match by Data Characteristics, Plot Type, and Visual Style.\n"
            'Output JSON: {"top10_plots": ["ref_0", "ref_1", ...]}'
        )
        output_key = "top10_plots"

    user_prompt = (
        f"Target Content:\n{args.content}\n\n"
        f"Target Intent:\n{args.intent}\n\n"
        f"Candidate Pool:\n{candidate_text}\n\n"
        "Select the Top 10 most relevant candidates."
    )

    contents = [{"type": "text", "text": user_prompt}]
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.5,
        candidate_count=1,
        max_output_tokens=5000,
    )

    print(f"Searching {len(candidates)} references with {model}...")
    results = await call_gemini_with_retry(client, model, contents, config)

    if not results:
        print("ERROR: No retrieval results.")
        sys.exit(1)

    response_text = (
        results[0].replace("```json", "").replace("```", "").strip()
    )
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        print(
            f"Warning: Could not parse response. "
            f"Raw output:\n{response_text}"
        )
        sys.exit(1)

    ref_ids = parsed.get(output_key, [])
    print(f"\nTop {len(ref_ids)} references:")

    id_to_item = {item["id"]: item for item in candidates}
    results_list = []
    for ref_id in ref_ids:
        item = id_to_item.get(ref_id, {})
        image_path = (
            data_dir / "PaperBananaBench" / task
            / item.get("path_to_gt_image", "")
        )
        print(f"  - {ref_id}: {item.get('visual_intent', 'N/A')[:80]}")
        results_list.append({
            "id": ref_id,
            "visual_intent": item.get("visual_intent", ""),
            "content": item.get("content", ""),
            "image_path": str(image_path) if image_path.exists() else None,
        })

    output_json = json.dumps(results_list, indent=2)
    if args.output:
        Path(args.output).write_text(output_json)
        print(f"\nResults saved to: {args.output}")
    else:
        print(f"\n{output_json}")


async def setup_dataset(args):
    """Download PaperBananaBench dataset."""
    import shutil

    data_dir = Path(args.data_dir)
    target = data_dir / "PaperBananaBench"

    if target.exists():
        print(f"Dataset already exists at: {target}")
        if not args.force:
            print("Use --force to re-download.")
            return
        shutil.rmtree(target)

    data_dir.mkdir(parents=True, exist_ok=True)

    print("Downloading PaperBananaBench dataset...")
    print("This may take a while depending on your connection.")

    repo_url = "https://github.com/dwzhu-pku/PaperBanana.git"
    clone_dir = data_dir / "_paperbanana_repo"

    result = subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(clone_dir)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"ERROR: Git clone failed: {result.stderr}")
        sys.exit(1)

    repo_data = clone_dir / "data" / "PaperBananaBench"
    if repo_data.exists():
        shutil.copytree(repo_data, target)
        shutil.rmtree(clone_dir)
        print(f"Dataset installed to: {target}")
    else:
        print(
            "Note: The PaperBananaBench dataset may need to be "
            "downloaded separately."
        )
        print(
            f"Check the repo at {repo_url} for dataset download "
            "instructions."
        )
        print(f"Place the dataset at: {target}")
        if clone_dir.exists():
            shutil.rmtree(clone_dir)


def main():
    parser = argparse.ArgumentParser(
        description="PaperBanana - Academic illustration generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Generate diagram
    gen = subparsers.add_parser(
        "generate", help="Generate a diagram from description"
    )
    gen.add_argument(
        "--description", "-d", help="Detailed figure description text"
    )
    gen.add_argument(
        "--description-file", "-f",
        help="File containing the description",
    )
    gen.add_argument(
        "--output", "-o", required=True,
        help="Output image path (JPEG)",
    )
    gen.add_argument(
        "--aspect-ratio", "-a", default="1:1",
        choices=["21:9", "16:9", "3:2", "1:1"],
        help="Image aspect ratio (default: 1:1)",
    )
    gen.add_argument("--model", "-m", help="Gemini model name override")

    # Generate plot
    plot_cmd = subparsers.add_parser(
        "plot", help="Generate a plot from description"
    )
    plot_cmd.add_argument(
        "--description", "-d", help="Detailed plot description text"
    )
    plot_cmd.add_argument(
        "--description-file", "-f",
        help="File containing the description",
    )
    plot_cmd.add_argument(
        "--output", "-o", required=True,
        help="Output image path (JPEG)",
    )
    plot_cmd.add_argument("--model", "-m", help="Gemini model name override")

    # Retrieve references
    ret = subparsers.add_parser(
        "retrieve", help="Retrieve relevant references from dataset"
    )
    ret.add_argument(
        "--task", "-t", required=True, choices=["diagram", "plot"],
        help="Task type",
    )
    ret.add_argument(
        "--content", "-c", required=True,
        help="Methodology section or raw data text",
    )
    ret.add_argument(
        "--intent", "-i", required=True,
        help="Figure caption or visual intent",
    )
    ret.add_argument(
        "--data-dir", default="./data",
        help="Path to data directory (default: ./data)",
    )
    ret.add_argument("--output", "-o", help="Output JSON file path")
    ret.add_argument("--model", "-m", help="Gemini model name override")

    # Setup dataset
    setup = subparsers.add_parser(
        "setup", help="Download PaperBananaBench dataset"
    )
    setup.add_argument(
        "--data-dir", default="./data",
        help="Target directory for dataset (default: ./data)",
    )
    setup.add_argument(
        "--force", action="store_true",
        help="Force re-download even if dataset exists",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    check_dependencies()

    if args.command == "generate":
        if not args.description and not args.description_file:
            print("ERROR: --description or --description-file required")
            sys.exit(1)
        asyncio.run(generate_diagram(args))
    elif args.command == "plot":
        if not args.description and not args.description_file:
            print("ERROR: --description or --description-file required")
            sys.exit(1)
        asyncio.run(generate_plot(args))
    elif args.command == "retrieve":
        asyncio.run(retrieve_references(args))
    elif args.command == "setup":
        asyncio.run(setup_dataset(args))


if __name__ == "__main__":
    main()
