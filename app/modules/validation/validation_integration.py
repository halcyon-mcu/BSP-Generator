#!/usr/bin/env python3
"""
validation_integration.py

High-level functions to integrate validation test generation into the main workflow.

This module provides:
- Functions to read generated BSP files
- Functions to extract relevant YAML slices
- Orchestration to call validation prompts and LLM
- File organization for test artifacts
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import json

from .validation_prompt import (
    build_validation_system_prompt,
    build_validation_user_prompt,
    build_integration_test_prompt,
    build_cross_file_validation_prompt,
)
from .prompt import invoke_model, Model
from .file_io import split_and_write_files
from .utils import extract_text_from_bedrock_response, _now_tag
from .yaml_utils import (
    build_peripheral_slices_for_prompt,
    build_system_slices_for_prompt,
    build_memmap_slice_for_prompt,
)


def read_generated_file(bsp_output_dir: Path, filename: str) -> str:
    """
    Read a generated file from the BSP output directory.

    Args:
        bsp_output_dir: Path to the output_<timestamp> directory
        filename: Name of file to read (e.g., "gio.c", "system.h")

    Returns:
        File contents as string, or empty string if not found

    Raises:
        FileNotFoundError if file does not exist
    """
    file_path = bsp_output_dir / filename
    if not file_path.exists():
        raise FileNotFoundError(f"Generated file not found: {file_path}")
    return file_path.read_text(encoding="utf-8")


def collect_generated_peripherals(bsp_output_dir: Path) -> List[str]:
    """
    Scan the BSP output directory and identify all generated peripheral drivers.

    Returns a list of base names (e.g., ["gio", "uart1", "spi1"]) by finding
    all .h files in the output directory.

    Args:
        bsp_output_dir: Path to output_<timestamp> directory

    Returns:
        List of peripheral base names
    """
    header_files = list(bsp_output_dir.glob("*.h"))
    peripherals = []

    for hfile in header_files:
        # Skip system files (system.h, entry.h, etc.)
        if hfile.name in ["system.h", "entry.h", "linker.h"]:
            continue
        base_name = hfile.stem  # removes .h extension
        peripherals.append(base_name)

    return sorted(peripherals)


def generate_peripheral_validation_test(
    bsp_output_dir: Path,
    periph_name: str,
    soc_yaml_data: Dict[str, Any],
    regs_yaml_data: Dict[str, Any],
    model: Model,
    max_tokens: int,
    output_dir: Optional[Path] = None,
) -> Tuple[bool, Path]:
    """
    Generate validation tests for a single peripheral driver.

    Args:
        bsp_output_dir: Path to generated BSP files
        periph_name: Name of peripheral (e.g., "GIO", "UART1")
        soc_yaml_data: Parsed soc.yaml
        regs_yaml_data: Parsed regs.yaml
        model: Claude model to use
        max_tokens: Max tokens for LLM response
        output_dir: Where to write test file (defaults to bsp_output_dir)

    Returns:
        Tuple of (success: bool, test_file_path: Path)
    """
    if output_dir is None:
        output_dir = bsp_output_dir

    output_dir.mkdir(parents=True, exist_ok=True)

    # Read generated source and header
    periph_lower = periph_name.lower()
    try:
        gen_header = read_generated_file(bsp_output_dir, f"{periph_lower}.h")
        gen_source = read_generated_file(bsp_output_dir, f"{periph_lower}.c")
    except FileNotFoundError as e:
        print(f"[error] Could not read generated files: {e}")
        return (False, output_dir / f"{periph_lower}_test.c")

    # Extract YAML slices
    try:
        soc_slice, init_ops = build_peripheral_slices_for_prompt(
            soc_yaml_data, periph_name
        )
        regs_slice = build_peripheral_slices_for_prompt(regs_yaml_data, periph_name)[0]
    except Exception as e:
        print(f"[error] Failed to extract YAML slices for {periph_name}: {e}")
        return (False, output_dir / f"{periph_lower}_test.c")

    # Build prompts
    system_prompt = build_validation_system_prompt()
    user_prompt = build_validation_user_prompt(
        generated_source=gen_source,
        generated_header=gen_header,
        soc_yaml_slice=soc_slice,
        regs_yaml_slice=regs_slice,
        expected_init_ops=init_ops,
        periph_name=periph_name,
    )

    # Invoke model
    print(f"[info] Generating validation tests for {periph_name}…")
    messages = [
        {
            "role": "user",
            "content": f"[SYSTEM]\n{system_prompt}\n\n[USER]\n{user_prompt}",
        }
    ]

    resp = invoke_model(model, max_tokens, messages)
    text = extract_text_from_bedrock_response(resp)

    if not text.strip():
        print(f"[warn] Empty response from model for {periph_name}")
        return (False, output_dir / f"{periph_lower}_test.c")

    # Save and extract test file
    try:
        written = split_and_write_files(text, output_dir)
        if not written:
            print(f"[warn] No test file generated for {periph_name}")
            return (False, output_dir / f"{periph_lower}_test.c")

        test_file = [p for p in written if p.name.endswith("_test.c")]
        if test_file:
            print(f"[ok] Generated validation test: {test_file[0]}")
            return (True, test_file[0])
        else:
            print(f"[warn] Expected test file not found in output for {periph_name}")
            return (False, output_dir / f"{periph_lower}_test.c")

    except Exception as e:
        print(f"[error] Failed to extract test file: {e}")
        return (False, output_dir / f"{periph_lower}_test.c")


def generate_integration_tests(
    bsp_output_dir: Path,
    memmap_yaml_data: Dict[str, Any],
    model: Model,
    max_tokens: int,
    output_dir: Optional[Path] = None,
) -> Tuple[bool, Path]:
    """
    Generate integration tests for startup, entry, system init, and linker script.

    Args:
        bsp_output_dir: Path to generated BSP files
        memmap_yaml_data: Parsed memmap.yaml
        model: Claude model to use
        max_tokens: Max tokens for LLM response
        output_dir: Where to write test file

    Returns:
        Tuple of (success: bool, test_file_path: Path)
    """
    if output_dir is None:
        output_dir = bsp_output_dir

    output_dir.mkdir(parents=True, exist_ok=True)

    # Read generated startup files
    try:
        system_h = read_generated_file(bsp_output_dir, "system.h")
        system_c = read_generated_file(bsp_output_dir, "system.c")
        entry_c = read_generated_file(bsp_output_dir, "entry.c")
        start_s = read_generated_file(bsp_output_dir, "start.s")
        linker_cmd = read_generated_file(bsp_output_dir, "linker.cmd")
    except FileNotFoundError as e:
        print(f"[error] Could not read startup files: {e}")
        return (False, output_dir / "startup_integration_test.c")

    # Extract MEMMAP slice
    try:
        memmap_slice = build_memmap_slice_for_prompt(memmap_yaml_data)
    except Exception as e:
        print(f"[error] Failed to extract MEMMAP slice: {e}")
        return (False, output_dir / "startup_integration_test.c")

    # Build prompts
    system_prompt = build_validation_system_prompt()
    user_prompt = build_integration_test_prompt(
        system_init_source=system_c,
        system_init_header=system_h,
        linker_script=linker_cmd,
        entry_c=entry_c,
        start_asm=start_s,
        memmap_yaml_slice=memmap_slice,
    )

    # Invoke model
    print("[info] Generating integration tests for startup sequence…")
    messages = [
        {
            "role": "user",
            "content": f"[SYSTEM]\n{system_prompt}\n\n[USER]\n{user_prompt}",
        }
    ]

    resp = invoke_model(model, max_tokens, messages)
    text = extract_text_from_bedrock_response(resp)

    if not text.strip():
        print("[warn] Empty response from model for integration tests")
        return (False, output_dir / "startup_integration_test.c")

    # Save and extract test file
    try:
        written = split_and_write_files(text, output_dir)
        if not written:
            print("[warn] No integration test file generated")
            return (False, output_dir / "startup_integration_test.c")

        test_file = [p for p in written if "integration" in p.name]
        if test_file:
            print(f"[ok] Generated integration test: {test_file[0]}")
            return (True, test_file[0])
        else:
            print("[warn] Integration test file not found in output")
            return (False, output_dir / "startup_integration_test.c")

    except Exception as e:
        print(f"[error] Failed to extract integration test: {e}")
        return (False, output_dir / "startup_integration_test.c")


def generate_cross_file_validation(
    bsp_output_dir: Path,
    soc_yaml_data: Dict[str, Any],
    regs_yaml_data: Dict[str, Any],
    memmap_yaml_data: Dict[str, Any],
    facts_canon: str,
    model: Model,
    max_tokens: int,
    output_dir: Optional[Path] = None,
) -> Tuple[bool, Path]:
    """
    Generate cross-file validation tests to ensure consistency across all generated code.

    Args:
        bsp_output_dir: Path to generated BSP files
        soc_yaml_data: Parsed soc.yaml
        regs_yaml_data: Parsed regs.yaml
        memmap_yaml_data: Parsed memmap.yaml
        facts_canon: Reference facts string
        model: Claude model to use
        max_tokens: Max tokens for LLM response
        output_dir: Where to write test file

    Returns:
        Tuple of (success: bool, test_file_path: Path)
    """
    if output_dir is None:
        output_dir = bsp_output_dir

    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect all generated files
    all_files = [
        (p.name, p.read_text(encoding="utf-8"))
        for p in bsp_output_dir.glob("*.c")
        if not p.name.endswith("_test.c")
    ]
    all_files += [
        (p.name, p.read_text(encoding="utf-8"))
        for p in bsp_output_dir.glob("*.h")
    ]
    all_files += [
        (p.name, p.read_text(encoding="utf-8"))
        for p in bsp_output_dir.glob("*.cmd")
    ]
    all_files += [
        (p.name, p.read_text(encoding="utf-8"))
        for p in bsp_output_dir.glob("*.s")
    ]

    # Prepare YAML specs (truncated for brevity)
    yaml_specs = [
        ("soc.yaml", json.dumps(soc_yaml_data, indent=2)[:1000]),
        ("regs.yaml", json.dumps(regs_yaml_data, indent=2)[:1000]),
        ("memmap.yaml", json.dumps(memmap_yaml_data, indent=2)[:1000]),
    ]

    # Build prompts
    system_prompt = build_validation_system_prompt()
    user_prompt = build_cross_file_validation_prompt(
        all_generated_files=all_files,
        all_yaml_specs=yaml_specs,
        facts_canon=facts_canon,
    )

    # Invoke model
    print("[info] Generating cross-file validation tests…")
    messages = [
        {
            "role": "user",
            "content": f"[SYSTEM]\n{system_prompt}\n\n[USER]\n{user_prompt}",
        }
    ]

    resp = invoke_model(model, max_tokens, messages)
    text = extract_text_from_bedrock_response(resp)

    if not text.strip():
        print("[warn] Empty response from model for cross-file validation")
        return (False, output_dir / "cross_validation_test.c")

    # Save and extract test file
    try:
        written = split_and_write_files(text, output_dir)
        if not written:
            print("[warn] No cross-validation test file generated")
            return (False, output_dir / "cross_validation_test.c")

        test_file = [p for p in written if "cross" in p.name.lower()]
        if test_file:
            print(f"[ok] Generated cross-file validation test: {test_file[0]}")
            return (True, test_file[0])
        else:
            print("[warn] Cross-validation test file not found in output")
            return (False, output_dir / "cross_validation_test.c")

    except Exception as e:
        print(f"[error] Failed to extract cross-validation test: {e}")
        return (False, output_dir / "cross_validation_test.c")


def write_test_manifest(
    output_dir: Path,
    test_results: List[Tuple[str, bool, Path]],
) -> Path:
    """
    Write a JSON manifest summarizing generated test files.

    Args:
        output_dir: Directory to write manifest
        test_results: List of (test_name, success, path) tuples

    Returns:
        Path to manifest file
    """
    manifest = {
        "generated_at": _now_tag(),
        "tests": [
            {
                "name": name,
                "success": success,
                "path": str(path.relative_to(output_dir)),
            }
            for name, success, path in test_results
        ],
        "total": len(test_results),
        "passed": sum(1 for _, success, _ in test_results if success),
    }

    manifest_path = output_dir / "validation_tests_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[ok] Test manifest: {manifest_path}")
    return manifest_path
