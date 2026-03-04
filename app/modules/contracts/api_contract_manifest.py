#!/usr/bin/env python3
"""
Build and persist a normalized API contract manifest.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_INVALID_PROTOTYPE_PREFIXES = {
    "return",
    "if",
    "for",
    "while",
    "switch",
    "case",
    "else",
}


def _normalize_space(text: str) -> str:
    return " ".join((text or "").strip().split())


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


def _parse_param(param: str) -> Dict[str, str]:
    p = _normalize_space(param).rstrip()
    if not p or p == "void":
        return {"name": "", "type": "void"}

    raw = p
    if "=" in raw:
        raw = raw.split("=", 1)[0].strip()
    if "[" in raw:
        raw = raw.split("[", 1)[0].strip()

    tokens = raw.split()
    if len(tokens) == 1:
        return {"name": "", "type": tokens[0]}

    name = tokens[-1].strip("*")
    ptype = " ".join(tokens[:-1])
    if tokens[-1].startswith("*"):
        ptype = f"{ptype} *".strip()
    return {"name": name, "type": _normalize_space(ptype)}


def parse_prototype(prototype: str) -> Optional[Dict[str, Any]]:
    proto = _normalize_space((prototype or "").strip().rstrip(";"))
    if not proto or "(" not in proto or ")" not in proto:
        return None
    if proto.startswith("typedef "):
        return None

    open_idx = proto.find("(")
    close_idx = proto.rfind(")")
    if close_idx <= open_idx:
        return None

    prefix = proto[:open_idx].strip()
    param_blob = proto[open_idx + 1 : close_idx].strip()
    prefix_tokens = prefix.split()
    if len(prefix_tokens) < 2:
        return None

    name = prefix_tokens[-1]
    return_type = " ".join(prefix_tokens[:-1]).strip()
    if return_type.lower() in _INVALID_PROTOTYPE_PREFIXES:
        return None
    if name.lower() in _INVALID_PROTOTYPE_PREFIXES:
        return None
    params: List[Dict[str, str]] = []
    if param_blob and param_blob != "void":
        for param in _split_top_level_commas(param_blob):
            parsed = _parse_param(param)
            if parsed["type"] != "void":
                params.append(parsed)

    return {
        "name": name,
        "return_type": _normalize_space(return_type),
        "params": params,
        "arity": len(params),
        "prototype": proto + ";",
    }


def _extract_types(module_entry: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for type_def in module_entry.get("types", []):
        name = type_def.get("name")
        kind = type_def.get("type")
        if not name or not kind:
            continue
        if kind == "struct":
            fields = []
            for member in type_def.get("members", []):
                m_name = member.get("name")
                m_type = member.get("type")
                if not m_name or not m_type:
                    continue
                fields.append({"name": m_name, "type": _normalize_space(m_type)})
            out[name] = {"kind": "struct", "fields": fields}
        elif kind == "enum":
            values = [v for v in type_def.get("values", []) if isinstance(v, str)]
            out[name] = {"kind": "enum", "values": values}
        else:
            out[name] = {"kind": kind}
    return out


def _find_first_fn(functions: Dict[str, Dict[str, Any]], candidates: List[str]) -> Optional[str]:
    for name in candidates:
        if name in functions:
            return name
    return None


def _find_fn_by_contains(
    functions: Dict[str, Dict[str, Any]],
    includes: List[str],
    excludes: Optional[List[str]] = None,
    min_arity: int = 0,
) -> Optional[str]:
    blocked = [token.upper() for token in (excludes or [])]
    for name in sorted(functions.keys()):
        upper = name.upper()
        if not all(token in upper for token in includes):
            continue
        if blocked and any(token in upper for token in blocked):
            continue
        arity = int((functions.get(name, {}) or {}).get("arity", 0))
        if arity < min_arity:
            continue
        return name
    return None


def _derive_module_capabilities(
    module_name: str,
    functions: Dict[str, Dict[str, Any]],
    types: Dict[str, Any],
) -> Dict[str, Any]:
    module_upper = module_name.upper()
    capabilities: Dict[str, Any] = {}

    init_fn = _find_fn_by_contains(functions, ["_INIT"]) or _find_first_fn(functions, [f"{module_upper}_Init"])
    if init_fn:
        capabilities["init"] = init_fn

    if module_upper in {"LIN", "SCI"}:
        if module_upper == "SCI":
            tx_byte_names = [f"{module_upper}_TransmitByte", f"{module_upper}_SendByte", f"{module_upper}_WriteByte"]
            tx_buffer_names = [f"{module_upper}_Transmit", f"{module_upper}_SendData", f"{module_upper}_Send", f"{module_upper}_Write"]
            rx_byte_names = [f"{module_upper}_ReceiveByte", f"{module_upper}_ReadByte"]
        else:
            tx_byte_names = [f"{module_upper}_TransmitByte", f"{module_upper}_SendByte"]
            tx_buffer_names = [f"{module_upper}_Transmit", f"{module_upper}_SendData", f"{module_upper}_Send"]
            rx_byte_names = [f"{module_upper}_ReceiveByte"]

        tx_byte = (
            _find_first_fn(functions, tx_byte_names)
            or _find_fn_by_contains(functions, ["TRANSMITBYTE"])
            or _find_fn_by_contains(functions, ["SENDBYTE"])
            or _find_fn_by_contains(functions, ["WRITEBYTE"])
        )
        tx_buffer = (
            _find_first_fn(functions, tx_buffer_names)
            or _find_fn_by_contains(functions, ["TRANSMIT"], excludes=["BYTE"], min_arity=2)
            or _find_fn_by_contains(functions, ["SENDDATA"], excludes=["BYTE"], min_arity=2)
            or _find_fn_by_contains(functions, ["SEND"], excludes=["BYTE"], min_arity=2)
            or _find_fn_by_contains(functions, ["WRITE"], excludes=["BYTE"], min_arity=2)
        )
        rx_byte = (
            _find_first_fn(functions, rx_byte_names)
            or _find_fn_by_contains(functions, ["RECEIVEBYTE"])
            or _find_fn_by_contains(functions, ["READBYTE"])
        )
        tx_ready = (
            _find_first_fn(
                functions,
                [f"{module_upper}_IsTxReady", f"{module_upper}_GetTxReady", f"{module_upper}_GetTxStatus"],
            )
            or _find_fn_by_contains(functions, ["ISTXREADY"])
            or _find_fn_by_contains(functions, ["GETTXREADY"])
            or _find_fn_by_contains(functions, ["GETTXSTATUS"])
        )
        rx_ready = (
            _find_first_fn(
                functions,
                [f"{module_upper}_IsRxReady", f"{module_upper}_GetRxReady", f"{module_upper}_GetRxStatus"],
            )
            or _find_fn_by_contains(functions, ["ISRXREADY"])
            or _find_fn_by_contains(functions, ["GETRXREADY"])
            or _find_fn_by_contains(functions, ["GETRXSTATUS"])
        )

        if tx_byte:
            capabilities["tx_byte"] = tx_byte
        if tx_buffer:
            capabilities["tx_buffer"] = tx_buffer
        if rx_byte:
            capabilities["rx_byte"] = rx_byte
            capabilities["rx_byte_arity"] = int(functions.get(rx_byte, {}).get("arity", 0))
        if tx_ready:
            capabilities["tx_ready"] = tx_ready
        if rx_ready:
            capabilities["rx_ready"] = rx_ready

    if module_upper == "GIO":
        configure_pin = _find_first_fn(functions, ["GIO_ConfigurePin"]) or _find_fn_by_contains(functions, ["CONFIGUREPIN"])
        write_pin = _find_first_fn(functions, ["GIO_WritePin"]) or _find_fn_by_contains(functions, ["WRITEPIN"])
        toggle_pin = _find_first_fn(functions, ["GIO_TogglePin"]) or _find_fn_by_contains(functions, ["TOGGLEPIN"])
        if configure_pin:
            capabilities["configure_pin"] = configure_pin
            capabilities["configure_pin_arity"] = int(functions.get(configure_pin, {}).get("arity", 0))
        if write_pin:
            capabilities["write_pin"] = write_pin
        if toggle_pin:
            capabilities["toggle_pin"] = toggle_pin
        if "gio_pin_config_t" in types:
            capabilities["pin_config_type"] = "gio_pin_config_t"

    return capabilities


def _add_lin_compatibility_wrappers(module_contract: Dict[str, Any]) -> None:
    functions = module_contract.setdefault("functions", {})
    wrappers = module_contract.setdefault("compatibility_wrappers", [])
    capabilities = module_contract.get("capabilities", {})
    tx_buffer = capabilities.get("tx_buffer")
    tx_byte = capabilities.get("tx_byte")
    tx_ready = capabilities.get("tx_ready")
    rx_ready = capabilities.get("rx_ready")

    def _has_name(name: str) -> bool:
        if name in functions:
            return True
        return any(w.get("name") == name for w in wrappers)

    def _append_wrapper(name: str, target: str, params: List[Dict[str, str]], return_type: str = "lin_status_t") -> None:
        if _has_name(name) or not target:
            return
        wrappers.append(
            {
                "name": name,
                "return_type": return_type,
                "params": params,
                "arity": len(params),
                "target": target,
                "prototype": (
                    f"{return_type} {name}("
                    + ", ".join(f"{p['type']} {p['name']}" for p in params)
                    + ");"
                ),
            }
        )

    if tx_buffer:
        _append_wrapper(
            "LIN_SendData",
            tx_buffer,
            [
                {"name": "data", "type": "const uint8_t*"},
                {"name": "length", "type": "uint32_t"},
            ],
        )
        _append_wrapper(
            "LIN_Send",
            tx_buffer,
            [
                {"name": "data", "type": "const uint8_t*"},
                {"name": "length", "type": "uint32_t"},
            ],
        )

    if tx_byte:
        _append_wrapper(
            "LIN_SendByte",
            tx_byte,
            [{"name": "data", "type": "uint8_t"}],
        )

    if tx_ready:
        _append_wrapper(
            "LIN_IsTxReady",
            tx_ready,
            [],
            return_type="bool",
        )
        _append_wrapper(
            "LIN_GetTxStatus",
            tx_ready,
            [],
            return_type="bool",
        )

    if rx_ready:
        _append_wrapper(
            "LIN_IsRxReady",
            rx_ready,
            [],
            return_type="bool",
        )
        _append_wrapper(
            "LIN_GetRxStatus",
            rx_ready,
            [],
            return_type="bool",
        )


def _add_sci_compatibility_wrappers(module_contract: Dict[str, Any]) -> None:
    functions = module_contract.setdefault("functions", {})
    wrappers = module_contract.setdefault("compatibility_wrappers", [])
    capabilities = module_contract.get("capabilities", {})
    tx_buffer = capabilities.get("tx_buffer")
    tx_byte = capabilities.get("tx_byte")
    rx_byte = capabilities.get("rx_byte")
    tx_ready = capabilities.get("tx_ready")
    rx_ready = capabilities.get("rx_ready")

    def _has_name(name: str) -> bool:
        if name in functions:
            return True
        return any(w.get("name") == name for w in wrappers)

    def _append_wrapper(name: str, target: str, params: List[Dict[str, str]], return_type: str = "sci_status_t") -> None:
        if _has_name(name) or not target:
            return
        wrappers.append(
            {
                "name": name,
                "return_type": return_type,
                "params": params,
                "arity": len(params),
                "target": target,
                "prototype": (
                    f"{return_type} {name}("
                    + ", ".join(f"{p['type']} {p['name']}" for p in params)
                    + ");"
                ),
            }
        )

    if tx_buffer:
        _append_wrapper(
            "SCI_SendData",
            tx_buffer,
            [
                {"name": "data", "type": "const uint8_t*"},
                {"name": "length", "type": "uint32_t"},
            ],
        )
        _append_wrapper(
            "SCI_Send",
            tx_buffer,
            [
                {"name": "data", "type": "const uint8_t*"},
                {"name": "length", "type": "uint32_t"},
            ],
        )

    if tx_byte:
        _append_wrapper(
            "SCI_SendByte",
            tx_byte,
            [{"name": "data", "type": "uint8_t"}],
        )

    if rx_byte:
        _append_wrapper(
            "SCI_ReceiveByte",
            rx_byte,
            [{"name": "data", "type": "uint8_t*"}],
        )

    if tx_ready:
        _append_wrapper(
            "SCI_IsTxReady",
            tx_ready,
            [],
            return_type="bool",
        )
        _append_wrapper(
            "SCI_GetTxStatus",
            tx_ready,
            [],
            return_type="bool",
        )

    if rx_ready:
        _append_wrapper(
            "SCI_IsRxReady",
            rx_ready,
            [],
            return_type="bool",
        )
        _append_wrapper(
            "SCI_GetRxStatus",
            rx_ready,
            [],
            return_type="bool",
        )


PROTOTYPE_RE = re.compile(
    r"^\s*([A-Za-z_][\w\s\*]*?)\s+([A-Za-z_]\w*)\s*\(([^;{}]*)\)\s*;\s*$",
    re.MULTILINE,
)
ENUM_RE = re.compile(
    r"typedef\s+enum\s*\{(.*?)\}\s*([A-Za-z_]\w*)\s*;",
    re.DOTALL | re.MULTILINE,
)
STRUCT_RE = re.compile(
    r"typedef\s+struct\s*\{(.*?)\}\s*([A-Za-z_]\w*)\s*;",
    re.DOTALL | re.MULTILINE,
)
FIELD_RE = re.compile(r"^\s*([A-Za-z_][\w\s\*]*?)\s+([A-Za-z_]\w*)\s*;\s*$")
ENUM_VALUE_RE = re.compile(r"^\s*([A-Za-z_]\w*)")


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def _parse_header_functions(header_text: str) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for match in PROTOTYPE_RE.finditer(header_text):
        ret, name, params = match.groups()
        parsed = parse_prototype(f"{ret} {name}({params});")
        if parsed:
            out[name] = parsed
    return out


def _parse_header_types(header_text: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    clean = _strip_comments(header_text)

    for match in ENUM_RE.finditer(clean):
        body, enum_name = match.groups()
        values: List[str] = []
        for raw in body.split(","):
            line = raw.strip()
            if not line:
                continue
            line = line.split("=", 1)[0].strip()
            value_match = ENUM_VALUE_RE.match(line)
            if value_match:
                values.append(value_match.group(1))
        out[enum_name] = {"kind": "enum", "values": values}

    for match in STRUCT_RE.finditer(clean):
        body, struct_name = match.groups()
        fields: List[Dict[str, str]] = []
        for raw in body.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            field_match = FIELD_RE.match(line)
            if not field_match:
                continue
            f_type, f_name = field_match.groups()
            fields.append({"name": f_name, "type": _normalize_space(f_type)})
        out[struct_name] = {"kind": "struct", "fields": fields}

    return out


def _canonical_hash(contract: Dict[str, Any]) -> str:
    hashable = {
        "target_board": contract.get("target_board"),
        "modules": contract.get("modules", {}),
        "metadata": contract.get("metadata", {}),
    }
    canonical = json.dumps(hashable, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_api_contract_manifest(
    bsp_manifest: Dict[str, Any],
    generation_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    profile = generation_profile or {}
    api_catalog = bsp_manifest.get("api_catalog", {})

    contract: Dict[str, Any] = {
        "generated_at": datetime.now().isoformat(),
        "target_board": profile.get("target_board", ""),
        "metadata": {
            "source_manifest": "bsp_manifest.json",
            "strict_validation": bool(profile.get("strict_validation", False)),
        },
        "modules": {},
    }

    for module_name in sorted(api_catalog.keys(), key=lambda n: n.upper()):
        entry = api_catalog[module_name] or {}
        module_upper = module_name.upper()
        driver_header = entry.get("driver_header_file", f"{module_name.lower()}_driver.h")
        if module_upper == "VIM":
            driver_header = "vim_driver.h"
        module_contract: Dict[str, Any] = {
            "module_name": module_upper,
            "driver_header_file": driver_header,
            "functions": {},
            "types": _extract_types(entry),
            "compatibility_wrappers": [],
            "capabilities": {},
        }

        for func in entry.get("functions", []):
            prototype = func.get("prototype", "")
            parsed = parse_prototype(prototype) if prototype else None
            if not parsed:
                continue
            module_contract["functions"][parsed["name"]] = parsed

        module_contract["capabilities"] = _derive_module_capabilities(
            module_upper,
            module_contract["functions"],
            module_contract["types"],
        )
        if module_upper == "LIN":
            _add_lin_compatibility_wrappers(module_contract)
        elif module_upper == "SCI":
            _add_sci_compatibility_wrappers(module_contract)

        contract["modules"][module_upper] = module_contract

    contract["api_contract_hash"] = _canonical_hash(contract)
    return contract


def write_api_contract_manifest(
    output_dir: Path,
    contract: Dict[str, Any],
    filename: str = "api_contract_manifest.json",
) -> Path:
    path = Path(output_dir) / filename
    path.write_text(json.dumps(contract, indent=2), encoding="utf-8")
    return path


def hydrate_contract_from_generated_headers(
    output_dir: Path,
    api_contract_manifest: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Reconcile/refresh contract using actual generated headers from Pass 2 output.
    """
    out_dir = Path(output_dir)
    modules = api_contract_manifest.get("modules", {})

    for module_name, module_contract in modules.items():
        header_name = module_contract.get("driver_header_file", f"{module_name.lower()}_driver.h")
        candidates = [
            out_dir / "include" / header_name,
            out_dir / header_name,
            out_dir / "source" / header_name,
        ]
        if str(module_name).upper() == "VIM":
            candidates.extend(
                [
                    out_dir / "include" / "vim.h",
                    out_dir / "vim.h",
                    out_dir / "source" / "vim.h",
                ]
            )
        header_path = next((p for p in candidates if p.exists()), None)
        if not header_path:
            continue

        header_text = header_path.read_text(encoding="utf-8", errors="ignore")
        parsed_functions = _parse_header_functions(header_text)
        parsed_types = _parse_header_types(header_text)

        if parsed_functions:
            module_contract["functions"] = parsed_functions
        if parsed_types:
            merged_types = dict(module_contract.get("types", {}))
            merged_types.update(parsed_types)
            module_contract["types"] = merged_types

        module_contract["capabilities"] = _derive_module_capabilities(
            module_name,
            module_contract.get("functions", {}),
            module_contract.get("types", {}),
        )
        module_contract["compatibility_wrappers"] = []
        if module_name.upper() == "LIN":
            _add_lin_compatibility_wrappers(module_contract)
        elif module_name.upper() == "SCI":
            _add_sci_compatibility_wrappers(module_contract)

    api_contract_manifest["api_contract_hash"] = _canonical_hash(api_contract_manifest)
    return api_contract_manifest
