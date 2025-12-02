#!/usr/bin/env python3
"""
Helpers for loading soc.yaml and interactively selecting which peripherals
to generate code for.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any

import yaml


def load_soc_yaml(path: Path) -> Dict[str, Any]:
    """Load soc.yaml into a Python dict."""
    with Path(path).open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "soc" not in data or "peripherals" not in data["soc"]:
        raise ValueError("soc.yaml does not match expected schema (missing soc.peripherals)")
    return data


def get_peripheral_list(soc_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Return the list of peripheral dicts from soc.yaml,
    excluding SYSTEM and PCR, and skipping any malformed entries.
    """
    raw_periphs = soc_data.get("soc", {}).get("peripherals", [])
    periphs: List[Dict[str, Any]] = []

    for idx, p in enumerate(raw_periphs):
        if not isinstance(p, dict):
            # Defensive: skip non-dict entries instead of crashing
            print(
                f"[warn] soc.speripherals[{idx}] is not an object "
                f"(got {type(p).__name__}); skipping."
            )
            continue

        name = str(p.get("name", "")).upper()
        if name in ("SYSTEM", "PCR"):
            # Don't show SYSTEM/PCR in the interactive menu
            continue

        periphs.append(p)

    return periphs


def _print_peripheral_menu(peripherals: List[Dict[str, Any]]) -> None:
    """Pretty-print the list of peripherals for user selection."""
    print("\nAvailable peripherals (excluding SYSTEM and PCR):")
    print("Index | Name        | Type       | Instance | Clock Ref")
    print("------+-------------+------------+----------+----------")
    for idx, p in enumerate(peripherals, start=1):
        name = str(p.get("name", ""))
        ptype = str(p.get("type", ""))
        inst = str(p.get("instance", ""))
        clock = str(p.get("clock_ref", ""))
        print(f"{idx:5d} | {name:11s} | {ptype:10s} | {inst:8s} | {clock}")


def _parse_selection(
    user_input: str,
    peripherals: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Parse user input into a list of peripheral dicts.

    Accepts:
      - 'a' or 'all' → all peripherals
      - comma-separated indices: '1,3,5'
      - comma-separated names: 'GIO,MIBSPI1'
      - mixed indices/names: '1,GIO'
    """
    text = user_input.strip()
    if not text:
        return []

    # All
    if text.lower() in ("a", "all", "everything"):
        return list(peripherals)

    # Build lookup maps
    by_index = {i + 1: p for i, p in enumerate(peripherals)}
    by_name = {str(p.get("name", "")).upper(): p for p in peripherals}

    chosen: List[Dict[str, Any]] = []
    seen = set()

    parts = [part.strip() for part in text.split(",") if part.strip()]
    for part in parts:
        # Try index
        if part.isdigit():
            idx = int(part)
            if idx in by_index and idx not in seen:
                chosen.append(by_index[idx])
                seen.add(idx)
            else:
                print(f"[warn] Index {idx} is out of range or already selected; ignoring.")
            continue

        # Try name
        key = part.upper()
        if key in by_name and key not in seen:
            chosen.append(by_name[key])
            seen.add(key)
        else:
            print(f"[warn] Peripheral name '{part}' not found or already selected; ignoring.")

    return chosen


def prompt_user_for_peripherals(soc_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Interactively ask the user which peripherals to generate for.

    Returns:
      List of peripheral dicts from soc_data["soc"]["peripherals"],
      excluding SYSTEM and PCR, limited to the ones the user selected.
    """
    peripherals = get_peripheral_list(soc_data)
    if not peripherals:
        print("[info] No peripherals available (besides SYSTEM/PCR).")
        return []

    while True:
        _print_peripheral_menu(peripherals)
        print("\nSelect peripherals to generate:")
        print("  - Enter 'a' or 'all' to generate for ALL peripherals.")
        print("  - Enter comma-separated indices (e.g. '1,3,5').")
        print("  - Or comma-separated names (e.g. 'GIO').")
        print("  - Press Enter with no input to cancel.\n")

        choice = input("Your selection: ").strip()
        if not choice:
            print("[info] No selection made. Aborting peripheral selection.")
            return []

        selected = _parse_selection(choice, peripherals)
        if not selected:
            print("[warn] No valid peripherals selected. Please try again.\n")
            continue

        print("\nYou selected:")
        for p in selected:
            print(
                f"  - {p.get('name', '')} "
                f"(type={p.get('type', '')}, instance={p.get('instance', '')})"
            )

        confirm = input("Proceed with these peripherals? [y/N]: ").strip().lower()
        if confirm in ("y", "yes"):
            return selected

        print("[info] Selection not confirmed. Let's try again.\n")