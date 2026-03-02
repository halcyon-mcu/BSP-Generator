"""
Pass 2 (Implementation) validation.

Validates driver implementations generated in Pass 2 to ensure:
- API contract compliance with manifest
- Proper clock gating and interrupt registration
- No hardcoded addresses
- Dependencies are met
"""

import re
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class Pass2ValidationResult:
    """Result of Pass 2 validation."""
    is_valid: bool
    critical_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    has_todos: bool = False


def _count_params(param_blob: str) -> int:
    blob = (param_blob or "").strip()
    if not blob or blob == "void":
        return 0
    return len([p for p in blob.split(",") if p.strip()])


def _extract_prototypes(content: str) -> Dict[str, int]:
    pattern = re.compile(r'^\s*[A-Za-z_][\w\s\*]*?\s+([A-Za-z_]\w*)\s*\(([^;{}]*)\)\s*;', re.MULTILINE)
    out: Dict[str, int] = {}
    for match in pattern.finditer(content):
        out[match.group(1)] = _count_params(match.group(2))
    return out


def _extract_definitions(content: str) -> Dict[str, int]:
    pattern = re.compile(r'^\s*[A-Za-z_][\w\s\*]*?\s+([A-Za-z_]\w*)\s*\(([^;{}]*)\)\s*\{', re.MULTILINE)
    out: Dict[str, int] = {}
    for match in pattern.finditer(content):
        out[match.group(1)] = _count_params(match.group(2))
    return out


def _extract_function_body(content: str, function_name: str) -> Optional[str]:
    """Extract a function body by name using brace matching."""
    sig = re.search(rf"\b{re.escape(function_name)}\s*\([^;{{}}]*\)\s*\{{", content)
    if not sig:
        return None

    open_brace = content.find("{", sig.start(), sig.end())
    if open_brace < 0:
        return None

    depth = 0
    idx = open_brace
    while idx < len(content):
        ch = content[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return content[open_brace + 1:idx]
        idx += 1
    return None


def _all_returns_guarded_by_lock(function_body: str) -> bool:
    """
    Return True when each explicit return statement has IOMM_Lock() directly
    before it (ignoring blank/comment-only lines).
    """
    lines = function_body.splitlines()
    for i, line in enumerate(lines):
        if not re.match(r"^\s*return\b", line):
            continue

        j = i - 1
        while j >= 0:
            prev = lines[j].strip()
            if not prev or prev.startswith("/*") or prev.startswith("*") or prev.startswith("//"):
                j -= 1
                continue
            if "IOMM_Lock();" in prev:
                break
            return False
        if j < 0:
            return False
    return True


def _find_first_pattern_index(content: str, patterns: List[str], start_idx: int = 0) -> int:
    """Return earliest match index across regex patterns, or -1 if not found."""
    best = -1
    search_blob = content[start_idx:] if start_idx > 0 else content
    for pattern in patterns:
        match = re.search(pattern, search_blob, re.IGNORECASE)
        if not match:
            continue
        idx = (start_idx + match.start()) if start_idx > 0 else match.start()
        if best < 0 or idx < best:
            best = idx
    return best


def _pll_sequence_patterns(checkpoint: str) -> List[str]:
    """Map contract checkpoint text to robust token patterns."""
    cp = (checkpoint or "").strip().lower()

    aliases = {
        "disable/set source bits": [
            r"\bCSDISSET\b",
            r"\bCSDISCLR\b",
            r"\bCSDIS\s*=",
        ],
        "write pllctl1/pllctl2(/pllctl3 if used)": [
            r"\bPLLCTL1\b",
            r"\bPLLCTL2\b",
        ],
        "poll csvstat": [r"\bCSVSTAT\b", r"\bwait_for_pll(?:[12])?_lock\s*\("],
        "write ghvsrc": [r"\bGHVSRC\b"],
        "write rclksrc": [r"\bRCLKSRC\b"],
        "write vclkasrc": [r"\bVCLKASRC\b"],
        "write clkcntl": [r"\bCLKCNTL\b"],
        "set pena": [r"\bPENA\b", r"\bSYSTEM_CLKCNTL_PENA\b"],
    }

    if cp in aliases:
        return aliases[cp]

    # Backward-compatible path: token-style checkpoints from older contracts.
    token = re.escape((checkpoint or "").strip())
    if token:
        return [token]
    return []


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
    alias_names = _macro_alias_names_for_literal(content, "0xA400")
    for alias in alias_names:
        if re.search(
            rf"\b[A-Za-z_][A-Za-z0-9_]*\s*==\s*{re.escape(alias)}\b",
            content,
            re.IGNORECASE,
        ):
            return True
    return False


def _function_or_called_helper_mentions_token(
    content: str,
    function_name: str,
    token: str,
    max_depth: int = 2,
) -> bool:
    root_body = _extract_function_body(content, function_name)
    if not root_body:
        return False
    if token in root_body:
        return True

    ignore_calls = {
        "if", "for", "while", "switch", "return", "sizeof",
        "uint32_t", "uint64_t", "int", "void", "static",
    }

    seen = {function_name}
    queue: List[tuple[str, int]] = [(function_name, 0)]
    while queue:
        current_fn, depth = queue.pop(0)
        if depth >= max_depth:
            continue
        current_body = _extract_function_body(content, current_fn)
        if not current_body:
            continue
        for match in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", current_body):
            callee = match.group(1)
            if callee in ignore_calls or callee in seen:
                continue
            seen.add(callee)
            callee_body = _extract_function_body(content, callee)
            if not callee_body:
                continue
            if token in callee_body:
                return True
            queue.append((callee, depth + 1))
    return False


def _validate_pll_required_sequence(
    file_name: str,
    pll_init_body: str,
    required_sequence: List[str],
) -> List[str]:
    """Validate required PLL sequence token/checkpoint presence and ordering."""
    errors: List[str] = []
    if not pll_init_body or not isinstance(required_sequence, list):
        return errors

    cursor = 0
    for checkpoint in required_sequence:
        if not isinstance(checkpoint, str) or not checkpoint.strip():
            continue

        patterns = _pll_sequence_patterns(checkpoint)
        if not patterns:
            continue

        # Special handling for combined checkpoint that requires both PLLCTL1 and PLLCTL2.
        normalized_checkpoint = checkpoint.strip().lower()
        if normalized_checkpoint == "write pllctl1/pllctl2(/pllctl3 if used)":
            pllctl1_idx = _find_first_pattern_index(pll_init_body, [r"\bPLLCTL1\b"], cursor)
            pllctl2_idx = _find_first_pattern_index(pll_init_body, [r"\bPLLCTL2\b"], cursor)
            if pllctl1_idx < 0 or pllctl2_idx < 0:
                errors.append(
                    f"{file_name}: Missing required PLL sequence checkpoint '{checkpoint}' (need both PLLCTL1 and PLLCTL2 writes)."
                )
                continue
            first_idx = min(pllctl1_idx, pllctl2_idx)
            if first_idx < cursor:
                errors.append(
                    f"{file_name}: PLL sequence ordering violation at checkpoint '{checkpoint}'."
                )
            cursor = max(pllctl1_idx, pllctl2_idx) + 1
            continue

        idx = _find_first_pattern_index(pll_init_body, patterns, cursor)
        if idx < 0:
            errors.append(
                f"{file_name}: Missing required PLL sequence checkpoint '{checkpoint}' from bring-up contract."
            )
            continue
        if idx < cursor:
            errors.append(
                f"{file_name}: PLL sequence ordering violation at checkpoint '{checkpoint}'."
            )
            continue
        cursor = idx + 1

    return errors


def _is_trm_dynamic_profile(profile_name: str) -> bool:
    profile = (profile_name or "").strip().lower()
    return profile in {"rm46_trm_dynamic", "rm46_trm_dynamic_with_hal_fallback"}


def _validate_trm_dynamic_pll_behavior(
    file_name: str,
    pll_init_body: Optional[str],
    pll_getfreq_body: Optional[str],
    require_enable_disable_sequence: bool,
) -> List[str]:
    """
    Validate TRM-oriented dynamic PLL programming behavior.

    This avoids HAL-literal lock-in by requiring field-based decode/programming
    paths and GHVSRC-aware runtime selection.
    """
    errors: List[str] = []
    init_blob = pll_init_body or ""
    freq_blob = pll_getfreq_body or ""

    if not init_blob:
        errors.append(f"{file_name}: Missing PLL_Init() body for TRM dynamic profile validation.")
        return errors
    if not freq_blob:
        errors.append(f"{file_name}: Missing PLL_GetFrequency() body for TRM dynamic profile validation.")
        return errors

    # PLLCTL writes should be expressed as field/mask composition in dynamic mode.
    pllctl1_field_style = re.search(
        r"PLLCTL1\s*=\s*[^;\n]*(<<|SYSTEM_PLLCTL1_|PLLCTL1_)",
        init_blob,
        re.IGNORECASE,
    ) is not None
    pllctl2_field_style = re.search(
        r"PLLCTL2\s*=\s*[^;\n]*(<<|SYSTEM_PLLCTL2_|PLLCTL2_)",
        init_blob,
        re.IGNORECASE,
    ) is not None
    if not pllctl1_field_style:
        errors.append(
            f"{file_name}: TRM dynamic profile expects PLLCTL1 field-composed programming (mask/shift form)."
        )
    if not pllctl2_field_style:
        errors.append(
            f"{file_name}: TRM dynamic profile expects PLLCTL2 field-composed programming (mask/shift form)."
        )

    # Frequency decode must read raw register fields and convert to effective divisors.
    has_pllctl_reads = "PLLCTL1" in freq_blob and "PLLCTL2" in freq_blob
    has_raw_extract = re.search(r"\b(nf_raw|nr_raw|plldiv_raw|odpll_raw)\b", freq_blob) is not None
    has_nr_convert = re.search(r"nr[_a-zA-Z0-9]*\s*\+\s*1U", freq_blob) is not None
    has_r_convert = (
        re.search(r"1U\s*<<\s*plldiv[_a-zA-Z0-9]*", freq_blob) is not None
        or re.search(r"plldiv[_a-zA-Z0-9]*\s*\+\s*1U", freq_blob) is not None
    )
    has_od_convert = re.search(r"odpll[_a-zA-Z0-9]*\s*\+\s*1U", freq_blob) is not None
    if not has_pllctl_reads or not has_raw_extract:
        errors.append(
            f"{file_name}: TRM dynamic profile requires PLL_GetFrequency() to extract PLL fields from PLLCTL1/PLLCTL2."
        )
    if not has_nr_convert:
        errors.append(f"{file_name}: Missing NR conversion (register encoding to effective divider) in PLL_GetFrequency().")
    if not has_r_convert:
        errors.append(f"{file_name}: Missing PLLDIV/R conversion logic in PLL_GetFrequency().")
    if not has_od_convert:
        errors.append(f"{file_name}: Missing ODPLL conversion logic in PLL_GetFrequency().")

    if require_enable_disable_sequence:
        if "CSDISSET" not in init_blob and "CSDIS =" not in init_blob:
            errors.append(
                f"{file_name}: TRM dynamic profile requires disable-before-reprogram sequence (CSDISSET/CSDIS)."
            )
        if "CSDISCLR" not in init_blob:
            errors.append(
                f"{file_name}: TRM dynamic profile requires explicit source enable via CSDISCLR after programming."
            )
        has_csvstat_path = (
            "CSVSTAT" in init_blob
            or "wait_for_pll_lock(" in init_blob
            or "wait_for_pll1_lock(" in init_blob
            or "wait_for_pll2_lock(" in init_blob
        )
        if not has_csvstat_path:
            errors.append(
                f"{file_name}: TRM dynamic profile requires CSVSTAT valid polling before clock handoff."
            )

    return errors


def validate_driver_implementation(
    module_name: str,
    manifest_entry: Dict,
    preamble: str,
    written_files: List[Path],
    soc_data: dict,
    regs_data: dict,
    clock_h_path: Path = None,
    bringup_contract: Optional[Dict] = None,
) -> Pass2ValidationResult:
    """
    Validate Pass 2 driver implementation.

    Args:
        module_name: Name of the peripheral module
        manifest_entry: Manifest entry for this module from Pass 1
        preamble: Preamble text from LLM output
        written_files: List of generated files
        soc_data: SOC configuration from soc.yaml
        regs_data: Register definitions from regs.yaml
        clock_h_path: Path to clock.h for validation

    Returns:
        Pass2ValidationResult with validation status
    """
    errors = []
    warnings = []
    has_todos = False
    bringup_contract = bringup_contract or {}

    def _parse_contract_int(value) -> Optional[int]:
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value, 0)
            except ValueError:
                return None
        return None

    # Check 1: FACTS MIRROR has no TODOs
    if "FACTS MIRROR" in preamble and "TODO:" in preamble:
        facts_pattern = re.compile(
            r'===== FACTS MIRROR =====\s*(.*?)\s*===== END FACTS MIRROR =====',
            re.DOTALL
        )
        match = facts_pattern.search(preamble)
        if match and "TODO:" in match.group(1):
            errors.append(f"{module_name}: FACTS MIRROR contains TODO items")
            has_todos = True

    # Check 2: All manifest API functions implemented
    expected_funcs = manifest_entry.get('api_functions', [])
    implemented_funcs = set()

    for file_path in written_files:
        if not file_path.exists() or file_path.suffix != '.c':
            continue

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            for func in expected_funcs:
                func_name = func.get('name', '')
                if func_name:
                    # Look for function definition (not just declaration)
                    pattern = rf'\b{re.escape(func_name)}\s*\([^)]*\)\s*\{{'
                    if re.search(pattern, content):
                        implemented_funcs.add(func_name)
        except Exception as e:
            warnings.append(f"Could not check functions in {file_path.name}: {e}")

    missing_funcs = set(f.get('name') for f in expected_funcs if f.get('name')) - implemented_funcs
    if missing_funcs:
        for func in missing_funcs:
            warnings.append(f"{module_name}: Function '{func}' from manifest not found in implementation")

    # Check 3: Init function exists
    # Get expected init function name from manifest (don't construct it)
    init_func_name = manifest_entry.get('init_function', f"{module_name.upper()}_Init")
    init_found = False

    for file_path in written_files:
        if not file_path.exists() or file_path.suffix != '.c':
            continue

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            if re.search(rf'\b{re.escape(init_func_name)}\s*\([^)]*\)\s*\{{', content):
                init_found = True
                break
        except Exception:
            pass

    if not init_found:
        errors.append(f"{module_name}: Missing init function '{init_func_name}'")

    # Check 4: Clock gating if has clock_ref
    periph_data = None
    for p in soc_data.get('peripherals', []):
        if p.get('name') == module_name:
            periph_data = p
            break

    if periph_data and periph_data.get('clock_ref'):
        clock_ref = periph_data['clock_ref']
        found_clock_enable = False

        for file_path in written_files:
            if not file_path.exists() or file_path.suffix != '.c':
                continue

            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                # Look for PLL_EnableClock() or clock_enable() call
                if ('PLL_EnableClock' in content or 'clock_enable' in content):
                    found_clock_enable = True
                    break
            except Exception:
                pass

        if not found_clock_enable:
            warnings.append(
                f"{module_name}: Has clock_ref '{clock_ref}' but doesn't call PLL_EnableClock() or clock_enable()"
            )

    # Check 5: No hardcoded addresses
    for file_path in written_files:
        if not file_path.exists() or file_path.suffix != '.c':
            continue

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            # Look for hardcoded addresses (8-digit hex values)
            hardcoded = re.findall(r'\b0x[0-9A-Fa-f]{8}\b', content)
            if hardcoded:
                # Filter out common non-address constants
                suspicious = [
                    addr for addr in hardcoded
                    if addr.lower() not in ['0x00000000', '0xffffffff', '0x12345678']
                ]
                if len(suspicious) > 2:  # More than a couple might indicate hardcoded addresses
                    warnings.append(
                        f"{file_path.name}: Contains potential hardcoded addresses: "
                        f"{', '.join(suspicious[:3])}"
                    )
        except Exception:
            pass

    # Check 6: Required headers included
    driver_c_files = [f for f in written_files if f.exists() and f.suffix == '.c']
    driver_h_files = [f for f in written_files if f.exists() and f.suffix == '.h']

    # Check 6b: Header/source prototype parity (ABI drift guard)
    if driver_c_files and driver_h_files:
        try:
            h_content = driver_h_files[0].read_text(encoding='utf-8', errors='ignore')
            c_content = driver_c_files[0].read_text(encoding='utf-8', errors='ignore')
            decls = _extract_prototypes(h_content)
            defs = _extract_definitions(c_content)
            module_prefix = f"{module_name.upper()}_"

            for fname, decl_arity in decls.items():
                if not fname.startswith(module_prefix):
                    continue
                if fname in defs and defs[fname] != decl_arity:
                    errors.append(
                        f"{module_name}: Header/source signature mismatch for {fname} "
                        f"({decl_arity} args in header, {defs[fname]} in source)"
                    )
        except Exception as e:
            warnings.append(f"{module_name}: Could not complete ABI drift check: {e}")

    for file_path in driver_c_files:
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')

            # Should include corresponding header
            expected_header = file_path.with_suffix('.h').name
            if f'#include "{expected_header}"' not in content and f"#include <{expected_header}>" not in content:
                warnings.append(f"{file_path.name}: Missing #include for {expected_header}")

            # If uses PLL_EnableClock, should include pll_driver.h
            if 'PLL_EnableClock' in content or 'PLL_GetFrequency' in content:
                if '#include "pll_driver.h"' not in content and '#include <pll_driver.h>' not in content:
                    warnings.append(f"{file_path.name}: Uses PLL APIs but doesn't include pll_driver.h")
            # If uses old clock API, should include clock.h
            elif 'clock_enable' in content or 'clock_get_hz' in content:
                if '#include "clock.h"' not in content and '#include <clock.h>' not in content:
                    warnings.append(f"{file_path.name}: Uses clock APIs but doesn't include clock.h")

        except Exception:
            pass

    # Check 7: No hardcoded frequency constants (if module has clock/PLL dependency)
    manifest_deps = manifest_entry.get('dependencies', [])
    has_clock_dep = any(
        d.lower() in ['clock', 'pll'] if isinstance(d, str) else False
        for d in manifest_deps
    )

    if has_clock_dep:
        for file_path in driver_c_files:
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')

                # Check for hardcoded frequency #defines
                freq_patterns = [
                    r'#define\s+\w*(?:VCLK|CLK|FREQUENCY|FREQ)\w*\s+\d+',
                    r'#define\s+\w+\s+\d{8,}U?L?L?\s*(?://.*frequency|/\*.*frequency)',
                ]

                for pattern in freq_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        errors.append(
                            f"{file_path.name}: Hardcoded frequency constant found: {matches[0]}. "
                            "Use PLL_GetFrequency() instead."
                        )
                        break

            except Exception:
                pass

    # Check 8: PLL_GetFrequency() usage for baud rate functions (if module has clock dependency)
    if has_clock_dep:
        for file_path in driver_c_files:
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')

                # Check if file has baud rate or prescaler functions
                has_baud_func = re.search(
                    r'\b(?:set_?baud|baud_?rate|set_?prescaler|configure_?timing)\b',
                    content,
                    re.IGNORECASE
                )

                if has_baud_func:
                    # Check if PLL_GetFrequency() or clock_get_hz() is called
                    if 'PLL_GetFrequency' not in content and 'clock_get_hz' not in content:
                        errors.append(
                            f"{file_path.name}: Has baud rate/timing function but doesn't call PLL_GetFrequency(). "
                            "Frequency must be queried dynamically, not hardcoded."
                        )

            except Exception:
                pass

    # Check 9: pll_driver.h include if module has PLL dependency
    if has_clock_dep:
        for file_path in driver_c_files:
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')

                # Check for pll_driver.h or clock.h include
                has_pll_include = '#include "pll_driver.h"' in content or '#include <pll_driver.h>' in content
                has_clock_include = '#include "clock.h"' in content or '#include <clock.h>' in content

                if not has_pll_include and not has_clock_include:
                    errors.append(
                        f"{file_path.name}: Module has 'PLL' or 'clock' dependency but doesn't include pll_driver.h or clock.h"
                    )

            except Exception:
                pass

    # Check 10: PLL-specific build-readiness checks (behavior-first, tokens second)
    if module_name.upper() == "PLL":
        pll_contract_cfg = bringup_contract.get("pll", {}) if isinstance(bringup_contract, dict) else {}
        pll_init_profile = (
            str(pll_contract_cfg.get("init_profile", "")).strip().lower()
            if isinstance(pll_contract_cfg, dict)
            else ""
        )
        freq_decode_cfg = pll_contract_cfg.get("frequency_decode", {}) if isinstance(pll_contract_cfg, dict) else {}
        required_sequence = pll_contract_cfg.get("required_sequence", []) if isinstance(pll_contract_cfg, dict) else []

        for file_path in driver_c_files:
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                pll_getfreq_body = _extract_function_body(content, "PLL_GetFrequency")
                pll_init_body = _extract_function_body(content, "PLL_Init")

                if pll_getfreq_body:
                    if not _function_or_called_helper_mentions_token(content, "PLL_GetFrequency", "GHVSRC"):
                        errors.append(
                            f"{file_path.name}: PLL_GetFrequency() does not reference GHVSRC. "
                            "Frequency must account for active clock source selection."
                        )

                # Catch obvious hardcoded HCLK style constants that hide clock-source issues.
                if re.search(r'#define\s+\w*HCLK\w*\s+\d{6,}', content, re.IGNORECASE):
                    warnings.append(
                        f"{file_path.name}: Contains hardcoded HCLK-like constant. "
                        "Prefer runtime derivation from PLL/GHVSRC registers."
                    )

                if isinstance(required_sequence, list) and required_sequence:
                    target_blob = pll_init_body if isinstance(pll_init_body, str) and pll_init_body else content
                    errors.extend(_validate_pll_required_sequence(file_path.name, target_blob, required_sequence))

                if pll_init_profile == "rm46_hal_aligned":
                    target_blob = pll_init_body if isinstance(pll_init_body, str) and pll_init_body else content
                    required_hal_tokens = ["GLBSTAT", "PLLCTL1", "PLLCTL2", "CSDIS", "CDDIS", "GHVSRC", "RCLKSRC", "VCLKASRC", "CLKCNTL", "PENA"]
                    missing_hal = [tok for tok in required_hal_tokens if tok not in target_blob]
                    if missing_hal:
                        errors.append(
                            f"{file_path.name}: Missing rm46_hal_aligned PLL init tokens: "
                            + ", ".join(missing_hal)
                        )
                    if not _contains_literal_or_alias(target_blob, "0x00000301", ["HAL_ALIGNED_GLBSTAT_CLEAR_VALUE", "RM46_GLBSTAT_CLEAR_MASK"]):
                        errors.append(
                            f"{file_path.name}: Missing rm46_hal_aligned GLBSTAT clear checkpoint (0x00000301 or alias)."
                        )
                    if not _contains_literal_or_alias(target_blob, "0x0000008C", ["HAL_ALIGNED_CSDIS_VALUE", "RM46_PLL_CSDIS_SNAPSHOT"]):
                        errors.append(
                            f"{file_path.name}: Missing rm46_hal_aligned CSDIS snapshot/checkpoint (0x0000008C or alias)."
                        )
                    if not _contains_literal_or_alias(target_blob, "0x00000020", ["HAL_ALIGNED_CDDIS_VALUE", "RM46_PLL_CDDIS_SNAPSHOT"]):
                        errors.append(
                            f"{file_path.name}: Missing rm46_hal_aligned CDDIS snapshot/checkpoint (0x00000020 or alias)."
                        )
                    has_csvstat_poll = (
                        "CSVSTAT" in target_blob
                        or "wait_for_pll_lock(" in target_blob
                        or "wait_for_pll1_lock(" in target_blob
                        or "wait_for_pll2_lock(" in target_blob
                    )
                    if not has_csvstat_poll:
                        errors.append(
                            f"{file_path.name}: Missing rm46_hal_aligned PLL lock/CSVSTAT polling path."
                        )

                if _is_trm_dynamic_profile(pll_init_profile) and not (
                    isinstance(freq_decode_cfg, dict) and bool(freq_decode_cfg)
                ):
                    errors.extend(
                        _validate_trm_dynamic_pll_behavior(
                            file_path.name,
                            pll_init_body,
                            pll_getfreq_body,
                            require_enable_disable_sequence=True,
                        )
                    )

                if isinstance(freq_decode_cfg, dict) and freq_decode_cfg:
                    required_behavior = freq_decode_cfg.get("required_behavior", {})
                    if not isinstance(required_behavior, dict):
                        required_behavior = {}

                    require_trm_field_decoding = _is_trm_dynamic_profile(pll_init_profile)
                    require_trm_enable_disable = _is_trm_dynamic_profile(pll_init_profile)

                    if require_trm_field_decoding or require_trm_enable_disable:
                        errors.extend(
                            _validate_trm_dynamic_pll_behavior(
                                file_path.name,
                                pll_init_body,
                                pll_getfreq_body,
                                require_enable_disable_sequence=require_trm_enable_disable,
                            )
                        )

                    allow_hal_encoded = bool(freq_decode_cfg.get("allow_hal_encoded_pllmul", False))
                    if allow_hal_encoded and "supports_hal_encoded_pllmul_literal" not in required_behavior:
                        required_behavior["supports_hal_encoded_pllmul_literal"] = True

                    if bool(required_behavior.get("supports_hal_encoded_pllmul_literal", False)):
                        if not _has_hal_decode_guard(content):
                            errors.append(
                                f"{file_path.name}: Missing HAL-encoded PLLMUL literal/decode guard required by bring-up contract."
                            )

                    if bool(required_behavior.get("uses_hal_literal_hclk_override", False)):
                        hal_hclk = _parse_contract_int(freq_decode_cfg.get("hal_literal_hclk_hz"))
                        if hal_hclk is None:
                            errors.append(
                                f"{file_path.name}: bring-up contract requires HAL literal HCLK override, but hal_literal_hclk_hz is missing/invalid."
                            )
                        else:
                            hal_hclk_hex = f"0x{hal_hclk:X}"
                            has_hclk_literal = (
                                str(hal_hclk) in content
                                or hal_hclk_hex.lower() in content.lower()
                            )
                            if not has_hclk_literal:
                                errors.append(
                                    f"{file_path.name}: Missing HAL literal HCLK override value {hal_hclk} required by bring-up contract."
                                )

                    if bool(required_behavior.get("uses_uint64_intermediate_math", False)):
                        has_uint64 = (
                            "uint64_t" in content
                            or re.search(r"\(\s*uint64_t\s*\)", content) is not None
                        )
                        if not has_uint64:
                            errors.append(
                                f"{file_path.name}: Missing uint64_t intermediate math in PLL frequency path required by bring-up contract."
                            )

                    if bool(required_behavior.get("derives_active_source_from_ghvsrc", False)):
                        if not _function_or_called_helper_mentions_token(content, "PLL_GetFrequency", "GHVSRC"):
                            errors.append(
                                f"{file_path.name}: Missing GHVSRC-driven active-source derivation in PLL_GetFrequency() required by bring-up contract."
                            )

                    # Keep required token checks as secondary hints (warning-level).
                    required_decode_tokens = freq_decode_cfg.get("required_tokens", [])
                    if isinstance(required_decode_tokens, list):
                        missing = [
                            token
                            for token in required_decode_tokens
                            if isinstance(token, str) and token and token not in content
                        ]
                        if missing:
                            warnings.append(
                                f"{file_path.name}: Missing optional PLL frequency-decode tokens: "
                                + ", ".join(missing)
                            )
            except Exception:
                pass

    # Check 11: LIN-specific SCI mode bring-up checks
    if module_name.upper() == "LIN":
        expected_scipio0 = 0x6
        lin_contract_cfg = bringup_contract.get("lin", {}) if isinstance(bringup_contract, dict) else {}
        if isinstance(lin_contract_cfg, dict):
            required_regs = lin_contract_cfg.get("required_registers", {})
            if isinstance(required_regs, dict):
                scipio0_rule = required_regs.get("SCIPIO0", {})
                if isinstance(scipio0_rule, dict):
                    parsed_value = _parse_contract_int(scipio0_rule.get("required_value"))
                    if parsed_value is not None:
                        expected_scipio0 = parsed_value

        for file_path in driver_c_files:
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')

                # Ensure SCIPIO0 config includes TX/RX functional bits (bit2 + bit1).
                if 'LIN_Init' in content and 'SCIPIO0' in content:
                    has_hex_mode = re.search(
                        rf'SCIPIO0\s*=\s*0x0*{expected_scipio0:X}U?',
                        content,
                        re.IGNORECASE,
                    ) is not None
                    expected_bits = [bit for bit in range(0, 32) if (expected_scipio0 >> bit) & 0x1]
                    has_bit_mode = all(
                        re.search(rf'1U?\s*<<\s*{bit}U?', content) is not None
                        for bit in expected_bits
                    )
                    has_macro_mode = False
                    for assign in re.finditer(r'SCIPIO0\s*[\|\&]?=\s*([^;]+);', content):
                        rhs = assign.group(1)
                        macro_tokens = re.findall(r'\b[A-Za-z_]\w*SCIPIO0\w*\b', rhs)
                        if macro_tokens and any(op in rhs for op in ('|', '&', '~', '<<')):
                            has_macro_mode = True
                            break
                    if not has_hex_mode and not has_bit_mode and not has_macro_mode:
                        errors.append(
                            f"{file_path.name}: LIN_Init() does not configure SCIPIO0 for SCI TX/RX "
                            f"(expected 0x{expected_scipio0:08X})."
                        )

                # Hard guard: when LIN is configured in SCI mode, SCIPIO0 TX/RX functional bits
                # must not be gated on optional pin_config booleans.
                scipio0_conditional = re.search(
                    r"SCIPIO0\s*=\s*[^;]*(tx_functional_mode|rx_functional_mode|tx_func_mode|rx_func_mode)[^;]*;",
                    content,
                    re.IGNORECASE,
                ) is not None
                if scipio0_conditional:
                    errors.append(
                        f"{file_path.name}: LIN SCI mode must force SCIPIO0 TX/RX functional bits unconditionally; "
                        "do not gate SCIPIO0 on pin_config functional-mode booleans."
                    )

                lin_rx_def = re.search(r'LIN_ReceiveByte\s*\(([^)]*)\)\s*\{', content)
                lin_rx_arity = _count_params(lin_rx_def.group(1)) if lin_rx_def else -1

                # Enforce non-blocking branch for timeout_ms == 0 only when timeout-aware API is present.
                if 'LIN_ReceiveByte' in content and lin_rx_arity >= 2:
                    if ('timeout_ms == 0' not in content) and ('timeout_ms==0' not in content):
                        errors.append(
                            f"{file_path.name}: LIN_ReceiveByte() missing explicit timeout_ms==0 non-blocking path."
                        )

                # Canonical ABI requirement: timeout-aware signature
                if not re.search(r'LIN_ReceiveByte\s*\(\s*uint8_t\s*\*\s*\w+\s*,\s*uint32_t\s+\w+\s*\)', content):
                    warnings.append(
                        f"{file_path.name}: LIN_ReceiveByte() does not match preferred timeout-aware "
                        f"signature. Acceptable if equivalent RX-byte API is used consistently."
                    )

                # Hard fail: timeout logic references timeout_ms without declaring it.
                lin_rx_block = re.search(
                    r'LIN_ReceiveByte\s*\(\s*uint8_t\s*\*\s*\w+\s*\)\s*\{([\s\S]*?)\n\s*\}',
                    content,
                )
                if lin_rx_block and re.search(r'\btimeout_ms\b', lin_rx_block.group(1)):
                    errors.append(
                        f"{file_path.name}: LIN_ReceiveByte() references timeout_ms but signature has no timeout parameter."
                    )

                # TX loop must not fail because RX is empty; this truncates startup banners to first byte.
                lin_tx_body = _extract_function_body(content, "LIN_Transmit")
                if lin_tx_body:
                    bad_status_gate = (
                        "LIN_GetStatus(" in lin_tx_body
                        and "LIN_STATUS_TX_EMPTY" in lin_tx_body
                        and "LIN_STATUS_RX_EMPTY" not in lin_tx_body
                    )
                    if bad_status_gate:
                        errors.append(
                            f"{file_path.name}: LIN_Transmit() treats RX-empty state as TX failure. "
                            "Allow RX_EMPTY in transmit loop or check only TX-relevant error flags."
                        )
            except Exception:
                pass

    # Check 12: IOMM bring-up path contract (unlock sequence + required pins)
    if module_name.upper() == "IOMM" and isinstance(bringup_contract, dict):
        iomm_cfg = bringup_contract.get("iomm", {})
        serial_cfg = bringup_contract.get("serial", {})
        required_pins = serial_cfg.get("required_pins", []) if isinstance(serial_cfg, dict) else []
        unlock_seq = iomm_cfg.get("unlock_sequence", []) if isinstance(iomm_cfg, dict) else []
        require_unlock_for_pin_config = True
        require_lock_after_pin_config = True
        configurepin_self_managed_locking = True
        if isinstance(iomm_cfg, dict):
            require_unlock_for_pin_config = bool(iomm_cfg.get("require_unlock_for_pin_config", True))
            require_lock_after_pin_config = bool(iomm_cfg.get("require_lock_after_pin_config", True))
            configurepin_self_managed_locking = bool(iomm_cfg.get("configurepin_self_managed_locking", True))
        for file_path in driver_c_files:
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                for unlock_val in unlock_seq:
                    value_int = _parse_contract_int(unlock_val)
                    if value_int is None:
                        continue
                    hex_token = f"0x{value_int:08X}"
                    if hex_token not in content and hex_token.lower() not in content.lower():
                        errors.append(
                            f"{file_path.name}: Missing IOMM unlock sequence value {hex_token} required by bring-up contract."
                        )

                for pin_entry in required_pins:
                    if not isinstance(pin_entry, dict):
                        continue
                    pin_num = pin_entry.get("pin")
                    bit_num = pin_entry.get("bit")
                    reg_name = pin_entry.get("register")
                    if isinstance(pin_num, int):
                        pin_pattern = rf"\b{pin_num}\b"
                        if re.search(pin_pattern, content) is None:
                            errors.append(
                                f"{file_path.name}: Missing required pin mapping for package pin {pin_num}."
                            )
                    if isinstance(bit_num, int):
                        bit_pattern = rf"\b{bit_num}\b"
                        if re.search(bit_pattern, content) is None:
                            warnings.append(
                                f"{file_path.name}: Could not confirm required bit position {bit_num} for bring-up pin mapping."
                            )
                    if isinstance(reg_name, str) and reg_name.strip():
                        if reg_name not in content:
                            warnings.append(
                                f"{file_path.name}: Register token '{reg_name}' not present; ensure mapping uses equivalent resolved index."
                            )

                # Enforce one-hot AF encoding in IOMM_ConfigurePin path.
                has_one_hot_encode = (
                    re.search(r"\b[A-Za-z_][A-Za-z0-9_]*\s*=\s*\(\s*1U\s*<<\s*\(uint32_t\)\s*[^)]+\)\s*;", content) is not None
                    or re.search(r"\(\s*1U\s*<<\s*\(uint32_t\)\s*[^)]+\)\s*&\s*0xFFU", content) is not None
                    or re.search(r"1U\s*<<\s*\(uint32_t\)\s*configs\s*\[[^\]]+\]\s*\.\s*function", content) is not None
                )
                if not has_one_hot_encode:
                    errors.append(
                        f"{file_path.name}: IOMM_ConfigurePin() must use one-hot AF encoding "
                        "(e.g., function_value = (1U << (uint32_t)function))."
                    )

                if configurepin_self_managed_locking:
                    configurepin_body = _extract_function_body(content, "IOMM_ConfigurePin")
                    if configurepin_body is None:
                        errors.append(
                            f"{file_path.name}: Missing IOMM_ConfigurePin() implementation required for bring-up locking checks."
                        )
                    else:
                        if require_unlock_for_pin_config:
                            unlock_idx = configurepin_body.find("IOMM_Unlock(")
                            if unlock_idx < 0:
                                errors.append(
                                    f"{file_path.name}: IOMM_ConfigurePin() must call IOMM_Unlock() before pin-mux writes."
                                )
                            else:
                                first_pin_write_idx = len(configurepin_body)
                                for token in ("reg_value = *pinmmr_reg", "*pinmmr_reg =", "IOMM_PINMMR("):
                                    idx = configurepin_body.find(token)
                                    if idx >= 0 and idx < first_pin_write_idx:
                                        first_pin_write_idx = idx
                                if first_pin_write_idx != len(configurepin_body) and unlock_idx > first_pin_write_idx:
                                    errors.append(
                                        f"{file_path.name}: IOMM_Unlock() must occur before first PINMMR access in IOMM_ConfigurePin()."
                                    )

                        if require_lock_after_pin_config:
                            if "IOMM_Lock();" not in configurepin_body:
                                errors.append(
                                    f"{file_path.name}: IOMM_ConfigurePin() must call IOMM_Lock() before returning."
                                )
                            elif not _all_returns_guarded_by_lock(configurepin_body):
                                errors.append(
                                    f"{file_path.name}: Every return path in IOMM_ConfigurePin() must be guarded by IOMM_Lock()."
                                )

                # Validate required pin mapping table entries against bring-up contract.
                # Accept either exact required bit (direct-bit mapping) or 8-bit field base
                # when one-hot encoding is used.
                pin_map_entries = {}
                for match in re.finditer(
                    r"\{\s*\.package_pin\s*=\s*(\d+)\s*,\s*\.pinmmr_reg\s*=\s*(\d+)\s*,\s*\.bit_position\s*=\s*(\d+)\s*\}",
                    content,
                ):
                    pin_map_entries[int(match.group(1))] = (int(match.group(2)), int(match.group(3)))

                if not pin_map_entries:
                    warnings.append(
                        f"{file_path.name}: Could not parse designated pin mapping entries; "
                        "required-pin mapping checks were reduced to token-level validation."
                    )
                    continue

                for pin_entry in required_pins:
                    if not isinstance(pin_entry, dict):
                        continue
                    pin_num = pin_entry.get("pin")
                    reg_name = pin_entry.get("register")
                    req_bit = pin_entry.get("bit")
                    if not isinstance(pin_num, int):
                        continue
                    if pin_num not in pin_map_entries:
                        errors.append(
                            f"{file_path.name}: Missing required pin mapping table entry for package pin {pin_num}."
                        )
                        continue

                    map_reg_idx, map_bit = pin_map_entries[pin_num]
                    reg_match = re.match(r"PINMMR(\d+)$", str(reg_name or "").strip(), re.IGNORECASE)
                    if reg_match:
                        req_reg_idx = int(reg_match.group(1))
                        if map_reg_idx != req_reg_idx:
                            errors.append(
                                f"{file_path.name}: Pin {pin_num} mapped to PINMMR{map_reg_idx}, "
                                f"expected PINMMR{req_reg_idx}."
                            )

                    if isinstance(req_bit, int):
                        field_base = req_bit - (req_bit % 8)
                        if map_bit not in (req_bit, field_base):
                            errors.append(
                                f"{file_path.name}: Pin {pin_num} bit_position {map_bit} does not match required "
                                f"bit {req_bit} (or field base {field_base} for one-hot encoding)."
                            )
            except Exception:
                pass

    # Check 13: Reserved for additional module checks.

    is_valid = len(errors) == 0 and not has_todos

    return Pass2ValidationResult(
        is_valid=is_valid,
        critical_errors=errors,
        warnings=warnings,
        has_todos=has_todos
    )


def validate_dependency_identifiers(module_name: str, source_code: str,
                                   dependency_manifests: Dict) -> List[str]:
    """
    Validate that generated code uses only declared dependency identifiers.

    Checks for:
    - Undefined enum constants (e.g., IOMM_PIN_FUNCTION_1 instead of IOMM_PIN_FUNC_ALT1)
    - Fabricated function names not in the manifest
    - Common pattern mismatches

    Args:
        module_name: Name of the module being validated
        source_code: Generated C source code
        dependency_manifests: Dict of dependency module manifests

    Returns:
        List of error strings describing validation failures. Empty list = success.
    """
    errors = []

    if not dependency_manifests:
        # No dependencies to validate
        return errors

    for dep_name, dep_manifest in dependency_manifests.items():
        # Build set of valid identifiers from manifest
        valid_identifiers = set()

        # Add all enum values
        for type_def in dep_manifest.get('types', []):
            if type_def.get('type') == 'enum':
                enum_values = type_def.get('values', [])
                valid_identifiers.update(enum_values)

        # Add function names (both short and full module-prefixed names)
        for func in dep_manifest.get('functions', []):
            func_name = func.get('name', '')
            if func_name:
                # Add both "Unlock" and "IOMM_Unlock" style names
                valid_identifiers.add(func_name)
                if '_' not in func_name:
                    full_name = f"{dep_name}_{func_name}"
                    valid_identifiers.add(full_name)

        # IOMM-specific validation
        if dep_name.upper() == 'IOMM':
            # Check for fabricated IOMM_PIN_FUNCTION_\d pattern
            bad_pattern = re.compile(r'\bIOMM_PIN_FUNCTION_\d+\b')
            matches = bad_pattern.findall(source_code)
            if matches:
                valid_names = [v for v in valid_identifiers if 'PIN_FUNC' in v]
                errors.append(
                    f"{module_name}: Uses undefined IOMM enum values: {set(matches)}. "
                    f"Should use one of: {valid_names}"
                )

            # Check for other common IOMM fabrication patterns
            # Pattern: IOMM_PIN_FUNCTION_GPIO, IOMM_PIN_FUNCTION_ALT1, etc.
            bad_pattern2 = re.compile(r'\bIOMM_PIN_FUNCTION_(GPIO|ALT\d+)\b')
            matches2 = bad_pattern2.findall(source_code)
            if matches2:
                # matches2 will be just the suffix (GPIO, ALT1, etc.)
                full_matches = [f"IOMM_PIN_FUNCTION_{m}" for m in matches2]
                valid_names = [v for v in valid_identifiers if 'PIN_FUNC' in v]
                errors.append(
                    f"{module_name}: Uses undefined IOMM enum values: {set(full_matches)}. "
                    f"Should use one of: {valid_names}"
                )

            # Check for undefined bit field constants like IOMM_PINMMR29_8
            bad_bit_pattern = re.compile(r'\bIOMM_PINMMR\d+_\d+\b')
            bit_matches = bad_bit_pattern.findall(source_code)
            if bit_matches:
                errors.append(
                    f"{module_name}: Uses undefined IOMM register bit constants: {set(bit_matches)}. "
                    f"These constants are not defined in reg_iomm.h. Use direct bit shifts instead."
                )

        # PLL-specific validation (extensibility example)
        if dep_name.upper() == 'PLL':
            # Check for fabricated clock domain names
            bad_clock_pattern = re.compile(r'\bCLOCKDOMAIN_[A-Z0-9_]+\b')
            clock_matches = bad_clock_pattern.findall(source_code)
            if clock_matches:
                # Check if any are invalid
                invalid_domains = [m for m in clock_matches if m not in valid_identifiers]
                if invalid_domains:
                    valid_domains = [v for v in valid_identifiers if v.startswith('CLOCKDOMAIN_')]
                    errors.append(
                        f"{module_name}: Uses undefined PLL clock domains: {set(invalid_domains)}. "
                        f"Valid domains: {valid_domains}"
                    )

    return errors


def validate_void_function_assignments(module_name: str, source_code: str,
                                       dependency_manifests: Dict) -> List[str]:
    """
    Validate that void-returning functions are not assigned to variables.

    Args:
        module_name: Name of the module being validated
        source_code: Generated C source code
        dependency_manifests: Dict of dependency module manifests

    Returns:
        List of error strings for void function assignments. Empty list = success.
    """
    errors = []

    if not dependency_manifests:
        return errors

    # Build map of function_name -> return_type
    void_functions = {}
    for dep_name, dep_manifest in dependency_manifests.items():
        for func in dep_manifest.get('functions', []):
            func_name = func.get('name', '')
            prototype = func.get('prototype', '')

            # Parse return type from prototype
            if prototype:
                # Extract return type (everything before function name)
                # Example: "void IOMM_Unlock(void);"
                parts = prototype.split('(')[0].strip().split()
                if len(parts) >= 2:
                    return_type = ' '.join(parts[:-1])
                    if return_type == 'void':
                        # Add both short and full names
                        void_functions[func_name] = return_type
                        if '_' not in func_name:
                            full_name = f"{dep_name}_{func_name}"
                            void_functions[full_name] = return_type

    # Check for assignments of void functions
    for func_name in void_functions:
        # Pattern: "variable = FunctionName(...);"
        pattern = rf'\w+\s*=\s*{re.escape(func_name)}\s*\('
        if re.search(pattern, source_code):
            errors.append(
                f"{module_name}: Assigns return value of void function {func_name}(). "
                f"This function returns void and should not be assigned."
            )

    return errors
