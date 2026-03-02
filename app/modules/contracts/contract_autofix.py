#!/usr/bin/env python3
"""
Deterministic autofixes for generated API drift.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..utils.file_io import normalize_generated_text


def _module_contract(api_contract_manifest: Dict[str, Any], module: str) -> Dict[str, Any]:
    return (api_contract_manifest.get("modules") or {}).get(module.upper(), {})


def _defined_macros(header_text: str) -> set[str]:
    return {
        name
        for name in re.findall(r"^\s*#define\s+([A-Za-z_]\w*)\b", header_text, flags=re.MULTILINE)
    }


def _lin_contract(api_contract_manifest: Dict[str, Any]) -> Dict[str, Any]:
    return _module_contract(api_contract_manifest, "LIN")


def _lin_enum_value(api_contract_manifest: Dict[str, Any], enum_type_name: str, contains: str) -> Optional[str]:
    lin_types = _lin_contract(api_contract_manifest).get("types", {})
    enum_def = lin_types.get(enum_type_name, {})
    values = enum_def.get("values", [])
    for value in values:
        if contains in value:
            return value
    return values[0] if values else None


def _capability_fn(module_contract: Dict[str, Any], key: str, candidates: List[str], fallback: str) -> str:
    caps = module_contract.get("capabilities", {}) if isinstance(module_contract, dict) else {}
    name = caps.get(key)
    if isinstance(name, str) and name:
        return name

    functions = module_contract.get("functions", {}) if isinstance(module_contract, dict) else {}
    wrappers = {
        w.get("name")
        for w in module_contract.get("compatibility_wrappers", [])
        if isinstance(w, dict) and w.get("name")
    } if isinstance(module_contract, dict) else set()

    for cand in candidates:
        if cand in functions or cand in wrappers:
            return cand
    return fallback


def _signature_decl(sig: Dict[str, Any]) -> str:
    ret = sig.get("return_type", "void")
    name = sig.get("name", "")
    params = sig.get("params", [])
    if not params:
        return f"{ret} {name}(void);"
    blob = ", ".join(f"{p.get('type', 'void')} {p.get('name', 'arg')}".strip() for p in params)
    return f"{ret} {name}({blob});"


def _signature_def(sig: Dict[str, Any]) -> str:
    return _signature_decl(sig).rstrip(";")


def _split_top_level_args(arg_blob: str) -> List[str]:
    args: List[str] = []
    cur: List[str] = []
    depth_paren = 0
    depth_bracket = 0
    depth_brace = 0
    in_string = False
    in_char = False
    escape = False

    for ch in arg_blob:
        if in_string or in_char:
            cur.append(ch)
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if in_string and ch == '"':
                in_string = False
            elif in_char and ch == "'":
                in_char = False
            continue

        if ch == '"':
            in_string = True
            cur.append(ch)
            continue
        if ch == "'":
            in_char = True
            cur.append(ch)
            continue

        if ch == "(":
            depth_paren += 1
            cur.append(ch)
            continue
        if ch == ")":
            depth_paren = max(0, depth_paren - 1)
            cur.append(ch)
            continue
        if ch == "[":
            depth_bracket += 1
            cur.append(ch)
            continue
        if ch == "]":
            depth_bracket = max(0, depth_bracket - 1)
            cur.append(ch)
            continue
        if ch == "{":
            depth_brace += 1
            cur.append(ch)
            continue
        if ch == "}":
            depth_brace = max(0, depth_brace - 1)
            cur.append(ch)
            continue

        if ch == "," and depth_paren == 0 and depth_bracket == 0 and depth_brace == 0:
            args.append("".join(cur).strip())
            cur = []
            continue
        cur.append(ch)

    tail = "".join(cur).strip()
    if tail:
        args.append(tail)
    return args


def _find_matching_paren(text: str, open_idx: int) -> int:
    depth = 0
    in_string = False
    in_char = False
    escape = False

    for idx in range(open_idx, len(text)):
        ch = text[idx]
        if in_string or in_char:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if in_string and ch == '"':
                in_string = False
            elif in_char and ch == "'":
                in_char = False
            continue

        if ch == '"':
            in_string = True
            continue
        if ch == "'":
            in_char = True
            continue

        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return idx
    return -1


def _rewrite_function_calls(
    text: str,
    function_name: str,
    arg_rewriter: Callable[[List[str]], List[str]],
) -> Tuple[str, int]:
    pattern = re.compile(rf"\b{re.escape(function_name)}\s*\(")
    cursor = 0
    parts: List[str] = []
    replacements = 0

    while True:
        match = pattern.search(text, cursor)
        if not match:
            parts.append(text[cursor:])
            break

        open_idx = match.end() - 1
        close_idx = _find_matching_paren(text, open_idx)
        if close_idx < 0:
            parts.append(text[cursor:])
            break

        arg_blob = text[open_idx + 1 : close_idx]
        args = _split_top_level_args(arg_blob)
        new_args = arg_rewriter(args)
        normalized_old = ", ".join(args)
        normalized_new = ", ".join(new_args)

        parts.append(text[cursor : open_idx + 1])
        if normalized_old != normalized_new:
            parts.append(normalized_new)
            replacements += 1
        else:
            parts.append(arg_blob)
        parts.append(")")
        cursor = close_idx + 1

    return "".join(parts), replacements


def autofix_module_contract(
    module_name: str,
    header_path: Path,
    source_path: Path,
    api_contract_manifest: Dict[str, Any],
) -> Dict[str, Any]:
    module_upper = module_name.upper()
    actions: List[str] = []

    if module_upper not in {"LIN", "IOMM"}:
        return {"module": module_upper, "actions": actions}
    if not header_path.exists() or not source_path.exists():
        return {"module": module_upper, "actions": actions}

    if module_upper == "IOMM":
        source_text = source_path.read_text(encoding="utf-8", errors="ignore")
        updated = source_text

        # RM46 PINMMR function fields are one-hot encoded within 8-bit slots.
        updated, n = re.subn(
            r"#define\s+IOMM_FUNCTION_BITS_MASK\s+\(0x07U\)",
            "#define IOMM_FUNCTION_BITS_MASK    (0xFFU)",
            updated,
        )
        if n:
            actions.append("Normalized IOMM function mask to 8-bit one-hot field width")

        updated, n = re.subn(
            r"#define\s+IOMM_BITS_PER_FUNCTION\s+\(3U\)",
            "#define IOMM_BITS_PER_FUNCTION     (8U)",
            updated,
        )
        if n:
            actions.append("Normalized IOMM function field size to 8 bits")

        updated, n = re.subn(
            r"\(\(uint32_t\)function\s*&\s*IOMM_FUNCTION_BITS_MASK\)\s*<<\s*bit_shift",
            "((1U << (uint32_t)function) & IOMM_FUNCTION_BITS_MASK) << bit_shift",
            updated,
        )
        if n:
            actions.append("Converted IOMM single-pin function writes to one-hot encoding")

        # Handle ordinal-style switch assignments (ALT1 -> 0x01, etc.).
        updated, n = re.subn(
            r"\bfunction_value\s*=\s*0x0?[0-7]U\s*;",
            "function_value = (1U << (uint32_t)function);",
            updated,
        )
        if n:
            actions.append("Normalized ordinal IOMM function assignments to one-hot encoding")

        updated, n = re.subn(
            r"\(\(uint32_t\)pin_configs\[i\]\.function\s*&\s*IOMM_FUNCTION_BITS_MASK\)\s*<<\s*bit_shift",
            "((1U << (uint32_t)pin_configs[i].function) & IOMM_FUNCTION_BITS_MASK) << bit_shift",
            updated,
        )
        if n:
            actions.append("Converted IOMM multi-pin function writes to one-hot encoding")

        if updated != source_text:
            source_path.write_text(
                normalize_generated_text(updated, source_path),
                encoding="utf-8",
            )
        return {"module": module_upper, "actions": actions}

    lin_contract = _lin_contract(api_contract_manifest)
    functions = lin_contract.get("functions", {})
    tx_buffer_fn = _capability_fn(lin_contract, "tx_buffer", ["LIN_Transmit", "LIN_SendData", "LIN_Send"], "LIN_Transmit")
    tx_byte_fn = _capability_fn(lin_contract, "tx_byte", ["LIN_TransmitByte", "LIN_SendByte"], "LIN_TransmitByte")
    rx_fn = _capability_fn(lin_contract, "rx_byte", ["LIN_ReceiveByte"], "LIN_ReceiveByte")
    tx_buffer_arity = int((functions.get(tx_buffer_fn, {}) or {}).get("arity", 2))
    tx_byte_arity = int((functions.get(tx_byte_fn, {}) or {}).get("arity", 1))

    header_text = header_path.read_text(encoding="utf-8", errors="ignore")
    source_text = source_path.read_text(encoding="utf-8", errors="ignore")

    new_header = header_text
    new_source = source_text

    expected_rx = functions.get(rx_fn)
    if expected_rx:
        target_rx_arity = int(expected_rx.get("arity", len(expected_rx.get("params", []) or [])))
        rx_decl = _signature_decl(expected_rx)
        rx_def = _signature_def(expected_rx)

        updated = re.subn(
            rf"{re.escape(expected_rx.get('return_type', 'lin_status_t'))}\s+{re.escape(rx_fn)}\s*\([^;]*\)\s*;",
            rx_decl,
            new_header,
        )
        if updated[1] > 0:
            new_header = updated[0]
            actions.append(f"Normalized {rx_fn} declaration in lin_driver.h")

        updated = re.subn(
            rf"{re.escape(expected_rx.get('return_type', 'lin_status_t'))}\s+{re.escape(rx_fn)}\s*\([^)]*\)",
            rx_def,
            new_source,
            count=1,
        )
        if updated[1] > 0:
            new_source = updated[0]
            actions.append(f"Normalized {rx_fn} definition in lin_driver.c")

        if target_rx_arity < 2:
            updated = re.subn(
                rf"\b{re.escape(rx_fn)}\s*\(\s*([^,\)]+)\s*,\s*[^)]*\)",
                rf"{rx_fn}(\1)",
                new_source,
            )
            if updated[1] > 0:
                new_source = updated[0]
                actions.append(f"Normalized {rx_fn} callsites to 1-arg form in lin_driver.c")
        elif target_rx_arity >= 2:
            def _rx_call_arity_repl(match: re.Match[str]) -> str:
                args = match.group(1).strip()
                if "," in args:
                    return f"{rx_fn}({args})"
                return f"{rx_fn}({args}, 0U)"

            updated = re.subn(
                rf"\b{re.escape(rx_fn)}\s*\(([^)]*)\)",
                _rx_call_arity_repl,
                new_source,
            )
            if updated[1] > 0:
                new_source = updated[0]
                actions.append(f"Normalized {rx_fn} callsites to timeout-aware form in lin_driver.c")

    def _append_wrapper(text: str, wrapper_name: str, target_fn: str, args: str, arg_types: str) -> str:
        if f"{wrapper_name}(" in text:
            return text
        if "#endif /* LIN_DRIVER_H */" not in text:
            return text
        wrapper = [
            "",
            f"static inline lin_status_t {wrapper_name}({arg_types})",
            "{",
            f"    return {target_fn}({args});",
            "}",
            "",
        ]
        actions.append(f"Added {wrapper_name} compatibility wrapper in lin_driver.h")
        return text.replace("#endif /* LIN_DRIVER_H */", "\n".join(wrapper) + "#endif /* LIN_DRIVER_H */")

    if tx_buffer_fn:
        tx_buffer_call_args = ["data", "length"]
        while len(tx_buffer_call_args) < tx_buffer_arity:
            tx_buffer_call_args.append("100U" if len(tx_buffer_call_args) >= 2 else "0U")
        tx_buffer_call_expr = ", ".join(tx_buffer_call_args[:tx_buffer_arity])
        send_wrapper_pattern = re.compile(
            r"static\s+inline\s+lin_status_t\s+LIN_Send\s*"
            r"\(\s*const\s+uint8_t\*\s*data\s*,\s*uint32_t\s*length\s*\)\s*"
            r"\{\s*return\s+[A-Za-z_]\w*\s*\([^;]*\);\s*\}",
            re.MULTILINE | re.DOTALL,
        )
        send_wrapper_replacement = (
            "static inline lin_status_t LIN_Send(const uint8_t* data, uint32_t length)\n"
            "{\n"
            f"    return {tx_buffer_fn}({tx_buffer_call_expr});\n"
            "}"
        )
        new_header, n = send_wrapper_pattern.subn(send_wrapper_replacement, new_header)
        if n:
            actions.append("Normalized LIN_Send compatibility wrapper call arity in lin_driver.h")
        new_header = _append_wrapper(
            new_header,
            "LIN_SendData",
            tx_buffer_fn,
            tx_buffer_call_expr,
            "const uint8_t* data, uint32_t length",
        )
        new_header = _append_wrapper(
            new_header,
            "LIN_Send",
            tx_buffer_fn,
            tx_buffer_call_expr,
            "const uint8_t* data, uint32_t length",
        )

    if tx_byte_fn:
        tx_byte_call_args = ["data"]
        while len(tx_byte_call_args) < tx_byte_arity:
            tx_byte_call_args.append("0U")
        new_header = _append_wrapper(
            new_header,
            "LIN_SendByte",
            tx_byte_fn,
            ", ".join(tx_byte_call_args[:tx_byte_arity]),
            "uint8_t data",
        )

    # Normalize LIN clear-interrupt macros against what reg_lin.h actually defines.
    # Some generations emit tokens like LIN_SCICLEARINT_CLR_BRKDT_INT even when reg_lin.h
    # only exposes CLR_BE_INT/CLR_RX_INT/CLR_TX_INT.
    reg_lin_candidates = [
        header_path.parent / "reg_lin.h",
        source_path.parent / "reg_lin.h",
        header_path.parent.parent / "include" / "reg_lin.h",
        source_path.parent.parent / "include" / "reg_lin.h",
    ]
    reg_lin_header = next((p for p in reg_lin_candidates if p.exists()), None)
    if reg_lin_header:
        reg_text = reg_lin_header.read_text(encoding="utf-8", errors="ignore")
        macros = _defined_macros(reg_text)
        clear_macros = sorted(set(re.findall(r"\bLIN_SCICLEARINT_CLR_[A-Z0-9_]+\b", new_source)))
        clear_fallback = "LIN_SCICLEARINT_CLR_BE_INT" if "LIN_SCICLEARINT_CLR_BE_INT" in macros else "0U"
        for macro in clear_macros:
            if macro in macros:
                continue
            new_source, n = re.subn(rf"\b{re.escape(macro)}\b", clear_fallback, new_source)
            if n > 0:
                actions.append(
                    f"Replaced undefined {macro} with {clear_fallback} in lin_driver.c"
                )

    if new_header != header_text:
        header_path.write_text(
            normalize_generated_text(new_header, header_path),
            encoding="utf-8",
        )
    if new_source != source_text:
        source_path.write_text(
            normalize_generated_text(new_source, source_path),
            encoding="utf-8",
        )

    return {"module": module_upper, "actions": actions}


def autofix_bsp_validate(
    bsp_validate_path: Path,
    api_contract_manifest: Dict[str, Any],
) -> Dict[str, Any]:
    actions: List[str] = []
    if not bsp_validate_path.exists():
        return {"module": "BSP_VALIDATE", "actions": actions}

    lin_contract = _module_contract(api_contract_manifest, "LIN")
    gio_contract = _module_contract(api_contract_manifest, "GIO")

    lin_tx_buffer = _capability_fn(lin_contract, "tx_buffer", ["LIN_Transmit", "LIN_SendData", "LIN_Send"], "LIN_Transmit")
    lin_tx_byte = _capability_fn(lin_contract, "tx_byte", ["LIN_TransmitByte", "LIN_SendByte"], "LIN_TransmitByte")
    lin_rx = _capability_fn(lin_contract, "rx_byte", ["LIN_ReceiveByte"], "LIN_ReceiveByte")

    lin_functions = lin_contract.get("functions", {})
    lin_rx_arity = int((lin_functions.get(lin_rx, {}) or {}).get("arity", lin_contract.get("capabilities", {}).get("rx_byte_arity", 2)))
    lin_tx_arity = int((lin_functions.get(lin_tx_buffer, {}) or {}).get("arity", 2))
    lin_tx_byte_arity = int((lin_functions.get(lin_tx_byte, {}) or {}).get("arity", 1))
    sci_contract = _module_contract(api_contract_manifest, "SCI")
    sci_types = sci_contract.get("types", {}) if isinstance(sci_contract, dict) else {}
    sci_cfg_type = sci_types.get("sci_config_t", {}) if isinstance(sci_types.get("sci_config_t", {}), dict) else {}
    sci_cfg_fields_meta = sci_cfg_type.get("fields", []) if isinstance(sci_cfg_type.get("fields", []), list) else []
    sci_cfg_fields = {
        f.get("name")
        for f in sci_cfg_fields_meta
        if isinstance(f, dict) and f.get("name")
    }
    sci_data_bits_type = next(
        (
            f.get("type")
            for f in sci_cfg_fields_meta
            if isinstance(f, dict) and f.get("name") == "data_bits"
        ),
        "",
    )

    gio_cap = gio_contract.get("capabilities", {}) if isinstance(gio_contract, dict) else {}
    gio_cfg_arity = int(gio_cap.get("configure_pin_arity", 3))

    text = bsp_validate_path.read_text(encoding="utf-8", errors="ignore")
    updated = text

    # Normalize LIN tx/rx names to discovered capabilities
    updated, n = re.subn(r"\bLIN_SendData\s*\(", f"{lin_tx_buffer}(", updated)
    if n:
        actions.append(f"Rewrote LIN_SendData() callsites to {lin_tx_buffer}()")

    updated, n = re.subn(r"\bLIN_Send\s*\(", f"{lin_tx_buffer}(", updated)
    if n:
        actions.append(f"Rewrote LIN_Send() callsites to {lin_tx_buffer}()")

    updated, n = re.subn(r"\bLIN_SendByte\s*\(", f"{lin_tx_byte}(", updated)
    if n:
        actions.append(f"Rewrote LIN_SendByte() callsites to {lin_tx_byte}()")

    updated, n = re.subn(r"\bLIN_TransmitByte\s*\(", f"{lin_tx_byte}(", updated)
    if n:
        actions.append(f"Rewrote LIN_TransmitByte() callsites to {lin_tx_byte}()")

    # Repair malformed cast fragments introduced by legacy comma-splitting arity fixes.
    updated, n = re.subn(
        r"\(\s*(u?int(?:8|16|32)_t)\s*,\s*(?:0U|100U)\s*\)\s*\(",
        r"(\1)(",
        updated,
    )
    if n:
        actions.append("Repaired malformed cast fragments from legacy LIN arity normalization in bsp_validate.c")

    # Normalize receive API and timeout argument count
    updated, n = re.subn(r"\bLIN_ReceiveByte\s*\(", f"{lin_rx}(", updated)
    if n:
        actions.append(f"Rewrote LIN_ReceiveByte() callsites to {lin_rx}()")

    def _normalize_arity(args: List[str], target_arity: int, fill_value: str) -> List[str]:
        trimmed = list(args[:target_arity]) if target_arity >= 0 else list(args)
        while len(trimmed) < target_arity:
            trimmed.append(fill_value)
        return trimmed

    updated, n = _rewrite_function_calls(
        updated,
        lin_rx,
        lambda args: _normalize_arity(args, lin_rx_arity, "0U"),
    )
    if n:
        actions.append(f"Normalized {lin_rx}() call arity in bsp_validate.c")

    updated, n = _rewrite_function_calls(
        updated,
        lin_tx_buffer,
        lambda args: _normalize_arity(args, lin_tx_arity, "100U"),
    )
    if n:
        actions.append(f"Normalized {lin_tx_buffer}() call arity in bsp_validate.c")

    updated, n = _rewrite_function_calls(
        updated,
        lin_tx_byte,
        lambda args: _normalize_arity(args, lin_tx_byte_arity, "0U"),
    )
    if n:
        actions.append(f"Normalized {lin_tx_byte}() call arity in bsp_validate.c")

    # GIO configure pin arity fix
    if gio_cfg_arity >= 3:
        updated, n = re.subn(
            r"\bGIO_ConfigurePin\s*\(\s*&led_cfg\s*\)",
            "GIO_ConfigurePin(BSP_VALIDATE_LED_PORT, BSP_VALIDATE_LED_PIN, &led_cfg)",
            updated,
        )
        if n:
            actions.append("Expanded GIO_ConfigurePin(&led_cfg) to 3-arg form")

    # Normalize LIN config fields
    lin_types = _lin_contract(api_contract_manifest).get("types", {})
    cfg_fields = {
        f.get("name")
        for f in (lin_types.get("lin_config_t", {}).get("fields") or [])
        if isinstance(f, dict) and f.get("name")
    }

    data_bits_enum = _lin_enum_value(api_contract_manifest, "lin_data_bits_t", "BITS_8")
    if not data_bits_enum:
        data_bits_enum = _lin_enum_value(api_contract_manifest, "lin_data_bits_t", "_8")
    if not data_bits_enum:
        data_bits_enum = "LIN_DATA_BITS_8"

    new_lines: List[str] = []
    for line in updated.splitlines():
        stripped = line.strip()
        field_match = re.search(r"\blin_cfg\.(\w+)\s*=", stripped)
        if field_match:
            field = field_match.group(1)
            if field == "data_length" and "data_bits" in cfg_fields:
                line = line.replace("lin_cfg.data_length", "lin_cfg.data_bits")
                line = line.replace("LIN_DATA_8BIT", data_bits_enum)
                actions.append("Mapped lin_cfg.data_length to lin_cfg.data_bits in bsp_validate.c")
            elif cfg_fields and field not in cfg_fields:
                actions.append(f"Removed unsupported lin_cfg.{field} assignment from bsp_validate.c")
                continue
        new_lines.append(line)

    updated = "\n".join(new_lines)

    # Ensure pin_config defaults are explicitly set when present in contract.
    # Missing functional-mode fields can silently disable SCI-over-LIN terminal output.
    if "pin_config" in cfg_fields:
        pin_cfg_field = next(
            (
                f
                for f in (lin_types.get("lin_config_t", {}).get("fields", []) or [])
                if isinstance(f, dict) and f.get("name") == "pin_config"
            ),
            None,
        )
        pin_cfg_type = str((pin_cfg_field or {}).get("type", ""))
        pin_cfg_fields = {
            f.get("name")
            for f in (
                lin_types.get(pin_cfg_type, {}).get("fields", [])
                if isinstance(lin_types.get(pin_cfg_type, {}), dict)
                else []
            )
            if isinstance(f, dict) and f.get("name")
        }
        desired_pin_assignments = [
            ("tx_functional_mode", "true"),
            ("rx_functional_mode", "true"),
            ("tx_func_mode", "true"),
            ("rx_func_mode", "true"),
            ("tx_open_drain", "false"),
            ("rx_open_drain", "false"),
            ("open_drain", "false"),
            ("tx_pull_enable", "false"),
            ("rx_pull_enable", "false"),
            ("pull_enable", "false"),
            ("tx_pull_select", "true"),
            ("rx_pull_select", "true"),
            ("pull_select", "true"),
        ]
        pin_lines_to_insert: List[str] = []
        for field_name, field_value in desired_pin_assignments:
            if field_name in pin_cfg_fields and not re.search(
                rf"\blin_cfg\.pin_config\.{re.escape(field_name)}\s*=",
                updated,
            ):
                pin_lines_to_insert.append(f"    lin_cfg.pin_config.{field_name} = {field_value};")

        if pin_lines_to_insert:
            insert_before_match = re.search(
                r"^\s*g_validate_lin_status\s*=.*$",
                updated,
                flags=re.MULTILINE,
            )
            if not insert_before_match:
                insert_before_match = re.search(
                    r"^\s*g_validate_heartbeat_ticks\s*=.*$",
                    updated,
                    flags=re.MULTILINE,
                )
            insert_idx = insert_before_match.start() if insert_before_match else len(updated)
            insertion = "\n".join(pin_lines_to_insert) + "\n"
            updated = updated[:insert_idx] + insertion + updated[insert_idx:]
            actions.append("Inserted missing lin_cfg.pin_config bring-up defaults in bsp_validate.c")

    # Drop unsupported sci_cfg assignments to prevent struct-field drift.
    if sci_cfg_fields:
        sci_lines: List[str] = []
        for line in updated.splitlines():
            stripped = line.strip()
            sci_field_match = re.search(r"\bsci_cfg\.(\w+)\s*=", stripped)
            if sci_field_match:
                sci_field = sci_field_match.group(1)
                if sci_field not in sci_cfg_fields:
                    actions.append(f"Removed unsupported sci_cfg.{sci_field} assignment from bsp_validate.c")
                    continue
            sci_lines.append(line)
        updated = "\n".join(sci_lines)

    if sci_data_bits_type in {"uint8_t", "uint16_t", "uint32_t", "unsigned int", "int"}:
        updated, n = re.subn(
            r"(sci_cfg\.data_bits\s*=\s*)[A-Za-z_][A-Za-z0-9_]*8[A-Za-z0-9_]*\s*;",
            r"\g<1>8U;",
            updated,
        )
        if n:
            actions.append("Normalized sci_cfg.data_bits token assignment to literal 8U in bsp_validate.c")

    if updated != text:
        bsp_validate_path.write_text(
            normalize_generated_text(updated, bsp_validate_path),
            encoding="utf-8",
        )

    return {"module": "BSP_VALIDATE", "actions": actions}
