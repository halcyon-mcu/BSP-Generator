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


def _get_init_gate_policy(bringup_contract: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    contract = _as_dict(bringup_contract)
    app_intent = _as_dict(contract.get("app_intent"))
    init_gate = _as_dict(app_intent.get("init_gate"))
    return {
        "mode": str(init_gate.get("mode", "auto_fix_then_fail")).strip() or "auto_fix_then_fail",
        "enforce_pre_use_init": bool(init_gate.get("enforce_pre_use_init", True)),
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


def resolve_app_intent_init_gate_contract(
    *,
    bringup_contract: Optional[Dict[str, Any]],
    api_contract_manifest: Optional[Dict[str, Any]],
    timing_recipe: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Resolve module init functions that must exist when module APIs are used by app_intent.c.
    """
    policy = _get_init_gate_policy(bringup_contract)
    modules_contract = _as_dict(_as_dict(api_contract_manifest).get("modules"))
    selected_timing_module = str(_as_dict(timing_recipe).get("selected_module", "")).upper()
    module_names = ["GIO", "LIN", "SCI", "IOMM", "RTI", "VIM", "PLL"]
    if selected_timing_module and selected_timing_module not in module_names:
        module_names.append(selected_timing_module)

    module_init_map: Dict[str, Dict[str, Any]] = {}
    for module_name in module_names:
        module_contract = _as_dict(modules_contract.get(module_name))
        capabilities = _as_dict(module_contract.get("capabilities"))
        functions = _as_dict(module_contract.get("functions"))
        init_name = str(capabilities.get("init") or "").strip()
        if not init_name:
            continue
        arity_raw = _as_dict(functions.get(init_name)).get("arity")
        arity = int(arity_raw) if isinstance(arity_raw, int) else None
        module_init_map[module_name] = {
            "init": init_name,
            "arity": arity,
        }

    return {
        "policy": policy,
        "modules": module_init_map,
    }


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


def _extract_app_intent_function(source_text: str, function_name: str) -> Optional[Dict[str, Any]]:
    span = _extract_c_function_definition_span(source_text, function_name)
    if not span:
        return None
    start, end = span
    fn_text = source_text[start:end]
    open_brace_rel = fn_text.find("{")
    close_brace_rel = fn_text.rfind("}")
    if open_brace_rel < 0 or close_brace_rel <= open_brace_rel:
        return None
    body_start = start + open_brace_rel + 1
    body_end = start + close_brace_rel
    return {
        "start": start,
        "end": end,
        "body_start": body_start,
        "body_end": body_end,
        "text": fn_text,
        "body": source_text[body_start:body_end],
    }


def _extract_statement_span(body_text: str, call_name: str) -> Optional[Tuple[int, int]]:
    pattern = re.compile(rf"(?m)^[ \t]*{re.escape(call_name)}\s*\([^;{{}}]*\)\s*;\s*$")
    match = pattern.search(body_text)
    if not match:
        return None
    return (match.start(), match.end())


def _insert_init_call_at_top(body_text: str, call_name: str) -> str:
    lines = body_text.splitlines()
    indent = "    "
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        leading = line[: len(line) - len(line.lstrip())]
        indent = leading or indent
        break
    prefix = "\n" if body_text and not body_text.startswith("\n") else ""
    return f"{prefix}{indent}{call_name}();\n{body_text.lstrip()}"


def _module_api_used(text_no_comments: str, module_name: str, init_name: str) -> bool:
    prefix = f"{module_name.upper()}_"
    call_re = re.compile(rf"\b({re.escape(prefix)}[A-Za-z_]\w*)\s*\(")
    for match in call_re.finditer(text_no_comments):
        name = str(match.group(1))
        if name == init_name:
            continue
        return True
    return False


def _enforce_init_before_use(
    source_text: str,
    *,
    module_init_contract: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cfg = _as_dict(module_init_contract)
    policy = _as_dict(cfg.get("policy"))
    modules = _as_dict(cfg.get("modules"))
    enforce = bool(policy.get("enforce_pre_use_init", True))
    if not enforce or not modules:
        return {
            "text": source_text,
            "changed": False,
            "actions": [],
            "failures": [],
        }

    working = str(source_text or "")
    changed = False
    actions: List[str] = []
    failures: List[str] = []
    text_no_comments = _strip_c_comments(working)
    init_fn = _extract_app_intent_function(working, "APP_INTENT_Init")
    if not init_fn:
        if any(
            _module_api_used(text_no_comments, module_name, str(_as_dict(entry).get("init") or ""))
            for module_name, entry in modules.items()
            if str(_as_dict(entry).get("init") or "").strip()
        ):
            failures.append("Missing APP_INTENT_Init; cannot enforce module init-before-use invariants.")
        return {
            "text": working,
            "changed": changed,
            "actions": actions,
            "failures": failures,
        }

    for module_name, entry in modules.items():
        module_info = _as_dict(entry)
        init_name = str(module_info.get("init") or "").strip()
        if not init_name:
            continue
        init_arity = module_info.get("arity")
        if not _module_api_used(text_no_comments, module_name, init_name):
            continue

        init_fn = _extract_app_intent_function(working, "APP_INTENT_Init")
        if not init_fn:
            failures.append(f"{module_name}: APP_INTENT_Init missing while {module_name}_* APIs are used.")
            continue
        init_call_exists_anywhere = re.search(rf"\b{re.escape(init_name)}\s*\(", text_no_comments) is not None
        if init_call_exists_anywhere:
            continue

        init_body = str(init_fn.get("body") or "")
        if init_arity == 0:
            new_body = _insert_init_call_at_top(init_body, init_name)
            if new_body != init_body:
                working = (
                    working[: int(init_fn["body_start"])]
                    + new_body
                    + working[int(init_fn["body_end"]) :]
                )
                changed = True
                actions.append(f"Inserted missing {init_name}() in APP_INTENT_Init.")
                text_no_comments = _strip_c_comments(working)
                continue

        failures.append(
            f"{module_name}: missing required init call {init_name}() while {module_name}_* APIs are used."
        )

    return {
        "text": working,
        "changed": changed,
        "actions": actions,
        "failures": failures,
    }


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
    module_init_contract: Optional[Dict[str, Any]] = None,
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

    init_gate_result = _enforce_init_before_use(
        updated,
        module_init_contract=module_init_contract,
    )
    updated = str(init_gate_result.get("text", updated))
    actions.extend(list(init_gate_result.get("actions", [])))
    init_gate_failures = list(init_gate_result.get("failures", []))

    return {
        "text": updated,
        "changed": updated != text,
        "actions": actions,
        "init_gate_actions": list(init_gate_result.get("actions", [])),
        "init_gate_failures": init_gate_failures,
    }


def validate_intent_behavior_alignment(
    *,
    intent_text: str,
    app_intent_c_text: str,
    board_capabilities_header_text: str = "",
) -> Dict[str, Any]:
    """
    Intent-derived behavior validation without fixed command grammar assumptions.
    """
    intent = str(intent_text or "").lower()
    text = str(app_intent_c_text or "")
    header = str(board_capabilities_header_text or "")

    aliases_available = (
        re.search(r"#define\s+BOARD_USER_LED_A_PRESENT\s+1U", header) is not None
        and re.search(r"#define\s+BOARD_USER_LED_B_PRESENT\s+1U", header) is not None
    )
    requested_aliases: List[str] = []
    if re.search(r"\bled\s*a\b|\bled_a\b", intent):
        requested_aliases.append("LED_A")
    if re.search(r"\bled\s*b\b|\bled_b\b", intent):
        requested_aliases.append("LED_B")

    if not requested_aliases and ("led2" in intent or "led 2" in intent):
        requested_aliases.append("LED_A")
    if not requested_aliases and ("led3" in intent or "led 3" in intent):
        requested_aliases.append("LED_B")

    if not requested_aliases and "heartbeat" in intent and aliases_available:
        requested_aliases.append("LED_B")

    used_aliases: List[str] = []
    if re.search(r"\bBOARD_USER_LED_A_", text):
        used_aliases.append("LED_A")
    if re.search(r"\bBOARD_USER_LED_B_", text):
        used_aliases.append("LED_B")

    failures: List[str] = []
    warnings: List[str] = []
    for alias in requested_aliases:
        if alias not in used_aliases and aliases_available:
            failures.append(f"Intent references {alias.replace('_', ' ')}, but generated code does not use {alias} alias macros.")
    if not requested_aliases:
        warnings.append("No explicit LED alias target inferred from intent text; behavior check kept generic.")

    return {
        "requested_aliases": requested_aliases,
        "used_aliases": used_aliases,
        "passed": len(failures) == 0,
        "failures": failures,
        "warnings": warnings,
    }


def lint_app_intent_api_reuse(
    app_intent_c_text: str,
    recipe: Dict[str, Any],
    *,
    gio_header_text: str = "",
    board_capabilities_header_text: str = "",
    timing_recipe: Optional[Dict[str, Any]] = None,
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
    timing_cfg = _as_dict(timing_recipe)

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
        if timing_cfg:
            selected_source = str(timing_cfg.get("selected_source", "")).strip().lower()
            selected_apis = _as_dict(timing_cfg.get("selected_apis"))
            timer_calls = [
                str(selected_apis.get("get_time_ms") or ""),
                str(selected_apis.get("get_tick") or ""),
                str(selected_apis.get("elapsed_ms") or ""),
            ]
            timer_calls = [name for name in timer_calls if name]
            has_timer_call = any(re.search(rf"\b{re.escape(name)}\s*\(", text) for name in timer_calls)
            has_counter_based_gate = re.search(
                r"(tick|counter|heartbeat|blink)\w*\s*(\+\+|=\s*\w+\s*\+\s*1)",
                step_body,
                flags=re.IGNORECASE,
            ) is not None
            if selected_source == "hardware_timer" and has_led_write and not has_timer_call:
                warnings.append(
                    "APP_INTENT: timing recipe selected hardware timer source, but APP_INTENT_Step "
                    "does not call resolved timer APIs."
                )
            if selected_source == "hardware_timer" and has_counter_based_gate and not has_timer_call:
                warnings.append(
                    "APP_INTENT: counter/divider timing detected while hardware timer recipe is selected."
                )

    header_text = str(board_capabilities_header_text or "")
    aliases_present = (
        re.search(r"#define\s+BOARD_USER_LED_A_PRESENT\s+1U", header_text) is not None
        and re.search(r"#define\s+BOARD_USER_LED_B_PRESENT\s+1U", header_text) is not None
    )
    if aliases_present and re.search(r"\bBOARD_LED[23]_", text):
        warnings.append(
            "APP_INTENT: direct BOARD_LED2_/BOARD_LED3_ macro usage detected while BOARD_USER_LED_A/B aliases are available."
        )

    for alias in ("A", "B"):
        uses_alias_pin = re.search(
            rf"\bBOARD_USER_LED_{alias}_GIO_(?:PORT_INDEX|PORT)\b", text
        ) is not None and re.search(
            rf"\bBOARD_USER_LED_{alias}_GIO_PIN\b", text
        ) is not None
        uses_alias_polarity = re.search(
            rf"\bBOARD_USER_LED_{alias}_ACTIVE_(?:LOW|HIGH)\b", text
        ) is not None
        raw_write = re.search(
            rf"\bGIO_WritePin\s*\([^;]*BOARD_USER_LED_{alias}_GIO_[^;]*,\s*BOARD_USER_LED_{alias}_GIO_PIN\s*,\s*(?:true|false|0U|1U|0|1)\s*\)",
            text,
        )
        if aliases_present and uses_alias_pin and raw_write and not uses_alias_polarity:
            warnings.append(
                f"APP_INTENT: LED {alias} write path appears to ignore alias polarity macros "
                f"(BOARD_USER_LED_{alias}_ACTIVE_LOW/HIGH)."
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
