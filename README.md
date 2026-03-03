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

## Run Policy

- Full end-to-end generation passes are user-run only.
- Codex should make targeted code/config edits and run focused checks/tests only.

## Materials

https://docs.claude.com/en/api/claude-on-amazon-bedrock
