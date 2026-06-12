#!/usr/bin/env python3
"""
scripts/list_flows.py
---------------------
Print all navigation flows in the KB — useful before running generate_tests.py.

Usage:
    python scripts/list_flows.py
    python scripts/list_flows.py --filter home
"""

import argparse
import json
import sys
from pathlib import Path

def main():
    ap = argparse.ArgumentParser(description="List navigation flows in wireframe KB")
    ap.add_argument("--kb",     default="input/wireframe_kb.json")
    ap.add_argument("--filter", default=None, help="Show only flows containing this string")
    args = ap.parse_args()

    kb_path = Path(args.kb)
    if not kb_path.exists():
        print(f"ERROR: {kb_path} not found"); sys.exit(1)

    kb    = json.loads(kb_path.read_text())
    flows = kb.get("navigation_flows", {})

    print(f"\n  System  : {kb.get('system','?')}")
    print(f"  Screens : {', '.join(kb.get('screens', {}).keys())}")
    print(f"  Flows   : {len(flows)} total\n")
    print(f"  {'ID':<35} {'FROM':<12} {'TO':<12} TRIGGER")
    print(f"  {'─'*35} {'─'*12} {'─'*12} {'─'*25}")

    for fid, flow in flows.items():
        if args.filter and args.filter.lower() not in fid.lower():
            continue
        print(f"  {fid:<35} {flow['from']:<12} {flow['to']:<12} {flow['trigger']}")

    print()

if __name__ == "__main__":
    main()
