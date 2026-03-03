# BSP-Generator

Automatic BSP generation with Python and Claude models via Amazon Bedrock

## Prerequisites

It's highly recommended to use [`uv`](https://docs.astral.sh/uv) for this project.

- Download it with `pip install uv`

Fill out the credentials as directed by [.env.example](./.env.example)

## Running

`uv run -m app.main`

If `build_gate` is strict and CCS workspace/project are missing, the CLI now prompts
for them during the run. You can leave prompts blank to skip compile gate for that run.

Use `--no-profile` to run with in-code defaults only (skip both `--profile` and
auto-discovered `generation_profile.yaml`).

### Interactive Menu

Running bare in a TTY (`py main.py` or `uv run -m app.main`) now opens a guided menu.
Flagged/scripted runs bypass the menu.

Menu actions:
- Full generation
- Validate existing output
- Post-gen prompt only (existing output)
- Post-gen prompt + firmware generation (existing output)
- Compile gate only (existing output)
- Docs only (Doxygen + quality report)
- Reflash existing output

### Output Picker

Recent outputs are discovered from:
- `./output_*`
- `./app/output_*`

Use:
- `--list-outputs` to print recent output folders and status hints
- `--output-index N` to select one non-interactively
- interactive picker when a menu/action requires an output folder

### Action Mode

You can run workflows directly with:

`py main.py --action <generate|validate|postgen_prompt|postgen_generate|compile_only|docs_only|reflash>`

Combine with `--output-dir` or `--output-index` for actions on existing outputs.

### Reflash Template

`generation_profile.yaml` supports:

```yaml
flash:
  enabled: true
  command_template: "your_flash_command --out \"{output_dir}\""
  working_dir: "C:/path/optional"
  timeout_sec: 120
  env:
    KEY: "VALUE"
```

Template variables:
- `{output_dir}`
- `{workspace}`
- `{project}`
- `{config}`
- `{timestamp_tag}`

Reflash logs are written to:
- `output_*/_artifacts/reflash_log_<timestamp>.txt`

### Doxygen Quality Report

Docs generation now always emits:
- `output_*/docs/doxygen_quality_report.json`

Quality findings are warnings (not hard-fail) by default.

## Run Policy

- Full end-to-end generation passes are user-run only.
- Codex should make targeted code/config edits and run focused checks/tests only.

## Materials

https://docs.claude.com/en/api/claude-on-amazon-bedrock
