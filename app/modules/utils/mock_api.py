"""
Mock API responses for testing without spending money on real API calls.

Enable mock mode by setting environment variable: BSP_MOCK_MODE=1
"""

import json
import random
import asyncio
from typing import Dict, Any


def generate_mock_manifest_response() -> str:
    """Generate a realistic mock manifest JSON."""
    return json.dumps({
        "module_name": "MOCK",
        "api_prefix": "MOCK",
        "reg_header_file": "reg_mock.h",
        "categories": ["control", "status"],
        "functions": [
            {
                "name": "MOCK_Init",
                "category": "control",
                "description": "Initialize the MOCK module",
                "parameters": [],
                "returns": "void"
            },
            {
                "name": "MOCK_GetStatus",
                "category": "status",
                "description": "Get module status",
                "parameters": [],
                "returns": "uint32_t"
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
    return f"""```c
#include "{module_name.lower()}.h"
#include "reg_{module_name.lower()}.h"

void {module_name}_Init(void) {{
    // Initialize {module_name} module
    {module_name}->CTRL = 0x00000001U;  // Enable module
}}

uint32_t {module_name}_GetStatus(void) {{
    return {module_name}->STATUS;
}}
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

    # Generate appropriate mock content
    if "manifest" in user_message or "json" in user_message:
        content = generate_mock_manifest_response()
        input_tokens = random.randint(3000, 5000)
        output_tokens = random.randint(800, 1500)
    elif "register header" in user_message or "reg_" in user_message:
        content = generate_mock_header_response()
        input_tokens = random.randint(8000, 15000)
        output_tokens = random.randint(2000, 4000)
    elif "driver" in user_message or "implementation" in user_message:
        # Extract module name if present
        module_name = "MOCK"
        for word in user_message.split():
            if word.isupper() and len(word) > 2:
                module_name = word
                break
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
    else:
        # Generic response
        content = f"Mock response for testing. Original request was approximately {len(user_message)} characters."
        input_tokens = random.randint(5000, 15000)
        output_tokens = random.randint(500, 2000)

    return create_mock_bedrock_response(content, input_tokens, output_tokens)
