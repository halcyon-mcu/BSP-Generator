#!/usr/bin/env python3
"""
Startup contract validation for deterministic RM46 bring-up.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.dependency_resolver import InitOrder


def _find_call_index(content: str, token: str) -> int:
    idx = content.find(token)
    return idx if idx >= 0 else 10**9


def validate_startup_contract(
    init_order: InitOrder,
    output_dir: Path,
    bringup_contract: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    checks: Dict[str, Any] = {}
    bringup_contract = bringup_contract or {}

    if not init_order.is_valid():
        errors.append("Startup init order is invalid due to dependency cycle")
        return {"passes": False, "errors": errors, "warnings": warnings, "checks": checks}

    order = init_order.order
    checks["init_order"] = order

    def _idx(name: str) -> int:
        return order.index(name) if name in order else 10**9

    system_idx = _idx("SYSTEM")
    pcr_idx = _idx("PCR")
    pll_idx = _idx("PLL")

    if pcr_idx == 10**9:
        errors.append("Missing PCR in init order")
    if pll_idx == 10**9:
        errors.append("Missing PLL in init order")
    if system_idx == 10**9:
        errors.append("Missing SYSTEM in init order")

    if system_idx != 10**9 and pcr_idx != 10**9 and system_idx > pcr_idx:
        errors.append("SYSTEM must initialize before PCR")
    if pcr_idx != 10**9 and pll_idx != 10**9 and pcr_idx > pll_idx:
        errors.append("PCR must initialize before PLL")

    gated_modules = ["IOMM", "GIO", "SCI", "LIN"]
    for module in gated_modules:
        mod_idx = _idx(module)
        if mod_idx != 10**9 and pcr_idx != 10**9 and pcr_idx > mod_idx:
            errors.append(f"PCR must initialize before {module}")

    system_c_candidates = [
        Path(output_dir) / "system.c",
        Path(output_dir) / "include" / "system.c",
        Path(output_dir) / "source" / "system.c",
    ]
    system_c = next((p for p in system_c_candidates if p.exists()), None)
    if system_c:
        content = system_c.read_text(encoding="utf-8", errors="ignore")
        pcr_init = _find_call_index(content, "PCR_Init(")
        pcr_enable = _find_call_index(content, "PCR_EnableAllPeripherals(")
        pll_init = _find_call_index(content, "PLL_Init(")
        checks["system_c_calls"] = {
            "PCR_Init": pcr_init != 10**9,
            "PCR_EnableAllPeripherals": pcr_enable != 10**9,
            "PLL_Init": pll_init != 10**9,
        }
        if pcr_init == 10**9 or pcr_enable == 10**9 or pll_init == 10**9:
            warnings.append("system.c missing one or more expected startup calls")
        elif not (pcr_init < pcr_enable < pll_init):
            errors.append("system.c startup ordering must be PCR_Init -> PCR_EnableAllPeripherals -> PLL_Init")

        flash_markers = ["system_setup_flash_waitstates(", "FLASH_FRDCNTL"]
        flash_indices = [content.find(marker) for marker in flash_markers if marker in content]
        if not flash_indices:
            errors.append(
                "system.c must configure flash wait-states before PLL_Init "
                "(expected system_setup_flash_waitstates/FLASH_FRDCNTL)."
            )
        else:
            flash_idx = min(flash_indices)
            if pll_init != 10**9 and flash_idx > pll_init:
                errors.append("system.c flash wait-state setup must occur before PLL_Init")

        if pcr_enable != 10**9:
            pcr_header_candidates = [
                Path(output_dir) / "pcr_driver.h",
                Path(output_dir) / "include" / "pcr_driver.h",
            ]
            pcr_source_candidates = [
                Path(output_dir) / "pcr_driver.c",
                Path(output_dir) / "source" / "pcr_driver.c",
                Path(output_dir) / "include" / "pcr_driver.c",
            ]
            pcr_header = next((p for p in pcr_header_candidates if p.exists()), None)
            pcr_source = next((p for p in pcr_source_candidates if p.exists()), None)
            if not pcr_header or "PCR_EnableAllPeripherals(" not in pcr_header.read_text(encoding="utf-8", errors="ignore"):
                errors.append("PCR_EnableAllPeripherals is called from system.c but missing in pcr_driver.h")
            if not pcr_source or "PCR_EnableAllPeripherals(" not in pcr_source.read_text(encoding="utf-8", errors="ignore"):
                errors.append("PCR_EnableAllPeripherals is called from system.c but missing in pcr_driver.c")

        startup_cfg = bringup_contract.get("startup", {}) if isinstance(bringup_contract, dict) else {}
        required_order = startup_cfg.get("required_order", []) if isinstance(startup_cfg, dict) else []
        if isinstance(required_order, list) and required_order:
            order_markers: Dict[str, int] = {}
            flash_markers = ["system_setup_flash_waitstates(", "FLASH_FRDCNTL"]
            for token in required_order:
                if not isinstance(token, str):
                    continue
                if token == "PCR_Init":
                    order_markers[token] = _find_call_index(content, "PCR_Init(")
                elif token == "PCR_EnableAllPeripherals":
                    order_markers[token] = _find_call_index(content, "PCR_EnableAllPeripherals(")
                elif token == "PLL_Init":
                    order_markers[token] = _find_call_index(content, "PLL_Init(")
                elif token == "flash_waitstates":
                    indices = [content.find(marker) for marker in flash_markers if marker in content]
                    order_markers[token] = min(indices) if indices else 10**9
                else:
                    order_markers[token] = _find_call_index(content, token)

            missing_tokens = [name for name, idx in order_markers.items() if idx == 10**9]
            if missing_tokens:
                errors.append(
                    "system.c missing required startup bring-up markers: " + ", ".join(missing_tokens)
                )
            else:
                ordered = list(required_order)
                for i in range(len(ordered) - 1):
                    left = ordered[i]
                    right = ordered[i + 1]
                    if order_markers.get(left, 10**9) > order_markers.get(right, 10**9):
                        errors.append(
                            f"system.c bring-up ordering violation: expected {left} before {right}"
                        )
    else:
        warnings.append("system.c not present for startup call-sequence validation")

    pll_candidates = [
        Path(output_dir) / "pll_driver.c",
        Path(output_dir) / "include" / "pll_driver.c",
        Path(output_dir) / "source" / "pll_driver.c",
    ]
    pll_path = next((p for p in pll_candidates if p.exists()), None)
    pll_cfg = bringup_contract.get("pll", {}) if isinstance(bringup_contract, dict) else {}
    required_sequence = pll_cfg.get("required_sequence", []) if isinstance(pll_cfg, dict) else []
    if pll_path and isinstance(required_sequence, list) and required_sequence:
        pll_text = pll_path.read_text(encoding="utf-8", errors="ignore")
        missing_tokens = []
        for token in required_sequence:
            if isinstance(token, str) and token and token not in pll_text:
                missing_tokens.append(token)
        if missing_tokens:
            errors.append(
                "pll_driver.c missing required bring-up sequence tokens: " + ", ".join(missing_tokens)
            )

    start_s_candidates = [
        Path(output_dir) / "start.s",
        Path(output_dir) / "include" / "start.s",
        Path(output_dir) / "source" / "start.s",
    ]
    start_s = next((p for p in start_s_candidates if p.exists()), None)
    if start_s:
        content = start_s.read_text(encoding="utf-8", errors="ignore")

        pattern_checks = [
            (r"\.sect\s+\"\.intvecs\"", ".intvecs section"),
            (r"\bB\s+(?:Reset_Handler|Reset_Entry)\b", "reset vector branch"),
            (r"\bB\s+Undef_Handler\b", "Undef handler vector"),
            (r"\bB\s+SVC_Handler\b", "SVC handler vector"),
            (r"\bB\s+Prefetch_Abort_Handler\b", "Prefetch abort vector"),
            (r"\bB\s+Data_Abort_Handler\b", "Data abort vector"),
            (r"\bB\s+Phantom_Handler\b", "Phantom handler vector"),
            (r"\bMRS\s+R0,\s*CPSR\b", "CPSR read in reset path"),
            (r"\bMSR\s+CPSR_c\b", "mode switch writes"),
            (r"\bLDR\s+SP,\s*stack_addr\b", "stack pointer initialization"),
            (r"\bBL\s+Reset_Handler_C\b", "C reset handoff"),
            (r"^\s*stack_addr\s*:", "stack_addr label"),
            (r"\.long\s+end_of_stack\b", "end_of_stack literal"),
        ]
        missing = [
            name
            for pattern, name in pattern_checks
            if re.search(pattern, content, re.MULTILINE) is None
        ]
        if missing:
            errors.append(
                "start.s missing required Cortex-R startup elements: " + ", ".join(missing)
            )

        vim_vector_count = len(re.findall(r"\bLDR\s+PC,\s*\[PC,\s*#-0x1B0\]", content, re.MULTILINE))
        if vim_vector_count < 2:
            errors.append("start.s must contain IRQ/FIQ VIM vectors using 'LDR PC, [PC, #-0x1B0]'")

        long_reset_count = len(re.findall(r'^\s*\.long\s+Reset_Handler\b', content, re.MULTILINE))
        if long_reset_count >= 3:
            errors.append(
                "start.s uses address-word vectors (.long Reset_Handler). "
                "Expected Cortex-R executable branch vectors in .intvecs."
            )

        if re.search(r"^\s*LDR\s+R\d+\s*,\s*=0x[0-9A-Fa-f]+", content, re.MULTILINE):
            errors.append(
                "start.s uses GNU-style immediate literal loads (LDR Rn, =0x...). "
                "Use TI-safe MOVW/MOVT sequences."
            )
    else:
        warnings.append("start.s not present for startup assembly validation")

    return {
        "passes": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }
