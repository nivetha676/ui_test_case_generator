#!/usr/bin/env python3
"""
scripts/batch_runner.py
-----------------------
Runs generate_tests.py for ALL formats in one go and produces
a single consolidated HTML report across every flow and format.

Usage:
    python scripts/batch_runner.py
    python scripts/batch_runner.py --model phi3:mini
    python scripts/batch_runner.py --flow home_to_media_via_tab
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

FORMATS = ["steps", "gherkin", "json"]

HTML_STYLE = """
<style>
body{font-family:system-ui,sans-serif;max-width:1100px;margin:40px auto;padding:0 20px;background:#fafaf9;color:#1a1a1a}
h1{font-size:20px;font-weight:500;margin-bottom:4px}
.meta{color:#888;font-size:13px;margin-bottom:24px}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:28px}
.card{background:#fff;border:1px solid #e8e8e4;border-radius:8px;padding:14px;text-align:center}
.card .n{font-size:26px;font-weight:500}.card .l{font-size:11px;color:#888;margin-top:2px}
.flow-block{background:#fff;border:1px solid #e8e8e4;border-radius:8px;padding:16px;margin-bottom:14px}
.flow-hdr{font-size:14px;font-weight:500;margin-bottom:10px;display:flex;gap:8px;align-items:center}
.badge{font-size:10px;padding:2px 8px;border-radius:4px}
.b-ok{background:#eaf3de;color:#3B6D11}.b-err{background:#fcebeb;color:#A32D2D}
.tabs{display:flex;gap:4px;margin-bottom:8px}
.tab-btn{border:1px solid #ddd;background:#f5f5f3;border-radius:4px;padding:3px 10px;font-size:11px;cursor:pointer}
.tab-btn.act{background:#1a1a1a;color:#fff;border-color:#1a1a1a}
.tc-content{display:none;font-size:12px;background:#f8f8f7;border-radius:6px;padding:12px;
  white-space:pre-wrap;font-family:monospace;line-height:1.6;max-height:400px;overflow-y:auto}
.tc-content.show{display:block}
.route{font-size:12px;color:#666}
</style>
"""

def run_format(fmt: str, model: str, kb: str, flow: str | None, out_base: str) -> dict:
    cmd = [
        sys.executable, "scripts/generate_tests.py",
        "--format", fmt,
        "--model",  model,
        "--kb",     kb,
        "--out",    out_base,
    ]
    if flow:
        cmd += ["--flow", flow]

    t0   = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = round(time.time() - t0, 1)

    summary_path = Path(out_base) / fmt / "_summary.json"
    summary      = {}
    if summary_path.exists():
        summary = json.loads(summary_path.read_text())

    return {
        "format":  fmt,
        "elapsed": elapsed,
        "ok":      proc.returncode == 0,
        "summary": summary,
        "stdout":  proc.stdout,
    }


def build_html(all_results: list, model: str, kb_path: str) -> str:
    # Collect per-flow results across formats
    flows: dict[str, dict] = {}
    total_ok = total_err = 0

    for fmt_result in all_results:
        fmt     = fmt_result["format"]
        summary = fmt_result.get("summary", {})
        for r in summary.get("results", []):
            fid = r["flow_id"]
            if fid not in flows:
                flows[fid] = {"id": fid, "formats": {}}
            flows[fid]["formats"][fmt] = r

            if r["status"] == "ok":
                total_ok += 1
            elif r["status"] == "error":
                total_err += 1

    # Read file contents
    for fid, data in flows.items():
        for fmt, r in data["formats"].items():
            p = Path(r.get("path", ""))
            data["formats"][fmt]["content"] = p.read_text() if p.exists() else "(not generated)"

    # Build HTML
    cards = f"""
<div class="cards">
  <div class="card"><div class="n">{len(flows)}</div><div class="l">Flows</div></div>
  <div class="card"><div class="n">{len(FORMATS)}</div><div class="l">Formats</div></div>
  <div class="card"><div class="n" style="color:#3B6D11">{total_ok}</div><div class="l">Generated</div></div>
  <div class="card"><div class="n" style="color:#A32D2D">{total_err}</div><div class="l">Errors</div></div>
</div>"""

    blocks = ""
    for fid, data in flows.items():
        fmts = data["formats"]
        any_ok = any(v["status"] == "ok" for v in fmts.values())
        status_badge = '<span class="badge b-ok">OK</span>' if any_ok else '<span class="badge b-err">ERROR</span>'

        tabs = ""
        contents = ""
        for i, (fmt, r) in enumerate(fmts.items()):
            act = "act" if i == 0 else ""
            show = "show" if i == 0 else ""
            tabs += f'<button class="tab-btn {act}" onclick="showTab(this,\'{fid}_{fmt}\')">{fmt}</button>'
            content = r.get("content", "").replace("<", "&lt;").replace(">", "&gt;")
            contents += f'<div class="tc-content {show}" id="{fid}_{fmt}">{content}</div>'

        blocks += f"""
<div class="flow-block">
  <div class="flow-hdr">{status_badge} <code>{fid}</code></div>
  <div class="tabs">{tabs}</div>
  {contents}
</div>"""

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Test cases — {model}</title>
{HTML_STYLE}
<script>
function showTab(btn, id){{
  const block = btn.closest('.flow-block');
  block.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('act'));
  block.querySelectorAll('.tc-content').forEach(c=>c.classList.remove('show'));
  btn.classList.add('act');
  document.getElementById(id).classList.add('show');
}}
</script>
</head><body>
<h1>Navigation flow test cases</h1>
<p class="meta">KB: {kb_path} &nbsp;·&nbsp; Model: {model} &nbsp;·&nbsp; {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC</p>
{cards}
{blocks}
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model",  default="mistral:7b")
    ap.add_argument("--kb",     default="input/wireframe_kb.json")
    ap.add_argument("--out",    default="output")
    ap.add_argument("--flow",   default=None)
    ap.add_argument("--formats",nargs="+", default=FORMATS,
                    choices=["steps","gherkin","json"])
    args = ap.parse_args()

    print(f"\n=== Batch runner  |  model: {args.model}  |  formats: {args.formats} ===")

    all_results = []
    for fmt in args.formats:
        print(f"\n>>> Format: {fmt}")
        r = run_format(fmt, args.model, args.kb, args.flow, args.out)
        all_results.append(r)
        status = "✓" if r["ok"] else "✗"
        print(f"    {status}  {r['elapsed']}s")

    # Write HTML report
    html = build_html(all_results, args.model, args.kb)
    report_path = Path(args.out) / "report.html"
    report_path.write_text(html)

    print(f"\n=== Done ===")
    print(f"  HTML report : {report_path.resolve()}")
    print(f"  Open it in your browser to review all test cases.")


if __name__ == "__main__":
    main()
