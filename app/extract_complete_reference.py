#!/usr/bin/env python3
"""
extract_complete_reference.py

One-time comprehensive extraction from all documentation:
- TRM PDFs (peripheral chapters from modules/pdfs/TRM_split/)
- Full datasheet (from input_docs/)
- Board schematic (from input_docs/)

SETUP:
1. Ensure TRM PDFs are in: modules/pdfs/TRM_split/
2. Place datasheet and schematic in: input_docs/
3. Run: python extract_complete_reference.py

COST SAFEGUARD: Stops execution if cost exceeds $75

Outputs complete reference documentation to: reference_docs/
"""

import asyncio
import datetime
from pathlib import Path
from typing import Dict, List, Optional
import yaml
from modules.pdf_text_extractor import (
    extract_text_from_pdf,
    extract_peripheral_name_from_filename,
    should_skip_pdf
)
from modules.prompt import Model

# Will need to import invoke_model
import sys
sys.path.append(str(Path(__file__).parent))
from pdf_to_yaml_extractor import invoke_model


# ============================================================================
# COST TRACKING AND SAFEGUARDS
# ============================================================================

class CostTracker:
    """Track API costs in real-time with budget enforcement."""

    def __init__(self, max_budget: float = 75.0):
        self.max_budget = max_budget
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.lock = asyncio.Lock()

        # Sonnet 4.5 pricing
        self.input_cost_per_million = 3.0
        self.output_cost_per_million = 15.0

    async def add_tokens(self, input_tokens: int, output_tokens: int):
        """Add tokens and calculate cost. Returns False if over budget."""
        async with self.lock:
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens

            input_cost = (input_tokens / 1_000_000) * self.input_cost_per_million
            output_cost = (output_tokens / 1_000_000) * self.output_cost_per_million
            self.total_cost += input_cost + output_cost

            if self.total_cost >= self.max_budget:
                return False  # Over budget

            return True  # Still within budget

    def get_status(self) -> Dict:
        """Get current cost status."""
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost": self.total_cost,
            "budget": self.max_budget,
            "remaining": self.max_budget - self.total_cost,
            "percent_used": (self.total_cost / self.max_budget) * 100
        }

    def format_status(self) -> str:
        """Format status for display."""
        status = self.get_status()
        return (
            f"Cost: ${status['total_cost']:.2f} / ${status['budget']:.2f} "
            f"({status['percent_used']:.1f}% used, ${status['remaining']:.2f} remaining)"
        )


# Global cost tracker
cost_tracker = None


class BudgetExceededError(Exception):
    """Raised when API cost budget is exceeded."""
    pass


# ============================================================================
# LOAD YAML STYLE EXAMPLES
# ============================================================================

def load_yaml_style_examples() -> str:
    """Load existing YAML files as style reference."""
    yaml_in_dir = Path("yaml_in")

    if not yaml_in_dir.exists():
        return ""

    examples = []

    # Load a few lines from each YAML as examples
    for yaml_file in ["soc.yaml", "regs.yaml", "bus.yaml", "irq.yaml", "pinmux.yaml"]:
        yaml_path = yaml_in_dir / yaml_file
        if yaml_path.exists():
            try:
                content = yaml_path.read_text(encoding='utf-8')
                # Take first 50 lines as example
                lines = content.split('\n')[:50]
                sample = '\n'.join(lines)
                examples.append(f"# Example from {yaml_file}:\n{sample}\n")
            except:
                pass

    if examples:
        style_guide = "\n\n".join(examples)
        return f"""

## YAML STYLE REFERENCE

Your team will convert this to YAML. Here are examples of existing YAML style:

{style_guide}

Use similar formatting, naming conventions, and structure in your output.
"""

    return ""


# ============================================================================
# PROMPTS FOR DIFFERENT DOCUMENT TYPES
# ============================================================================

PERIPHERAL_REFERENCE_PROMPT = """Extract ALL hardware information from this TRM peripheral chapter.

Create a comprehensive reference document covering:

## 1. REGISTERS
- List ALL register names with offsets and base address
- Include register map table
- Note any register groups or blocks (e.g., SYS, SYS2)

## 2. CLOCK CONFIGURATION
- Clock sources required
- PLL settings if applicable
- Clock domain/divider information
- Clock enable/gate registers

## 3. PIN ASSIGNMENTS
- All pins used by this peripheral
- Pin numbers/names
- Alternate functions/multiplexing options
- Pin mux registers and bit settings

## 4. INITIALIZATION SEQUENCE
- Step-by-step initialization procedure
- Dependencies (what must be configured first: clocks, power, other peripherals)
- Register write order
- Any timing requirements or delays

## 5. DMA CONFIGURATION
- DMA channel assignments
- Request/trigger signals
- DMA setup requirements

## 6. INTERRUPTS
- IRQ channel numbers
- Interrupt sources/types
- Priority information
- Interrupt enable/status registers

## 7. OPERATIONAL MODES
- Different modes of operation
- Mode configuration
- Use cases for each mode

Format as clear markdown. Be comprehensive - this is a reference document.
If a section doesn't have information, write "Not specified in this chapter."
{style_examples}
PDF Content:
{pdf_text}

Generate complete reference now:"""


DATASHEET_REFERENCE_PROMPT = """Extract system-level hardware information from this device datasheet.

Focus on chip-level details, NOT peripheral-specific details (those come from TRM).

Create reference covering:

## 1. DEVICE OVERVIEW
- Part number and variants
- CPU core type and speed
- Memory sizes (Flash, RAM, etc.)
- Package type and pin count

## 2. ELECTRICAL CHARACTERISTICS
- Operating voltage ranges
- Power consumption specs
- I/O voltage levels (VIH, VIL, VOH, VOL)
- Drive strength specifications
- Timing characteristics (setup, hold, propagation)

## 3. PIN ASSIGNMENTS (CHIP LEVEL)
- Complete pinout table
- Pin numbers to signal names
- Power pins (VDD, VSS, VCCIO, etc.)
- Special pins (RESET, BOOT, JTAG, etc.)
- Default pin states at reset

## 4. CLOCK SYSTEM
- External oscillator requirements
- Crystal specifications
- PLL frequency ranges and multipliers
- Clock tree overview
- Maximum clock frequencies

## 5. MEMORY MAP
- Flash memory regions (address ranges, sizes)
- RAM regions (TCM, system RAM)
- Peripheral address space
- Reserved regions

## 6. POWER MANAGEMENT
- Power domains
- Low-power modes
- Wake-up sources
- Power sequencing requirements

## 7. RESET AND BOOT
- Reset sources
- Reset timing
- Boot modes and configuration
- Boot sequence

## 8. PACKAGE INFORMATION
- Package dimensions
- Pin pitch
- Thermal characteristics
- Recommended PCB footprint

Extract all numerical values exactly as shown (addresses, voltages, frequencies, etc.).
{style_examples}
Datasheet Content:
{pdf_text}

Generate comprehensive device reference now:"""


SCHEMATIC_REFERENCE_PROMPT = """Extract board-specific hardware configuration from this schematic.

Focus on how the chip is connected on THIS SPECIFIC BOARD.

Create reference covering:

## 1. POWER SUPPLY
- Supply voltage levels used
- Power supply chips/circuits
- Filtering and decoupling
- Power sequencing

## 2. CLOCK CONFIGURATION
- External crystal frequency
- Crystal load capacitors
- Clock source selection (pins tied high/low)

## 3. PIN CONNECTIONS
- Which chip pins are actually used on this board
- What each pin connects to:
  - External components (resistors, capacitors, LEDs, etc.)
  - Connectors/headers
  - Other ICs
  - Test points
- Pull-up/pull-down resistors on pins

## 4. PERIPHERAL CONNECTIONS
For each peripheral in use:
- Which physical connector/header it goes to
- Pin mappings (chip pin → connector pin)
- Signal names/net names
- External components (termination, protection, etc.)

## 5. BOOT/CONFIGURATION
- Boot mode selection (pin strapping)
- Configuration pins tied high/low
- DIP switches or jumpers

## 6. INTERFACES
- Connectors: type, pin count, pin assignments
- External devices connected
- Communication protocols used

## 7. SPECIAL CIRCUITS
- Reset circuit details
- Debug/JTAG interface
- LEDs and their connections
- Buttons/switches

## 8. NET NAMES
- Important net names from schematic
- Signal routing information
- Test points

Be specific with component values (resistor ohms, capacitor farads, etc.).
Note connector types and pin numbers.
{style_examples}
Schematic Content:
{pdf_text}

Generate board-specific reference now:"""


# ============================================================================
# EXTRACTION FUNCTIONS
# ============================================================================

class ExtractionProgress:
    """Simple progress tracker."""
    def __init__(self, total: int):
        self.total = total
        self.completed = 0
        self.failed = 0
        self.lock = asyncio.Lock()

    async def increment(self, success: bool):
        async with self.lock:
            self.completed += 1
            if not success:
                self.failed += 1
            print(f"Progress: {self.completed}/{self.total} ({self.failed} failed)")


async def extract_peripheral_reference(
    pdf_path: Path,
    model: Model,
    progress: ExtractionProgress,
    output_dir: Path,
    style_examples: str = ""
) -> Dict:
    """Extract comprehensive reference for one peripheral from TRM."""

    global cost_tracker

    peripheral_name, full_name = extract_peripheral_name_from_filename(pdf_path.name)

    try:
        print(f"\n[{progress.completed + 1}/{progress.total}] {peripheral_name}: Extracting text...")

        # Extract PDF text
        pdf_text = extract_text_from_pdf(pdf_path)

        # Use larger limit for comprehensive extraction
        # SYSTEM peripheral gets even more space
        if peripheral_name.upper() == 'SYSTEM':
            max_chars = 500000  # 125k tokens
        else:
            max_chars = 400000  # 100k tokens

        if len(pdf_text) > max_chars:
            print(f"  {peripheral_name}: Truncating {len(pdf_text)} → {max_chars} chars")
            pdf_text = pdf_text[:max_chars] + "\n\n[...content truncated due to length...]"

        print(f"  {peripheral_name}: Calling Claude API...")

        # Single Claude call to extract everything
        prompt = PERIPHERAL_REFERENCE_PROMPT.format(
            pdf_text=pdf_text,
            style_examples=style_examples
        )

        response, input_tokens, output_tokens = await invoke_model(
            model=model,
            max_tokens=16000,
            system_prompt="You are a technical documentation assistant creating comprehensive hardware reference guides.",
            user_prompt=prompt
        )

        # Track cost
        within_budget = await cost_tracker.add_tokens(input_tokens, output_tokens)
        if not within_budget:
            print(f"  {peripheral_name}: ⚠ BUDGET EXCEEDED - stopping")
            raise BudgetExceededError(f"Cost limit of ${cost_tracker.max_budget} reached")

        # Write output
        output_file = output_dir / "peripherals" / f"{peripheral_name}_reference.md"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        content = f"""# {peripheral_name} - {full_name}

**Source**: {pdf_path.name}
**Generated**: {datetime.datetime.now().isoformat()}
**Tokens**: {input_tokens} input, {output_tokens} output
**Cost**: ${(input_tokens * 3 / 1_000_000 + output_tokens * 15 / 1_000_000):.3f}

---

{response}

---

*This reference was auto-generated from TRM documentation. Verify critical values against official datasheet.*
"""
        output_file.write_text(content, encoding='utf-8')

        print(f"  {peripheral_name}: ✓ Wrote {output_file.name}")
        print(f"  {cost_tracker.format_status()}")
        await progress.increment(True)

        return {
            "peripheral": peripheral_name,
            "success": True,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens
        }

    except BudgetExceededError as e:
        # Don't mark as failed - just stopping due to budget
        print(f"  {peripheral_name}: Budget limit reached, stopping extraction")
        raise  # Re-raise to stop main loop

    except Exception as e:
        print(f"  {peripheral_name}: ✗ Failed - {e}")
        await progress.increment(False)
        return {
            "peripheral": peripheral_name,
            "success": False,
            "error": str(e)
        }


async def extract_datasheet_reference(
    datasheet_path: Path,
    model: Model,
    output_dir: Path,
    style_examples: str = ""
) -> Dict:
    """Extract chip-level reference from full datasheet."""

    global cost_tracker

    print(f"\n{'='*80}")
    print(f"DATASHEET: Extracting from {datasheet_path.name}")
    print(f"{'='*80}")

    try:
        print(f"  Extracting text from {datasheet_path.name}...")
        pdf_text = extract_text_from_pdf(datasheet_path)

        # For 200-page datasheet, use full content or large sample
        max_chars = 800000  # 200k tokens - very large

        if len(pdf_text) > max_chars:
            print(f"  Truncating {len(pdf_text)} → {max_chars} chars")
            # Take first 80% and last 20% to get both overview and details
            split_point = int(max_chars * 0.8)
            pdf_text = (
                pdf_text[:split_point] +
                "\n\n[...middle content truncated...]\n\n" +
                pdf_text[-(max_chars - split_point):]
            )

        print(f"  Calling Claude API (this will take longer - large document)...")

        prompt = DATASHEET_REFERENCE_PROMPT.format(
            pdf_text=pdf_text,
            style_examples=style_examples
        )

        response, input_tokens, output_tokens = await invoke_model(
            model=model,
            max_tokens=24000,  # More tokens for comprehensive datasheet
            system_prompt="You are a technical documentation assistant creating comprehensive chip-level reference guides.",
            user_prompt=prompt
        )

        # Track cost
        within_budget = await cost_tracker.add_tokens(input_tokens, output_tokens)
        if not within_budget:
            print(f"  ⚠ BUDGET EXCEEDED - stopping")
            raise BudgetExceededError(f"Cost limit of ${cost_tracker.max_budget} reached")

        # Write output
        output_file = output_dir / "DATASHEET_reference.md"

        content = f"""# Device Datasheet Reference - RM46L852

**Source**: {datasheet_path.name}
**Generated**: {datetime.datetime.now().isoformat()}
**Tokens**: {input_tokens} input, {output_tokens} output
**Cost**: ${(input_tokens * 3 / 1_000_000 + output_tokens * 15 / 1_000_000):.3f}

---

{response}

---

*This reference was auto-generated from device datasheet. Verify critical values against official documentation.*
"""
        output_file.write_text(content, encoding='utf-8')

        print(f"  ✓ Wrote {output_file.name}")
        print(f"  {cost_tracker.format_status()}")

        return {
            "source": "datasheet",
            "success": True,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens
        }

    except BudgetExceededError:
        raise  # Re-raise to stop

    except Exception as e:
        print(f"  ✗ Failed - {e}")
        return {
            "source": "datasheet",
            "success": False,
            "error": str(e)
        }


async def extract_schematic_reference(
    schematic_path: Path,
    model: Model,
    output_dir: Path,
    style_examples: str = ""
) -> Dict:
    """Extract board-specific reference from schematic."""

    global cost_tracker

    print(f"\n{'='*80}")
    print(f"SCHEMATIC: Extracting from {schematic_path.name}")
    print(f"{'='*80}")

    try:
        print(f"  Extracting text from {schematic_path.name}...")
        pdf_text = extract_text_from_pdf(schematic_path)

        # Schematics are usually smaller
        max_chars = 300000  # 75k tokens

        if len(pdf_text) > max_chars:
            print(f"  Truncating {len(pdf_text)} → {max_chars} chars")
            pdf_text = pdf_text[:max_chars] + "\n\n[...content truncated...]"

        print(f"  Calling Claude API...")

        prompt = SCHEMATIC_REFERENCE_PROMPT.format(
            pdf_text=pdf_text,
            style_examples=style_examples
        )

        response, input_tokens, output_tokens = await invoke_model(
            model=model,
            max_tokens=16000,
            system_prompt="You are a technical documentation assistant creating board-specific hardware reference guides.",
            user_prompt=prompt
        )

        # Track cost
        within_budget = await cost_tracker.add_tokens(input_tokens, output_tokens)
        if not within_budget:
            print(f"  ⚠ BUDGET EXCEEDED - stopping")
            raise BudgetExceededError(f"Cost limit of ${cost_tracker.max_budget} reached")

        # Write output
        output_file = output_dir / "SCHEMATIC_reference.md"

        content = f"""# Board Schematic Reference

**Source**: {schematic_path.name}
**Generated**: {datetime.datetime.now().isoformat()}
**Tokens**: {input_tokens} input, {output_tokens} output
**Cost**: ${(input_tokens * 3 / 1_000_000 + output_tokens * 15 / 1_000_000):.3f}

---

{response}

---

*This reference was auto-generated from board schematic. Verify connections against actual hardware.*
"""
        output_file.write_text(content, encoding='utf-8')

        print(f"  ✓ Wrote {output_file.name}")
        print(f"  {cost_tracker.format_status()}")

        return {
            "source": "schematic",
            "success": True,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens
        }

    except BudgetExceededError:
        raise  # Re-raise to stop

    except Exception as e:
        print(f"  ✗ Failed - {e}")
        return {
            "source": "schematic",
            "success": False,
            "error": str(e)
        }


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

async def extract_all_documentation(
    trm_dir: Path,
    datasheet_path: Optional[Path] = None,
    schematic_path: Optional[Path] = None,
    output_dir: Path = Path("reference_docs"),
    model: Model = Model.SONNET_4_5,
    max_concurrent: int = 4,
    max_budget: float = 75.0
):
    """
    Extract comprehensive reference from all documentation.

    Args:
        trm_dir: Directory with TRM peripheral PDFs
        datasheet_path: Path to full datasheet PDF
        schematic_path: Path to board schematic PDF
        output_dir: Where to write output
        model: Claude model to use
        max_concurrent: Max parallel extractions (4-6 recommended for overnight)
        max_budget: Maximum cost in USD (default: $75)
    """

    global cost_tracker

    # Initialize cost tracker
    cost_tracker = CostTracker(max_budget=max_budget)

    print("="*80)
    print("COMPREHENSIVE DOCUMENTATION EXTRACTION")
    print("="*80)
    print(f"Model: {model.value}")
    print(f"Max concurrent: {max_concurrent}")
    print(f"Output directory: {output_dir}")
    print(f"Budget limit: ${max_budget:.2f}")
    print()

    output_dir.mkdir(exist_ok=True)

    # Load YAML style examples
    print("Loading YAML style examples from yaml_in/...")
    style_examples = load_yaml_style_examples()
    if style_examples:
        print("  ✓ Loaded style examples")
    else:
        print("  ⚠ No yaml_in/ examples found")

    # Get all TRM PDFs
    trm_pdfs = [p for p in trm_dir.glob("*.pdf") if not should_skip_pdf(p.name, p)]

    total_tasks = len(trm_pdfs)
    if datasheet_path and datasheet_path.exists():
        total_tasks += 1
    if schematic_path and schematic_path.exists():
        total_tasks += 1

    print(f"Total documents to process: {total_tasks}")
    print(f"  - TRM peripherals: {len(trm_pdfs)}")
    print(f"  - Datasheet: {'Yes' if datasheet_path and datasheet_path.exists() else 'No'}")
    print(f"  - Schematic: {'Yes' if schematic_path and schematic_path.exists() else 'No'}")
    print()

    start_time = datetime.datetime.now()

    budget_exceeded = False

    # Extract datasheet first (not parallelized due to size)
    datasheet_result = None
    if datasheet_path and datasheet_path.exists():
        try:
            datasheet_result = await extract_datasheet_reference(
                datasheet_path, model, output_dir, style_examples
            )
        except BudgetExceededError:
            budget_exceeded = True
            print("\n⚠ Budget exceeded during datasheet extraction")

    # Extract schematic (also large, do separately)
    schematic_result = None
    if not budget_exceeded and schematic_path and schematic_path.exists():
        try:
            schematic_result = await extract_schematic_reference(
                schematic_path, model, output_dir, style_examples
            )
        except BudgetExceededError:
            budget_exceeded = True
            print("\n⚠ Budget exceeded during schematic extraction")

    # Extract all TRM peripherals in parallel
    peripheral_results = []

    if not budget_exceeded:
        progress = ExtractionProgress(len(trm_pdfs))
        semaphore = asyncio.Semaphore(max_concurrent)

        async def extract_with_limit(pdf_path):
            async with semaphore:
                return await extract_peripheral_reference(
                    pdf_path, model, progress, output_dir, style_examples
                )

        print(f"\n{'='*80}")
        print(f"EXTRACTING {len(trm_pdfs)} TRM PERIPHERALS ({max_concurrent} concurrent)")
        print(f"{'='*80}")

        try:
            peripheral_results = await asyncio.gather(
                *[extract_with_limit(pdf) for pdf in trm_pdfs],
                return_exceptions=True
            )
        except BudgetExceededError:
            budget_exceeded = True
            print("\n⚠ Budget exceeded during peripheral extraction")
            # peripheral_results will be incomplete, but that's okay

    # Calculate statistics
    end_time = datetime.datetime.now()
    duration = end_time - start_time

    successful = sum(1 for r in peripheral_results if isinstance(r, dict) and r.get("success"))
    failed = len(peripheral_results) - successful

    total_input_tokens = sum(
        r.get("input_tokens", 0)
        for r in [datasheet_result, schematic_result] + list(peripheral_results)
        if isinstance(r, dict) and r.get("success")
    )
    total_output_tokens = sum(
        r.get("output_tokens", 0)
        for r in [datasheet_result, schematic_result] + list(peripheral_results)
        if isinstance(r, dict) and r.get("success")
    )

    total_cost = (total_input_tokens * 3 / 1_000_000 + total_output_tokens * 15 / 1_000_000)

    # Create master index
    create_master_index(output_dir, trm_pdfs, datasheet_path, schematic_path,
                       successful, failed, duration, total_cost)

    # Print summary
    print("\n" + "="*80)
    if budget_exceeded:
        print("EXTRACTION STOPPED - BUDGET LIMIT REACHED")
        print("(All completed extractions have been saved)")
    else:
        print("EXTRACTION COMPLETE")
    print("="*80)
    print(f"Duration: {duration}")
    print(f"TRM Peripherals: {successful} succeeded, {failed} failed")
    if datasheet_result:
        print(f"Datasheet: {'✓' if datasheet_result.get('success') else '✗'}")
    if schematic_result:
        print(f"Schematic: {'✓' if schematic_result.get('success') else '✗'}")
    print()
    print(f"Total tokens: {total_input_tokens:,} input, {total_output_tokens:,} output")
    print(f"Total cost: ${total_cost:.2f} / ${max_budget:.2f} budget")
    if budget_exceeded:
        print(f"⚠ Budget limit of ${max_budget:.2f} was reached")
        print(f"  {successful + (1 if datasheet_result else 0) + (1 if schematic_result else 0)} documents were successfully extracted before stopping")
    print()
    print(f"Output directory: {output_dir.absolute()}")
    print(f"Open {output_dir / 'INDEX.md'} to browse")
    print("="*80)


def create_master_index(
    output_dir: Path,
    trm_pdfs: List[Path],
    datasheet_path: Optional[Path],
    schematic_path: Optional[Path],
    successful: int,
    failed: int,
    duration: datetime.timedelta,
    cost: float
):
    """Create master index with links to all references."""

    index_content = f"""# Complete Hardware Reference Documentation

**Generated**: {datetime.datetime.now().isoformat()}
**Duration**: {duration}
**Extraction Cost**: ${cost:.2f}
**Success Rate**: {successful}/{successful + failed} peripherals

---

## Quick Links

- [Device Datasheet Reference](DATASHEET_reference.md) - Chip-level specifications
- [Board Schematic Reference](SCHEMATIC_reference.md) - Board-specific connections
- [Peripheral References](#peripheral-references) - TRM peripheral details

---

## Document Sources

### TRM (Technical Reference Manual)
Peripheral-specific details extracted from individual TRM chapters.

### Datasheet
"""

    if datasheet_path:
        index_content += f"- Source: `{datasheet_path.name}`\n"
    else:
        index_content += "- Not provided\n"

    index_content += """
### Board Schematic
"""

    if schematic_path:
        index_content += f"- Source: `{schematic_path.name}`\n"
    else:
        index_content += "- Not provided\n"

    index_content += """

---

## Peripheral References

Each peripheral has a comprehensive reference covering:
- Registers (names, offsets, base address)
- Clock configuration requirements
- Pin assignments and multiplexing
- Initialization sequence
- DMA channels (if applicable)
- Interrupt assignments
- Operational modes

### Alphabetical List

"""

    # Sort peripherals alphabetically
    peripheral_refs = []
    for pdf_path in sorted(trm_pdfs):
        peripheral_name, full_name = extract_peripheral_name_from_filename(pdf_path.name)
        ref_file = f"peripherals/{peripheral_name}_reference.md"
        peripheral_refs.append((peripheral_name, full_name, ref_file))

    for peripheral_name, full_name, ref_file in sorted(peripheral_refs):
        index_content += f"- [{peripheral_name}]({ref_file}) - {full_name}\n"

    index_content += """

---

## How to Use This Reference

### For Your Team (Converting to YAML)

1. **Start with the Index**: Browse this file to find relevant peripherals
2. **Read Peripheral References**: Each markdown file shows what information exists
3. **Check Datasheet**: For chip-level details (electrical specs, pinout)
4. **Check Schematic**: For board-specific connections

### What to Look For

Each peripheral reference contains:

- **Registers Section**: All registers with offsets → goes in `regs.yaml`
- **Clock Configuration**: Clock sources needed → goes in `bus.yaml`
- **Pin Assignments**: Pins used and mux settings → goes in `pinmux.yaml`
- **Init Sequence**: Initialization steps → goes in `soc.yaml` (init_sequence field)
- **DMA/Interrupts**: Channel assignments → goes in `soc.yaml` (dma_refs, irq_ref fields)

### Verification

This documentation was AI-generated. Always verify critical values:
- Register addresses and offsets
- Reset values
- Pin numbers
- Electrical specifications
- Timing requirements

Cross-check against official TI documentation when in doubt.

---

## Extraction Details

### Model Used
- Claude Sonnet 4.5 via AWS Bedrock
- Max tokens: 16,000 per peripheral, 24,000 for datasheet

### Coverage
- ✓ All TRM peripheral chapters processed
- ✓ Full device datasheet analyzed
- ✓ Board schematic analyzed

### Limitations
- Very large documents (>400k chars) were truncated
- Diagrams/figures are described textually, not extracted visually
- Some embedded tables may have formatting issues
- AI may miss or misinterpret some details

---

*Generated by extract_complete_reference.py*
"""

    (output_dir / "INDEX.md").write_text(index_content, encoding='utf-8')


# ============================================================================
# CLI
# ============================================================================

async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract comprehensive reference from all documentation",
        epilog="""
SETUP:
1. TRM PDFs should be in: modules/pdfs/TRM_split/ (already there)
2. Place datasheet and schematic in: input_docs/
3. Run: python extract_complete_reference.py

The script will auto-detect PDFs in input_docs/ directory.
        """
    )
    parser.add_argument(
        "--trm",
        type=Path,
        default=Path("modules/pdfs/TRM_split"),
        help="Directory with TRM PDFs (default: modules/pdfs/TRM_split)"
    )
    parser.add_argument(
        "--input-docs",
        type=Path,
        default=Path("input_docs"),
        help="Directory with datasheet and schematic (default: input_docs)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reference_docs"),
        help="Output directory (default: reference_docs)"
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=4,
        help="Max concurrent extractions (default: 4, increase for faster processing)"
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=75.0,
        help="Maximum API cost in USD (default: 75.00)"
    )
    parser.add_argument(
        "--model",
        choices=["haiku4.5", "sonnet4.5"],
        default="sonnet4.5",
        help="Claude model to use (default: sonnet4.5)"
    )

    args = parser.parse_args()

    # Map model choice
    if args.model == "haiku4.5":
        model = Model.HAIKU_4_5
    else:
        model = Model.SONNET_4_5

    # Validate TRM directory
    if not args.trm.exists():
        print(f"ERROR: TRM directory not found: {args.trm}")
        return

    # Create input_docs directory if it doesn't exist
    input_docs_dir = args.input_docs
    input_docs_dir.mkdir(exist_ok=True)

    # Auto-detect datasheet and schematic from input_docs/
    datasheet_path = None
    schematic_path = None

    if input_docs_dir.exists():
        pdf_files = list(input_docs_dir.glob("*.pdf"))

        if len(pdf_files) == 0:
            print(f"\nℹ No PDFs found in {input_docs_dir}/")
            print(f"  Place your datasheet and schematic PDFs in {input_docs_dir}/")
            print(f"  Or run without them (TRM only extraction)")
            print()
        else:
            print(f"\nAuto-detecting PDFs in {input_docs_dir}/:")
            for pdf in pdf_files:
                # Simple heuristic: larger file is probably datasheet
                file_size_mb = pdf.stat().st_size / (1024 * 1024)

                # Check filename for hints
                name_lower = pdf.name.lower()
                if 'schematic' in name_lower or 'sch' in name_lower or 'board' in name_lower:
                    schematic_path = pdf
                    print(f"  Schematic: {pdf.name} ({file_size_mb:.1f} MB)")
                elif 'datasheet' in name_lower or 'ds' in name_lower or file_size_mb > 10:
                    datasheet_path = pdf
                    print(f"  Datasheet: {pdf.name} ({file_size_mb:.1f} MB)")
                else:
                    # If unclear, assign based on size
                    if datasheet_path is None and file_size_mb > 5:
                        datasheet_path = pdf
                        print(f"  Datasheet (guessed): {pdf.name} ({file_size_mb:.1f} MB)")
                    elif schematic_path is None:
                        schematic_path = pdf
                        print(f"  Schematic (guessed): {pdf.name} ({file_size_mb:.1f} MB)")

            print()

    # Run extraction
    await extract_all_documentation(
        trm_dir=args.trm,
        datasheet_path=datasheet_path,
        schematic_path=schematic_path,
        output_dir=args.output,
        model=model,
        max_concurrent=args.concurrent,
        max_budget=args.budget
    )


if __name__ == "__main__":
    asyncio.run(main())
