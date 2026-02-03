#!/usr/bin/env python3
"""
extract_to_yaml.py

Multi-pass YAML extraction with source attribution:
- Pass 1: Extract from each PDF with provenance tracking
- Output: Per-peripheral YAML fragments with x-source metadata

Every extracted value includes:
- source_pdf: Which PDF it came from
- source_pages: Page numbers
- confidence: high/medium/low
- needs_verification: List of cross-references to resolve
"""

import asyncio
import datetime
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import yaml

from modules.pdf_text_extractor import (
    extract_text_from_pdf,
    extract_peripheral_name_from_filename,
    should_skip_pdf
)
from modules.prompt import Model
from pdf_to_yaml_extractor import invoke_model


# ============================================================================
# COST TRACKING (reuse from extract_complete_reference.py)
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

            return self.total_cost < self.max_budget

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


class BudgetExceededError(Exception):
    """Raised when API cost budget is exceeded."""
    pass


# Global cost tracker
cost_tracker = None


# ============================================================================
# SCHEMA LOADERS
# ============================================================================

def load_yaml_schemas() -> Dict[str, str]:
    """Load YAML schemas to guide extraction format."""
    schemas = {}
    schema_dir = Path("yaml_schemas")

    if not schema_dir.exists():
        return schemas

    for schema_file in ["soc.schema.yaml", "regs.schema.yaml", "bus.schema.yaml",
                        "irq.schema.yaml", "pinmux.schema.yaml"]:
        schema_path = schema_dir / schema_file
        if schema_path.exists():
            try:
                with open(schema_path) as f:
                    schemas[schema_file] = f.read()
            except:
                pass

    return schemas


def load_yaml_examples() -> str:
    """Load existing YAML files as format examples."""
    yaml_in_dir = Path("yaml_in")

    if not yaml_in_dir.exists():
        return ""

    examples = []

    for yaml_file in ["soc.yaml", "regs.yaml", "bus.yaml", "irq.yaml", "pinmux.yaml"]:
        yaml_path = yaml_in_dir / yaml_file
        if yaml_path.exists():
            try:
                content = yaml_path.read_text(encoding='utf-8')
                # Take first 100 lines as example
                lines = content.split('\n')[:100]
                sample = '\n'.join(lines)
                examples.append(f"# Example from {yaml_file}:\n```yaml\n{sample}\n```\n")
            except:
                pass

    if examples:
        return "\n\n".join(examples)

    return ""


# ============================================================================
# EXTRACTION PROMPTS
# ============================================================================

PERIPHERAL_EXTRACTION_PROMPT = """Extract comprehensive hardware information from this TRM peripheral chapter.

CRITICAL INSTRUCTIONS:
1. You MUST output VALID YAML - no markdown code blocks, no backticks
2. Extract ALL 7 sections below (not just registers!)
3. Include x-source for every extracted value
4. If a section has no data, still include the section header with empty dict

OUTPUT FORMAT: Plain YAML (no ```yaml blocks, no markdown)

# SECTION 1: REGISTERS (for regs.yaml)
registers:
  REGISTER_NAME:
    offset: "0xXX"
    reset: "0xXXXXXXXX"
    description: "..."
    fields:
      FIELD_NAME:
        bits: "31:24"
        description: "..."
        x-source:
          pdf: "{pdf_name}"
          pages: [12, 13]
          confidence: "high"  # high/medium/low

# SECTION 2: CLOCK CONFIGURATION (for bus.yaml)
clock_config:
  clock_source: "VCLK"
  clock_enable_register: "PCR1"
  clock_enable_bit: 2
  x-source:
    pdf: "{pdf_name}"
    pages: [5]
    confidence: "medium"

# SECTION 3: PIN ASSIGNMENTS (for pinmux.yaml)
pins:
  - ball: "A1"
    default_function: "GIOA[0]"
    x-source:
      pdf: "{pdf_name}"
      pages: [8]
      confidence: "low"

# If a section needs cross-verification, add x-needs-verification as a TOP-LEVEL key:
pins_x-needs-verification:
  - "Complete pin table found in device datasheet Section 4"

# SECTION 4: INITIALIZATION SEQUENCE (for soc.yaml)
init_sequence:
  - step: 1
    action: "Enable peripheral clock"
    register: "PCR1"
    value: "0x00000004"
    x-source:
      pdf: "{pdf_name}"
      pages: [10]
      confidence: "high"

# SECTION 5: DMA CHANNELS (for soc.yaml)
dma_channels:
  - channel: 5
    trigger: "GIO_INT"
    x-source:
      pdf: "{pdf_name}"
      pages: [15]
      confidence: "medium"

# SECTION 6: INTERRUPTS (for irq.yaml)
# CRITICAL: All fields for an interrupt must be indented under the list item (after the dash)
interrupts:
  - name: "GIO_INT"
    vim_channel: 9
    priority_register: "GIOPRY"
    flag_register: "GIOFLG"
    x-source:
      pdf: "{pdf_name}"
      pages: [14]
      confidence: "low"

# SECTION 7: METADATA (for soc.yaml)
peripheral_metadata:
  name: "{peripheral_name}"
  base_address: "0xFFF7BC00"
  description: "General Purpose I/O"
  x-source:
    pdf: "{pdf_name}"
    pages: [1, 2]
    confidence: "high"

CRITICAL RULES:
1. OUTPUT PLAIN YAML ONLY - No markdown, no ``` blocks, no backticks
2. Include ALL 7 sections (even if empty with {{}})
3. Every value needs x-source: pdf, pages, confidence
4. Add x-needs-verification as TOP-LEVEL keys like "pins_x-needs-verification:", NOT nested in lists
5. Use exact values from PDF
6. YAML LIST SYNTAX: In list sections (pins, init_sequence, dma_channels, interrupts), ALL fields for an item must be indented under the dash (-). Never add a new key at the same level as list items.

PDF: {pdf_name}
Content:
{pdf_text}

OUTPUT ALL 7 SECTIONS AS VALID YAML:
"""


DATASHEET_EXTRACTION_PROMPT = """Extract system-level information from device datasheet.

Focus on information NOT in individual peripheral chapters:

## 1. MEMORY MAP (for memmap.yaml)
```yaml
memory_regions:
  - name: "Flash"
    base: "0x00000000"
    size: "0x00300000"  # 3MB
    type: "flash"
    x-source:
      pdf: "{pdf_name}"
      pages: [23]
      confidence: "high"
```

## 2. COMPLETE PINMUX TABLE (for pinmux.yaml)
```yaml
# Extract COMPLETE pin table from datasheet
pinmux_table:
  - ball: "A1"
    default: "GIOA[0]"
    alt1: "SPI1_CLK"
    alt2: "EQEP1_A"
    x-source:
      pdf: "{pdf_name}"
      pages: [45, 46, 47]  # Pinmux table pages
      confidence: "high"
```

## 3. INTERRUPT TABLE (for irq.yaml)
```yaml
# Extract COMPLETE VIM channel assignments
vim_channels:
  - channel: 9
    source: "GIO_INT"
    peripheral: "GIO"
    default_priority: 0
    x-source:
      pdf: "{pdf_name}"
      pages: [89]  # Interrupt table page
      confidence: "high"
```

## 4. CLOCK TREE (for bus.yaml)
```yaml
clock_domains:
  - name: "VCLK"
    source: "PLL1"
    divider: 2
    frequency_hz: 80000000
    x-source:
      pdf: "{pdf_name}"
      pages: [34]
      confidence: "high"
```

## 5. PERIPHERAL BASE ADDRESSES (for soc.yaml)
```yaml
peripheral_addresses:
  GIO: "0xFFF7BC00"
  SCI1: "0xFFF7E400"
  MIBSPI1: "0xFFF7F400"
  # ... (all peripherals)
  x-source:
    pdf: "{pdf_name}"
    pages: [25, 26]  # Memory map section
    confidence: "high"
```

IMPORTANT:
- Pinmux and interrupt tables are PRIMARY sources in datasheet
- Extract COMPLETE tables, not partial
- This is the authoritative source for pin/IRQ assignments

YAML STYLE GUIDE:
{yaml_examples}

Datasheet: {pdf_name}
Content:
{pdf_text}

Generate YAML extraction:
"""


# ============================================================================
# EXTRACTION FUNCTIONS
# ============================================================================

async def extract_peripheral_yaml(
    pdf_path: Path,
    model: Model,
    output_dir: Path,
    yaml_examples: str = ""
) -> Dict:
    """Extract YAML for one peripheral with source attribution."""

    global cost_tracker

    peripheral_name, full_name = extract_peripheral_name_from_filename(pdf_path.name)

    print(f"\n[Extracting] {peripheral_name} from {pdf_path.name}...")

    try:
        # Extract PDF text
        pdf_text = extract_text_from_pdf(pdf_path)

        # Truncate if needed (SYSTEM gets more space)
        max_chars = 300000 if peripheral_name.upper() == 'SYSTEM' else 200000
        if len(pdf_text) > max_chars:
            pdf_text = pdf_text[:max_chars] + "\n\n[...truncated...]"

        # Build prompt
        prompt = PERIPHERAL_EXTRACTION_PROMPT.format(
            pdf_name=pdf_path.name,
            peripheral_name=peripheral_name,
            pdf_text=pdf_text,
            yaml_examples=yaml_examples
        )

        # Call Claude
        print(f"  Calling Claude API...")
        response, input_tokens, output_tokens = await invoke_model(
            model=model,
            max_tokens=24000,  # Increased for all 7 sections
            system_prompt="You are a hardware documentation extraction assistant. Output VALID YAML with NO markdown code blocks. Extract all 7 required sections with source attribution.",
            user_prompt=prompt
        )

        # Track cost
        within_budget = await cost_tracker.add_tokens(input_tokens, output_tokens)
        if not within_budget:
            raise BudgetExceededError(f"Budget exceeded")

        # Parse YAML from response
        yaml_content = extract_yaml_from_response(response)

        # Save to output directory
        periph_dir = output_dir / "extracted" / peripheral_name
        periph_dir.mkdir(parents=True, exist_ok=True)

        # Save complete extraction
        output_file = periph_dir / f"{peripheral_name}_extracted.yaml"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(yaml_content)

        # Also save metadata
        meta_file = periph_dir / "metadata.json"
        with open(meta_file, 'w') as f:
            json.dump({
                "peripheral": peripheral_name,
                "source_pdf": pdf_path.name,
                "extracted_at": datetime.datetime.now().isoformat(),
                "tokens": {"input": input_tokens, "output": output_tokens},
                "cost": (input_tokens * 3 + output_tokens * 15) / 1_000_000
            }, f, indent=2)

        print(f"  [OK] Wrote {output_file.name}")
        print(f"  {cost_tracker.format_status()}")

        return {
            "peripheral": peripheral_name,
            "success": True,
            "output_file": str(output_file)
        }

    except BudgetExceededError:
        print(f"  ⚠ Budget exceeded")
        raise

    except Exception as e:
        print(f"  [FAIL] Failed: {e}")
        return {
            "peripheral": peripheral_name,
            "success": False,
            "error": str(e)
        }


async def extract_datasheet_yaml(
    datasheet_path: Path,
    model: Model,
    output_dir: Path,
    yaml_examples: str = ""
) -> Dict:
    """Extract system-level YAML from datasheet."""

    global cost_tracker

    print(f"\n{'='*80}")
    print(f"[Extracting] DATASHEET: {datasheet_path.name}")
    print(f"{'='*80}")

    try:
        pdf_text = extract_text_from_pdf(datasheet_path)

        # Datasheet is large - take first and last portions
        max_chars = 400000
        if len(pdf_text) > max_chars:
            split = max_chars // 2
            pdf_text = pdf_text[:split] + "\n\n[...middle truncated...]\n\n" + pdf_text[-split:]

        prompt = DATASHEET_EXTRACTION_PROMPT.format(
            pdf_name=datasheet_path.name,
            pdf_text=pdf_text,
            yaml_examples=yaml_examples
        )

        print(f"  Calling Claude API (large document)...")
        response, input_tokens, output_tokens = await invoke_model(
            model=model,
            max_tokens=24000,
            system_prompt="You are extracting system-level information from a datasheet. Include complete pinmux and interrupt tables.",
            user_prompt=prompt
        )

        within_budget = await cost_tracker.add_tokens(input_tokens, output_tokens)
        if not within_budget:
            raise BudgetExceededError(f"Budget exceeded")

        yaml_content = extract_yaml_from_response(response)

        # Save
        ds_dir = output_dir / "extracted" / "DATASHEET"
        ds_dir.mkdir(parents=True, exist_ok=True)

        output_file = ds_dir / "datasheet_extracted.yaml"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(yaml_content)

        print(f"  [OK] Wrote {output_file.name}")
        print(f"  {cost_tracker.format_status()}")

        return {
            "source": "datasheet",
            "success": True,
            "output_file": str(output_file)
        }

    except BudgetExceededError:
        raise
    except Exception as e:
        print(f"  [FAIL] Failed: {e}")
        return {"source": "datasheet", "success": False, "error": str(e)}


def extract_yaml_from_response(response: str) -> str:
    """Extract YAML content from Claude response, removing markdown artifacts."""
    import re

    # Remove any markdown code blocks
    if "```yaml" in response:
        # Extract from ```yaml ... ```
        match = re.search(r'```yaml\s*\n(.*?)\n```', response, re.DOTALL)
        if match:
            return match.group(1).strip()
    elif "```" in response:
        # Extract from generic ``` ... ```
        match = re.search(r'```\s*\n(.*?)\n```', response, re.DOTALL)
        if match:
            return match.group(1).strip()

    # Remove any leading text before the first YAML key
    # Look for common YAML start patterns
    lines = response.split('\n')
    yaml_start = 0

    for i, line in enumerate(lines):
        # Check if line starts a YAML structure
        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*:', line) or line.startswith('#'):
            yaml_start = i
            break

    yaml_content = '\n'.join(lines[yaml_start:])

    # Remove trailing non-YAML text (often explanatory notes)
    # Stop at common ending patterns
    yaml_lines = []
    for line in yaml_content.split('\n'):
        # Stop if we hit obvious non-YAML
        if line.strip().startswith('Note:') or line.strip().startswith('This YAML'):
            break
        yaml_lines.append(line)

    return '\n'.join(yaml_lines).strip()


# ============================================================================
# MAIN EXTRACTION PIPELINE
# ============================================================================

async def extract_all_peripherals(
    trm_dir: Path,
    datasheet_path: Optional[Path],
    output_dir: Path,
    model: Model = Model.SONNET_4_5,
    max_concurrent: int = 4,
    max_budget: float = 75.0,
    test_peripherals: Optional[List[str]] = None
):
    """
    Pass 1: Extract YAML from all PDFs with source attribution.

    Args:
        trm_dir: Directory with TRM peripheral PDFs
        datasheet_path: Path to datasheet (for pinmux/IRQ tables)
        output_dir: Output directory
        model: Claude model
        max_concurrent: Parallel extractions
        max_budget: Cost limit
        test_peripherals: If set, only extract these peripherals (for testing)
    """

    global cost_tracker
    cost_tracker = CostTracker(max_budget=max_budget)

    print("="*80)
    print("YAML EXTRACTION - PASS 1: Initial Extraction with Source Attribution")
    print("="*80)
    print(f"Model: {model.value}")
    print(f"Budget: ${max_budget:.2f}")
    if test_peripherals:
        print(f"TEST MODE: Only extracting {test_peripherals}")
    print()

    # Load YAML examples
    print("Loading YAML examples from yaml_in/...")
    yaml_examples = load_yaml_examples()
    if yaml_examples:
        print("  [OK] Loaded examples")

    # Get TRM PDFs
    trm_pdfs = [p for p in trm_dir.glob("*.pdf") if not should_skip_pdf(p.name, p)]

    # Filter for test mode
    if test_peripherals:
        test_set = set(p.upper() for p in test_peripherals)
        trm_pdfs = [
            p for p in trm_pdfs
            if extract_peripheral_name_from_filename(p.name)[0].upper() in test_set
        ]

    print(f"\nExtracting from {len(trm_pdfs)} TRM PDFs")
    if datasheet_path and datasheet_path.exists():
        print(f"Plus datasheet: {datasheet_path.name}")
    print()

    start_time = datetime.datetime.now()

    # Extract datasheet first (has pinmux/IRQ tables)
    datasheet_result = None
    if datasheet_path and datasheet_path.exists():
        try:
            datasheet_result = await extract_datasheet_yaml(
                datasheet_path, model, output_dir, yaml_examples
            )
        except BudgetExceededError:
            print("\n⚠ Budget exceeded during datasheet extraction")
            return

    # Extract peripherals in parallel
    semaphore = asyncio.Semaphore(max_concurrent)

    async def extract_with_limit(pdf_path):
        async with semaphore:
            return await extract_peripheral_yaml(
                pdf_path, model, output_dir, yaml_examples
            )

    try:
        results = await asyncio.gather(
            *[extract_with_limit(pdf) for pdf in trm_pdfs],
            return_exceptions=True
        )
    except BudgetExceededError:
        print("\n⚠ Budget exceeded during peripheral extraction")
        results = []

    # Summary
    end_time = datetime.datetime.now()
    duration = end_time - start_time

    successful = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
    failed = len(results) - successful

    print("\n" + "="*80)
    print("PASS 1 COMPLETE")
    print("="*80)
    print(f"Duration: {duration}")
    print(f"Peripherals: {successful} succeeded, {failed} failed")
    if datasheet_result:
        print(f"Datasheet: {'[OK]' if datasheet_result.get('success') else '[FAIL]'}")
    print()
    print(f"{cost_tracker.format_status()}")
    print()
    print(f"Output: {output_dir / 'extracted'}")
    print("="*80)


# ============================================================================
# CLI
# ============================================================================

async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract YAML from PDFs with source attribution (Pass 1)"
    )
    parser.add_argument(
        "--trm",
        type=Path,
        default=Path("modules/pdfs/TRM_split"),
        help="TRM directory"
    )
    parser.add_argument(
        "--datasheet",
        type=Path,
        help="Path to datasheet PDF"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("yaml_out"),
        help="Output directory"
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=4,
        help="Max concurrent extractions"
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=75.0,
        help="Max cost in USD"
    )
    parser.add_argument(
        "--test-peripherals",
        type=str,
        help="Comma-separated list of peripherals to extract (test mode), e.g., 'GIO,SCI,SYSTEM'"
    )
    parser.add_argument(
        "--model",
        choices=["haiku4.5", "sonnet4.5"],
        default="sonnet4.5"
    )

    args = parser.parse_args()

    # Parse test peripherals
    test_peripherals = None
    if args.test_peripherals:
        test_peripherals = [p.strip().upper() for p in args.test_peripherals.split(',')]

    # Auto-detect datasheet if not specified
    if not args.datasheet:
        input_docs = Path("input_docs")
        if input_docs.exists():
            candidates = []
            for pdf in input_docs.glob("*.pdf"):
                # Skip schematic files
                if "schematic" in pdf.name.lower():
                    continue

                size_mb = pdf.stat().st_size / (1024 * 1024)

                # Prefer files with "datasheet" in name
                if "datasheet" in pdf.name.lower():
                    args.datasheet = pdf
                    print(f"Auto-detected datasheet: {pdf.name} ({size_mb:.1f} MB)")
                    break

                # Otherwise collect candidates >1MB
                if size_mb > 1:
                    candidates.append((pdf, size_mb))

            # If no explicit "datasheet" name found, use largest candidate
            if not args.datasheet and candidates:
                candidates.sort(key=lambda x: x[1], reverse=True)
                args.datasheet = candidates[0][0]
                print(f"Auto-detected datasheet: {args.datasheet.name} ({candidates[0][1]:.1f} MB)")

    model = Model.HAIKU_4_5 if args.model == "haiku4.5" else Model.SONNET_4_5

    await extract_all_peripherals(
        trm_dir=args.trm,
        datasheet_path=args.datasheet,
        output_dir=args.output,
        model=model,
        max_concurrent=args.concurrent,
        max_budget=args.budget,
        test_peripherals=test_peripherals
    )


if __name__ == "__main__":
    asyncio.run(main())
