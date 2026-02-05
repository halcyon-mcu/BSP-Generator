#!/usr/bin/env python3
"""
register_discovery.py

Use Claude to discover registers in PDF text before full extraction.
Much more robust than regex patterns - Claude understands varied table formats.
"""

from typing import Dict, List, Any, Optional
import json


def build_discovery_prompt(pdf_text: str, peripheral_name: str) -> tuple[str, str]:
    """
    Build prompts for Claude to discover registers.

    Args:
        pdf_text: Extracted PDF text
        peripheral_name: Name of peripheral

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    system_prompt = """You are a register discovery assistant specialized in finding hardware registers in technical documentation.

Your task: Thoroughly scan the documentation and list ALL registers found, including registers from multiple register blocks if present.

Output ONLY a JSON list of registers with this format:
[
  {"name": "REGISTER_NAME1", "offset": "0x00"},
  {"name": "REGISTER_NAME2", "offset": "0x04"},
  ...
]

Rules:
- List register NAME and OFFSET only (no descriptions, no fields)
- Include ALL registers you find (even if details are incomplete)
- Look carefully for register map tables - these often contain dozens of registers
- Extract EVERY entry from register tables (don't skip any rows)
- If multiple register blocks exist (e.g., SYSTEM and SYSTEM2), include registers from ALL blocks
- If offset is unclear, use "0x??" as placeholder
- Be extremely thorough - missing a register is worse than including a questionable one
- Look for patterns like "Register_Name" followed by hex addresses like "0x00", "0x04", etc.
- Output ONLY the JSON array, nothing else"""

    # Use more text for SYSTEM peripheral to ensure we get all register blocks
    text_limit = 200000 if peripheral_name.upper() == 'SYSTEM' else 120000

    user_prompt = f"""Scan this technical documentation for {peripheral_name} peripheral.

IMPORTANT: This peripheral may have MULTIPLE register blocks. Find ALL of them.
{"CRITICAL: This is the SYSTEM module which contains multiple register blocks including SYS, SYS2, and clock control registers. You MUST find ALL register blocks." if peripheral_name.upper() == "SYSTEM" else ""}

Find and list ALL registers mentioned in:
- Register map tables (extract EVERY row from these tables - don't skip any!)
- Register summary sections (often at the beginning of the chapter)
- Register descriptions (detailed sections for each register)
- Memory map sections
- Peripheral frame sections
- Any other register references

Look especially for:
- Tables with columns like "Register Name", "Offset", "Address", "Reset Value"
- Lists of registers with hex addresses (0x00, 0x04, 0x08, etc.)
- Register blocks with different prefixes (e.g., SYS_, SYS2_, CLK_, etc.)
- Multiple sections describing different register groups

INSTRUCTIONS:
1. Scan the ENTIRE document below carefully
2. Find ALL register map tables (there may be multiple)
3. Extract EVERY register name and offset from each table
4. Look for register names like: REG_NAME, PREFIX_NAME, MODULE_REG, etc.
5. Include registers even if details are incomplete
6. If you find 50+ registers, keep going - some peripherals have 100+ registers

PDF Content (first {text_limit} characters):
{pdf_text[:text_limit]}

Output the complete JSON list of ALL registers found now:"""

    return system_prompt, user_prompt


def parse_discovery_response(response: str) -> Dict[str, Any]:
    """
    Parse Claude's discovery response.

    Args:
        response: Raw response from Claude

    Returns:
        Dictionary with:
        - registers: List of discovered registers
        - count: Number found
        - register_names: List of names only
    """
    # Try to extract JSON from response
    import re

    # Look for JSON array
    json_match = re.search(r'\[.*\]', response, re.DOTALL)
    if not json_match:
        return {
            'registers': [],
            'count': 0,
            'register_names': [],
            'error': 'No JSON array found in response'
        }

    try:
        registers = json.loads(json_match.group(0))

        # Validate and clean
        cleaned_registers = []
        for reg in registers:
            if isinstance(reg, dict) and 'name' in reg:
                cleaned_registers.append({
                    'name': reg['name'],
                    'offset': reg.get('offset', '0x??'),
                })

        return {
            'registers': cleaned_registers,
            'count': len(cleaned_registers),
            'register_names': [r['name'] for r in cleaned_registers],
        }
    except json.JSONDecodeError as e:
        return {
            'registers': [],
            'count': 0,
            'register_names': [],
            'error': f'Failed to parse JSON: {e}'
        }


def format_discovery_summary(discovery: Dict[str, Any]) -> str:
    """
    Format discovery results for main extraction prompt.

    Args:
        discovery: Results from parse_discovery_response()

    Returns:
        Formatted string for prompt
    """
    if discovery['count'] == 0:
        return ""

    summary = f"""
=== REGISTER DISCOVERY RESULTS ===
Found {discovery['count']} registers in pre-scan:

"""

    # List all registers
    for i, reg in enumerate(discovery['registers'][:30], 1):
        summary += f"{i:2d}. {reg['name']:<20s} @ {reg['offset']}\n"

    if discovery['count'] > 30:
        summary += f"... and {discovery['count'] - 30} more\n"

    summary += f"""
CRITICAL: You MUST extract ALL {discovery['count']} registers listed above.
If you cannot find full details for a register, include it with minimal information.
Missing registers is a critical error.
===================================

"""
    return summary


async def discover_registers(
    pdf_text: str,
    peripheral_name: str,
    invoke_model_func,
    model,
    progress=None,
) -> Dict[str, Any]:
    """
    Use Claude to discover registers in PDF.

    Args:
        pdf_text: Extracted PDF text
        peripheral_name: Name of peripheral
        invoke_model_func: Function to invoke Claude
        model: Model to use
        progress: Optional progress tracker

    Returns:
        Discovery results dictionary
    """
    # Build discovery prompts
    system_prompt, user_prompt = build_discovery_prompt(pdf_text, peripheral_name)

    # Call Claude for discovery
    if progress:
        await progress.set_current_file(peripheral_name, "Discovering registers")

    # Use more tokens for complex peripherals with many registers
    max_tokens = 8000 if peripheral_name.upper() in ['SYSTEM', 'ARCHITECTURE'] else 4000

    response, input_tokens, output_tokens = await invoke_model_func(
        model=model,
        max_tokens=max_tokens,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )

    # Track tokens
    if progress:
        await progress.add_tokens(input_tokens, output_tokens)

    # Parse response
    discovery = parse_discovery_response(response)

    return discovery


# Example usage
if __name__ == "__main__":
    # Test prompt building
    sample_text = """
    System Module Registers

    Table 2-1. System Module Register Map

    Offset    Name        Description
    0x00      SYS_PC      System PC
    0x04      SYS_PCR     Peripheral Control
    0x08      SYS2        System 2 Register
    0x20      CLKCNTL     Clock Control
    """

    sys_prompt, user_prompt = build_discovery_prompt(sample_text, "SYSTEM")

    print("System Prompt:")
    print("=" * 80)
    print(sys_prompt)
    print()

    print("User Prompt:")
    print("=" * 80)
    print(user_prompt[:500])
    print()

    # Test parsing
    sample_response = '''Here are the registers found:
[
  {"name": "SYS_PC", "offset": "0x00"},
  {"name": "SYS_PCR", "offset": "0x04"},
  {"name": "SYS2", "offset": "0x08"},
  {"name": "CLKCNTL", "offset": "0x20"}
]
'''

    discovery = parse_discovery_response(sample_response)
    print("Parsed Discovery:")
    print("=" * 80)
    print(f"Count: {discovery['count']}")
    print(f"Names: {discovery['register_names']}")
    print()

    print("Formatted Summary:")
    print("=" * 80)
    print(format_discovery_summary(discovery))
