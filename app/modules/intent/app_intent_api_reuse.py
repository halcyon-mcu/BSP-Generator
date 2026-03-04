"""
Deterministic app-intent API reuse recipe resolution and lint helpers.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _get_policy(bringup_contract: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    contract = _as_dict(bringup_contract)
    app_intent = _as_dict(contract.get("app_intent"))
    api_reuse = _as_dict(app_intent.get("api_reuse"))
    pin_init = _as_dict(api_reuse.get("pin_init"))
    tx_string = _as_dict(api_reuse.get("tx_string"))

    return {
        "mode": str(api_reuse.get("mode", "warn_only")).strip() or "warn_only",
        "docs_target": str(api_reuse.get("docs_target", "both")).strip() or "both",
        "pin_init": {
            "prefer_enable_pins": bool(pin_init.get("prefer_enable_pins", True)),
            "call_enable_pins_before_init": bool(pin_init.get("call_enable_pins_before_init", True)),
            "allow_iomm_fallback": bool(pin_init.get("allow_iomm_fallback", True)),
        },
        "tx_string": {
            "prefer_capability": str(tx_string.get("prefer_capability", "tx_buffer")).strip() or "tx_buffer",
            "fallback_capability": str(tx_string.get("fallback_capability", "tx_byte")).strip() or "tx_byte",
            "forbid_manual_byte_loop_when_tx_buffer_exists": bool(
                tx_string.get("forbid_manual_byte_loop_when_tx_buffer_exists", True)
            ),
            "forbid_busy_wait_loops_in_step_path": bool(
                tx_string.get("forbid_busy_wait_loops_in_step_path", True)
            ),
        },
    }


def _derive_primary_serial_module(bringup_contract: Optional[Dict[str, Any]]) -> Optional[str]:
    serial = _as_dict(_as_dict(bringup_contract).get("serial"))
    primary = str(serial.get("primary_path", "")).upper()
    tx_only = str(serial.get("primary_tx_only", "")).upper()

    if tx_only in {"LIN", "SCI"}:
        return tx_only
    if "LIN" in primary:
        return "LIN"
    if "SCI" in primary:
        return "SCI"
    return None


def _get_module_contract(api_contract_manifest: Optional[Dict[str, Any]], module_name: str) -> Dict[str, Any]:
    modules = _as_dict(_as_dict(api_contract_manifest).get("modules"))
    return _as_dict(modules.get(module_name.upper()))


def _discover_enable_pins_symbol(
    module_name: str,
    driver_source_symbols: Optional[Dict[str, List[str]]] = None,
    module_contract: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    expected = f"{module_name.upper()}_EnablePins"
    contract_functions = _as_dict(_as_dict(module_contract).get("functions"))
    if expected in contract_functions:
        return expected

    symbols = driver_source_symbols or {}
    for _, names in symbols.items():
        for name in names or []:
            if str(name) == expected:
                return expected
    return None


def _build_module_recipe(
    module_name: str,
    module_contract: Dict[str, Any],
    driver_source_symbols: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Any]:
    capabilities = _as_dict(module_contract.get("capabilities"))
    functions = _as_dict(module_contract.get("functions"))
    wrappers = _as_list(module_contract.get("compatibility_wrappers"))

    tx_buffer = capabilities.get("tx_buffer")
    tx_buffer_source = "capability" if tx_buffer else "missing"
    tx_byte = capabilities.get("tx_byte")

    # Fallback inference from function/wrapper prototypes for prompt guidance only.
    # Keep low-confidence inferred names out of drift warnings.
    if not tx_buffer:
        candidates: List[str] = []
        for name, info in functions.items():
            upper = str(name).upper()
            info_dict = _as_dict(info)
            arity_raw = info_dict.get("arity")
            arity = int(arity_raw) if isinstance(arity_raw, int) else -1
            if not upper.startswith(f"{module_name.upper()}_"):
                continue
            if "BYTE" in upper:
                continue
            if arity >= 0 and arity < 2:
                continue
            if any(token in upper for token in ("SEND", "TRANSMIT", "WRITE")):
                candidates.append(str(name))
        for wrapper in wrappers:
            wrapper_name = str(_as_dict(wrapper).get("name", ""))
            upper = wrapper_name.upper()
            arity = int(_as_dict(wrapper).get("arity", 0))
            if not wrapper_name or not upper.startswith(f"{module_name.upper()}_"):
                continue
            if "BYTE" in upper:
                continue
            if arity < 2:
                continue
            if any(token in upper for token in ("SEND", "TRANSMIT", "WRITE")):
                candidates.append(wrapper_name)
        if candidates:
            tx_buffer = sorted(set(candidates))[0]
            tx_buffer_source = "inferred"

    if not tx_byte:
        byte_candidates: List[str] = []
        for name, info in functions.items():
            upper = str(name).upper()
            info_dict = _as_dict(info)
            arity_raw = info_dict.get("arity")
            arity = int(arity_raw) if isinstance(arity_raw, int) else -1
            if not upper.startswith(f"{module_name.upper()}_"):
                continue
            if arity >= 0 and arity != 1:
                continue
            if "BYTE" in upper and any(token in upper for token in ("SEND", "TRANSMIT", "WRITE")):
                byte_candidates.append(str(name))
        if byte_candidates:
            tx_byte = sorted(set(byte_candidates))[0]

    return {
        "module": module_name.upper(),
        "init": capabilities.get("init"),
        "tx_buffer": tx_buffer,
        "tx_buffer_source": tx_buffer_source,
        "tx_byte": tx_byte,
        "tx_ready": capabilities.get("tx_ready"),
        "rx_ready": capabilities.get("rx_ready"),
        "enable_pins": _discover_enable_pins_symbol(
            module_name=module_name,
            driver_source_symbols=driver_source_symbols,
            module_contract=module_contract,
        ),
    }


def resolve_app_intent_api_reuse_recipe(
    *,
    bringup_contract: Optional[Dict[str, Any]],
    api_contract_manifest: Optional[Dict[str, Any]],
    driver_source_symbols: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Any]:
    """
    Build normalized app-intent API reuse recipe from bring-up policy + API contract.
    """
    policy = _get_policy(bringup_contract)
    primary_module = _derive_primary_serial_module(bringup_contract)

    lin_contract = _get_module_contract(api_contract_manifest, "LIN")
    sci_contract = _get_module_contract(api_contract_manifest, "SCI")
    iomm_contract = _get_module_contract(api_contract_manifest, "IOMM")

    recipe = {
        "policy": policy,
        "primary_serial_module": primary_module,
        "modules": {
            "LIN": _build_module_recipe("LIN", lin_contract, driver_source_symbols),
            "SCI": _build_module_recipe("SCI", sci_contract, driver_source_symbols),
            "IOMM": _build_module_recipe("IOMM", iomm_contract, driver_source_symbols),
        },
    }
    return recipe


def _preferred_tx_for_module(module_recipe: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Optional[str]]:
    tx_cfg = _as_dict(policy.get("tx_string"))
    prefer = str(tx_cfg.get("prefer_capability", "tx_buffer"))
    fallback = str(tx_cfg.get("fallback_capability", "tx_byte"))
    preferred_name = module_recipe.get(prefer)
    fallback_name = module_recipe.get(fallback)
    return {
        "preferred_capability": prefer,
        "preferred_name": preferred_name,
        "fallback_capability": fallback,
        "fallback_name": fallback_name,
    }


def build_app_intent_api_recipe_text(recipe: Dict[str, Any]) -> str:
    """
    Render recipe into a deterministic text block for prompt context.
    """
    policy = _as_dict(recipe.get("policy"))
    mode = str(policy.get("mode", "warn_only"))
    docs_target = str(policy.get("docs_target", "both"))
    primary_module = recipe.get("primary_serial_module") or "AUTO"
    modules = _as_dict(recipe.get("modules"))

    lines: List[str] = [
        f"policy.mode: {mode}",
        f"policy.docs_target: {docs_target}",
        f"primary_serial_module: {primary_module}",
    ]

    pin_cfg = _as_dict(policy.get("pin_init"))
    lines.append(
        "pin_init: "
        f"prefer_enable_pins={bool(pin_cfg.get('prefer_enable_pins', True))}, "
        f"call_enable_pins_before_init={bool(pin_cfg.get('call_enable_pins_before_init', True))}, "
        f"allow_iomm_fallback={bool(pin_cfg.get('allow_iomm_fallback', True))}"
    )

    tx_cfg = _as_dict(policy.get("tx_string"))
    lines.append(
        "tx_string: "
        f"prefer_capability={tx_cfg.get('prefer_capability', 'tx_buffer')}, "
        f"fallback_capability={tx_cfg.get('fallback_capability', 'tx_byte')}, "
        f"forbid_manual_byte_loop_when_tx_buffer_exists="
        f"{bool(tx_cfg.get('forbid_manual_byte_loop_when_tx_buffer_exists', True))}, "
        f"forbid_busy_wait_loops_in_step_path="
        f"{bool(tx_cfg.get('forbid_busy_wait_loops_in_step_path', True))}"
    )

    for module_name in ("LIN", "SCI"):
        module_recipe = _as_dict(modules.get(module_name))
        preferred = _preferred_tx_for_module(module_recipe, policy)
        lines.extend(
            [
                f"{module_name}.init: {module_recipe.get('init') or '<missing>'}",
                f"{module_name}.enable_pins: {module_recipe.get('enable_pins') or '<none>'}",
                f"{module_name}.tx.preferred: {preferred['preferred_name'] or '<missing>'} ({preferred['preferred_capability']})",
                f"{module_name}.tx.preferred_source: {module_recipe.get('tx_buffer_source') or 'missing'}",
                f"{module_name}.tx.fallback: {preferred['fallback_name'] or '<missing>'} ({preferred['fallback_capability']})",
                f"{module_name}.tx_ready: {module_recipe.get('tx_ready') or '<missing>'}",
                f"{module_name}.rx_ready: {module_recipe.get('rx_ready') or '<missing>'}",
            ]
        )

    iomm_recipe = _as_dict(modules.get("IOMM"))
    lines.append(f"IOMM.init: {iomm_recipe.get('init') or '<missing>'}")
    return "\n".join(lines)


def _extract_c_function_body(source_text: str, function_name: str) -> str:
    sig = re.search(rf"\b{re.escape(function_name)}\s*\(\s*void\s*\)\s*\{{", source_text)
    if not sig:
        return ""
    open_brace = source_text.find("{", sig.start())
    if open_brace < 0:
        return ""
    depth = 0
    idx = open_brace
    while idx < len(source_text):
        ch = source_text[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source_text[open_brace + 1 : idx]
        idx += 1
    return ""


def _has_visible_led_timing_gate(step_body: str) -> bool:
    body = str(step_body or "")
    if not body.strip():
        return False

    # Common cadence/state signals (ticks, ms, counters, heartbeat period, etc.).
    cadence_signal = re.search(
        r"(tick|ticks|ms|millis|elapsed|deadline|period|heartbeat|next_blink|counter|count|timestamp)",
        body,
        flags=re.IGNORECASE,
    )
    gated_compare = re.search(r"\bif\s*\([^)]*(>=|<=|>|<|==|!=|%)", body)
    if cadence_signal and gated_compare:
        return True

    # Heuristic for helper APIs that encapsulate cadence logic.
    helper_gate = re.search(
        r"\bif\s*\(\s*[A-Za-z_]\w*(Tick|Time|Elapsed|Period|Heartbeat|Blink)\w*\s*\(",
        body,
    )
    if helper_gate:
        return True

    return False


def _extract_c_function_definition_span(source_text: str, function_name: str) -> Optional[Tuple[int, int]]:
    sig = re.search(
        rf"(?m)^\s*(?:static\s+)?[A-Za-z_][\w\s\*]*\b{re.escape(function_name)}\s*\([^;{{}}]*\)\s*\{{",
        source_text,
    )
    if not sig:
        return None
    open_brace = source_text.find("{", sig.start())
    if open_brace < 0:
        return None
    depth = 0
    idx = open_brace
    while idx < len(source_text):
        ch = source_text[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return (sig.start(), idx + 1)
        idx += 1
    return None


def _strip_c_comments(text: str) -> str:
    stripped = re.sub(r"/\*.*?\*/", "", str(text or ""), flags=re.DOTALL)
    stripped = re.sub(r"//[^\n]*", "", stripped)
    return stripped


def _collect_declared_function_symbols(text: str) -> set[str]:
    stripped = _strip_c_comments(text)
    names: set[str] = set()
    for match in re.finditer(
        r"(?m)^\s*(?:extern\s+)?[A-Za-z_][\w\s\*]*?\b([A-Za-z_]\w*)\s*\([^;{}]*\)\s*;\s*$",
        stripped,
    ):
        names.add(str(match.group(1)))
    return names


def _extract_local_include_names(text: str) -> List[str]:
    return [str(m.group(1)) for m in re.finditer(r'(?m)^\s*#include\s+"([^"]+)"', str(text or ""))]


def _read_include_file(out_dir: Path, include_name: str) -> str:
    include = str(include_name or "").strip()
    if not include:
        return ""
    candidates = [
        Path(out_dir) / include,
        Path(out_dir) / "include" / include,
        Path(out_dir) / "source" / include,
    ]
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8", errors="ignore")
    return ""


def _inject_after_includes(source_text: str, snippet: str) -> str:
    include_block = re.search(r"^(\s*#include[^\n]*\n)+", source_text, flags=re.MULTILINE)
    if include_block:
        insert_at = include_block.end()
        return source_text[:insert_at] + "\n" + snippet.rstrip() + "\n" + source_text[insert_at:]
    return snippet.rstrip() + "\n\n" + source_text


def _extract_driver_prototype(
    *,
    out_dir: Path,
    symbol: str,
    source_file_hint: Optional[str],
) -> Optional[str]:
    source_dir = Path(out_dir) / "source"
    candidates: List[Path] = []
    if source_file_hint:
        hinted = source_dir / str(source_file_hint)
        if hinted.exists():
            candidates.append(hinted)
    if source_dir.exists():
        candidates.extend(p for p in sorted(source_dir.glob("*_driver.c")) if p not in candidates)

    for path in candidates:
        text = path.read_text(encoding="utf-8", errors="ignore")
        match = re.search(
            rf"(?m)^\s*(?!static\b)([A-Za-z_][\w\s\*]*?)\s+({re.escape(symbol)})\s*\(([^;{{}}]*)\)\s*\{{",
            text,
        )
        if not match:
            continue
        ret = " ".join(match.group(1).split())
        args = " ".join(str(match.group(3) or "").split())
        if not args:
            args = "void"
        return f"{ret} {symbol}({args});"

    if symbol.endswith("_EnablePins"):
        return f"void {symbol}(void);"
    return None


def _gio_port_mode(gio_header_text: str) -> str:
    text = str(gio_header_text or "")
    if re.search(r"\bGIO_(?:ConfigurePin|WritePin|ReadPin|TogglePin)\s*\(\s*uint8_t\s+port\b", text):
        return "numeric"
    if re.search(r"\bGIO_(?:ConfigurePin|WritePin|ReadPin|TogglePin)\s*\(\s*gio_port_t\s+port\b", text):
        return "enum"
    return "unknown"


def _normalize_gio_port_arguments(app_intent_text: str, gio_port_mode: str) -> tuple[str, List[str]]:
    text = str(app_intent_text or "")
    actions: List[str] = []
    if gio_port_mode not in {"numeric", "enum"}:
        return text, actions

    gpio_calls = ("GIO_ConfigurePin", "GIO_SetPinDirection", "GIO_WritePin", "GIO_ReadPin", "GIO_TogglePin")

    def _replace_literal(match: re.Match[str]) -> str:
        call = str(match.group(1))
        raw_port = str(match.group(2))
        port_char = raw_port.upper()
        replacement = f"'{raw_port}'"
        if gio_port_mode == "numeric":
            mapping = {"A": "0U", "B": "1U", "0": "0U", "1": "1U"}
            replacement = mapping.get(port_char, replacement)
        else:
            mapping = {"A": "GIO_PORT_A", "B": "GIO_PORT_B"}
            replacement = mapping.get(port_char, replacement)
        if replacement != f"'{raw_port}'":
            actions.append(f"Normalized {call} port literal '{raw_port}' to {replacement}.")
        return f"{call}({replacement},"

    text = re.sub(
        rf"\b({'|'.join(gpio_calls)})\s*\(\s*'([A-Za-z0-9])'\s*,",
        _replace_literal,
        text,
    )

    def _replace_board_macro(match: re.Match[str]) -> str:
        call = str(match.group(1))
        macro = str(match.group(2))
        if gio_port_mode == "numeric":
            replacement = f"(({macro}) == 'B' ? 1U : 0U)"
        else:
            replacement = f"(({macro}) == 'B' ? GIO_PORT_B : GIO_PORT_A)"
        actions.append(f"Normalized {call} board port macro {macro} to {gio_port_mode} port expression.")
        return f"{call}({replacement},"

    text = re.sub(
        rf"\b({'|'.join(gpio_calls)})\s*\(\s*(BOARD_[A-Z0-9_]+_GIO_PORT)\s*,",
        _replace_board_macro,
        text,
    )
    return text, actions


def sanitize_app_intent_generated_source(
    *,
    out_dir: Path,
    app_intent_text: str,
    driver_source_symbols: Optional[Dict[str, List[str]]],
    gio_header_text: str = "",
) -> Dict[str, Any]:
    """
    Apply deterministic safety fixes to generated app_intent.c.
    """
    text = str(app_intent_text or "")
    if not text.strip():
        return {"text": text, "changed": False, "actions": []}

    symbol_map = driver_source_symbols if isinstance(driver_source_symbols, dict) else {}
    symbol_to_file: Dict[str, str] = {}
    for source_file, symbols in symbol_map.items():
        for name in symbols or []:
            symbol_to_file.setdefault(str(name), str(source_file))

    driver_symbols = sorted(symbol_to_file.keys())
    removed_symbols: List[str] = []
    actions: List[str] = []
    updated = text

    for symbol in driver_symbols:
        if symbol in {"APP_INTENT_Init", "APP_INTENT_Step"}:
            continue
        span = _extract_c_function_definition_span(updated, symbol)
        if not span:
            continue
        start, end = span
        updated = updated[:start].rstrip() + "\n\n" + updated[end:].lstrip()
        removed_symbols.append(symbol)
        actions.append(f"Removed local app-intent definition of driver API {symbol}.")

    declaration_lines: List[str] = []
    declared_local = _collect_declared_function_symbols(updated)
    declared_from_includes: set[str] = set()
    for include_name in _extract_local_include_names(updated):
        include_text = _read_include_file(Path(out_dir), include_name)
        if include_text:
            declared_from_includes.update(_collect_declared_function_symbols(include_text))

    for symbol in driver_symbols:
        if symbol in {"APP_INTENT_Init", "APP_INTENT_Step"}:
            continue
        has_call = re.search(rf"\b{re.escape(symbol)}\s*\(", updated) is not None
        if not has_call:
            continue
        if symbol in declared_local or symbol in declared_from_includes:
            continue
        proto = _extract_driver_prototype(
            out_dir=Path(out_dir),
            symbol=symbol,
            source_file_hint=symbol_to_file.get(symbol),
        )
        if not proto:
            continue
        declaration_lines.append(proto)
        declared_local.add(symbol)
        if symbol in removed_symbols:
            actions.append(f"Added forward declaration for {symbol}.")
        else:
            actions.append(f"Added forward declaration for called driver symbol {symbol}.")

    if declaration_lines:
        decl_block = "\n".join(sorted(set(declaration_lines)))
        updated = _inject_after_includes(updated, decl_block)

    port_mode = _gio_port_mode(gio_header_text)
    normalized_ports, port_actions = _normalize_gio_port_arguments(updated, port_mode)
    updated = normalized_ports
    actions.extend(port_actions)

    return {
        "text": updated,
        "changed": updated != text,
        "actions": actions,
    }


def lint_app_intent_api_reuse(
    app_intent_c_text: str,
    recipe: Dict[str, Any],
    *,
    gio_header_text: str = "",
) -> List[str]:
    """
    Warn-only checks for post-generated app_intent.c drift from API reuse recipe.
    """
    text = str(app_intent_c_text or "")
    if not text.strip():
        return ["app_intent.c missing or empty; API reuse drift checks skipped."]

    warnings: List[str] = []
    policy = _as_dict(recipe.get("policy"))
    tx_cfg = _as_dict(policy.get("tx_string"))
    pin_cfg = _as_dict(policy.get("pin_init"))
    modules = _as_dict(recipe.get("modules"))
    primary_module = str(recipe.get("primary_serial_module") or "").upper()
    module_candidates = [primary_module] if primary_module in {"LIN", "SCI"} else ["LIN", "SCI"]

    step_body = _extract_c_function_body(text, "APP_INTENT_Step")

    for module_name in module_candidates:
        module_recipe = _as_dict(modules.get(module_name))
        tx = _preferred_tx_for_module(module_recipe, policy)
        tx_byte_name = str(module_recipe.get("tx_byte") or "")
        tx_ready_name = str(module_recipe.get("tx_ready") or "")
        enable_pins_name = str(module_recipe.get("enable_pins") or "")
        init_name = str(module_recipe.get("init") or "")
        protected_apis = [
            init_name,
            str(tx.get("preferred_name") or ""),
            tx_byte_name,
            tx_ready_name,
            str(module_recipe.get("rx_ready") or ""),
            enable_pins_name,
        ]

        for api_name in protected_apis:
            if not api_name:
                continue
            if _extract_c_function_definition_span(text, api_name):
                warnings.append(
                    f"{module_name}: app_intent.c defines {api_name}; do not redefine driver APIs in app-intent."
                )

        if (
            bool(tx_cfg.get("forbid_manual_byte_loop_when_tx_buffer_exists", True))
            and tx.get("preferred_capability") == "tx_buffer"
            and tx.get("preferred_name")
            and str(module_recipe.get("tx_buffer_source", "missing")) == "capability"
            and tx_byte_name
        ):
            tx_buffer_name = str(tx.get("preferred_name"))
            has_tx_buffer_call = re.search(rf"\b{re.escape(tx_buffer_name)}\s*\(", text) is not None
            byte_loop_pattern = re.search(
                rf"(for|while)\s*\([^)]*\)\s*\{{[^{{}}]{{0,600}}?\b{re.escape(tx_byte_name)}\s*\(",
                text,
                flags=re.DOTALL,
            )
            if byte_loop_pattern and not has_tx_buffer_call:
                warnings.append(
                    f"{module_name}: manual byte-loop TX via {tx_byte_name} detected while preferred "
                    f"buffer API {tx_buffer_name} exists."
                )

        if bool(tx_cfg.get("forbid_busy_wait_loops_in_step_path", True)) and step_body:
            busy_wait_pattern = None
            if tx_ready_name:
                busy_wait_pattern = re.search(
                    rf"while\s*\(\s*!\s*{re.escape(tx_ready_name)}\s*\(\s*\)\s*\)",
                    step_body,
                )
            generic_busy_wait = re.search(r"while\s*\(\s*!\s*[A-Za-z_]\w*TxReady\s*\(\s*\)\s*\)", step_body)
            if busy_wait_pattern or generic_busy_wait:
                warnings.append(
                    f"{module_name}: busy-wait TX-ready loop detected in APP_INTENT_Step; step path must remain non-blocking."
                )

        if (
            bool(pin_cfg.get("prefer_enable_pins", True))
            and enable_pins_name
            and re.search(r"\bIOMM_Configure(?:Pin|Pins|MultiplePins)\s*\(", text)
            and re.search(rf"\b{re.escape(enable_pins_name)}\s*\(", text) is None
        ):
            warnings.append(
                f"{module_name}: direct IOMM pin configuration detected without {enable_pins_name} call."
            )

    port_mode = _gio_port_mode(gio_header_text)
    if port_mode in {"numeric", "enum"}:
        char_port_call = re.search(
            r"\bGIO_(?:ConfigurePin|SetPinDirection|WritePin|ReadPin|TogglePin)\s*\(\s*'[A-Za-z0-9]'\s*,",
            text,
        )
        board_char_port_call = re.search(
            r"\bGIO_(?:ConfigurePin|SetPinDirection|WritePin|ReadPin|TogglePin)\s*\(\s*BOARD_[A-Z0-9_]+_GIO_PORT\s*,",
            text,
        )
        if char_port_call or board_char_port_call:
            if port_mode == "numeric":
                warnings.append(
                    "GIO: raw character port values used with uint8_t port APIs; use numeric ports (A=0, B=1) "
                    "or BOARD_*_GIO_PORT_INDEX."
                )
            else:
                warnings.append(
                    "GIO: raw character port values used with gio_port_t APIs; use GIO_PORT_A/GIO_PORT_B."
                )

    if step_body:
        has_led_write = re.search(r"\bGIO_(?:TogglePin|WritePin)\s*\(", step_body) is not None
        if has_led_write and not _has_visible_led_timing_gate(step_body):
            warnings.append(
                "APP_INTENT: LED state change in APP_INTENT_Step has no visible timing gate; "
                "tight-loop blink may be too fast to observe."
            )

    return warnings


def build_driver_usage_recipe_comment(
    *,
    module_name: str,
    recipe: Dict[str, Any],
) -> str:
    """
    Build a deterministic Doxygen usage recipe comment for driver headers.
    """
    module_upper = str(module_name or "").upper()
    if module_upper not in {"LIN", "SCI", "IOMM"}:
        return ""

    policy = _as_dict(recipe.get("policy"))
    docs_target = str(policy.get("docs_target", "both"))
    if docs_target not in {"both", "headers_only"}:
        return ""

    module_recipe = _as_dict(_as_dict(recipe.get("modules")).get(module_upper))
    if not any(
        (
            module_recipe.get("init"),
            module_recipe.get("tx_buffer"),
            module_recipe.get("tx_byte"),
            module_recipe.get("enable_pins"),
        )
    ):
        return ""
    tx = _preferred_tx_for_module(module_recipe, policy)
    init_name = module_recipe.get("init") or f"{module_upper}_Init"
    enable_pins_name = module_recipe.get("enable_pins") or f"{module_upper}_EnablePins (if available)"
    mode = str(policy.get("mode", "warn_only"))

    if module_upper == "IOMM":
        lines = [
            "/**",
            " * @brief App-intent pin-init guidance",
            " * @details Generated from bringup_contract.app_intent.api_reuse.",
            " *          Recommended sequence for app code:",
            " *          1) Prefer module-specific EnablePins wrappers where available.",
            " *          2) Use IOMM pin configuration fallback only when wrapper APIs are unavailable.",
            f" *          Policy mode: {mode}",
            " */",
        ]
        return "\n".join(lines)

    preferred_tx = tx.get("preferred_name") or "<missing>"
    fallback_tx = tx.get("fallback_name") or "<missing>"
    lines = [
        "/**",
        " * @brief App-intent usage recipe",
        " * @details Generated from bringup_contract.app_intent.api_reuse.",
        " *          Recommended app-level init sequence:",
        f" *          1) {enable_pins_name}",
        f" *          2) {init_name}",
        " *          Recommended string TX path:",
        f" *          - Preferred: {preferred_tx}",
        f" *          - Fallback: {fallback_tx}",
        " *          Avoid manual per-byte string loops when preferred buffer API exists.",
        f" *          Policy mode: {mode}",
        " */",
    ]
    return "\n".join(lines)


def inject_driver_usage_recipe_comment(
    *,
    header_text: str,
    module_name: str,
    recipe: Dict[str, Any],
) -> str:
    """
    Inject usage recipe Doxygen block before header #endif when enabled by policy.
    """
    comment = build_driver_usage_recipe_comment(module_name=module_name, recipe=recipe)
    if not comment:
        return header_text
    marker = "App-intent usage recipe"
    if marker in header_text or "App-intent pin-init guidance" in header_text:
        return header_text

    match = re.search(r"^\s*#endif\b.*$", header_text, flags=re.MULTILINE)
    if not match:
        tail = "\n" if not header_text.endswith("\n") else ""
        return f"{header_text}{tail}\n{comment}\n"

    insert_at = match.start()
    prefix = header_text[:insert_at].rstrip()
    suffix = header_text[insert_at:]
    return f"{prefix}\n\n{comment}\n{suffix}"
