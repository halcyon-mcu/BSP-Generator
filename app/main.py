import argparse
import asyncio
import inspect
from pathlib import Path

from config import YAMLS_DIR, TARGET_FILES, FACTS_CANON, PATTERN_SNIPS

from modules.file_io import split_and_write_files
from modules.utils import _read, extract_text_from_bedrock_response, _now_tag

from modules.prompt import invoke_model, Model, build_user_prompt, build_system_prompt

"""
Sample run example:
py -m app/main.py 
"""

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
    system_prompt = build_system_prompt(target_files=TARGET_FILES)
    user_prompt = build_user_prompt(facts_canon=FACTS_CANON,
                                    yamls=yamls,
                                    api_header=gpio_api_header,
                                    target_files=TARGET_FILES,
                                    pattern_snippets=PATTERN_SNIPS,
                                    )

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
