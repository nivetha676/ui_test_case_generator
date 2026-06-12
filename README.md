# Navigation flow test case generator

Reads a `wireframe_kb.json` and uses a local Ollama model to generate
test cases for every navigation flow — in step-by-step, Gherkin, or JSON format.

## How to run the scripts:

```bash
# Single scenario — step-by-step
python scripts/scenario_steps.py --scenario "play a song"

# Gherkin format
python scripts/scenario_steps.py --scenario "turn on A/C" --format gherkin

# JSON (machine-readable, every step has element_id)
python scripts/scenario_steps.py --scenario "navigate to work" --format json

# Start from a specific screen (not home)
python scripts/scenario_steps.py --scenario "call back a missed call" --start phone

# Save to output/scenarios/
python scripts/scenario_steps.py --scenario "enable defrost" --save

# Interactive REPL — type scenarios one after another
python scripts/scenario_steps.py
```

## Project structure

```
testgen_project/
├── input/
│   └── wireframe_kb.json          ← your wireframe (edit this)
├── prompts/
│   └── templates.py               ← all prompt templates (edit to customise)
├── output/
│   ├── steps/                     ← .txt files, one per flow
│   ├── gherkin/                   ← .feature files, one per flow
│   ├── json/                      ← .json files, one per flow
│   └── report.html                ← consolidated HTML report (batch runner)
├── scripts/
│   ├── generate_tests.py          ← main generator
│   ├── batch_runner.py            ← runs all formats + builds HTML report
│   └── list_flows.py              ← list flows in KB
└── requirements.txt
```

## Setup

```bash
pip install -r requirements.txt

# Pull whichever model you have
ollama pull mistral:7b      # recommended — fast, structured output
ollama pull phi3:mini       # lighter (2.2 GB)
ollama pull llama3:8b       # good quality, more RAM
```

## Quick start

```bash
# 1. See all flows in your KB
python scripts/list_flows.py

# 2. Generate test cases for ONE flow (step-by-step)
python scripts/generate_tests.py --flow home_to_media_via_tab

# 3. Generate for ALL flows (step-by-step, default)
python scripts/generate_tests.py

# 4. Generate ALL flows in ALL formats → HTML report
python scripts/batch_runner.py

# Open the report
open output/report.html        # macOS
xdg-open output/report.html    # Linux
```

## All CLI options

### generate_tests.py

| Option      | Default                    | Description                            |
|-------------|----------------------------|----------------------------------------|
| `--kb`      | `input/wireframe_kb.json`  | Path to your KB file                   |
| `--flow`    | *(all flows)*              | Single flow ID to generate             |
| `--format`  | `steps`                    | `steps` / `gherkin` / `json` / `all`  |
| `--model`   | `mistral:7b`               | Any Ollama model you have pulled       |
| `--out`     | `output/`                  | Output directory                       |
| `--dry-run` | off                        | Print prompts without calling Ollama   |
| `--delay`   | `0`                        | Seconds between calls (rate limiting)  |

### batch_runner.py

| Option      | Default                    | Description                            |
|-------------|----------------------------|----------------------------------------|
| `--model`   | `mistral:7b`               | Ollama model                           |
| `--kb`      | `input/wireframe_kb.json`  | KB path                                |
| `--out`     | `output/`                  | Output directory                       |
| `--flow`    | *(all flows)*              | Limit to one flow                      |
| `--formats` | `steps gherkin json`       | Which formats to run                   |

## Using your own wireframe_kb.json

Replace `input/wireframe_kb.json` with your file. The only required keys are:

```json
{
  "system": "Your App Name",
  "screens": {
    "screen_id": { "id": "...", "title": "...", "url": "/..." }
  },
  "navigation_flows": {
    "flow_id": {
      "id": "flow_id",
      "from": "source_screen_id",
      "to": "target_screen_id",
      "trigger": "element_id",
      "label": "Human-readable element name"
    }
  }
}
```

## Customising prompts

Edit `prompts/templates.py`. Each format has its own function:
- `steps_prompt(flow, screens)` → step-by-step format
- `gherkin_prompt(flow, screens)` → Gherkin BDD format
- `json_prompt(flow, screens)` → JSON format
- `all_prompt(flow, screens)` → all three combined

The `SYSTEM` constant at the top sets the LLM persona — adjust it to match
your domain (e.g. replace "automotive infotainment" with "mobile banking app").

## Output files

Each flow produces one file named `<flow_id>.<ext>`:

| Format  | Extension | Example file                              |
|---------|-----------|-------------------------------------------|
| steps   | `.txt`    | `output/steps/home_to_media_via_tab.txt`  |
| gherkin | `.feature`| `output/gherkin/home_to_media_via_tab.feature` |
| json    | `.json`   | `output/json/home_to_media_via_tab.json`  |

A `_summary.json` is also written to each format folder after a run.
The batch runner writes `output/report.html` — open it in any browser.

## Model recommendations

| Model            | Size   | Quality | Speed  | Best for               |
|------------------|--------|---------|--------|------------------------|
| `mistral:7b`     | 4.1 GB | ★★★★   | ★★★   | Default — balanced     |
| `phi3:mini`      | 2.2 GB | ★★★    | ★★★★  | Low RAM machines       |
| `llama3:8b`      | 4.7 GB | ★★★★★  | ★★★   | Highest quality output |
| `qwen2.5:7b`     | 4.7 GB | ★★★★   | ★★★   | Good at structured JSON|
