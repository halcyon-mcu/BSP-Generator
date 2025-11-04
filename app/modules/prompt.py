import json
import os
import boto3
from langchain_aws import BedrockEmbeddings

from config import TARGET_FILES

client = boto3.client(
    service_name="bedrock-runtime",
    region_name="us-west-2"
)

# ---------------- Prompt builders (hardened) ----------------

def build_system_prompt(target_files: list[str]) -> str:
    first_file = target_files[0]
    files_bulleted = "\n  ".join(target_files)

    return f"""You are generating minimal, portable C11 BSP files for TI RM46 (Cortex-R4).

FACTS POLICY (strict):
- Use ONLY the numeric values from FACTS CANON.
- Do NOT invent, transform, or reformat addresses/offsets/bits.
- If any required value is missing, emit a TODO in the FACTS MIRROR and STOP (do not emit files).

VERIFICATION STEP (required):
- Emit EXACTLY this header block BEFORE any files:
===== FACTS MIRROR =====
<key> = <hex or int>
...
===== END FACTS MIRROR =====

HARD OUTPUT CONTRACT:
- After the FACTS MIRROR, emit ONLY these files, with these separators, IN THIS ORDER:
  {files_bulleted}
- Each file MUST be delimited by a line of the form:
  ===== FILE: <path> =====
- The FIRST line of the entire response MUST be:
  ===== FILE: {first_file} =====
  (This is enforced by our post-processor. If you need to include the mirror first, then output the mirror and immediately re-emit the first separator as the next line.)
- No prose, explanations, or extra text outside the FACTS MIRROR block and the file blocks.

CODING RULES:
- Public headers MUST NOT include vendor headers or vendor-specific types.
- Use ONLY values from FACTS CANON for base addresses and register offsets.
- For GPIO toggling, read DOUT_* (not DIN_*). Prefer DSET/DCLR for writes (avoid RMW on DOUT).
- Add a short provenance comment above each register access:  // [prov] regs.yaml:<PERIPH>.<REGISTER>
- C standard = C11. Build target = CCS for Cortex-R4 (RM46).

REUSE POLICY (POC):
- Reuse HALCoGen startup/vector/linker/system/pinmux; do NOT include vendor headers in public APIs.
"""


def build_user_prompt(
    facts_canon: str,
    yamls: dict[str, str],
    api_header: str,
    target_files: list[str],
    pattern_snippets: list[tuple[str, str]] | None = None,
) -> str:
    """
    facts_canon: pre-extracted tiny block like
        --- FACTS CANON ---
        GIO_BASE = 0xFFF7BC00
        GIO_DIR_A_OFFSET = 0x0034
        ...
        --- END FACTS CANON ---
    yamls: dict of filename->text (e.g., {"regs.yaml": "...", ...})
    api_header: the golden public API header text
    pattern_snippets: list of (title, code) small templates you want the model to follow
    """
    # Assemble YAML sections (optional, keep them after the CANON so they don’t distract)
    yaml_sections = []
    for name in ["soc.yaml", "regs.yaml", "pinmux.yaml", "memmap.yaml", "irq.yaml", "bus.yaml"]:
        if name in yamls:
            yaml_sections.append(f"--- {name} ---\n{yamls[name]}")

    # Optional golden patterns
    patterns = []
    if pattern_snippets:
        for title, code in pattern_snippets:
            patterns.append(f"--- PATTERN: {title} ---\n{code}\n--- END PATTERN ---")

    files_list = "\n".join(f"- {p}" for p in target_files)

    return f"""INPUTS:

{facts_canon}

{"\n\n".join(patterns) if patterns else ""}

--- gpio_api_header.txt ---
{api_header}

{"\n\n".join(yaml_sections) if yaml_sections else ""}

TASK:
Generate EXACTLY the following files, in this order, using the API above and ONLY the values in FACTS CANON:
{files_list}

Per-file guidance:
1) drivers/gpio.h
   - Emit EXACTLY the API provided in gpio_api_header.txt (no vendor includes).
2) drivers/gpio.c
   - Implement using RM46 GIO registers from FACTS CANON (DIR_A/B, DSET_A/B, DCLR_A/B, DOUT_A/B).
   - Use a tiny helper for base+offset access. Add provenance comments before each access.
   - Toggle must read DOUT_* to decide set/clear.
   - Include private header: soc/rm46_gio_regs.h
3) soc/rm46_gio_regs.h
   - #define GIO_BASE and OFFSETS (A/B: DIR/DIN/DOUT/DSET/DCLR) using EXACT values from FACTS CANON.
   - Provide a small macro for register addressing.
4) board/pinmux_init.c
   - Stub calling vendor pinmux until replaced:
     extern void pinMuxInitialize(void);
     void pinmux_init_led(void) {{ pinMuxInitialize(); }}
5) examples/blinky/main.c
   - Use only the public gpio API to configure one LED pin and blink with a crude delay.

IMPORTANT:
- First emit the FACTS MIRROR block, then the files with exact separators:
  ===== FILE: <path> =====
- The first file block MUST start with:
  ===== FILE: {target_files[0]} =====
- If any constant is missing from FACTS CANON, emit TODOs in the FACTS MIRROR and STOP (do not emit files).
"""


from enum import Enum

class Model(Enum):
    HAIKU_3_0 = "haiku3.0"
    HAIKU_4_5 = "haiku4.5"
    SONNET_3_5 = "sonnet3.5"
    SONNET_4_5 = "sonnet4.5"

    def get_model_id(self):
        model_ids = {
            "haiku3.0": "us.anthropic.claude-3-haiku-20240307-v1:0",
            "sonnet3.5": "us.anthropic.claude-3-5-sonnet-20240620-v1:0",
            "haiku4.5": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
            "sonnet4.5": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        }

        return model_ids[self.value]


from typing import TypedDict, Literal


class Message(TypedDict):
    role: Literal["user", "assistant"]
    content: str


async def invoke_model(model: Model, max_tokens: int, messages: list[Message]) -> str:
    body = {
        "max_tokens": max_tokens,
        "anthropic_version": "bedrock-2023-05-31",
        "messages": messages,
    }

    response = client.invoke_model(modelId=model.get_model_id(), body=json.dumps(body))
    return response


from enum import Enum


# class EmbeddingsModel(Enum):
#     TITAN_V2 = "titan-v2"

#     def get_client(self) -> BedrockEmbeddings:
#         model_clients = {"titan-v2": embeddings_titan_v2}
#         return model_clients[self.value]


# def get_embeddings_client(model: EmbeddingsModel) -> BedrockEmbeddings:
#     return model.get_client()
