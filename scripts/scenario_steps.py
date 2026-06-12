#!/usr/bin/env python3
"""
scripts/scenario_steps.py
--------------------------
Give it a plain-English scenario; it uses the local Ollama model +
wireframe KB to produce step-by-step test instructions.

Usage
-----
# Interactive mode (prompts you for a scenario)
python scripts/scenario_steps.py

# Inline scenario
python scripts/scenario_steps.py --scenario "play a song"

# Specific format
python scripts/scenario_steps.py --scenario "increase driver temperature to 74" --format json

# Specify starting screen
python scripts/scenario_steps.py --scenario "call back a missed call" --start phone

# Different model
python scripts/scenario_steps.py --scenario "navigate home" --model phi3:mini

# Save to file
python scripts/scenario_steps.py --scenario "play a song" --save

Options
-------
  --scenario    Plain-English goal (omit for interactive prompt)
  --format      steps | gherkin | json          [default: steps]
  --model       Ollama model name               [default: mistral:7b]
  --kb          Path to wireframe_kb.json       [default: input/wireframe_kb.json]
  --start       Starting screen ID              [default: home]
  --save        Save output to output/scenarios/
  --dry-run     Print prompt without calling model
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from prompts.scenario_prompt import build_scenario_prompt

try:
    import ollama
except ImportError:
    print("ERROR: ollama not installed.  pip install ollama")
    sys.exit(1)


DEFAULT_MODEL = "mistral:7b"
DEFAULT_KB    = "input/wireframe_kb.json"
DEFAULT_FMT   = "steps"
OUTPUT_DIR    = Path("output/scenarios")

FMT_EXT = {"steps": "txt", "gherkin": "feature", "json": "json"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_kb(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        print(f"ERROR: KB not found: {p}")
        sys.exit(1)
    return json.loads(p.read_text())


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:60]


def call_model(model: str, system: str, user: str) -> str:
    resp = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        options={"temperature": 0.2, "num_ctx": 8192},
    )
    return resp["message"]["content"].strip()


def save_result(scenario: str, fmt: str, content: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{slugify(scenario)}.{FMT_EXT.get(fmt, 'txt')}"
    path     = OUTPUT_DIR / filename
    path.write_text(content, encoding="utf-8")
    return path


def print_divider(title: str = ""):
    print(f"\n{'─' * 60}")
    if title:
        print(f"  {title}")
        print(f"{'─' * 60}")


def parse_json_output(raw: str) -> dict | None:
    """Try to extract JSON from model output, stripping fences if needed."""
    clean = re.sub(r"^```[a-z]*\n?", "", raw.strip())
    clean = re.sub(r"\n?```$", "", clean).strip()
    try:
        return json.loads(clean)
    except Exception:
        return None


# ── Core ──────────────────────────────────────────────────────────────────────

def run_scenario(
    scenario: str,
    kb: dict,
    model: str,
    fmt: str,
    start_screen: str | None,
    save: bool,
    dry_run: bool,
):
    system, user = build_scenario_prompt(
        scenario=scenario,
        kb=kb,
        fmt=fmt,
        start_screen=start_screen,
    )

    print_divider("Scenario")
    print(f"  Goal    : {scenario}")
    print(f"  Format  : {fmt}")
    print(f"  Model   : {model}")
    if start_screen:
        print(f"  Start   : {start_screen}")

    if dry_run:
        print_divider("System prompt (preview)")
        print(system[:400])
        print_divider("User prompt (preview)")
        print(user[:800])
        print("\n[dry-run complete — no model call made]")
        return

    print_divider("Generating…")
    t0 = time.time()

    try:
        raw = call_model(model, system, user)
    except Exception as e:
        print(f"\nERROR calling model: {e}")
        sys.exit(1)

    elapsed = round(time.time() - t0, 1)

    # Pretty-print JSON if applicable
    if fmt == "json":
        parsed = parse_json_output(raw)
        if parsed:
            output = json.dumps(parsed, indent=2)
        else:
            output = raw
            print("  [warning] Model output was not clean JSON — showing raw text")
    else:
        output = raw

    print_divider(f"Result  ({elapsed}s)")
    print(output)

    if save:
        path = save_result(scenario, fmt, output)
        print(f"\n  Saved → {path.resolve()}")

    return output


# ── Interactive mode ──────────────────────────────────────────────────────────

EXAMPLE_SCENARIOS = [
    "play a song",
    "navigate home",
    "increase driver temperature to 74 degrees",
    "turn on A/C",
    "call back a missed call",
    "switch audio source to FM Radio",
    "enable defrost",
    "set navigation to work",
    "turn on shuffle and play music",
    "reduce fan speed",
]

def interactive_mode(kb: dict, model: str, fmt: str, save: bool):
    print("\n  Car Infotainment — Scenario Test Step Generator")
    print("  Type a scenario in plain English, or 'quit' to exit.\n")
    print("  Examples:")
    for ex in EXAMPLE_SCENARIOS:
        print(f"    • {ex}")
    print()

    screens = list(kb.get("screens", {}).keys())

    while True:
        try:
            scenario = input("  Scenario > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Bye!")
            break

        if not scenario:
            continue
        if scenario.lower() in ("quit", "exit", "q"):
            print("  Bye!")
            break

        # Optional: ask for format override
        fmt_input = input(f"  Format   [steps/gherkin/json, enter={fmt}] > ").strip().lower()
        use_fmt   = fmt_input if fmt_input in ("steps", "gherkin", "json") else fmt

        # Optional: ask for start screen
        start_input = input(f"  Start screen  [{'/'.join(screens)}, enter=home] > ").strip().lower()
        use_start   = start_input if start_input in screens else "home"

        run_scenario(
            scenario=scenario,
            kb=kb,
            model=model,
            fmt=use_fmt,
            start_screen=use_start,
            save=save,
            dry_run=False,
        )
        print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Generate test steps for a plain-English scenario using "
                    "the wireframe KB and a local Ollama model.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\nExamples:\n"
               '  python scripts/scenario_steps.py --scenario "play a song"\n'
               '  python scripts/scenario_steps.py --scenario "turn on A/C" --format gherkin\n'
               "  python scripts/scenario_steps.py   # interactive mode\n",
    )
    p.add_argument("--scenario", default=None,
                   help="Plain-English scenario (omit for interactive mode)")
    p.add_argument("--format",   default=DEFAULT_FMT,
                   choices=["steps", "gherkin", "json"])
    p.add_argument("--model",    default=DEFAULT_MODEL)
    p.add_argument("--kb",       default=DEFAULT_KB)
    p.add_argument("--start",    default="home",
                   help="Starting screen ID")
    p.add_argument("--save",     action="store_true",
                   help="Save output to output/scenarios/")
    p.add_argument("--dry-run",  action="store_true",
                   help="Print prompt without calling Ollama")
    return p.parse_args()


def main():
    args = parse_args()
    kb   = load_kb(args.kb)

    if args.scenario:
        run_scenario(
            scenario     = args.scenario,
            kb           = kb,
            model        = args.model,
            fmt          = args.format,
            start_screen = args.start,
            save         = args.save,
            dry_run      = args.dry_run,
        )
    else:
        interactive_mode(
            kb    = kb,
            model = args.model,
            fmt   = args.format,
            save  = args.save,
        )


if __name__ == "__main__":
    main()
