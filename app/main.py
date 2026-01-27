import argparse
import asyncio
import inspect
import os
from pathlib import Path

from .config import YAMLS_DIR, TARGET_FILES, FACTS_CANON, PATTERN_SNIPS

from .modules.file_io import split_and_write_files, write_makefile, write_manifest, write_doxyfile, run_doxygen
from .modules.utils import _read, extract_text_from_bedrock_response, _now_tag
from .modules.prompt import (
    build_clock_prompt,
    invoke_model,
    Model,
    build_system_prompt,
    build_user_prompt,            # peripheral driver prompt
    build_system_init_prompt,     # system.c/system_init
    build_linker_prompt,          # linker script
    build_entry_prompt,           # entry.c
    build_start_asm_prompt,       # start.s
    build_vim_prompt,             # VIM driver
    _progress,                    # global progress tracker
)
from .modules.user import prompt_user_for_peripherals

from .modules.yaml_utils import (
    dump_yaml_str,
    load_bus_yaml,
    load_soc_yaml,
    load_regs_yaml,
    load_memmap_yaml,
    load_irq_yaml,
    build_system_slices_for_prompt,
    build_peripheral_slices_for_prompt,
    build_memmap_slice_for_prompt,
)


async def _invoke_and_write(
    tag: str,
    system_prompt: str,
    user_prompt: str,
    model_enum: Model,
    max_tokens: int,
    artifacts_dir: Path,
    out_dir: Path,
):
    """
    Helper to:
      - save system/user prompts for this call,
      - invoke the model,
      - save raw text,
      - split and write files immediately upon completion.
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
    
    # invoke_model is now truly async
    resp = await invoke_model(model_enum, max_tokens, messages)

    text = extract_text_from_bedrock_response(resp)
    ts = _now_tag()

    if not text.strip():
        (artifacts_dir / f"{tag}_empty_text_{ts}.txt").write_text(
            str(resp), encoding="utf-8"
        )
        print(f"[warn] Empty model text for {tag}; raw response saved.")
        return []

    (artifacts_dir / f"{tag}_llm_text_{ts}.txt").write_text(text, encoding="utf-8")
    
    # Write files immediately
    written_files = split_and_write_files(text, out_dir)
    for file in written_files:
        try:
            relative_path = file.relative_to(out_dir)
        except ValueError:
            relative_path = file
        print(f"[ok] {tag}: {relative_path}")
    
    return written_files


async def _generate_startup(
    system_prompt: str,
    model_enum: Model,
    max_tokens: int,
    artifacts_dir: Path,
    out_dir: Path,
    start_user_prompt: str,
):
    """Generate start.s (assembly vector / SP setup)"""
    return await _invoke_and_write(
        tag="start_asm",
        system_prompt=system_prompt,
        user_prompt=start_user_prompt,
        model_enum=model_enum,
        max_tokens=max_tokens,
        artifacts_dir=artifacts_dir,
        out_dir=out_dir,
    )


async def _generate_entry(
    system_prompt: str,
    model_enum: Model,
    max_tokens: int,
    artifacts_dir: Path,
    out_dir: Path,
    entry_user_prompt: str,
):
    """Generate entry.c (Reset_Handler_C → system_init() → main())"""
    return await _invoke_and_write(
        tag="entry_c",
        system_prompt=system_prompt,
        user_prompt=entry_user_prompt,
        model_enum=model_enum,
        max_tokens=max_tokens,
        artifacts_dir=artifacts_dir,
        out_dir=out_dir,
    )


async def _generate_clock(
    system_prompt: str,
    model_enum: Model,
    max_tokens: int,
    artifacts_dir: Path,
    out_dir: Path,
    clock_user_prompt: str,
):
    """Generate clock setup code"""
    return await _invoke_and_write(
        tag="clock_setup",
        system_prompt=system_prompt,
        user_prompt=clock_user_prompt,
        model_enum=model_enum,
        max_tokens=max_tokens,
        artifacts_dir=artifacts_dir,
        out_dir=out_dir,
    )


async def _generate_system(
    system_prompt: str,
    model_enum: Model,
    max_tokens: int,
    artifacts_dir: Path,
    out_dir: Path,
    system_init_user_prompt: str,
):
    """Generate system.c / system.h"""
    return await _invoke_and_write(
        tag="system_init",
        system_prompt=system_prompt,
        user_prompt=system_init_user_prompt,
        model_enum=model_enum,
        max_tokens=max_tokens,
        artifacts_dir=artifacts_dir,
        out_dir=out_dir,
    )


async def _generate_linker(
    system_prompt: str,
    model_enum: Model,
    max_tokens: int,
    artifacts_dir: Path,
    out_dir: Path,
    linker_user_prompt: str,
):
    """Generate linker script"""
    return await _invoke_and_write(
        tag="linker",
        system_prompt=system_prompt,
        user_prompt=linker_user_prompt,
        model_enum=model_enum,
        max_tokens=max_tokens,
        artifacts_dir=artifacts_dir,
        out_dir=out_dir,
    )


async def _generate_vim(
    system_prompt: str,
    model_enum: Model,
    max_tokens: int,
    artifacts_dir: Path,
    out_dir: Path,
    vim_user_prompt: str,
):
    """Generate VIM driver"""
    return await _invoke_and_write(
        tag="vim_driver",
        system_prompt=system_prompt,
        user_prompt=vim_user_prompt,
        model_enum=model_enum,
        max_tokens=max_tokens,
        artifacts_dir=artifacts_dir,
        out_dir=out_dir,
    )


async def _generate_peripheral(
    periph: dict,
    system_prompt: str,
    model_enum: Model,
    max_tokens: int,
    artifacts_dir: Path,
    out_dir: Path,
    periph_user_prompt: str,
):
    """Generate driver for a single peripheral"""
    name = str(periph.get("name", "UNKNOWN"))
    tag = f"periph_{name.lower()}"
    
    return await _invoke_and_write(
        tag=tag,
        system_prompt=system_prompt,
        user_prompt=periph_user_prompt,
        model_enum=model_enum,
        max_tokens=max_tokens,
        artifacts_dir=artifacts_dir,
        out_dir=out_dir,
    )


# ---------------- Main ----------------
async def main():
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
        default=str(YAMLS_DIR),
        help="Origin directory for YAML files used in code generation",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=20000,
    )
    parser.add_argument(
        "--targets",
        nargs="+",
        default=["all"],
        choices=["all", "startup", "entry", "system", "clock", "linker", "vim", "peripherals"],
        help=(
            "Which components to generate. "
            "Choices: all, startup (start.s), entry (entry.c), "
            "system (system.c/h), linker (linker.cmd), vim (VIM driver), peripherals (drivers). "
            "Default: all."
        ),
    )
    args = parser.parse_args()

    # Parse target flags
    targets = set(args.targets)
    generate_start = "all" in targets or "startup" in targets
    generate_entry = "all" in targets or "entry" in targets
    generate_system = "all" in targets or "system" in targets
    generate_linker = "all" in targets or "linker" in targets
    generate_vim = "all" in targets or "vim" in targets
    generate_clock = "all" in targets or "clock" in targets
    generate_peripherals = "all" in targets or "peripherals" in targets

    # Setup output directories
    base_out = Path(args.out)
    run_tag = _now_tag()
    out_dir = base_out / f"output_{run_tag}"
    out_dir.mkdir(parents=True, exist_ok=True)

    artifacts = out_dir / "_artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    # Load YAMLs
    soc_data = load_soc_yaml(Path(args.yamlpath) / "soc.yaml")
    regs_data = load_regs_yaml(Path(args.yamlpath) / "regs.yaml")
    irq_data = load_irq_yaml(Path(args.yamlpath) / "irq.yaml")
    memmap_data = load_memmap_yaml(Path(args.yamlpath) / "memmap.yaml")
    bus_data = load_bus_yaml(Path(args.yamlpath) / "bus.yaml")

    # Get user peripheral selections
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

    # Setup model and system prompt
    system_prompt = build_system_prompt()
    model_enum = {
        "haiku3.0": Model.HAIKU_3_0,
        "haiku4.5": Model.HAIKU_4_5,
        "sonnet3.5": Model.SONNET_3_5,
        "sonnet4.5": Model.SONNET_4_5,
    }[args.model]

    # Prepare prompts upfront (before launching concurrent tasks)
    print("[info] Preparing prompts...")
    
    start_user_prompt = None
    if generate_start:
        start_user_prompt = build_start_asm_prompt()

    entry_user_prompt = None
    if generate_entry:
        entry_user_prompt = build_entry_prompt()

    clock_user_prompt = None
    if generate_clock:
        system_soc_slice, system_regs_slice = build_system_slices_for_prompt(
            soc_data, regs_data
        )
        clock_user_prompt = build_clock_prompt(
            soc_yaml=system_soc_slice,
            regs_yaml=system_regs_slice,
            bus_yaml=bus_data
        )

    system_init_user_prompt = None
    if generate_system:
        system_soc_slice, system_regs_slice = build_system_slices_for_prompt(
            soc_data, regs_data
        )
        system_init_user_prompt = build_system_init_prompt(
            system_soc_slice, system_regs_slice
        )

    linker_user_prompt = None
    if generate_linker:
        memmap_slice_str = build_memmap_slice_for_prompt(memmap_data)
        linker_user_prompt = build_linker_prompt(memmap_slice_str)

    vim_user_prompt = None
    if generate_vim:
        vim_soc_slice, vim_regs_slice, _ = build_peripheral_slices_for_prompt(
            soc_data, regs_data, irq_data, "VIM"
        )
        vim_user_prompt = build_vim_prompt(
            vim_soc_slice, vim_regs_slice, dump_yaml_str(irq_data)
        )

    # Prepare peripheral prompts
    peripheral_prompts = {}
    if generate_peripherals and chosen_peripherals:
        for periph in chosen_peripherals:
            name = str(periph.get("name", "UNKNOWN")).upper()
            # Skip VIM as it's generated separately above
            if name == "VIM":
                print(f"[info] Skipping {name}; already generated as system component.")
                continue

            soc_slice_str, regs_slice_str, irq_slice_str = build_peripheral_slices_for_prompt(
                soc_data, regs_data, irq_data, name
            )
            periph_user_prompt = build_user_prompt(
                soc_slice_str, regs_slice_str, irq_slice_str
            )
            peripheral_prompts[name] = (periph, periph_user_prompt)

    # Build generation tasks (now just async wrappers around pre-built prompts)
    generation_tasks = []

    if generate_start:
        generation_tasks.append(
            _generate_startup(
                system_prompt, model_enum, args.max_tokens, artifacts, out_dir,
                start_user_prompt
            )
        )
        print("[debug] Added task: start_asm")
    else:
        print("[info] Skipping startup (start.s) generation due to --targets.")

    if generate_entry:
        generation_tasks.append(
            _generate_entry(
                system_prompt, model_enum, args.max_tokens, artifacts, out_dir,
                entry_user_prompt
            )
        )
        print("[debug] Added task: entry_c")
    else:
        print("[info] Skipping entry.c generation due to --targets.")

    if generate_clock:
        generation_tasks.append(
            _generate_clock(
                system_prompt,
                model_enum,
                args.max_tokens,
                artifacts,
                out_dir,
                clock_user_prompt,
            )
        )
        print("[debug] Added task: clock_setup")
    else:
        print("[info] Skipping clock setup generation due to --targets.")

    if generate_system:
        generation_tasks.append(
            _generate_system(
                system_prompt,
                model_enum,
                args.max_tokens,
                artifacts,
                out_dir,
                system_init_user_prompt,
            )
        )
        print("[debug] Added task: system_init")
    else:
        print("[info] Skipping system.c/system.h generation due to --targets.")

    if generate_linker:
        generation_tasks.append(
            _generate_linker(
                system_prompt,
                model_enum,
                args.max_tokens,
                artifacts,
                out_dir,
                linker_user_prompt,
            )
        )
        print("[debug] Added task: linker")
    else:
        print("[info] Skipping linker.cmd generation due to --targets.")

    if generate_vim:
        generation_tasks.append(
            _generate_vim(
                system_prompt,
                model_enum,
                args.max_tokens,
                artifacts,
                out_dir,
                vim_user_prompt,
            )
        )
        print("[debug] Added task: vim_driver")

    if peripheral_prompts:
        for name, (periph, periph_user_prompt) in peripheral_prompts.items():
            generation_tasks.append(
                _generate_peripheral(
                    periph,
                    system_prompt,
                    model_enum,
                    args.max_tokens,
                    artifacts,
                    out_dir,
                    periph_user_prompt,
                )
            )
            print(f"[debug] Added task: periph_{name.lower()}")

    # Run all generation tasks concurrently
    if generation_tasks:
        print(f"[info] Total tasks to run: {len(generation_tasks)}")
        print("[info] Starting concurrent generation of all components...\n")
        
        # Initialize progress tracker
        _progress.set_total(len(generation_tasks))
        _progress.stop_event.clear()
        
        # Start the global progress spinner
        spinner_thread = _progress.start_spinner()
        
        try:
            await asyncio.gather(*generation_tasks)
        finally:
            # Stop progress spinner
            _progress.stop_spinner()
            spinner_thread.join(timeout=1)
            print()  # Newline after progress bar
    else:
        print("[warn] No generation tasks created.")

    # Generate documentation
    await _generate_documentation(out_dir)


async def _generate_documentation(out_dir: Path):
    """Generate Doxygen documentation (optional, skipped if doxygen not available)"""
    print(f"\n[info] Creating documentation with Doxygen")
    docs_dir = out_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        doxy_path = write_doxyfile(docs_dir)
        run_doxygen(out_dir, doxy_path)
        print(f"[ok] Documentation generated in {docs_dir / 'html'}.")
        
        if (docs_dir / "html" / "index.html").exists():
            abs_path = os.path.abspath(docs_dir / "html" / "index.html")
            print(f"[info] Docs index located at {abs_path}.")
    except FileNotFoundError as e:
        print(f"[warn] Doxygen not found in system PATH. Install doxygen to generate documentation.")
        print(f"       Details: {e}")
    except Exception as e:
        print(f"[warn] Doxygen generation failed (documentation skipped).")
        print(f"       Details: {e}")


if __name__ == "__main__":
    asyncio.run(main())
