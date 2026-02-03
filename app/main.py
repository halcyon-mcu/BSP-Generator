import argparse
import asyncio
import inspect
import os
from pathlib import Path

from config import YAMLS_DIR, TARGET_FILES, FACTS_CANON, PATTERN_SNIPS

from modules.file_io import split_and_write_files, write_makefile, write_manifest, write_doxyfile, run_doxygen
from modules.utils import _read, extract_text_from_bedrock_response, _now_tag
from modules.prompt import (
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
from modules.user import prompt_user_for_peripherals

from modules.yaml_utils import (
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
    soc_data: dict = None,
    regs_data: dict = None,
):
    """
    Helper to:
      - save system/user prompts for this call,
      - invoke the model,
      - save raw text,
      - split and write files immediately upon completion,
      - validate FACTS MIRROR (if soc_data and regs_data provided).
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

    # Write files immediately and extract preamble
    written_files, preamble = split_and_write_files(text, out_dir)
    for file in written_files:
        try:
            relative_path = file.relative_to(out_dir)
        except ValueError:
            relative_path = file
        print(f"[ok] {tag}: {relative_path}")

    # Validate if YAML data provided
    if soc_data is not None and regs_data is not None and written_files:
        from modules.validation_engine import validate_generation_output
        try:
            validation_result = validate_generation_output(
                tag=tag,
                preamble=preamble,
                written_files=written_files,
                soc_data=soc_data,
                regs_data=regs_data
            )

            if not validation_result.is_valid:
                print(f"[warn] Validation warnings for {tag}:")
                for error in validation_result.errors[:3]:  # Show first 3
                    print(f"  - {error}")
            elif validation_result.warnings:
                print(f"[info] Validation passed with {len(validation_result.warnings)} warnings")

        except Exception as e:
            print(f"[warn] Validation error for {tag}: {e}")

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
        default="yaml_in",
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

    # Setup model and system prompt
    system_prompt = build_system_prompt()
    model_enum = {
        "haiku3.0": Model.HAIKU_3_0,
        "haiku4.5": Model.HAIKU_4_5,
        "sonnet3.5": Model.SONNET_3_5,
        "sonnet4.5": Model.SONNET_4_5,
    }[args.model]

    # --- PASS 1: Architecture Discovery ---
    from modules.discovery import run_discovery_pass
    from modules.implementation import run_implementation_pass
    import sys

    print("\n[info] Starting Pass 1: Architecture Discovery...")
    bsp_manifest = await run_discovery_pass(
        soc_data,
        regs_data,
        model_enum,
        out_dir,
        max_tokens=args.max_tokens
    )
    print("\n[info] Pass 1 Complete.")

    # --- PASS 2: Implementation ---
    
    # Select peripherals for implementation
    pass2_allowed_modules = []
    if generate_peripherals:
        print("\n[user] Select Peripherals for Driver Implementation:")
        chosen_peripherals = prompt_user_for_peripherals(soc_data)
        if chosen_peripherals:
            pass2_allowed_modules = [p.get("name") for p in chosen_peripherals]
        else:
            print("[info] No peripherals selected.")
    else:
        print("[info] Skipping peripheral driver selection due to --targets flag.")

    if pass2_allowed_modules:
        print(f"\n[info] Starting Pass 2: Implementation for {len(pass2_allowed_modules)} modules...")
        await run_implementation_pass(
            bsp_manifest,
            soc_data,
            bus_data,
            model_enum,
            out_dir,
            max_tokens=args.max_tokens,
            allowed_modules=pass2_allowed_modules
        )
        print("\n[info] Pass 2 Complete.")
    else:
        print("\n[info] Skipping Pass 2 (No modules selected).")

    # --- DEPENDENCY RESOLUTION & INIT ORDERING ---
    print("\n[info] Building dependency graph and generating initialization sequence...")

    try:
        from modules.dependency_resolver import (
            build_dependency_graph,
            generate_init_order,
            generate_main_c
        )

        # Build dependency graph
        dep_graph = build_dependency_graph(
            bsp_manifest,
            soc_data,
            selected_modules=pass2_allowed_modules
        )

        # Generate initialization order
        init_order = generate_init_order(dep_graph)

        if init_order.is_valid():
            print(f"[ok] Dependency graph valid - {len(init_order.order)} modules")
            print(f"[info] Init order: {' → '.join(init_order.order[:5])}{'...' if len(init_order.order) > 5 else ''}")

            # Generate main.c with correct init sequence
            main_c_path = generate_main_c(init_order, dep_graph, out_dir)
            print(f"[ok] Generated {main_c_path.name} with dependency-ordered init sequence")
        else:
            print(f"[error] Circular dependency detected!")
            print(f"[error] Cycle: {' → '.join(init_order.cycle_nodes)}")
            print(f"[warn] Skipping main.c generation due to dependency cycle")

    except Exception as e:
        print(f"[warn] Dependency resolution error: {e}")
        import traceback
        traceback.print_exc()

    print("\n[info] Proceeding to Platform Generation...")

    # --- PASS 3: Platform & System Files ---
    # Restoring logic for linker, startup, system, etc.
    
    # Re-setup model/prompt if needed (mostly reusing existing)
    system_prompt = build_system_prompt()
    
    print("[info] Preparing Platform prompts...")
    
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
        # Note: We keep VIM here because it often needs IRQ data which generic Pass 2 might not fully utilize yet.
        vim_user_prompt = build_vim_prompt(
            vim_soc_slice, vim_regs_slice, dump_yaml_str(irq_data)
        )

    # Build generation tasks for Platform files
    generation_tasks = []

    if generate_start:
        generation_tasks.append(
            _generate_startup(
                system_prompt, model_enum, args.max_tokens, artifacts, out_dir,
                start_user_prompt
            )
        )
        print("[debug] Added task: start_asm")

    if generate_entry:
        generation_tasks.append(
            _generate_entry(
                system_prompt, model_enum, args.max_tokens, artifacts, out_dir,
                entry_user_prompt
            )
        )
        print("[debug] Added task: entry_c")

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

    if generate_system:
        # This may overlap with system_driver.c from Pass 2, but usually contains sys_init/clocks logic.
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

    # Run platform tasks
    if generation_tasks:
        print(f"[info] Starting Platform Generation ({len(generation_tasks)} tasks)...")
        _progress.set_total(len(generation_tasks))
        _progress.stop_event.clear()
        spinner_thread = _progress.start_spinner()
        try:
            await asyncio.gather(*generation_tasks)
        finally:
            _progress.stop_spinner()
            spinner_thread.join(timeout=1)
            print()
    else:
        print("[info] No additional platform tasks to run.")

    # Generate documentation
    await _generate_documentation(out_dir)

    # --- FINAL VALIDATION REPORT ---
    print("\n[info] Generating final validation report...")

    try:
        from modules.validation_report import (
            create_validation_report,
            write_json_report,
            write_markdown_report,
            print_console_summary
        )

        # Create comprehensive report
        # Note: validation_results would need to be collected throughout execution
        # For now, we create a minimal report showing dependency graph status
        from modules.validation_report import ValidationReport, ValidationSummary

        final_report = ValidationReport(
            timestamp=_now_tag(),
            bsp_output_dir=str(out_dir)
        )

        # Add dependency graph info if available
        if 'dep_graph' in locals() and 'init_order' in locals():
            final_report.dependency_graph_info = {
                "total_nodes": len(dep_graph.nodes),
                "has_cycles": init_order.has_cycles,
                "init_order": init_order.order if init_order.is_valid() else [],
                "cycle_nodes": init_order.cycle_nodes if init_order.has_cycles else []
            }

        # Write reports
        json_path = out_dir / "validation_report.json"
        md_path = out_dir / "validation_report.md"

        write_json_report(final_report, json_path)
        write_markdown_report(final_report, md_path)

        print(f"[ok] Validation report: {json_path.name}")
        print(f"[ok] Validation report: {md_path.name}")

        # Print console summary
        print_console_summary(final_report)

    except Exception as e:
        print(f"[warn] Could not generate final validation report: {e}")

    print(f"\n[info] ✓ BSP generation complete!")
    print(f"[info] Output directory: {out_dir}")


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
