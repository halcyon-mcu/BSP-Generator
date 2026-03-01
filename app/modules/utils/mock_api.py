"""
Mock API responses for testing without spending money on real API calls.

Enable mock mode by setting environment variable: BSP_MOCK_MODE=1
"""

import json
import random
import asyncio
import re
from typing import Dict, Any


def _extract_module_name(user_message: str) -> str:
    """Best-effort module name extraction from prompt text."""
    explicit = re.search(r'module\s+name:\s*"?([a-z0-9_]+)"?', user_message, re.IGNORECASE)
    if explicit:
        return explicit.group(1).upper()

    known = [
        "SYSTEM", "PCR", "IOMM", "PLL", "VIM", "SCI", "LIN", "GIO",
        "CAN", "DCAN", "I2C", "MIBSPI", "ADC", "RTI", "DMA", "ESM"
    ]
    upper_msg = user_message.upper()
    for name in known:
        if re.search(rf"\b{name}\b", upper_msg):
            return name
    return "MOCK"


def generate_mock_manifest_response(module_name: str) -> str:
    """Generate a realistic mock manifest JSON."""
    mod = module_name.upper()
    return json.dumps({
        "module_name": mod,
        "api_prefix": mod,
        "reg_header_file": f"reg_{mod.lower()}.h",
        "header_file": f"{mod.lower()}.h",
        "source_file": f"{mod.lower()}.c",
        "init_function": f"{mod}_Init",
        "types": [],
        "dependencies": [],
        "categories": ["control", "status"],
        "functions": [
            {
                "name": f"{mod}_Init",
                "prototype": f"void {mod}_Init(void);",
                "category": "control",
                "brief": f"Initialize the {mod} module"
            },
            {
                "name": f"{mod}_GetStatus",
                "prototype": f"uint32_t {mod}_GetStatus(void);",
                "category": "status",
                "brief": "Get module status"
            }
        ]
    })


def generate_mock_header_response() -> str:
    """Generate a realistic mock register header."""
    return """```c
#ifndef REG_MOCK_H
#define REG_MOCK_H

#include <stdint.h>

typedef struct {
    volatile uint32_t CTRL;      /* Control Register */
    volatile uint32_t STATUS;    /* Status Register */
    volatile uint32_t DATA;      /* Data Register */
} MOCK_RegisterMap_t;

#define MOCK_BASE (0xFFF7BC00U)
#define MOCK ((MOCK_RegisterMap_t *)MOCK_BASE)

#endif /* REG_MOCK_H */
```"""


def generate_mock_driver_response(module_name: str) -> str:
    """Generate a realistic mock driver implementation."""
    mod = module_name.upper()
    return f"""```c
#include "{mod.lower()}_driver.h"
#include "reg_{mod.lower()}.h"

void {mod}_Init(void) {{
    // Initialize {mod} module
}}

uint32_t {mod}_GetStatus(void) {{
    return 0U;
}}
```"""


def generate_mock_driver_header_response(module_name: str) -> str:
    """Generate a realistic mock driver header."""
    mod = module_name.upper()
    return f"""```c
#ifndef {mod}_DRIVER_H
#define {mod}_DRIVER_H

#include <stdint.h>

void {mod}_Init(void);
uint32_t {mod}_GetStatus(void);

#endif /* {mod}_DRIVER_H */
```"""


def generate_mock_platform_response(file_type: str) -> str:
    """Generate mock platform file content."""
    if file_type == "start_asm":
        return """```asm
.text
.global _start
_start:
    b main
```"""
    elif file_type == "entry_c":
        return """```c
#include <stdint.h>
void main(void) {
    while(1);
}
```"""
    elif file_type == "linker":
        return """MEMORY {
    FLASH : ORIGIN = 0x00000000, LENGTH = 3M
    RAM   : ORIGIN = 0x08000000, LENGTH = 256K
}
SECTIONS {
    .text : { *(.text*) } > FLASH
    .data : { *(.data*) } > RAM
}"""
    else:
        return f"/* Mock {file_type} content */"


def create_mock_bedrock_response(content: str, input_tokens: int = None, output_tokens: int = None) -> Dict[str, Any]:
    """
    Create a mock Bedrock response in the correct format.

    Args:
        content: The text content to return
        input_tokens: Simulated input tokens (random if not specified)
        output_tokens: Simulated output tokens (random if not specified)

    Returns:
        Dict mimicking boto3 Bedrock response
    """
    # Simulate realistic token counts if not provided
    if input_tokens is None:
        input_tokens = random.randint(5000, 15000)
    if output_tokens is None:
        # Output roughly 15-25% of input
        output_tokens = random.randint(int(input_tokens * 0.15), int(input_tokens * 0.25))

    # Create response in Bedrock format
    payload = {
        "id": "mock-msg-" + "".join(random.choices("0123456789abcdef", k=16)),
        "type": "message",
        "role": "assistant",
        "content": [
            {
                "type": "text",
                "text": content
            }
        ],
        "model": "mock-model",
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens
        }
    }

    # Encode as bytes (like real Bedrock response)
    body_bytes = json.dumps(payload).encode('utf-8')

    return {
        'body': body_bytes,
        'ResponseMetadata': {
            'RequestId': 'mock-request-' + "".join(random.choices("0123456789abcdef", k=16)),
            'HTTPStatusCode': 200
        }
    }


async def mock_invoke_model(model, max_tokens: int, messages: list) -> Dict[str, Any]:
    """
    Mock version of invoke_model that returns fake responses without API calls.

    Simulates realistic delays and token usage for testing.

    Args:
        model: Model enum (ignored in mock)
        max_tokens: Max tokens (used to scale output)
        messages: Message list (analyzed to determine response type)

    Returns:
        Mock Bedrock response
    """
    # Simulate realistic API latency (2-5 seconds, matching real Claude API)
    delay = random.uniform(2.0, 5.0)
    await asyncio.sleep(delay)

    # Determine what type of content to generate based on the prompt
    user_message = ""
    for msg in messages:
        if msg.get("role") == "user":
            user_message = msg.get("content", "").lower()
            break

    module_name = _extract_module_name(user_message)

    # Generate appropriate mock content (specific handlers first)
    if "generate the register map header file" in user_message:
        content = generate_mock_header_response()
        input_tokens = random.randint(8000, 15000)
        output_tokens = random.randint(2000, 4000)
    elif "public driver header file" in user_message or "generate the c header file" in user_message:
        content = generate_mock_driver_header_response(module_name)
        input_tokens = random.randint(7000, 12000)
        output_tokens = random.randint(1200, 2500)
    elif "driver implementation file" in user_message or "generate the c source file" in user_message:
        content = generate_mock_driver_response(module_name)
        input_tokens = random.randint(10000, 20000)
        output_tokens = random.randint(2000, 5000)
    elif "start.s" in user_message or "startup" in user_message:
        content = generate_mock_platform_response("start_asm")
        input_tokens = random.randint(15000, 25000)
        output_tokens = random.randint(1000, 2000)
    elif "entry.c" in user_message:
        content = generate_mock_platform_response("entry_c")
        input_tokens = random.randint(15000, 25000)
        output_tokens = random.randint(1500, 3000)
    elif "linker" in user_message:
        content = generate_mock_platform_response("linker")
        input_tokens = random.randint(20000, 30000)
        output_tokens = random.randint(2000, 4000)
    elif (
        "valid json object" in user_message
        or "output format (critical" in user_message
        or ("define its software interface" in user_message and "\"module_name\"" in user_message)
        or "manifest" in user_message
    ):
        content = generate_mock_manifest_response(module_name)
        input_tokens = random.randint(3000, 5000)
        output_tokens = random.randint(800, 1500)
    else:
        # Generic response
        content = f"Mock response for testing. Original request was approximately {len(user_message)} characters."
        input_tokens = random.randint(5000, 15000)
        output_tokens = random.randint(500, 2000)

    return create_mock_bedrock_response(content, input_tokens, output_tokens)
