import argparse
import asyncio
import inspect
import os
from pathlib import Path

from config import YAMLS_DIR, TARGET_FILES, FACTS_CANON, PATTERN_SNIPS

from modules.file_io import split_and_write_files, write_makefile, write_manifest, write_doxyfile, run_doxygen
from modules.utils import _read, extract_text_from_bedrock_response, _now_tag
from modules.prompt import (
    invoke_model,
    Model,
    build_system_prompt,
    build_user_prompt,            # peripheral driver prompt
    build_system_init_prompt,     # system.c/system_init
    build_linker_prompt,          # linker script
    build_entry_prompt,           # entry.c
    build_start_asm_prompt,       # start.s
)
from modules.user import prompt_user_for_peripherals

from modules.yaml_utils import (
    load_soc_yaml,
    load_regs_yaml,
    load_memmap_yaml,
    build_system_slices_for_prompt,
    build_peripheral_slices_for_prompt,
    build_memmap_slice_for_prompt,
)


def _invoke_with_prompts(
    tag: str,
    system_prompt: str,
    user_prompt: str,
    model_enum: Model,
    max_tokens: int,
    artifacts_dir: Path,
):
    """
    Helper to:
      - save system/user prompts for this call,
      - invoke the model,
      - save raw text,
      - return the extracted text (or "" on empty).
    """
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Save prompts for reproducibility (tagged by phase)
    (artifacts_dir / f"{tag}_system_prompt.txt").write_text(
        system_prompt, encoding="utf-8"
    )
    (artifacts_dir / f"{tag}_user_prompt.txt").write_text(
        user_prompt, encoding="utf-8"
    )

    messages = [
        {
            "role": "user",
            "content": f"[SYSTEM]\n{system_prompt}\n\n[USER]\n{user_prompt}",
        }
    ]

    print(f"[info] Invoking {model_enum.name} for {tag} …")
    resp = invoke_model(model_enum, max_tokens, messages)

    # Handle async/sync return
    if inspect.isawaitable(resp):
        resp = asyncio.run(resp)

    text = extract_text_from_bedrock_response(resp)
    ts = _now_tag()

    if not text.strip():
        (artifacts_dir / f"{tag}_empty_text_{ts}.txt").write_text(
            str(resp), encoding="utf-8"
        )
        print(f"[warn] Empty model text for {tag}; raw response saved.")
        return ""

    (artifacts_dir / f"{tag}_llm_text_{ts}.txt").write_text(text, encoding="utf-8")
    return text


# ---------------- Main ----------------
def main():
    parser = argparse.ArgumentParser(
        description="YAML-in → Claude → BSP-out (multi-peripheral BSP)"
    )
    parser.add_argument(
        "--out",
        default=".",
        help="Base output directory. A subdir output_<timestamp> will be created.",
    )
    parser.add_argument(
        "--model",
        default="sonnet4.5",
        choices=["haiku3.0", "haiku4.5", "sonnet3.5", "sonnet4.5"],
    )
    parser.add_argument(
        "--yamlpath",
        default="yaml_in",
        help="Origin directory for YAML files used in code generation",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=12000,
    )
    parser.add_argument(
        "--targets",
        nargs="+",
        default=["all"],
        choices=["all", "startup", "entry", "system", "linker", "peripherals"],
        help=(
            "Which components to generate. "
            "Choices: all, startup (start.s), entry (entry.c), "
            "system (system.c/h), linker (linker.cmd), peripherals (drivers). "
            "Default: all."
        ),
    )
    args = parser.parse_args()

    targets = set(args.targets)
    generate_start = "all" in targets or "startup" in targets
    generate_entry = "all" in targets or "entry" in targets
    generate_system = "all" in targets or "system" in targets
    generate_linker = "all" in targets or "linker" in targets
    generate_peripherals = "all" in targets or "peripherals" in targets

    # Root for this run: output_<timestamp>
    base_out = Path(args.out)
    run_tag = _now_tag()
    out_dir = base_out / f"output_{run_tag}"
    out_dir.mkdir(parents=True, exist_ok=True)

    artifacts = out_dir / "_artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    # Load structured YAMLs for slicing
    soc_path = Path(args.yamlpath) / "soc.yaml"
    regs_path = Path(args.yamlpath) / "regs.yaml"
    memmap_path = Path(args.yamlpath) / "memmap.yaml"

    soc_data = load_soc_yaml(soc_path)
    regs_data = load_regs_yaml(regs_path)
    memmap_data = load_memmap_yaml(memmap_path)

    # Let the user choose which peripherals to generate drivers for (if requested)
    if generate_peripherals:
        chosen_peripherals = prompt_user_for_peripherals(soc_data)
        if not chosen_peripherals:
            print(
                "[info] No peripherals selected (besides SYSTEM/PCR). "
                "Continuing without peripheral drivers."
            )
    else:
        chosen_peripherals = []
        print("[info] Peripheral driver generation disabled by --targets.")

    # Build the global system prompt once (FACTS_POLICY, file separators, etc.)
    system_prompt = build_system_prompt()

    # Map CLI string to your Model enum
    model_enum = {
        "haiku3.0": Model.HAIKU_3_0,
        "haiku4.5": Model.HAIKU_4_5,
        "sonnet3.5": Model.SONNET_3_5,
        "sonnet4.5": Model.SONNET_4_5,
    }[args.model]

    all_written: list[Path] = []

    # 1) start.s (assembly vector / SP setup)
    if generate_start:
        start_user_prompt = build_start_asm_prompt()
        start_text = _invoke_with_prompts(
            tag="start_asm",
            system_prompt=system_prompt,
            user_prompt=start_user_prompt,
            model_enum=model_enum,
            max_tokens=args.max_tokens,
            artifacts_dir=artifacts,
        )
        if start_text:
            all_written += split_and_write_files(start_text, out_dir)
    else:
        print("[info] Skipping startup (start.s) generation due to --targets.")

    # 2) entry.c (Reset_Handler_C → system_init() → main())
    if generate_entry:
        entry_user_prompt = build_entry_prompt()
        entry_text = _invoke_with_prompts(
            tag="entry_c",
            system_prompt=system_prompt,
            user_prompt=entry_user_prompt,
            model_enum=model_enum,
            max_tokens=args.max_tokens,
            artifacts_dir=artifacts,
        )
        if entry_text:
            all_written += split_and_write_files(entry_text, out_dir)
    else:
        print("[info] Skipping entry.c generation due to --targets.")

    # 3) system.c / system.h (system_init using SYSTEM + PCR slices)
    if generate_system:
        system_soc_slice, system_regs_slice = build_system_slices_for_prompt(
            soc_data, regs_data
        )
        system_init_user_prompt = build_system_init_prompt(
            system_soc_slice, system_regs_slice
        )
        system_init_text = _invoke_with_prompts(
            tag="system_init",
            system_prompt=system_prompt,
            user_prompt=system_init_user_prompt,
            model_enum=model_enum,
            max_tokens=args.max_tokens,
            artifacts_dir=artifacts,
        )
        if system_init_text:
            all_written += split_and_write_files(system_init_text, out_dir)
    else:
        print("[info] Skipping system.c/system.h generation due to --targets.")

    # 4) Linker script (FLASH/RAM from MEMMAP slice)
    if generate_linker:
        memmap_slice_str = build_memmap_slice_for_prompt(memmap_data)
        linker_user_prompt = build_linker_prompt(memmap_slice_str)
        linker_text = _invoke_with_prompts(
            tag="linker",
            system_prompt=system_prompt,
            user_prompt=linker_user_prompt,
            model_enum=model_enum,
            max_tokens=args.max_tokens,
            artifacts_dir=artifacts,
        )
        if linker_text:
            all_written += split_and_write_files(linker_text, out_dir)
    else:
        print("[info] Skipping linker.cmd generation due to --targets.")

    # 5) Per-peripheral drivers (one call per selected peripheral)
    if generate_peripherals and chosen_peripherals:
        for periph in chosen_peripherals:
            name = str(periph.get("name", "UNKNOWN"))
            tag = f"periph_{name.lower()}"

            # Build YAML slices for THIS peripheral (soc + regs)
            soc_slice_str, regs_slice_str = build_peripheral_slices_for_prompt(
                soc_data, regs_data, name
            )

            # Reuse build_user_prompt for per-peripheral driver generation
            periph_user_prompt = build_user_prompt(soc_slice_str, regs_slice_str)

            text = _invoke_with_prompts(
                tag=tag,
                system_prompt=system_prompt,
                user_prompt=periph_user_prompt,
                model_enum=model_enum,
                max_tokens=args.max_tokens,
                artifacts_dir=artifacts,
            )
            if text:
                all_written += split_and_write_files(text, out_dir)

    if all_written:
        print("\n[ok] Generated files in", out_dir)
        for p in all_written:
            try:
                print("  -", p.relative_to(out_dir))
            except ValueError:
                print("  -", p)
    else:
        print("[warn] No files split. See _artifacts/ for raw outputs and preamble.")


    print(f"\n [info] Creating documentation with Doxygen")
    docs_dir = out_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    try:
        doxy_path = write_doxyfile(docs_dir)
        run_doxygen(out_dir, doxy_path)
    except Exception as e:
        print(f"[error] Doxygen generation failed: {e}")

    else:
        print(f"[ok] Documentation generated in {docs_dir / 'html'}.")

        if (docs_dir / "html" / "index.html").exists():
            print(f"[info] Docs index located at {os.path.abspath(docs_dir / 'html' / 'index.html')}.")



if __name__ == "__main__":
    main()
    
