"""
prompts/templates.py
--------------------
All prompt templates for navigation flow test case generation.
Each template receives a single `flow` dict and `screens` dict and returns
a ready-to-send prompt string.

Flow dict shape:
  {
    "id":      "home_to_media_via_tab",
    "from":    "home",
    "to":      "media",
    "trigger": "tab_media",
    "label":   "Media tab"
  }
"""

# ── Shared system message ─────────────────────────────────────────────────────

SYSTEM = (
    "You are a senior QA engineer specialising in automotive touchscreen "
    "infotainment systems. You write precise, complete test cases that a junior "
    "tester can execute without ambiguity. Always reference element IDs exactly "
    "as given. Consider driver-safety concerns (response time, no distraction). "
    "Output ONLY the test case content — no preamble, no explanation."
)

# ── Helper ────────────────────────────────────────────────────────────────────

def _screen_line(screens: dict, sid: str) -> str:
    s = screens.get(sid, {})
    return f'"{s.get("title", sid)}" (url: {s.get("url", "/" + sid)})'


# ── Format 1: Step-by-step ────────────────────────────────────────────────────

STEPS_TEMPLATE = """\
Generate a step-by-step test case for the following navigation flow.

NAVIGATION FLOW
  Flow ID   : {flow_id}
  From      : {from_screen}  →  {from_title}
  To        : {to_screen}    →  {to_title}
  Trigger   : element id = "{trigger_id}",  label = "{trigger_label}"

OUTPUT FORMAT — use exactly this structure:
  Test ID     : TC-NAV-{flow_id_upper}
  Title       : <one sentence describing what is being verified>
  Priority    : High | Medium | Low
  Precondition: <system state before the test starts>

  Steps:
    1. <action>
    2. <action>
    ...

  Expected result : <what the tester should observe if the flow works correctly>
  Pass criteria   : <binary observable condition>
  Fail indicators : <list of observable signs that indicate a failure>
  Notes           : <automotive / driver-safety considerations if any>

Generate the test case now.
"""

def steps_prompt(flow: dict, screens: dict) -> str:
    return STEPS_TEMPLATE.format(
        flow_id        = flow["id"],
        flow_id_upper  = flow["id"].upper(),
        from_screen    = flow["from"],
        from_title     = _screen_line(screens, flow["from"]),
        to_screen      = flow["to"],
        to_title       = _screen_line(screens, flow["to"]),
        trigger_id     = flow["trigger"],
        trigger_label  = flow["label"],
    )


# ── Format 2: Gherkin BDD ─────────────────────────────────────────────────────

GHERKIN_TEMPLATE = """\
Generate a Gherkin BDD feature file for the following navigation flow.

NAVIGATION FLOW
  Flow ID   : {flow_id}
  From      : {from_screen}  →  {from_title}
  To        : {to_screen}    →  {to_title}
  Trigger   : element id = "{trigger_id}",  label = "{trigger_label}"

OUTPUT FORMAT — valid Gherkin syntax only:

Feature: Navigation — {from_screen} to {to_screen}

  Background:
    Given <system precondition>

  Scenario: Happy path — navigate via "{trigger_label}"
    Given ...
    When  ...
    Then  ...
    And   ...

  Scenario: Element is visible and tappable
    Given ...
    Then  ...

  Scenario: Navigating back returns to source screen
    Given the user has navigated to {to_screen}
    When  ...
    Then  ...

Generate the feature file now.
"""

def gherkin_prompt(flow: dict, screens: dict) -> str:
    return GHERKIN_TEMPLATE.format(
        flow_id        = flow["id"],
        from_screen    = flow["from"],
        from_title     = _screen_line(screens, flow["from"]),
        to_screen      = flow["to"],
        to_title       = _screen_line(screens, flow["to"]),
        trigger_id     = flow["trigger"],
        trigger_label  = flow["label"],
    )


# ── Format 3: JSON ────────────────────────────────────────────────────────────

JSON_TEMPLATE = """\
Generate test cases as a JSON object for the following navigation flow.
Return ONLY valid JSON — no markdown fences, no explanation.

NAVIGATION FLOW
  Flow ID   : {flow_id}
  From      : {from_screen}  ({from_url})
  To        : {to_screen}    ({to_url})
  Trigger   : element id = "{trigger_id}",  label = "{trigger_label}"

JSON SCHEMA:
{{
  "flow_id": "{flow_id}",
  "from_screen": "{from_screen}",
  "to_screen": "{to_screen}",
  "trigger_element": "{trigger_id}",
  "test_cases": [
    {{
      "id": "TC-NAV-001",
      "title": "<string>",
      "priority": "High|Medium|Low",
      "precondition": "<string>",
      "steps": ["<string>", "<string>"],
      "expected_result": "<string>",
      "pass_criteria": "<string>",
      "fail_indicators": ["<string>"],
      "tags": ["navigation", "<other tags>"]
    }}
  ]
}}

Generate at least 3 test cases covering: happy path, element visibility, back navigation.
"""

def json_prompt(flow: dict, screens: dict) -> str:
    from_screen = screens.get(flow["from"], {})
    to_screen   = screens.get(flow["to"],   {})
    return JSON_TEMPLATE.format(
        flow_id       = flow["id"],
        from_screen   = flow["from"],
        from_url      = from_screen.get("url", "/" + flow["from"]),
        to_screen     = flow["to"],
        to_url        = to_screen.get("url",   "/" + flow["to"]),
        trigger_id    = flow["trigger"],
        trigger_label = flow["label"],
    )


# ── Format 3: All three combined ──────────────────────────────────────────────

ALL_TEMPLATE = """\
Generate test cases in ALL THREE formats for the following navigation flow.

NAVIGATION FLOW
  Flow ID   : {flow_id}
  From      : {from_screen}  →  {from_title}
  To        : {to_screen}    →  {to_title}
  Trigger   : element id = "{trigger_id}",  label = "{trigger_label}"

OUTPUT — produce three clearly labelled sections:

--- STEP-BY-STEP ---
(numbered test case with precondition, steps, expected result, pass/fail criteria)

--- GHERKIN ---
(Feature / Background / Scenario blocks in valid Gherkin)

--- JSON ---
(valid JSON object, no fences, matching the schema:
 flow_id, from_screen, to_screen, trigger_element, test_cases[])

Generate all three sections now.
"""

def all_prompt(flow: dict, screens: dict) -> str:
    return ALL_TEMPLATE.format(
        flow_id        = flow["id"],
        from_screen    = flow["from"],
        from_title     = _screen_line(screens, flow["from"]),
        to_screen      = flow["to"],
        to_title       = _screen_line(screens, flow["to"]),
        trigger_id     = flow["trigger"],
        trigger_label  = flow["label"],
    )


# ── Dispatch ──────────────────────────────────────────────────────────────────

PROMPT_FN = {
    "steps":   steps_prompt,
    "gherkin": gherkin_prompt,
    "json":    json_prompt,
    "all":     all_prompt,
}

def build_prompt(fmt: str, flow: dict, screens: dict) -> tuple[str, str]:
    """Return (system_message, user_message) for the given format."""
    fn = PROMPT_FN.get(fmt)
    if not fn:
        raise ValueError(f"Unknown format '{fmt}'. Choose: {list(PROMPT_FN)}")
    return SYSTEM, fn(flow, screens)
