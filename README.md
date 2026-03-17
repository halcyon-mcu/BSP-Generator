# BSP-Generator

Automated Board Support Package generator for the **TI RM46 Hercules** (LAUNCHXL2-TMS57012) microcontroller. Reads hardware configuration from YAML files and uses Claude (via Amazon Bedrock) to generate production-quality C driver code, register definitions, initialization sequences, and documentation.

## How It Works

```
YAML Configs          Python Pipeline          Claude API            C Output
┌──────────┐       ┌─────────────────┐      ┌──────────┐      ┌──────────────┐
│ soc.yaml │──┐    │ Discovery pass  │─────>│ Bedrock  │─────>│ Drivers (.c) │
│ bus.yaml │  ├───>│ Implementation  │      │ Claude   │      │ Headers (.h) │
│pinmux.yaml│ │    │ Validation      │      │ Sonnet   │      │ Linker (.ld) │
│board.yaml│──┘    │ Contract check  │      └──────────┘      │ Docs         │
└──────────┘       └─────────────────┘                        └──────────────┘
```

The pipeline performs a two-pass generation (discovery then implementation), validates generated code against hardware contracts (PLL sequencing, register parity, startup ordering), and optionally compiles via TI Code Composer Studio.

## Project Structure

```
BSP-Generator/
├── README.md                     # This file
├── .env.example                  # Credentials template (AWS Bedrock)
├── pyproject.toml                # Project config & dependencies
├── requirements.txt              # Pinned dependencies
├── app/
│   ├── main.py                   # Entry point & interactive menu
│   ├── config.py                 # Path & constant configuration
│   ├── modules/
│   │   ├── generation/           # Core BSP generation (prompts, discovery, implementation)
│   │   ├── validation/           # Multi-stage validation engine & contract checkers
│   │   ├── build/                # CCS build integration & diagnostics
│   │   ├── contracts/            # API contract manifest & autofix
│   │   ├── intent/               # Board capabilities, timing recipes, post-gen prompts
│   │   ├── regeneration/         # Retry policies & token strategies
│   │   ├── utils/                # File I/O, dependency resolver, progress tracking
│   │   ├── yaml/                 # YAML loading, validation, formatting
│   │   └── _archived/            # Legacy one-time tools (extraction, registers, etc.)
│   ├── yaml_in/                  # Hardware configuration inputs
│   │   ├── soc.yaml              # Peripheral definitions & init sequences
│   │   ├── bus.yaml              # Clock tree & PLL configuration
│   │   ├── pinmux.yaml           # Pin multiplexing
│   │   ├── board.yaml            # Board-specific config (crystal, LEDs, connectors)
│   │   ├── irq.yaml              # Interrupt definitions
│   │   ├── memmap.yaml           # Memory map
│   │   ├── regs.yaml             # Register definitions
│   │   ├── bringup_contract.yaml # PLL/startup sequence constraints
│   │   └── generation_profile.yaml # Generation feature flags & flash config
│   ├── yaml_schemas/             # YAML schema validation definitions
│   ├── input_docs/               # TI reference PDFs (TRM, datasheet, schematic)
│   ├── schematic_extracted/      # Extracted schematic page images
│   ├── tests/                    # Pytest test suite
│   └── docs/                     # Project documentation
│       ├── ARCHITECTURE.md       # System design overview
│       ├── VALIDATION.md         # Validation pipeline details
│       └── bringup/              # Hardware bring-up & debugging notes
└── output_*/                     # Generated BSP outputs (timestamped)
```

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv) package manager (recommended): `pip install uv`
- AWS credentials configured for Amazon Bedrock (Claude access)

## Setup

1. Clone the repository
2. Copy `.env.example` to `.env` and fill in your AWS/Bedrock credentials
3. Install dependencies: `uv sync`

## Usage

### Interactive Menu

```bash
uv run -m app.main
```

Running in a TTY opens a guided menu with these actions:

| Action | Description |
|--------|-------------|
| **Full generation** | Complete BSP generation pipeline (API-intensive) |
| **Validate existing output** | Run validators on a previous output |
| **Post-gen prompt only** | Post-generation analysis on existing output |
| **Post-gen prompt + firmware** | Generate firmware from existing output |
| **Compile gate only** | CCS build check on existing output |
| **Docs only** | Doxygen generation + quality report |
| **Reflash existing output** | Flash firmware to target board |

### CLI Flags

```bash
# Direct action mode (bypass menu)
uv run -m app.main --action <generate|validate|postgen_prompt|postgen_generate|compile_only|docs_only|reflash>

# List recent output directories
uv run -m app.main --list-outputs

# Select a specific output non-interactively
uv run -m app.main --action validate --output-index 1

# Skip generation profile (use in-code defaults only)
uv run -m app.main --no-profile
```

### Output Picker

Recent outputs are discovered from `./output_*` and `./app/output_*`. Use `--output-index N` to select one non-interactively, or the interactive picker when a menu action requires an output folder.

### Flash Configuration

Configure in `generation_profile.yaml`:

```yaml
flash:
  enabled: true
  command_template: "your_flash_command --out \"{output_dir}\""
  working_dir: "C:/path/optional"
  timeout_sec: 120
```

Template variables: `{output_dir}`, `{workspace}`, `{project}`, `{config}`, `{timestamp_tag}`

## Configuration Files

| File | Purpose |
|------|---------|
| `soc.yaml` | Peripheral definitions, register references, initialization sequences |
| `bus.yaml` | Clock tree: PLL parameters, HCLK/VCLK dividers, clock source mapping |
| `pinmux.yaml` | Pin multiplexing: IOMM PINMMR register assignments per peripheral |
| `board.yaml` | Board config: crystal frequency, LEDs, buttons, connector pinouts |
| `irq.yaml` | VIM interrupt channel assignments and priorities |
| `memmap.yaml` | Memory regions: Flash, RAM, peripheral address ranges |
| `regs.yaml` | Full register definitions with field-level bit masks |
| `bringup_contract.yaml` | Required PLL/startup sequencing constraints for validation |
| `generation_profile.yaml` | Feature flags, build gate settings, flash configuration |

## Testing

```bash
cd app && PYTHONPATH=. uv run pytest tests/ -q
```

To skip the Doxygen test (requires Doxygen installed):
```bash
cd app && PYTHONPATH=. uv run pytest tests/ -q --ignore=tests/test_doxygen.py
```

## Documentation

See [app/docs/](app/docs/) for detailed documentation:
- [Architecture](app/docs/ARCHITECTURE.md) — system design and module overview
- [Validation](app/docs/VALIDATION.md) — validation pipeline and contract checking
- [Bringup notes](app/docs/bringup/) — hardware debugging reference (PLL, terminal output)

## Run Policy

Full end-to-end BSP generation is **user-initiated only** — it consumes significant API tokens. Automated tools should make targeted edits and run focused checks/tests only.
