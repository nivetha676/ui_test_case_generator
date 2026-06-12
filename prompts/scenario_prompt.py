"""
prompts/scenario_prompt.py
--------------------------
Builds the prompt sent to the local LLM for scenario-based test step generation.

The LLM receives:
  1. The full wireframe KB (screens + nav flows) as structured context
  2. The user's plain-English scenario ("play a song", "set temperature to 72")
  3. Clear output instructions for the chosen format

Output formats
--------------
  steps    — numbered human-readable steps
  gherkin  — Given / When / Then BDD scenarios
  json     — machine-readable step objects
"""

import json


# ── System persona ─────────────────────────────────────────────────────────────

SYSTEM = """\
You are a senior QA engineer for a car infotainment touchscreen system.
You are given the complete UI wireframe as structured data (screens, elements,
navigation flows). When the user describes a goal or scenario in plain English,
you must:

1. Identify which screen(s) are involved
2. Find the correct navigation path through the wireframe
3. List every tap, swipe, or input needed — referencing element IDs exactly
4. State the expected result after each key action
5. Flag any preconditions (e.g. Bluetooth must be connected)

Be precise. A junior tester must be able to follow your steps without
asking questions. Reference element IDs in parentheses after each step.
Consider driver-safety: note if an action should only be performed while parked.
"""


# ── KB formatter ───────────────────────────────────────────────────────────────

def _format_kb(kb: dict) -> str:
    """
    Produces a compact but complete text representation of the KB
    so it fits in the model's context window.
    """
    lines = []
    lines.append(f"SYSTEM: {kb.get('system', 'Unknown')}")
    lines.append("")

    # Screens + their interactive elements
    lines.append("SCREENS AND ELEMENTS:")
    for sid, screen in kb.get("screens", {}).items():
        lines.append(f"  Screen: {sid} — {screen.get('title','')} ({screen.get('url','')})")
        for el in screen.get("elements", []):
            if not el.get("tappable", False):
                continue
            action = el.get("action", "none")
            target = f" → {el['target_screen']}" if el.get("target_screen") else ""
            states = f" [{'/'.join(el['states'])}]" if el.get("states") else ""
            rng    = f" (min:{el['min']} max:{el['max']})" if "min" in el else ""
            req    = f" ⚠ requires: {el['requires']}" if el.get("requires") else ""
            lines.append(
                f"    [{el['type']}] id={el['id']}  label=\"{el['label']}\""
                f"  action={action}{target}{states}{rng}{req}"
            )
        lines.append("")

    # Navigation flows
    lines.append("NAVIGATION FLOWS:")
    for fid, flow in kb.get("navigation_flows", {}).items():
        lines.append(
            f"  {flow['from']} → {flow['to']}"
            f"  via element \"{flow['trigger']}\" ({flow['label']})"
        )

    return "\n".join(lines)


# ── Format templates ───────────────────────────────────────────────────────────

_STEPS_INSTRUCTION = """\
OUTPUT FORMAT — step-by-step test procedure:

  Scenario    : <restate the goal clearly>
  Start screen: <which screen the user starts on>
  Precondition: <what must be true before starting>

  Steps:
    1. <action — include element id in parentheses>
    2. <action>
    ...

  Expected outcome : <what the user sees/hears when done>
  Pass criteria    : <binary observable condition>
  Safety note      : <any driver-safety concern, or "None">
"""

_GHERKIN_INSTRUCTION = """\
OUTPUT FORMAT — Gherkin BDD (Feature / Background / Scenario blocks):

  Feature: <scenario title>

    Background:
      Given <system precondition>
      And   <any other precondition>

    Scenario: Happy path — <goal>
      Given  <starting state>
      When   <first action with element id>
      And    <next action>
      ...
      Then   <expected outcome>
      And    <additional assertion>

    Scenario: Already on correct screen
      Given  ...
      Then   ...

  Use element IDs in step text like: tap "Play/Pause" (btn_play_pause)
"""

_JSON_INSTRUCTION = """\
OUTPUT FORMAT — valid JSON only, no markdown fences, no explanation:

{
  "scenario": "<plain-English goal>",
  "start_screen": "<screen_id>",
  "preconditions": ["<string>"],
  "steps": [
    {
      "step_number": 1,
      "screen": "<screen_id at this point>",
      "action": "tap | swipe | type | observe",
      "element_id": "<id from KB or null>",
      "element_label": "<human label>",
      "input_value": "<text/value if action=type, else null>",
      "description": "<what the tester does>",
      "expected_result": "<what happens after this step>"
    }
  ],
  "final_expected_outcome": "<string>",
  "pass_criteria": "<string>",
  "safety_note": "<string or null>"
}
"""

FORMAT_INSTRUCTIONS = {
    "steps":   _STEPS_INSTRUCTION,
    "gherkin": _GHERKIN_INSTRUCTION,
    "json":    _JSON_INSTRUCTION,
}


# ── Main builder ───────────────────────────────────────────────────────────────

def build_scenario_prompt(
    scenario: str,
    kb: dict,
    fmt: str = "steps",
    start_screen: str | None = None,
) -> tuple[str, str]:
    """
    Returns (system_message, user_message) for the given scenario.

    Parameters
    ----------
    scenario     : plain-English goal, e.g. "play a song"
    kb           : parsed wireframe_kb.json dict
    fmt          : "steps" | "gherkin" | "json"
    start_screen : optional starting screen override (default: first screen in KB)
    """
    if fmt not in FORMAT_INSTRUCTIONS:
        raise ValueError(f"Unknown format '{fmt}'. Choose: {list(FORMAT_INSTRUCTIONS)}")

    kb_text    = _format_kb(kb)
    fmt_instr  = FORMAT_INSTRUCTIONS[fmt]
    start_hint = (
        f"The user starts on the '{start_screen}' screen."
        if start_screen
        else "Assume the user starts on the home/dashboard screen."
    )

    user = f"""\
WIREFRAME KNOWLEDGE BASE:
{kb_text}

─────────────────────────────────────────
SCENARIO TO TEST:
  "{scenario}"

{start_hint}

{fmt_instr}

Generate the test steps for this scenario now.
"""
    return SYSTEM, user
