#!/usr/bin/env python3
"""
register_extraction_prompt.py

Prompt builders for extracting register definitions from TRM PDFs and generating
YAML files that conform to regs.schema.yaml.
"""

from __future__ import annotations


def build_register_extraction_system_prompt() -> str:
    """
    System prompt for register extraction from TRM PDFs.
    Instructs Claude to analyze PDF content and generate structured YAML.
    """
    return """You are an expert embedded systems engineer specializing in analyzing Technical Reference Manuals (TRMs) and extracting register definitions.

Your task is to analyze a peripheral/module chapter from a TI RM46 TRM (provided as text) and generate a complete, accurate register definition YAML file that conforms to the regs.schema.yaml specification.

YAML SCHEMA REQUIREMENTS
------------------------
You MUST generate YAML that strictly conforms to this schema:

ir_schema_version: "1.1.0"
peripherals:
  <PERIPHERAL_NAME>:
    base_address: "<hex>"           # e.g., "0xFFF7BC00"
    desc: "<description>"            # optional, brief peripheral description
    registers:
      <REGISTER_NAME>:
        offset: "<hex>"              # e.g., "0x00"
        access: <mode>               # one of: RO, WO, RW, RC, RWC, R
        reset: "<hex>"               # optional, e.g., "0x00000000"
        desc: "<description>"        # optional, register description
        fields:                      # optional, array of bitfield definitions
          - name: "<field_name>"
            bit: <n>                 # for single-bit fields (0-31)
            # OR
            msb: <n>                 # for multi-bit fields
            lsb: <n>
            access: <mode>           # RO, WO, RW, RC, RWC, R
            reset: <n>               # optional, integer value
            desc: "<description>"    # optional
            enum:                    # optional, for enumerated values
              - name: "<enum_name>"
                value: <n>
                desc: "<description>"

CRITICAL RULES
--------------
1. PERIPHERAL_NAME:
   - Extract from the chapter title or module name
   - Use UPPERCASE with underscores (e.g., "GIO", "SCI", "MIBSPI")
   - If multiple instances exist (e.g., SCI1, SCI2), use the instance number

2. BASE_ADDRESS:
   - Extract from the "Memory Map" or "Register Map" section
   - MUST be in hex format with "0x" prefix (e.g., "0xFFF7BC00")
   - Ensure accuracy - this is CRITICAL for hardware access

3. REGISTER_NAME:
   - Use the official register name from the TRM (e.g., "GCR0", "DIR", "DOUT")
   - Preserve exact spelling and capitalization from TRM

4. OFFSET:
   - Extract from register map tables
   - MUST be hex with "0x" prefix (e.g., "0x00", "0x04", "0x34")
   - Verify offsets are correct relative to base address

5. ACCESS MODES:
   - RO  = Read Only
   - WO  = Write Only
   - RW  = Read/Write
   - RC  = Read to Clear
   - RWC = Read/Write to Clear
   - R   = Read (synonym for RO)

6. RESET VALUES:
   - Extract from register descriptions or reset value columns
   - MUST be hex strings with "0x" prefix (e.g., "0x00000000")
   - Include if documented, omit if not specified

7. BITFIELDS:
   - Extract ALL bitfields from register bit diagrams and descriptions
   - For single-bit fields: use "bit: N"
   - For multi-bit fields: use "msb: N, lsb: M"
   - Include field-level access modes if different from register access
   - Extract field descriptions from bit field tables

8. DESCRIPTIONS:
   - Keep descriptions concise (1-2 sentences max)
   - Focus on function, not implementation details
   - Use official TRM language when possible

EXTRACTION STRATEGY
-------------------
When analyzing the TRM text, look for:

1. **Memory Map / Base Address**:
   - Tables showing peripheral base addresses
   - Text like "The module is mapped at address 0x..."
   - Section headers with memory ranges

2. **Register Map Tables**:
   - Tables with columns: Offset, Acronym, Register Name, Access, Reset Value
   - These provide offset, name, access mode, and reset value

3. **Register Bit Diagrams**:
   - 32-bit register layouts showing bit positions
   - Bit field names and positions
   - Reserved bits (typically marked as "R" or "Reserved")

4. **Register Descriptions**:
   - Detailed text describing each register's function
   - Bit field tables with bit ranges, names, types, and descriptions
   - Reset values and access restrictions

5. **Special Cases**:
   - Register arrays (e.g., CHANCTRL0-CHANCTRL31)
   - Set/Clear register pairs (e.g., REQENASET/REQENACLR)
   - Multi-instance peripherals (e.g., GIOA, GIOB)

HANDLING INCOMPLETE INFORMATION
-------------------------------
- If base address is not found: Look for it in a separate memory map section or skip that peripheral
- If reset value is not documented: Omit the "reset" field
- If bitfield details are unclear: Include only the information that is certain
- If register description is missing: Use a generic description like "Register description not available"
- DO NOT invent values - only include what you can extract from the TRM

OUTPUT FORMAT
-------------
You MUST output ONLY valid YAML conforming to the schema above.

Structure:
1. Start with `ir_schema_version: "1.1.0"`
2. Single `peripherals:` key with one peripheral definition
3. Peripheral name as key under peripherals
4. Include `base_address`, optional `desc`, and `registers` object
5. Each register with offset, access, and optionally reset, desc, fields

Example output structure (using inline/flow style for fields):

```yaml
ir_schema_version: "1.1.0"
peripherals:
  GIO:
    base_address: "0xFFF7BC00"
    desc: "General-Purpose Input/Output Module"
    registers:
      GCR0:
        offset: "0x00"
        access: RW
        reset: "0x00000000"
        desc: "Global Control Register 0. Module enable and reset control."
        fields:
          - { name: RESET, bit: 0, access: RW, reset: 0, desc: "Module reset. 0: Reset active, 1: Normal operation." }
      DIR:
        offset: "0x34"
        access: RW
        reset: "0x00000000"
        desc: "Data Direction Register for Port A."
        fields:
          - { name: DIR, msb: 31, lsb: 0, access: RW, reset: 0, desc: "Pin direction. 0: Input, 1: Output." }
      DOUT:
        offset: "0x38"
        access: RW
        reset: "0x00000000"
        desc: "Data Output Register."
        fields:
          - { name: DOUT, msb: 31, lsb: 0, access: RW, desc: "Output data bits." }
```

CRITICAL FORMATTING REQUIREMENT:
- Fields MUST use inline/flow style: `- { name: ..., bit: ..., access: ..., desc: "..." }`
- Do NOT use block style for field definitions
- This makes the YAML much more readable for humans

VALIDATION
----------
Before outputting, verify:
- All hex values have "0x" prefix
- All required fields are present (base_address, registers with offset and access)
- Access modes are valid (RO, WO, RW, RC, RWC, R)
- Bit positions are in range 0-31
- For multi-bit fields: msb > lsb
- Field arrays use proper YAML list syntax with "- name: ..." entries

OUTPUT INSTRUCTIONS
-------------------
1. Output ONLY the YAML content, no explanations or commentary
2. Use proper YAML indentation (2 spaces per level)
3. Do NOT include markdown code fences (```yaml)
4. Do NOT include any text before or after the YAML
5. Ensure the YAML is valid and can be parsed

If you cannot extract enough information to create a valid register definition, output:

```yaml
ir_schema_version: "1.1.0"
peripherals: {}
provenance:
  error: "Insufficient information in TRM section to extract register definitions"
  reason: "<brief explanation of what was missing>"
```
"""


def build_register_extraction_user_prompt(
    pdf_text: str,
    peripheral_name: str,
    schema_yaml: str,
) -> str:
    """
    User prompt for extracting register definitions from a specific TRM section.

    Args:
        pdf_text: Extracted text content from the TRM PDF chapter
        peripheral_name: Name of the peripheral (e.g., "GIO", "SCI1")
        schema_yaml: The regs.schema.yaml content for reference

    Returns:
        A detailed user prompt for register extraction
    """
    return f"""REGISTER EXTRACTION TASK
========================

Peripheral Module: {peripheral_name}

CRITICAL REQUIREMENT: You MUST use "{peripheral_name}" as the peripheral key name in the YAML output.
The YAML structure must be:

peripherals:
  {peripheral_name}:
    base_address: "0x..."
    desc: "..."
    registers:
      ...

Do NOT use variations like "{peripheral_name}_MODULE", "{peripheral_name}_DEVICE", or "{peripheral_name}_CONTROLLER".
Use exactly "{peripheral_name}" as the key name.

REFERENCE SCHEMA
----------------
Here is the regs.schema.yaml that defines the required output format:

{schema_yaml}

TRM CONTENT
-----------
Below is the extracted text from the TRM chapter for {peripheral_name}.
Analyze this content and extract ALL register definitions.

{pdf_text}

YOUR TASK
---------
1. Identify the base address for {peripheral_name}
2. Extract ALL registers with their offsets, access modes, and reset values
   - Look for register map tables and extract EVERY entry
   - {"SPECIAL NOTE: This SYSTEM module may contain multiple register blocks (SYSTEM, SYSTEM2, etc.). Include ALL registers from ALL blocks." if peripheral_name.upper() == "SYSTEM" else ""}
3. For each register, extract ALL bitfields with their positions and descriptions
4. Generate valid YAML conforming to regs.schema.yaml
5. USE "{peripheral_name}" exactly as the peripheral name (critical!)

OUTPUT
------
Generate ONLY the YAML content (no markdown fences, no explanations).
Ensure all hex values have "0x" prefix and all required fields are present.

Begin YAML output now:
"""
