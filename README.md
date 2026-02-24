# BSP-Generator

**Automatic Board Support Package (BSP) generation for the TI RM46 Cortex-R4 MCU using Claude AI via Amazon Bedrock**

This tool automatically generates production-ready C drivers, startup code, linker scripts, and comprehensive unit tests from YAML-based hardware specifications.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Setup](#setup)
4. [Running the Generator](#running-the-generator)
5. [Testing the Generated Code](#testing-the-generated-code)
6. [Deploying to Hardware](#deploying-to-hardware)
7. [Project Structure](#project-structure)
8. [Documentation](#documentation)

---

## Overview

The BSP-Generator creates complete Board Support Packages (BSP) for the TI RM46 Cortex-R4 microcontroller by:

1. **Reading YAML specifications** of your hardware configuration (clocks, peripherals, interrupts, memory layout)
2. **Invoking Claude AI** via AWS Bedrock to generate optimized C driver code
3. **Post-processing output** to extract generated files and validate against specifications
4. **Generating documentation** with Doxygen
5. **Creating unit tests** with mocked hardware registers for validation

**Generated Artifacts:**
- ✅ Peripheral drivers (GPIO, UART, Clock, Interrupt Manager)
- ✅ System initialization code
- ✅ ARM assembly startup code
- ✅ Linker script for TI ARM CGT toolchain
- ✅ Unit tests with mock hardware
- ✅ Doxygen API documentation

---

## Prerequisites

### Software Requirements

- **Python 3.11+** (with pip or uv)
- **AWS Account** with Bedrock access enabled
- **GCC** (for compiling unit tests)
- **TI Code Composer Studio (CCS)** 12.0+ (for board deployment)
- **TI HalCoGen** (optional, for additional peripheral configuration)

### AWS Setup

1. Create an AWS account or use existing credentials
2. Enable Amazon Bedrock in your region
3. Request access to Claude model (usually instant)
4. Create IAM user with `AmazonBedrockFullAccess` policy
5. Generate long-term access key (AKIA prefix, not temporary ASIA tokens)

### Hardware

- TI RM46 Cortex-R4 evaluation board or custom hardware
- USB connection to board (JTAG interface for debugging/flashing)

---

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/halcyon-mcu/BSP-Generator.git
cd BSP-Generator
```

### 2. Install Python Dependencies

Using **uv** (recommended):
```bash
uv sync
```

Or with **pip**:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r pyproject.toml
```

### 3. Configure AWS Credentials

Create a `.env` file in the project root:

```bash
AWS_ACCESS_KEY=AKIA...your_access_key...
AWS_SECRET_KEY=your_secret_key...
```

Or configure via AWS CLI:
```bash
aws configure
```

### 4. Verify Setup

Test the installation:
```bash
python -c "import boto3; import langchain_aws; import yaml; print('✓ All dependencies installed')"
```

---

## Running the Generator

### Basic Usage

```bash
python -m app.main
```

This will:
1. Display available peripherals from your YAML configuration
2. Prompt you to select which peripherals to generate
3. Invoke Claude to generate C code for each component
4. Output a complete BSP in `bsp_gen/output_<timestamp>/`

### Example Session

```
Available peripherals (excluding SYSTEM and PCR):
Index | Name        | Type       | Instance | Clock Ref
------+-------------+------------+----------+----------
    1 | GIO         | gpio       | 1        | VCLK
    2 | SCI         | sci        | 1        | VCLK
    3 | VIM         | vim        | 1        | HCLK

Your selection: all

[info] Preparing prompts...
[info] Total tasks to run: 8
[info] Starting concurrent generation of all components...

⠸ Generating: 5/8 tasks completed (01:23)
[ok] Documentation generated in output_20260210_130852\docs\html
[ok] Validation report saved: output_20260210_130852\validation_report.json
```

### Output Directory Structure

```
bsp_gen/output_20260210_130852/
├── start.s                    # ARM assembly startup code
├── entry.c                    # C reset handler
├── system.h/c                 # System initialization
├── linker.cmd                 # TI ARM CGT linker script
├── clock.h/c                  # Clock driver
├── gio.h/c                    # GPIO driver
├── sci.h/c                    # UART driver
├── vim.h/c                    # Interrupt manager driver
├── docs/html/                 # Doxygen documentation
├── validation_report.json     # Output validation report
├── _artifacts/                # LLM responses and prompts
└── validation_tests/          # Optional: generated test files
```

---

## Testing the Generated Code

### Unit Tests with Mocked Hardware

The generator creates mock hardware implementations and unit tests to validate generated code **before deploying to the board**.

#### Running GPIO Tests

```bash
cd bsp_gen/output_20260210_130852/

# Compile mock + tests
gcc gio_mock.c gio_test.c -o gio_test -I.

# Run tests
./gio_test
```

**Expected Output:**
```
╔════════════════════════════════════════════════════════════════════════════════╗
║                    GPIO (GIO) Driver Unit Test Suite                          ║
║                         TI RM46 Cortex-R4 MCU                                  ║
╚════════════════════════════════════════════════════════════════════════════════╝

Test Case: Mock Initialization
  [PASS] Port A output starts at 0
  [PASS] Port A all pins configured as inputs
  ... (62 more tests)

═══════════════════════════════════════════════════════════════════════════════════
  Total Tests:     64
  Passed:          64  ✓
  Failed:           0
  Success Rate:   100.0%
═══════════════════════════════════════════════════════════════════════════════════
```

#### Running SCI (UART) Tests

```bash
# Compile mock + tests
gcc sci_mock.c sci_test.c -o sci_test -I.

# Run tests
./sci_test
```

**Expected Results:**
- Total: 40 tests
- Passed: 38+ (95%+)
- Tests include: initialization, transmission, reception, buffer overflow, loopback

#### Compiling All Drivers

```bash
# Compile all C source files (without tests)
foreach ($file in @('clock.c', 'gio.c', 'sci.c', 'vim.c', 'system.c', 'entry.c')) {
    gcc -c $file -o "$($file -replace '.c', '.o')" -I.
}

# List compiled objects
ls *.o
```

### Test Coverage

| Driver | Tests | Coverage | Status |
|--------|-------|----------|--------|
| GIO    | 64    | 100%     | ✅ PASS |
| SCI    | 40    | 95%+     | ✅ PASS |
| Clock  | -     | -        | 📋 Generated |
| VIM    | -     | -        | 📋 Generated |

---

## Deploying to Hardware

### For step-by-step instructions on deploying and validating on actual hardware, see:

**→ [HARDWARE_DEPLOYMENT.md](./HARDWARE_DEPLOYMENT.md)**

This guide covers:
- Setting up TI Code Composer Studio
- Importing the generated BSP
- Configuring the debugger
- Flashing and running on the RM46 board
- Validating functionality with test programs
- Using HalCoGen for additional configuration (if needed)

---

## Project Structure

```
BSP-Generator/
├── README.md                          # This file
├── HARDWARE_DEPLOYMENT.md             # Deployment guide
├── pyproject.toml                     # Python dependencies
├── .env.example                       # AWS credential template
│
├── app/
│   ├── main.py                        # Entry point
│   ├── config.py                      # Configuration
│   └── modules/
│       ├── prompt.py                  # Claude prompt builders
│       ├── file_io.py                 # File post-processing
│       ├── yaml_utils.py              # YAML parsing
│       ├── validation_*.py            # Validation system
│       └── user.py                    # User interaction
│
├── app/yaml_in/                       # Your hardware specifications
│   ├── soc.yaml                       # SoC configuration
│   ├── regs.yaml                      # Register definitions
│   ├── memmap.yaml                    # Memory layout
│   ├── irq.yaml                       # Interrupt configuration
│   └── *.yaml
│
├── bsp_gen/
│   └── output_*/                      # Generated BSP outputs (timestamped)
│       ├── *.c *.h                    # Generated drivers
│       ├── *.exe                      # Compiled tests
│       ├── docs/html/                 # API documentation
│       └── TEST_RESULTS.md            # Test summary
│
└── [Documentation files]
    ├── TEST_ARCHITECTURE.md
    ├── VALIDATION_TESTING.md
    └── ...

```

---

## Documentation

### User Guides
- **[HARDWARE_DEPLOYMENT.md](./HARDWARE_DEPLOYMENT.md)** - Deploy tests on actual board
- **[TEST_ARCHITECTURE.md](./TEST_ARCHITECTURE.md)** - How the testing system works
- **[YAML_SPECIFICATIONS.md](./app/yaml_in/README.md)** - Configure your hardware

### API Documentation
- Open `bsp_gen/output_*/docs/html/index.html` in a browser for full API reference

### Generated Test Reports
- Check `bsp_gen/output_*/TEST_RESULTS.md` for detailed test results
- Check `bsp_gen/output_*/validation_report.json` for programmatic validation data

---

## Troubleshooting

### AWS Credential Errors

**Error:** `UnrecognizedClientException: The security token included in the request is invalid`

**Solution:** Your credentials have expired or are invalid.
- Use long-term IAM credentials (AKIA prefix), not temporary tokens (ASIA)
- Regenerate credentials in AWS Console: IAM → Users → Security Credentials → Create Access Key

### Compilation Errors

**Error:** `gcc: command not found`

**Solution:** Install GCC
- Windows: `choco install mingw`
- Mac: `brew install gcc`
- Linux: `sudo apt install build-essential`

### Python Import Errors

**Error:** `ModuleNotFoundError: No module named 'boto3'`

**Solution:** Activate the virtual environment
```bash
.venv\Scripts\Activate.ps1  # Windows
source .venv/bin/activate    # Linux/Mac
```

---

## Performance

- **Generation time:** ~2-3 minutes for full BSP (concurrent AI calls)
- **Test execution:** <100ms for unit test suite
- **Documentation generation:** ~5-10 seconds with Doxygen

---

## License

See LICENSE file for details

## Materials & References

- [Claude API Documentation](https://docs.claude.com/en/api/claude-on-amazon-bedrock)
- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [TI RM46 Reference Manual](https://www.ti.com/product/RM46L852)
- [TI Code Composer Studio Documentation](https://software-dl.ti.com/ccs/esd/documents/users_guide/index.html)

---

## Support

For issues, questions, or contributions:
- Check existing documentation in this repo
- Review test results and validation reports in `bsp_gen/output_*/`
- Consult the generated API documentation in `docs/html/`
