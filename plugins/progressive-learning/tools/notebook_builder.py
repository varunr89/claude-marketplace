"""
Notebook builder for progressive-learning exercises.

Generates valid Jupyter notebooks (nbformat v4) from a list of cell
definitions. Used by phase-specific generation scripts to produce
LeetCode-style exercise notebooks.

Usage in a generation script:

    import sys, os
    sys.path.insert(0, os.environ.get("CLAUDE_PLUGIN_ROOT", ".") + "/tools")
    from notebook_builder import md, code, write_notebook

    cells = [
        md("# Title", "", "Description..."),
        code("import numpy as np", "", "print('ready')"),
        md("## Task A", "", "Instructions..."),
        code("def solve():", "    # YOUR CODE HERE", "    pass"),
        code("# Tests", "assert solve() == 42"),
    ]

    write_notebook(cells, "exercises/phase-N-name.ipynb")
"""

import json
import uuid
import os


def _make_source(lines):
    """Normalize cell source into nbformat's list-of-strings format.

    Accepts:
      - Multiple string arguments (one per line)
      - A single multi-line string (split on newlines)
      - A list of strings (used as-is)

    Returns a list of strings where every line except the last ends with '\\n'.
    """
    if isinstance(lines, str):
        lines = lines.split("\n")
    elif not isinstance(lines, (list, tuple)):
        lines = [str(lines)]
    else:
        lines = list(lines)

    # Ensure every line except the last ends with \n
    result = []
    for i, line in enumerate(lines):
        if i < len(lines) - 1:
            result.append(line if line.endswith("\n") else line + "\n")
        else:
            result.append(line.rstrip("\n"))
    return result


def md(*lines):
    """Create a markdown cell.

    Each argument is one line. Or pass a single multi-line string.

    Examples:
        md("# Title", "", "Some description")
        md('''# Title

        Some description''')
    """
    if len(lines) == 1:
        source = _make_source(lines[0])
    else:
        source = _make_source(list(lines))

    return {
        "cell_type": "markdown",
        "id": uuid.uuid4().hex[:8],
        "metadata": {},
        "source": source,
    }


def code(*lines):
    """Create a code cell.

    Each argument is one line. Or pass a single multi-line string.

    Examples:
        code("x = 1", "print(x)")
        code('''x = 1
        print(x)''')
    """
    if len(lines) == 1:
        source = _make_source(lines[0])
    else:
        source = _make_source(list(lines))

    return {
        "cell_type": "code",
        "id": uuid.uuid4().hex[:8],
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": source,
    }


def section_break():
    """Create a markdown cell with just a horizontal rule (---).

    Useful as a visual separator between tasks.
    """
    return md("---")


def task_header(task_id, title, instructions, theory_connection=None):
    """Create a standard task header markdown cell.

    Parameters
    ----------
    task_id : str
        e.g., "A", "B", "C"
    title : str
        e.g., "Grid Foundations"
    instructions : str
        Multi-line markdown with the task description.
    theory_connection : str, optional
        A sentence connecting this task to the theory from the Learn portion.
    """
    lines = [f"---", f"## Task {task_id}: {title}", "", instructions]
    if theory_connection:
        lines.extend(["", f"**Connection to theory:** {theory_connection}"])
    return md("\n".join(lines))


def test_cell(task_id, test_code):
    """Create a standardized test cell for a task.

    Wraps test_code in a function and prints pass/fail summary.
    The test_code should use assert statements and increment passed/total.

    Parameters
    ----------
    task_id : str
        e.g., "A", "B"
    test_code : str
        The body of the test function (will be indented inside the function).
    """
    header = f"# ── Tests for Task {task_id} {'─' * (52 - len(task_id))}"
    return code(f"{header}\n\n{test_code}")


def experiment_cell(number, title, prediction_prompt, experiment_code):
    """Create a predict-then-observe experiment cell.

    Parameters
    ----------
    number : int
        Experiment number.
    title : str
        Brief title.
    prediction_prompt : str
        What the learner should predict (multiline ok).
    experiment_code : str
        Code that runs the experiment and shows results.
    """
    lines = [
        f"# ── Experiment {number}: {title} {'─' * max(1, 48 - len(title))}",
        *[f"# {line}" for line in prediction_prompt.strip().split("\n")],
        "# YOUR PREDICTION: ???",
        "",
        experiment_code.strip(),
    ]
    return code("\n".join(lines))


def ensure_env(venv_path, kernel_name, kernel_display, packages):
    """Ensure a virtual environment exists with required packages and a Jupyter kernel.

    Idempotent -- skips steps that are already done.

    Parameters
    ----------
    venv_path : str
        Path to the virtual environment (e.g., ".venv").
    kernel_name : str
        Jupyter kernel name (e.g., "rl").
    kernel_display : str
        Display name in Jupyter (e.g., "RL (Python 3)").
    packages : list[str]
        Packages to install (e.g., ["numpy", "matplotlib"]).
    """
    import subprocess
    import sys

    venv_path = os.path.abspath(venv_path)
    python = os.path.join(venv_path, "bin", "python")
    pip = os.path.join(venv_path, "bin", "pip")

    # Create venv if needed
    if not os.path.exists(python):
        print(f"Creating venv at {venv_path}...")
        subprocess.run([sys.executable, "-m", "venv", venv_path], check=True)

    # Install packages (pip install is fast when already installed)
    all_packages = list(packages) + ["ipykernel"]
    print(f"Installing packages: {', '.join(all_packages)}...")
    subprocess.run(
        [pip, "install", "-q"] + all_packages,
        check=True,
        capture_output=True,
    )

    # Register Jupyter kernel (idempotent)
    subprocess.run(
        [python, "-m", "ipykernel", "install", "--user",
         "--name", kernel_name, "--display-name", kernel_display],
        check=True,
        capture_output=True,
    )
    print(f"Kernel '{kernel_name}' ready.")


def write_notebook(cells, path, kernel="python3", kernel_display=None):
    """Write cells to a Jupyter notebook file.

    Parameters
    ----------
    cells : list
        List of cell dicts (from md(), code(), etc.).
    path : str
        Output file path (e.g., "exercises/phase-1-mdp.ipynb").
    kernel : str
        Kernel name (default: "python3").
    kernel_display : str, optional
        Display name for the kernel. Defaults to kernel name.

    Returns
    -------
    str
        The absolute path to the written notebook.
    """
    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": kernel_display or kernel,
                "language": "python",
                "name": kernel,
            },
            "language_info": {
                "name": "python",
                "version": "3.11.0",
            },
        },
        "cells": cells,
    }

    # Ensure parent directory exists
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    abs_path = os.path.abspath(path)
    with open(abs_path, "w") as f:
        json.dump(notebook, f, indent=1)

    print(f"Wrote {len(cells)} cells to {abs_path}")
    return abs_path
