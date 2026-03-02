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


def _find_regex_index(content: str, pattern: str) -> int:
    match = re.search(pattern, content, re.MULTILINE)
    return match.start() if match else 10**9


def _find_ci_index(content: str, token: str) -> int:
    idx = content.lower().find((token or "").lower())
    return idx if idx >= 0 else 10**9


def _strip_c_comments(content: str) -> str:
    """
    Remove C/C++ comments before token ordering checks.

    This avoids false positives when call tokens (e.g., PLL_Init) appear in
    documentation comments ahead of the real code call sites.
    """
    no_block = re.sub(r"/\*.*?\*/", " ", content, flags=re.DOTALL)
    no_line = re.sub(r"//.*?$", " ", no_block, flags=re.MULTILINE)
    return no_line


def _find_first_pattern_index(content: str, patterns: List[str]) -> int:
    indices: List[int] = []
    for pattern in patterns:
        idx = _find_regex_index(content, pattern)
        if idx != 10**9:
            indices.append(idx)
    return min(indices) if indices else 10**9


def _pll_sequence_patterns() -> Dict[str, List[str]]:
    return {
        "disable/set source bits": [
            r"\bCSDIS(?:SET|CLR|)\b",
            r"\bSYSTEM_CSDIS(?:SET|CLR|)_",
        ],
        "write PLLCTL1/PLLCTL2(/PLLCTL3 if used)": [
            r"\bPLLCTL1\b",
            r"\bPLLCTL2\b",
        ],
        "poll CSVSTAT": [
            r"\bCSVSTAT\b",
            r"while\s*\([^)]*CSVSTAT",
            r"for\s*\([^)]*CSVSTAT",
            r"\bwait_for_pll(?:[12])?_lock\s*\(",
        ],
        "write GHVSRC": [
            r"\bGHVSRC\b",
        ],
        "write RCLKSRC": [
            r"\bRCLKSRC\b",
        ],
        "write VCLKASRC": [
            r"\bVCLKASRC\b",
        ],
        "write CLKCNTL": [
            r"\bCLKCNTL\b",
        ],
        "set PENA": [
            r"\bPENA\b",
            r"\bCLKCNTL\b[^;\n]*\|=\s*[^;\n]*PENA",
        ],
    }


def _validate_pll_required_sequence(content: str, required_sequence: List[str]) -> List[str]:
    markers = _pll_sequence_patterns()
    seen_indices: Dict[str, int] = {}
    missing: List[str] = []
    ordered_checkpoints: List[str] = []
    search_start = 0

    top_level_returns = _find_top_level_return_indices(content)

    for checkpoint in required_sequence:
        if not isinstance(checkpoint, str):
            continue
        checkpoint_key = checkpoint.strip()
        if not checkpoint_key:
            continue
        ordered_checkpoints.append(checkpoint_key)
        patterns = markers.get(checkpoint_key)
        if patterns:
            idx = _find_first_pattern_index_after(content, patterns, search_start)
        else:
            idx = _find_ci_index_after(content, checkpoint_key, search_start)
        if idx == 10**9:
            missing.append(checkpoint_key)
        else:
            if any(ret_idx < idx for ret_idx in top_level_returns if ret_idx >= search_start):
                missing.append(f"control_flow:return_before:{checkpoint_key}")
                break
            seen_indices[checkpoint_key] = idx
            search_start = idx + 1

    if not missing:
        ordered = [cp for cp in ordered_checkpoints if cp in seen_indices]
        for i in range(len(ordered) - 1):
            left = ordered[i].strip()
            right = ordered[i + 1].strip()
            if seen_indices[left] > seen_indices[right]:
                missing.append(f"order:{left}->{right}")
                break
    return missing


def _find_first_pattern_index_after(content: str, patterns: List[str], start_index: int) -> int:
    best = 10**9
    for pattern in patterns:
        for match in re.finditer(pattern, content, re.MULTILINE):
            if match.start() >= start_index:
                best = min(best, match.start())
                break
    return best


def _find_ci_index_after(content: str, token: str, start_index: int) -> int:
    idx = content.lower().find((token or "").lower(), start_index)
    return idx if idx >= 0 else 10**9


def _find_top_level_return_indices(content: str) -> List[int]:
    """
    Approximate control-flow guard: track returns at top function-body scope.
    """
    indices: List[int] = []
    depth = 0
    in_string = False
    quote_char = ""
    i = 0
    while i < len(content):
        ch = content[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == quote_char:
                in_string = False
            i += 1
            continue

        if ch in {"'", '"'}:
            in_string = True
            quote_char = ch
            i += 1
            continue

        if ch == "{":
            depth += 1
            i += 1
            continue
        if ch == "}":
            depth = max(0, depth - 1)
            i += 1
            continue

        if depth == 0 and content.startswith("return", i):
            before_ok = i == 0 or not (content[i - 1].isalnum() or content[i - 1] == "_")
            after_idx = i + len("return")
            after_ok = after_idx >= len(content) or not (
                content[after_idx].isalnum() or content[after_idx] == "_"
            )
            if before_ok and after_ok:
                indices.append(i)
        i += 1
    return indices


def _macro_alias_names_for_literal(content: str, literal_hex: str) -> List[str]:
    token = re.escape(literal_hex)
    pattern = re.compile(
        rf"#define\s+([A-Za-z_][A-Za-z0-9_]*)\s+\(*\s*{token}U?\s*\)*\b",
        re.IGNORECASE,
    )
    return [m.group(1) for m in pattern.finditer(content)]


def _contains_literal_or_alias(content: str, literal_hex: str, aliases: Optional[List[str]] = None) -> bool:
    aliases = aliases or []
    if re.search(re.escape(literal_hex), content, re.IGNORECASE):
        return True
    for alias in aliases:
        if alias and re.search(rf"\b{re.escape(alias)}\b", content):
            return True
    for macro_alias in _macro_alias_names_for_literal(content, literal_hex):
        if re.search(rf"\b{re.escape(macro_alias)}\b", content):
            return True
    return False


def _has_hal_decode_guard(content: str) -> bool:
    if not _contains_literal_or_alias(content, "0xA400"):
        return False

    direct_cmp = re.search(
        r"\b[A-Za-z_][A-Za-z0-9_]*\s*==\s*\(*\s*0xA400U?\s*\)*",
        content,
        re.IGNORECASE,
    )
    if direct_cmp is not None:
        return True

    for alias in _macro_alias_names_for_literal(content, "0xA400"):
        if re.search(
            rf"\b[A-Za-z_][A-Za-z0-9_]*\s*==\s*{re.escape(alias)}\b",
            content,
            re.IGNORECASE,
        ):
            return True
    return False


def _is_trm_dynamic_profile(profile_name: str) -> bool:
    profile = (profile_name or "").strip().lower()
    return profile in {"rm46_trm_dynamic", "rm46_trm_dynamic_with_hal_fallback"}


def _validate_trm_dynamic_pll_startup(pll_init_body: str) -> List[str]:
    """
    Validate minimum TRM-driven PLL startup semantics in PLL_Init().
    """
    errors: List[str] = []
    if not pll_init_body:
        return ["pll_driver.c missing PLL_Init() body required for TRM dynamic startup validation."]

    required_tokens = ["PLLCTL1", "PLLCTL2", "CSDISCLR", "GHVSRC"]
    missing = [tok for tok in required_tokens if tok not in pll_init_body]
    if missing:
        errors.append(
            "pll_driver.c TRM dynamic profile missing required PLL_Init checkpoints: "
            + ", ".join(missing)
        )
    has_csvstat_poll = (
        "CSVSTAT" in pll_init_body
        or "wait_for_pll_lock(" in pll_init_body
        or "wait_for_pll1_lock(" in pll_init_body
        or "wait_for_pll2_lock(" in pll_init_body
    )
    if not has_csvstat_poll:
        errors.append(
            "pll_driver.c TRM dynamic profile missing required PLL lock/CSVSTAT polling path."
        )

    if "CSDISSET" not in pll_init_body and "CSDIS =" not in pll_init_body:
        errors.append(
            "pll_driver.c TRM dynamic profile should disable PLL source before reprogramming (CSDISSET/CSDIS)."
        )

    # PLLCTL programming should not be opaque literal-only in dynamic mode.
    pllctl1_field_style = re.search(
        r"PLLCTL1\s*=\s*[^;\n]*(<<|SYSTEM_PLLCTL1_|PLLCTL1_)",
        pll_init_body,
        re.IGNORECASE,
    ) is not None
    pllctl2_field_style = re.search(
        r"PLLCTL2\s*=\s*[^;\n]*(<<|SYSTEM_PLLCTL2_|PLLCTL2_)",
        pll_init_body,
        re.IGNORECASE,
    ) is not None
    if not pllctl1_field_style or not pllctl2_field_style:
        errors.append(
            "pll_driver.c TRM dynamic profile expects field-composed PLLCTL programming (mask/shift form)."
        )

    return errors


def _extract_function_body(content: str, function_name: str) -> Optional[str]:
    signature = re.search(
        rf"\b{re.escape(function_name)}\s*\([^)]*\)\s*\{{",
        content,
        re.MULTILINE,
    )
    if not signature:
        return None
    start = signature.end() - 1
    depth = 0
    i = start
    n = len(content)
    while i < n:
        ch = content[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return content[start + 1 : i]
        i += 1
    return None


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
        code_content = _strip_c_comments(content)
        pcr_init = _find_call_index(code_content, "PCR_Init(")
        pcr_enable = _find_call_index(code_content, "PCR_EnableAllPeripherals(")
        pll_init = _find_call_index(code_content, "PLL_Init(")
        checks["system_c_calls"] = {
            "PCR_Init": pcr_init != 10**9,
            "PCR_EnableAllPeripherals": pcr_enable != 10**9,
            "PLL_Init": pll_init != 10**9,
        }
        if pcr_init == 10**9 or pcr_enable == 10**9 or pll_init == 10**9:
            warnings.append("system.c missing one or more expected startup calls")
        elif not (pcr_init < pcr_enable < pll_init):
            errors.append("system.c startup ordering must be PCR_Init -> PCR_EnableAllPeripherals -> PLL_Init")

        flash_cfg = bringup_contract.get("flash", {}) if isinstance(bringup_contract, dict) else {}
        required_flash_regs = (
            flash_cfg.get("required_registers", {})
            if isinstance(flash_cfg, dict)
            else {}
        )
        flash_indices: List[int] = []
        if isinstance(required_flash_regs, dict) and required_flash_regs:
            for reg_name, reg_rule in required_flash_regs.items():
                if not isinstance(reg_rule, dict):
                    continue
                addr = str(reg_rule.get("address", "") or "").strip()
                if addr:
                    addr_idx = _find_ci_index(code_content, addr)
                    if addr_idx == 10**9:
                        errors.append(
                            f"system.c missing flash register address {addr} for {reg_name} required by bring-up contract."
                        )
                    else:
                        flash_indices.append(addr_idx)
                for write_token in reg_rule.get("required_write_tokens", []) or []:
                    if not isinstance(write_token, str) or not write_token.strip():
                        continue
                    if _find_ci_index(code_content, write_token) == 10**9:
                        errors.append(
                            f"system.c missing required flash write token {write_token} for {reg_name}."
                        )

        if not flash_indices:
            flash_call_idx = _find_regex_index(code_content, r"\bsystem_setup_flash_waitstates\s*\(\s*\)\s*;")
            flash_reg_idx = _find_regex_index(code_content, r"\bFLASH_FRDCNTL\b")
            if flash_call_idx != 10**9:
                flash_indices = [flash_call_idx]
            else:
                flash_indices = [idx for idx in (flash_reg_idx,) if idx != 10**9]
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
                    order_markers[token] = _find_call_index(code_content, "PCR_Init(")
                elif token == "PCR_EnableAllPeripherals":
                    order_markers[token] = _find_call_index(code_content, "PCR_EnableAllPeripherals(")
                elif token == "PLL_Init":
                    order_markers[token] = _find_call_index(code_content, "PLL_Init(")
                elif token == "flash_waitstates":
                    call_idx = _find_regex_index(code_content, r"\bsystem_setup_flash_waitstates\s*\(\s*\)\s*;")
                    reg_idx = _find_regex_index(code_content, r"\bFLASH_FRDCNTL\b")
                    if call_idx != 10**9:
                        indices = [call_idx]
                    else:
                        indices = [idx for idx in (reg_idx,) if idx != 10**9]
                    order_markers[token] = min(indices) if indices else 10**9
                else:
                    order_markers[token] = _find_call_index(code_content, token)

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
    pll_init_profile = (
        str(pll_cfg.get("init_profile", "")).strip().lower()
        if isinstance(pll_cfg, dict)
        else ""
    )
    required_sequence = pll_cfg.get("required_sequence", []) if isinstance(pll_cfg, dict) else []
    if pll_path:
        pll_text = pll_path.read_text(encoding="utf-8", errors="ignore")
        pll_init_body = _extract_function_body(pll_text, "PLL_Init")
        target_text = pll_init_body if isinstance(pll_init_body, str) and pll_init_body.strip() else pll_text
        if isinstance(required_sequence, list) and required_sequence:
            missing_tokens = _validate_pll_required_sequence(target_text, required_sequence)
            if missing_tokens:
                errors.append(
                    "pll_driver.c missing required bring-up sequence tokens: " + ", ".join(missing_tokens)
                )
        freq_decode = pll_cfg.get("frequency_decode", {}) if isinstance(pll_cfg, dict) else {}
        if isinstance(freq_decode, dict) and freq_decode:
            required_behavior = freq_decode.get("required_behavior", {})
            if not isinstance(required_behavior, dict):
                required_behavior = {}

            require_trm_field_decoding = _is_trm_dynamic_profile(pll_init_profile)
            require_trm_enable_disable = _is_trm_dynamic_profile(pll_init_profile)
            if require_trm_field_decoding or require_trm_enable_disable:
                errors.extend(_validate_trm_dynamic_pll_startup(target_text))

            allow_hal_encoded = bool(freq_decode.get("allow_hal_encoded_pllmul", False))
            if allow_hal_encoded and "supports_hal_encoded_pllmul_literal" not in required_behavior:
                required_behavior["supports_hal_encoded_pllmul_literal"] = True

            if bool(required_behavior.get("supports_hal_encoded_pllmul_literal", False)):
                if not _has_hal_decode_guard(pll_text):
                    errors.append(
                        "pll_driver.c missing HAL-encoded PLLMUL literal/decode guard required by bring-up contract."
                    )
            if bool(required_behavior.get("uses_hal_literal_hclk_override", False)):
                hal_hclk_raw = freq_decode.get("hal_literal_hclk_hz")
                try:
                    hal_hclk = int(hal_hclk_raw) if hal_hclk_raw is not None else None
                except (TypeError, ValueError):
                    hal_hclk = None
                if hal_hclk is None or hal_hclk <= 0:
                    errors.append(
                        "bring-up contract requires HAL literal HCLK override, but pll.frequency_decode.hal_literal_hclk_hz is missing/invalid."
                    )
                else:
                    hal_hclk_hex = f"0x{hal_hclk:X}"
                    has_hclk_literal = (
                        str(hal_hclk) in pll_text
                        or hal_hclk_hex.lower() in pll_text.lower()
                    )
                    if not has_hclk_literal:
                        errors.append(
                            f"pll_driver.c missing HAL literal HCLK override value {hal_hclk} required by bring-up contract."
                        )
            if bool(required_behavior.get("uses_uint64_intermediate_math", False)):
                if "uint64_t" not in pll_text and re.search(r"\(\s*uint64_t\s*\)", pll_text) is None:
                    errors.append(
                        "pll_driver.c missing uint64_t intermediate math required by bring-up contract."
                    )
            if bool(required_behavior.get("derives_active_source_from_ghvsrc", False)):
                if "GHVSRC" not in pll_text:
                    errors.append(
                        "pll_driver.c missing GHVSRC-based active-source derivation required by bring-up contract."
                    )

            decode_required = freq_decode.get("required_tokens", [])
            if isinstance(decode_required, list):
                missing_decode = [
                    token
                    for token in decode_required
                    if isinstance(token, str) and token and token not in pll_text
                ]
                if missing_decode:
                    warnings.append(
                        "pll_driver.c missing optional PLL frequency-decode tokens: "
                        + ", ".join(missing_decode)
                    )
        elif _is_trm_dynamic_profile(pll_init_profile):
            errors.extend(_validate_trm_dynamic_pll_startup(target_text))
        if pll_init_profile == "rm46_hal_aligned":
            required_hal_tokens = ["GLBSTAT", "PLLCTL1", "PLLCTL2", "RCLKSRC", "VCLKASRC", "CLKCNTL", "PENA"]
            missing_hal = [tok for tok in required_hal_tokens if tok not in target_text]
            if missing_hal:
                errors.append(
                    "pll_driver.c missing rm46_hal_aligned checkpoints: " + ", ".join(missing_hal)
                )
            if not _contains_literal_or_alias(target_text, "0x00000301", ["HAL_ALIGNED_GLBSTAT_CLEAR_VALUE", "RM46_GLBSTAT_CLEAR_MASK"]):
                errors.append("pll_driver.c missing rm46_hal_aligned GLBSTAT clear checkpoint (0x00000301 or alias).")
            has_csdis_snapshot = (
                _contains_literal_or_alias(target_text, "0x0000008C", ["HAL_ALIGNED_CSDIS_VALUE", "RM46_PLL_CSDIS_SNAPSHOT"])
                or re.search(r"\bCSDIS\s*=", target_text) is not None
            )
            has_cddis_snapshot = (
                _contains_literal_or_alias(target_text, "0x00000020", ["HAL_ALIGNED_CDDIS_VALUE", "RM46_PLL_CDDIS_SNAPSHOT"])
                or re.search(r"\bCDDIS\s*=", target_text) is not None
            )
            if not has_csdis_snapshot:
                errors.append("pll_driver.c missing rm46_hal_aligned CSDIS snapshot/checkpoint.")
            if not has_cddis_snapshot:
                errors.append("pll_driver.c missing rm46_hal_aligned CDDIS snapshot/checkpoint.")

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
