#!/usr/bin/env python3
"""
scripts/generate_tests.py
--------------------------
Reads wireframe_kb.json, calls a local Ollama model for every navigation
flow, and writes test cases to the output/ folder.

Usage examples
--------------
# All flows, step-by-step format, default model
python scripts/generate_tests.py

# Single flow
python scripts/generate_tests.py --flow home_to_media_via_tab

# All flows, Gherkin format, specific model
python scripts/generate_tests.py --format gherkin --model mistral:7b

# All flows, all three formats
python scripts/generate_tests.py --format all

# Dry-run: print prompts without calling Ollama
python scripts/generate_tests.py --dry-run

Options
-------
  --kb        Path to wireframe_kb.json   [default: input/wireframe_kb.json]
  --flow      Single flow ID to generate  [default: all flows]
  --format    steps | gherkin | json | all [default: steps]
  --model     Ollama model name           [default: mistral:7b]
  --out       Output directory            [default: output/]
  --dry-run   Print prompts only, no LLM calls
  --delay     Seconds between calls       [default: 0]
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))
from prompts.templates import build_prompt

try:
    import ollama
except ImportError:
    print("ERROR: ollama package not installed.\n  pip install ollama")
    sys.exit(1)


# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_KB     = "input/wireframe_kb.json"
DEFAULT_MODEL  = "mistral:7b"
DEFAULT_FORMAT = "steps"
DEFAULT_OUT    = "output"

FORMAT_EXT = {
    "steps":   "txt",
    "gherkin": "feature",
    "json":    "json",
    "all":     "txt",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_kb(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        print(f"ERROR: KB file not found: {p}")
        sys.exit(1)
    return json.loads(p.read_text())


def call_ollama(model: str, system: str, user: str) -> str:
    resp = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        options={"temperature": 0.2, "num_ctx": 4096},
    )
    return resp["message"]["content"].strip()


def save_output(out_dir: Path, flow_id: str, fmt: str, content: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ext  = FORMAT_EXT.get(fmt, "txt")
    path = out_dir / f"{flow_id}.{ext}"
    path.write_text(content, encoding="utf-8")
    return path


def print_banner(msg: str):
    print(f"\n{'─'*60}")
    print(f"  {msg}")
    print(f"{'─'*60}")


# ── Core generation ───────────────────────────────────────────────────────────

def generate_one(flow: dict, screens: dict, model: str,
                 fmt: str, out_dir: Path, dry_run: bool) -> dict:
    fid    = flow["id"]
    system, user = build_prompt(fmt, flow, screens)

    print(f"\n  Flow  : {fid}")
    print(f"  Route : {flow['from']} → {flow['to']}  via '{flow['label']}'")

    if dry_run:
        print("\n  [DRY-RUN] Prompt (system):")
        print("  " + system[:120] + "...")
        print("\n  [DRY-RUN] Prompt (user):")
        print("  " + user[:300] + "...")
        return {"flow_id": fid, "status": "dry-run"}

    print(f"  Model : {model}  |  format: {fmt}")
    t0 = time.time()

    try:
        content = call_ollama(model, system, user)
        elapsed = round(time.time() - t0, 1)
        out_path = save_output(out_dir, fid, fmt, content)
        print(f"  ✓  {elapsed}s  →  {out_path}")
        return {"flow_id": fid, "status": "ok",
                "elapsed_s": elapsed, "path": str(out_path)}
    except Exception as e:
        print(f"  ✗  ERROR: {e}")
        return {"flow_id": fid, "status": "error", "error": str(e)}


def generate_all(kb: dict, flow_filter: str | None, model: str,
                 fmt: str, out_dir: Path, dry_run: bool, delay: float) -> list:
    flows   = kb.get("navigation_flows", {})
    screens = kb.get("screens", {})

    if not flows:
        print("ERROR: No navigation_flows found in KB.")
        sys.exit(1)

    targets = (
        {flow_filter: flows[flow_filter]}
        if flow_filter
        else flows
    )

    if flow_filter and flow_filter not in flows:
        print(f"ERROR: Flow '{flow_filter}' not found. Available:")
        for k in flows:
            print(f"  {k}")
        sys.exit(1)

    print_banner(
        f"Generating {len(targets)} test case(s)  "
        f"| model: {model}  | format: {fmt}"
    )

    results = []
    for i, (fid, flow) in enumerate(targets.items(), 1):
        print(f"\n[{i}/{len(targets)}]", end="")
        r = generate_one(flow, screens, model, fmt, out_dir, dry_run)
        results.append(r)
        if delay and i < len(targets):
            time.sleep(delay)

    return results


# ── Summary report ────────────────────────────────────────────────────────────

def write_summary(results: list, out_dir: Path, model: str, fmt: str):
    ok      = [r for r in results if r["status"] == "ok"]
    errors  = [r for r in results if r["status"] == "error"]
    skipped = [r for r in results if r["status"] == "dry-run"]

    print_banner("Summary")
    print(f"  Total   : {len(results)}")
    print(f"  OK      : {len(ok)}")
    print(f"  Errors  : {len(errors)}")
    print(f"  Skipped : {len(skipped)}")
    if ok:
        avg = round(sum(r.get("elapsed_s", 0) for r in ok) / len(ok), 1)
        print(f"  Avg time: {avg}s per flow")
    print(f"\n  Output  : {out_dir.resolve()}/")

    if errors:
        print("\n  Failed flows:")
        for r in errors:
            print(f"    ✗ {r['flow_id']}: {r['error']}")

    # Write JSON summary log
    out_dir.mkdir(parents=True, exist_ok=True)
    log = {
        "generated_at": datetime.now().isoformat() + "Z",
        "model":  model,
        "format": fmt,
        "results": results,
    }
    log_path = out_dir / "_summary.json"
    log_path.write_text(json.dumps(log, indent=2))
    print(f"\n  Log     : {log_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Generate navigation-flow test cases from a wireframe KB "
                    "using a local Ollama model.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--kb",      default=DEFAULT_KB,     help="Path to wireframe_kb.json")
    p.add_argument("--flow",    default=None,            help="Single flow ID (omit for all)")
    p.add_argument("--format",  default=DEFAULT_FORMAT,
                   choices=["steps", "gherkin", "json", "all"],
                   help="Test case output format")
    p.add_argument("--model",   default=DEFAULT_MODEL,   help="Ollama model name")
    p.add_argument("--out",     default=DEFAULT_OUT,     help="Output directory")
    p.add_argument("--dry-run", action="store_true",     help="Print prompts, skip LLM")
    p.add_argument("--delay",   type=float, default=0,   help="Seconds between calls")
    return p.parse_args()


def main():
    args    = parse_args()
    kb      = load_kb(args.kb)
    out_dir = Path(args.out) / args.format

    results = generate_all(
        kb          = kb,
        flow_filter = args.flow,
        model       = args.model,
        fmt         = args.format,
        out_dir     = out_dir,
        dry_run     = args.dry_run,
        delay       = args.delay,
    )

    write_summary(results, out_dir, args.model, args.format)


if __name__ == "__main__":
    main()
