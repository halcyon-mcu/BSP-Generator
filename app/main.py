import argparse
import asyncio
import inspect
import json
import os
import re
from pathlib import Path
from datetime import datetime
from typing import List

from prompt import invoke_model, Model

# ---------------- Config ----------------
YAMLS_DIR = Path("app/yamls_in")
TARGET_FILES = [
    "drivers/gpio.h",
    "drivers/gpio.c",
    "soc/rm46_gio_regs.h",
    "board/pinmux_init.c",
    "examples/blinky/main.c",
]
FILE_SPLIT_RE = re.compile(r"^===== FILE: (.+) =====\s*$", re.M)

# ---- your existing pieces are assumed available in scope:
# - Model Enum with get_model_id()
# - invoke_model(model: Model, max_tokens: int, messages: list[Message]) -> (bedrock resp OR text)

# ---------------- Utils ----------------
def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")

def extract_text_from_bedrock_response(resp) -> str:
    """
    Works whether invoke_model returns the raw Bedrock response (with .body)
    or already-decoded JSON, or just a text string.
    """
    # Already plain text?
    if isinstance(resp, str):
        return resp

    # boto3 response?
    try:
        if hasattr(resp, "get"):
            body = resp.get("body")
            payload = json.loads(body.read()) if hasattr(body, "read") else json.loads(body)
        else:
            payload = resp
    except Exception:
        # last resort
        return str(resp)

    parts = []
    for item in payload.get("content", []):
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(item.get("text", ""))
    text = "\n".join(parts).strip()

    if not text and "output_text" in payload:
        text = str(payload["output_text"]).strip()

    return text

import os
from pathlib import Path, PurePosixPath

FILE_SPLIT_RE = re.compile(r"^===== FILE: (.+) =====\s*$", re.M)

def _safe_relpath(s: str) -> str:
    """
    Normalize a model-provided path:
    - forbid absolute paths
    - collapse backslashes to forward slashes
    - forbid parent directory traversal
    """
    p = str(s).strip()
    # Normalize slashes
    p = p.replace("\\", "/")
    # Remove leading './'
    if p.startswith("./"):
        p = p[2:]
    # Forbid absolute or drive-qualified paths
    if os.path.isabs(p):
        raise ValueError(f"Refusing absolute path from model: {s!r}")
    # Forbid parent traversal
    parts = PurePosixPath(p).parts
    if any(seg == ".." for seg in parts):
        raise ValueError(f"Refusing path with '..' from model: {s!r}")
    return p

def split_and_write_files(raw_text: str, out_dir: Path) -> list[Path]:
    out_dir = out_dir.resolve()  # <-- key fix
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts = out_dir / "_artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    ts = _now_tag()
    (artifacts / f"llm_raw_{ts}.txt").write_text(raw_text, encoding="utf-8")

    matches = list(FILE_SPLIT_RE.finditer(raw_text))
    if not matches:
        print("[warn] No file separators found. Check _artifacts/ for raw output.")
        return []

    written: list[Path] = []

    # Save any preamble before the first separator
    first = matches[0]
    if first.start() > 0:
        preamble = raw_text[: first.start()].strip()
        if preamble:
            (artifacts / f"llm_preamble_{ts}.txt").write_text(preamble, encoding="utf-8")
            print("[warn] Preamble saved to _artifacts/llm_preamble_*.txt")

    for i, m in enumerate(matches):
        raw_rel = m.group(1).strip()
        rel_norm = _safe_relpath(raw_rel)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
        content = raw_text[start:end].lstrip("\n")

        target = (out_dir / rel_norm).resolve()
        # Ensure the resolved path is still under out_dir (defense in depth)
        try:
            target.relative_to(out_dir)
        except ValueError:
            raise RuntimeError(f"Refusing to write outside out_dir: {target}")

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(target)

        # Print a friendly relative path (robust across Windows)
        try:
            print("[ok] Wrote", target.relative_to(out_dir))
        except ValueError:
            # Fallback if something odd happens
            print("[ok] Wrote", os.path.relpath(str(target), str(out_dir)))

# ---------------- Prompt builders ----------------
def build_system_prompt() -> str:
    return (
        "You are generating minimal, portable C11 BSP files for TI RM46 (Cortex-R4) to blink an LED via GIO.\n"
        "\n"
        "HARD OUTPUT CONTRACT:\n"
        "- Output ONLY these files, each delimited by:  ===== FILE: <path> =====\n"
        f"- FIRST line must be exactly: ===== FILE: {TARGET_FILES[0]} =====\n"
        "- No prose before the first separator. No explanations anywhere.\n"
        "\n"
        "CODING RULES:\n"
        "- Public headers MUST NOT include vendor headers or vendor-specific types.\n"
        "- Use ONLY facts from the provided YAMLs for base addresses and offsets.\n"
        "- Prefer GIO DSET/DCLR over read-modify-write of DOUT for write/toggle.\n"
        "- Add a short provenance comment above each register access:  // [prov] regs.yaml:GIO.<REGISTER>\n"
        "- C standard = C11. Target = CCS for Cortex-R4 (RM46).\n"
        "\n"
        "REUSE POLICY (for this POC):\n"
        "- Reuse HALCoGen startup/vector/linker/system/pinmux; do NOT include vendor headers in public APIs.\n"
    )

def build_user_prompt(yamls: dict, gpio_api_header: str) -> str:
    # Assemble YAML sections
    sections = []
    for name in ["soc.yaml", "regs.yaml", "pinmux.yaml", "memmap.yaml", "irq.yaml", "bus.yaml"]:
        if name in yamls:
            sections.append(f"--- {name} ---\n{yamls[name]}")

    files_list = "\n".join(f"- {p}" for p in TARGET_FILES)

    return (
        "Here are the inputs:\n\n"
        + "\n\n".join(sections)
        + "\n\n--- gpio_api_header.txt ---\n"
        + gpio_api_header
        + "\n\n"
        "TASK:\n"
        "Generate EXACTLY the following files, in this order, using the API above and the GIO facts from regs.yaml:\n"
        f"{files_list}\n\n"
        "Guidance per file:\n"
        "1) drivers/gpio.h\n"
        "   - EXACTLY the API provided in gpio_api_header.txt.\n"
        "2) drivers/gpio.c\n"
        "   - Implement the API using RM46 GIO registers from regs.yaml (DIR_A/B, DSET_A/B, DCLR_A/B, DIN_A/B).\n"
        "   - Provide a tiny helper for base+offset access, and provenance comments before each access.\n"
        "   - No vendor includes. Include a private header you will create: soc/rm46_gio_regs.h\n"
        "3) soc/rm46_gio_regs.h\n"
        "   - #define GIO_BASE and the offsets for A/B DIR/DIN/DOUT/DSET/DCLR using values from regs.yaml.\n"
        "   - Provide a small macro for register addressing.\n"
        "4) board/pinmux_init.c\n"
        "   - Stub that calls vendor pinmux until we replace it later:\n"
        "     extern void pinMuxInitialize(void);\n"
        "     void pinmux_init_led(void) { pinMuxInitialize(); }\n"
        "5) examples/blinky/main.c\n"
        "   - Use only the public gpio API to configure one LED pin and blink with a crude delay.\n"
        "\n"
        "IMPORTANT:\n"
        f"- Emit ONLY these files and use the separators exactly:  ===== FILE: <path> =====\n"
        f"- The first line MUST be:  ===== FILE: {TARGET_FILES[0]} =====\n"
    )

# ---------------- Main ----------------
def main():
    parser = argparse.ArgumentParser(description="YAML-in → Claude → BSP-out (GPIO POC)")
    parser.add_argument("--out", default=".", help="Output directory for generated files.")
    parser.add_argument("--model", default="sonnet4.5",
                        choices=["haiku3.0", "haiku4.5", "sonnet3.5", "sonnet4.5"])
    parser.add_argument("--max-tokens", type=int, default=6000)
    parser.add_argument("--gpio-api", default=None,
                        help="Path to a file containing the golden public GPIO API header. If omitted, a default is used.")
    args = parser.parse_args()

    out_dir = Path(args.out)
    artifacts = out_dir / "_artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    # Load YAMLs
    yamls = {}
    for name in ["soc.yaml", "regs.yaml", "pinmux.yaml", "memmap.yaml", "irq.yaml", "bus.yaml"]:
        p = YAMLS_DIR / name
        if p.exists():
            yamls[name] = _read(p)

    # Golden public API header (you can keep this in repo)
    default_api = (
        "#pragma once\n"
        "#include <stdint.h>\n"
        "#include <stdbool.h>\n\n"
        "typedef enum { BSP_GPIO_OK = 0, BSP_GPIO_EINVAL = -22 } bsp_gpio_status_t;\n"
        "typedef struct { uint8_t port; uint8_t pin; bool output; } bsp_gpio_cfg_t;\n\n"
        "bsp_gpio_status_t bsp_gpio_port_init(uint8_t port);\n"
        "bsp_gpio_status_t bsp_gpio_pin_config(const bsp_gpio_cfg_t* cfg);\n"
        "bsp_gpio_status_t bsp_gpio_write(uint8_t port, uint8_t pin, bool high);\n"
        "bsp_gpio_status_t bsp_gpio_toggle(uint8_t port, uint8_t pin);\n"
    )
    gpio_api_header = _read(Path(args.gpio_api)) if args.gpio_api else default_api

    # Build prompts
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(yamls, gpio_api_header)

    # Save prompts for reproducibility
    (artifacts / "system_prompt.txt").write_text(system_prompt, encoding="utf-8")
    (artifacts / "user_prompt.txt").write_text(user_prompt, encoding="utf-8")

    # Messages for your existing invoke_model
    messages = [{"role": "user", "content": f"[SYSTEM]\n{system_prompt}\n\n[USER]\n{user_prompt}"}]

    # Map CLI string to your Model enum
    from enum import Enum  # noqa

    model_enum = {
        "haiku3.0": Model.HAIKU_3_0,
        "haiku4.5": Model.HAIKU_4_5,
        "sonnet3.5": Model.SONNET_3_5,
        "sonnet4.5": Model.SONNET_4_5,
    }[args.model]

    print(f"[info] Invoking {model_enum.name} …")
    resp = invoke_model(model_enum, args.max_tokens, messages)

    # Handle async/sync return
    if inspect.isawaitable(resp):
        resp = asyncio.run(resp)

    text = extract_text_from_bedrock_response(resp)
    if not text.strip():
        (artifacts / f"empty_text_{_now_tag()}.txt").write_text(str(resp), encoding="utf-8")
        print("[warn] Empty model text; raw response saved.")
        return

    (artifacts / f"llm_text_{_now_tag()}.txt").write_text(text, encoding="utf-8")
    print("Writing files…")
    written = split_and_write_files(text, out_dir)

    if written:
        print("[ok] Generated files:")
        for p in written:
            print("  -", p.relative_to(out_dir))
    else:
        print("[warn] No files split. See _artifacts/ for raw outputs and preamble.")

if __name__ == "__main__":
    main()
