#!/usr/bin/env python3
"""
Contract checking for generated headers/sources/helper modules.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from .api_contract_manifest import parse_prototype


PROTOTYPE_RE = re.compile(
    r"^\s*([A-Za-z_][\w\s\*]*?)\s+([A-Za-z_]\w*)\s*\(([^;{}]*)\)\s*;\s*$",
    re.MULTILINE,
)
DEFINITION_RE = re.compile(
    r"^\s*([A-Za-z_][\w\s\*]*?)\s+([A-Za-z_]\w*)\s*\(([^;{}]*)\)\s*\{",
    re.MULTILINE,
)
LIN_CFG_FIELD_RE = re.compile(r"\blin_cfg\.(\w+)\s*=")
SCI_CFG_FIELD_RE = re.compile(r"\bsci_cfg\.(\w+)\s*=")


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def _extract_function_block(text: str, function_name: str) -> Dict[str, str]:
    sig_re = re.compile(
        rf"\b{re.escape(function_name)}\s*\(([^)]*)\)\s*\{{",
        re.MULTILINE,
    )
    match = sig_re.search(text)
    if not match:
        return {}
    open_brace = match.end() - 1
    idx = open_brace + 1
    depth = 1
    while idx < len(text) and depth > 0:
        ch = text[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        idx += 1
    if depth != 0:
        return {}
    return {
        "params": (match.group(1) or "").strip(),
        "body": text[open_brace + 1 : idx - 1],
    }


def _split_top_level_commas(text: str) -> List[str]:
    parts: List[str] = []
    current: List[str] = []
    depth = 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")" and depth > 0:
            depth -= 1
        if ch == "," and depth == 0:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
            continue
        current.append(ch)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _param_arity(param_blob: str) -> int:
    blob = (param_blob or "").strip()
    if not blob or blob == "void":
        return 0
    return len(_split_top_level_commas(blob))


def _parse_function_map(text: str, pattern: re.Pattern[str]) -> Dict[str, Dict[str, Any]]:
    funcs: Dict[str, Dict[str, Any]] = {}
    for match in pattern.finditer(text):
        ret, name, params = match.groups()
        proto = f"{ret.strip()} {name}({params.strip()});"
        parsed = parse_prototype(proto)
        if not parsed:
            parsed = {
                "name": name,
                "return_type": ret.strip(),
                "params": [],
                "arity": _param_arity(params),
                "prototype": proto,
            }
        funcs[name] = parsed
    return funcs


def _collect_callsites(text: str, module_prefixes: List[str]) -> Dict[str, List[int]]:
    callsites: Dict[str, List[int]] = {}
    if not module_prefixes:
        return callsites
    prefix_re = "|".join(re.escape(p) for p in module_prefixes)
    call_re = re.compile(rf"\b(({prefix_re})_[A-Za-z]\w*)\s*\(")
    for match in call_re.finditer(text):
        fname = match.group(1)
        open_idx = match.end() - 1
        idx = open_idx + 1
        depth = 1
        while idx < len(text) and depth > 0:
            if text[idx] == "(":
                depth += 1
            elif text[idx] == ")":
                depth -= 1
            idx += 1
        if depth != 0:
            continue
        args = text[open_idx + 1 : idx - 1]
        arity = _param_arity(args)
        callsites.setdefault(fname, []).append(arity)
    return callsites


def check_generated_module_contract(
    module_name: str,
    header_path: Path,
    source_path: Path,
    api_contract_manifest: Dict[str, Any],
) -> Dict[str, Any]:
    module_upper = module_name.upper()
    errors: List[str] = []
    warnings: List[str] = []
    module_contract = (api_contract_manifest.get("modules") or {}).get(module_upper, {})

    if not module_contract:
        return {
            "module": module_upper,
            "passed": True,
            "errors": [],
            "warnings": [f"{module_upper}: No module contract found"],
        }

    if not header_path.exists() or not source_path.exists():
        return {
            "module": module_upper,
            "passed": False,
            "errors": [f"{module_upper}: Missing generated header/source for contract check"],
            "warnings": [],
        }

    header_text = header_path.read_text(encoding="utf-8", errors="ignore")
    source_text = source_path.read_text(encoding="utf-8", errors="ignore")

    header_funcs = _parse_function_map(header_text, PROTOTYPE_RE)
    source_funcs = _parse_function_map(source_text, DEFINITION_RE)
    expected_funcs = module_contract.get("functions", {})

    for fname, expected in expected_funcs.items():
        header_decl = header_funcs.get(fname)
        source_def = source_funcs.get(fname)
        expected_arity = int(expected.get("arity", 0))

        if not header_decl:
            errors.append(f"{module_upper}: Missing declaration for {fname} in header")
        elif int(header_decl.get("arity", -1)) != expected_arity:
            errors.append(
                f"{module_upper}: Header arity mismatch for {fname} "
                f"(expected {expected_arity}, got {header_decl.get('arity')})"
            )

        if not source_def:
            errors.append(f"{module_upper}: Missing definition for {fname} in source")
        elif int(source_def.get("arity", -1)) != expected_arity:
            errors.append(
                f"{module_upper}: Source arity mismatch for {fname} "
                f"(expected {expected_arity}, got {source_def.get('arity')})"
            )

    for fname, header_decl in header_funcs.items():
        if not fname.startswith(f"{module_upper}_"):
            continue
        source_def = source_funcs.get(fname)
        if source_def and header_decl.get("arity") != source_def.get("arity"):
            errors.append(
                f"{module_upper}: Header/source prototype drift for {fname} "
                f"({header_decl.get('arity')} args vs {source_def.get('arity')} args)"
            )

    source_text_no_comments = _strip_comments(source_text)

    # Validate internal callsites against source definitions.
    internal_calls = _collect_callsites(source_text_no_comments, [module_upper])
    for fname, arities in internal_calls.items():
        source_def = source_funcs.get(fname)
        if not source_def:
            continue
        expected_arity = int(source_def.get("arity", 0))
        for got_arity in arities:
            if got_arity != expected_arity:
                errors.append(
                    f"{module_upper}: Internal call arity mismatch for {fname} "
                    f"(definition expects {expected_arity}, call uses {got_arity})"
                )

    # Deterministic declared-symbol gate for dependency calls.
    known_functions: Dict[str, int] = {}
    modules = api_contract_manifest.get("modules", {})
    for contract in modules.values():
        for fname, sig in (contract.get("functions") or {}).items():
            known_functions[fname] = int(sig.get("arity", 0))
        for wrapper in contract.get("compatibility_wrappers", []):
            w_name = wrapper.get("name")
            if w_name:
                known_functions[w_name] = int(wrapper.get("arity", 0))

    cross_calls = _collect_callsites(source_text_no_comments, list(modules.keys()))
    for fname, arities in cross_calls.items():
        module_prefix = fname.split("_", 1)[0] if "_" in fname else ""
        if module_prefix == module_upper:
            continue

        if fname not in known_functions:
            errors.append(f"{module_upper}: Unknown dependency API call {fname}()")
            continue

        expected_arity = known_functions[fname]
        for got_arity in arities:
            if got_arity != expected_arity:
                errors.append(
                    f"{module_upper}: Dependency API arity mismatch for {fname} "
                    f"(expected {expected_arity}, got {got_arity})"
                )

    if module_upper == "LIN" and "LIN_ReceiveByte" in source_funcs:
        block = _extract_function_block(source_text_no_comments, "LIN_ReceiveByte")
        if block:
            params = block.get("params", "")
            body = block.get("body", "")
            if "timeout_ms" in body and "timeout_ms" not in params:
                errors.append(
                    "LIN: LIN_ReceiveByte uses timeout_ms in body but signature does not declare timeout_ms"
                )

    return {
        "module": module_upper,
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def check_bsp_validate_contract(
    bsp_validate_path: Path,
    api_contract_manifest: Dict[str, Any],
) -> Dict[str, Any]:
    if not bsp_validate_path.exists():
        return {
            "module": "BSP_VALIDATE",
            "passed": True,
            "errors": [],
            "warnings": ["bsp_validate.c not generated"],
        }

    text = bsp_validate_path.read_text(encoding="utf-8", errors="ignore")
    errors: List[str] = []
    warnings: List[str] = []
    modules = api_contract_manifest.get("modules", {})

    known: Dict[str, int] = {}
    for module_name, contract in modules.items():
        for fname, sig in (contract.get("functions") or {}).items():
            known[fname] = int(sig.get("arity", 0))
        for wrapper in contract.get("compatibility_wrappers", []):
            w_name = wrapper.get("name")
            if w_name:
                known[w_name] = int(wrapper.get("arity", 0))

    text_no_comments = _strip_comments(text)
    calls = _collect_callsites(text_no_comments, list(modules.keys()))
    for fname, arities in calls.items():
        module_prefix = fname.split("_", 1)[0] if "_" in fname else ""
        if fname not in known:
            if module_prefix == "LIN":
                errors.append(f"BSP_VALIDATE: Unknown API call {fname}()")
            else:
                warnings.append(f"BSP_VALIDATE: Unknown API call {fname}()")
            continue
        expected = known[fname]
        for got in arities:
            if got != expected:
                msg = (
                    f"BSP_VALIDATE: API arity mismatch for {fname} "
                    f"(expected {expected}, got {got})"
                )
                if module_prefix == "LIN":
                    errors.append(msg)
                else:
                    warnings.append(msg)

    lin_contract = modules.get("LIN", {})
    lin_types = lin_contract.get("types", {})
    lin_cfg = lin_types.get("lin_config_t", {})
    allowed_fields = {
        f.get("name") for f in lin_cfg.get("fields", []) if isinstance(f, dict) and f.get("name")
    }
    if allowed_fields:
        for field in LIN_CFG_FIELD_RE.findall(text):
            if field not in allowed_fields:
                errors.append(f"BSP_VALIDATE: lin_cfg.{field} is not in lin_config_t contract")
    else:
        warnings.append("BSP_VALIDATE: LIN contract missing lin_config_t fields")

    # Guard against silent terminal-output regressions:
    # when LIN config exposes pin_config functional-mode fields, BSP validate must enable them.
    if "pin_config" in allowed_fields:
        pin_cfg_field = next(
            (
                f
                for f in (lin_cfg.get("fields", []) or [])
                if isinstance(f, dict) and f.get("name") == "pin_config"
            ),
            None,
        )
        pin_cfg_type = str((pin_cfg_field or {}).get("type", ""))
        pin_cfg = lin_types.get(pin_cfg_type, {}) if pin_cfg_type else {}
        pin_cfg_fields = {
            f.get("name")
            for f in (pin_cfg.get("fields", []) if isinstance(pin_cfg, dict) else [])
            if isinstance(f, dict) and f.get("name")
        }
        required_functional_fields = [
            name
            for name in ("tx_functional_mode", "tx_func_mode", "rx_functional_mode", "rx_func_mode")
            if name in pin_cfg_fields
        ]
        for field in required_functional_fields:
            if not re.search(
                rf"\blin_cfg\.pin_config\.{re.escape(field)}\s*=\s*true\s*;",
                text_no_comments,
            ):
                errors.append(
                    f"BSP_VALIDATE: lin_cfg.pin_config.{field} must be set true for LIN/SCI functional mode"
                )

    sci_contract = modules.get("SCI", {})
    sci_types = sci_contract.get("types", {})
    sci_cfg = sci_types.get("sci_config_t", {})
    sci_allowed_fields = {
        f.get("name") for f in sci_cfg.get("fields", []) if isinstance(f, dict) and f.get("name")
    }
    if sci_allowed_fields:
        for field in SCI_CFG_FIELD_RE.findall(text):
            if field not in sci_allowed_fields:
                errors.append(f"BSP_VALIDATE: sci_cfg.{field} is not in sci_config_t contract")
    else:
        warnings.append("BSP_VALIDATE: SCI contract missing sci_config_t fields")

    return {
        "module": "BSP_VALIDATE",
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }
