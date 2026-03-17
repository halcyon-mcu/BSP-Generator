#!/usr/bin/env python3
"""
extract_vim_wake_regs.py

Targeted extraction of VIM wake registers from TRM Chapter 15.
Extracts 8 specific registers: WAKENASET0-3 and WAKENACLR0-3.
"""

import asyncio
from pathlib import Path
import yaml

from ..extraction.pdf_text_extractor import extract_text_from_pdf
from ..extraction.pdf_to_yaml_extractor import invoke_model, extract_yaml_from_response, Model


async def extract_vim_wake_registers():
    """Extract VIM wake registers and save to YAML."""

    # Paths
    pdf_path = Path(r"c:\Users\dovyd\Documents\GitHub\BSP-Generator\app\modules\pdfs\TRM_split\15_Vectored_Interrupt_Manager_VIM_Module.pdf")
    output_path = Path(r"c:\Users\dovyd\Documents\GitHub\BSP-Generator\app\yaml_out\vim_wake_registers.yaml")

    print("=" * 80)
    print("VIM Wake Register Extraction")
    print("=" * 80)
    print(f"PDF: {pdf_path.name}")
    print(f"Output: {output_path}")
    print()

    # Step 1: Extract text from PDF
    print("[1/3] Extracting text from PDF...")
    pdf_text = extract_text_from_pdf(pdf_path)
    print(f"  Extracted {len(pdf_text)} characters from PDF")

    # Step 2: Build targeted prompt
    print("\n[2/3] Building extraction prompt...")

    system_prompt = """You are an expert embedded systems engineer analyzing a Technical Reference Manual (TRM).

Your task is to extract ONLY the 8 VIM wake registers from the provided text:
- WAKENASET0 (offset 0x0050)
- WAKENASET1 (offset 0x0054)
- WAKENASET2 (offset 0x0058)
- WAKENASET3 (offset 0x005C)
- WAKENACLR0 (offset 0x0060)
- WAKENACLR1 (offset 0x0064)
- WAKENACLR2 (offset 0x0068)
- WAKENACLR3 (offset 0x006C)

For each register, extract:
- Offset (hex with 0x prefix)
- Access type (RW, RO, WO, etc.)
- Reset value (hex with 0x prefix)
- Register description
- All field definitions with:
  - Field name
  - Bit position (bit: N for single bit, msb/lsb for multi-bit)
  - Access type
  - Description
  - Reset value (if available)

Output ONLY valid YAML in this exact format:

```yaml
ir_schema_version: "1.1.0"
peripherals:
  VIM:
    base_address: "0xFFFFFE00"
    desc: "Vectored Interrupt Manager Module"
    registers:
      WAKENASET0:
        offset: "0x0050"
        access: RW
        reset: "0x00000000"
        desc: "Wake enable set register 0"
        fields:
          - { name: FIELD_NAME, msb: X, lsb: Y, access: RW, reset: 0, desc: "Field description" }
      WAKENASET1:
        offset: "0x0054"
        access: RW
        reset: "0x00000000"
        desc: "Wake enable set register 1"
        fields:
          - { name: FIELD_NAME, msb: X, lsb: Y, access: RW, reset: 0, desc: "Field description" }
      # ... (continue for all 8 registers)
```

CRITICAL RULES:
1. Extract ONLY these 8 wake registers, nothing else
2. Use inline/flow style for fields: `- { name: ..., bit: ..., access: ..., desc: "..." }`
3. All hex values must have "0x" prefix
4. If a register has a single field covering all 32 bits, use: msb: 31, lsb: 0
5. Use "bit: N" for single-bit fields, "msb/lsb" for multi-bit fields
6. Include reset values if documented
7. Keep descriptions concise and accurate
8. Output ONLY the YAML content, no explanations

Begin your analysis and extract these 8 registers now."""

    user_prompt = f"""EXTRACTION TASK: VIM Wake Registers
========================================

Extract ONLY these 8 registers from the VIM TRM chapter:

TARGET REGISTERS (in order):
1. WAKENASET0 - offset 0x0050
2. WAKENASET1 - offset 0x0054
3. WAKENASET2 - offset 0x0058
4. WAKENASET3 - offset 0x005C
5. WAKENACLR0 - offset 0x0060
6. WAKENACLR1 - offset 0x0064
7. WAKENACLR2 - offset 0x0068
8. WAKENACLR3 - offset 0x006C

These registers control which VIM interrupt channels can wake the CPU from low-power modes.

TRM CONTENT:
============

{pdf_text}

YOUR TASK:
==========
1. Locate the VIM base address (should be 0xFFFFFE00)
2. Find each of the 8 wake registers listed above
3. Extract offset, access type, reset value, and description
4. Extract ALL field definitions for each register
5. Generate YAML in the exact format shown in the system prompt

OUTPUT ONLY THE YAML CONTENT NOW:
"""

    print(f"  System prompt: {len(system_prompt)} chars")
    print(f"  User prompt: {len(user_prompt)} chars")

    # Step 3: Call Claude API
    print("\n[3/3] Calling Claude API...")
    print("  (this may take 10-30 seconds)")

    response, input_tokens, output_tokens = await invoke_model(
        model=Model.SONNET_4_5,
        max_tokens=16000,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )

    print(f"  Received response: {len(response)} chars")
    print(f"  Token usage: {input_tokens:,} in / {output_tokens:,} out")

    # Extract YAML
    yaml_content = extract_yaml_from_response(response)
    if yaml_content is None:
        print("\nERROR: Failed to extract YAML from response")
        print("\nRaw response:")
        print(response[:2000])
        return False

    # Parse and validate
    try:
        yaml_data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        print(f"\nERROR: Invalid YAML generated: {e}")
        return False

    # Basic validation
    if 'peripherals' not in yaml_data:
        print("\nERROR: Missing 'peripherals' key in YAML")
        return False

    if 'VIM' not in yaml_data['peripherals']:
        print("\nERROR: Missing 'VIM' peripheral in YAML")
        return False

    vim_regs = yaml_data['peripherals']['VIM'].get('registers', {})
    expected_regs = [
        'WAKENASET0', 'WAKENASET1', 'WAKENASET2', 'WAKENASET3',
        'WAKENACLR0', 'WAKENACLR1', 'WAKENACLR2', 'WAKENACLR3'
    ]

    missing_regs = [reg for reg in expected_regs if reg not in vim_regs]
    if missing_regs:
        print(f"\nWARNING: Missing registers: {', '.join(missing_regs)}")

    found_regs = [reg for reg in expected_regs if reg in vim_regs]
    print(f"\n[SUCCESS] Extracted {len(found_regs)}/8 registers:")
    for reg in found_regs:
        field_count = len(vim_regs[reg].get('fields', []))
        print(f"  - {reg}: {field_count} fields")

    # Save output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml_content, encoding='utf-8')
    print(f"\n[SAVED] Output written to: {output_path}")

    # Print summary
    print("\n" + "=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)
    print(f"Peripheral: VIM (Vectored Interrupt Manager)")
    print(f"Base Address: {yaml_data['peripherals']['VIM'].get('base_address', 'N/A')}")
    print(f"Registers Extracted: {len(found_regs)}/8")

    total_fields = sum(len(vim_regs[reg].get('fields', [])) for reg in found_regs)
    print(f"Total Fields: {total_fields}")
    print("=" * 80)

    return True


if __name__ == "__main__":
    success = asyncio.run(extract_vim_wake_registers())
    exit(0 if success else 1)
