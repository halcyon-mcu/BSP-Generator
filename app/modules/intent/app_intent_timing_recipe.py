"""
Deterministic app-intent timing source resolver (RTI-preferred with fallback).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _get_timing_policy(bringup_contract: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    contract = _as_dict(bringup_contract)
    app_intent = _as_dict(contract.get("app_intent"))
    timing = _as_dict(app_intent.get("timing"))
    return {
        "prefer_hardware_timer": bool(timing.get("prefer_hardware_timer", True)),
        "preferred_module": str(timing.get("preferred_module", "RTI")).strip().upper() or "RTI",
        "fallback": str(timing.get("fallback", "software_divider")).strip().lower() or "software_divider",
        "heartbeat_hz": float(timing.get("heartbeat_hz", 1.0) or 1.0),
        "blink_on_ms": int(timing.get("blink_on_ms", 150) or 150),
        "blink_off_ms": int(timing.get("blink_off_ms", 150) or 150),
    }


def _get_module_contract(api_contract_manifest: Optional[Dict[str, Any]], module_name: str) -> Dict[str, Any]:
    modules = _as_dict(_as_dict(api_contract_manifest).get("modules"))
    return _as_dict(modules.get(module_name.upper()))


def _extract_timer_symbol_candidates(
    *,
    module_name: str,
    module_contract: Dict[str, Any],
    driver_source_symbols: Optional[Dict[str, List[str]]] = None,
) -> List[str]:
    prefix = f"{module_name.upper()}_"
    capabilities = _as_dict(module_contract.get("capabilities"))
    functions = _as_dict(module_contract.get("functions"))
    candidates: List[str] = []

    for value in capabilities.values():
        if isinstance(value, str) and value.strip().upper().startswith(prefix):
            candidates.append(value.strip())
    for fn_name in functions.keys():
        if isinstance(fn_name, str) and fn_name.strip().upper().startswith(prefix):
            candidates.append(fn_name.strip())

    source_symbols = driver_source_symbols if isinstance(driver_source_symbols, dict) else {}
    for symbols in source_symbols.values():
        if not isinstance(symbols, list):
            continue
        for symbol in symbols:
            if isinstance(symbol, str) and symbol.strip().upper().startswith(prefix):
                candidates.append(symbol.strip())

    unique = sorted(set(candidates))
    return unique


def _pick_timer_apis(symbols: List[str]) -> Dict[str, Optional[str]]:
    normalized = [name for name in symbols if isinstance(name, str)]
    upper_map = {name.upper(): name for name in normalized}

    def _pick(*tokens: str) -> Optional[str]:
        for upper_name, original in upper_map.items():
            if all(token in upper_name for token in tokens):
                return original
        return None

    return {
        "init": _pick("INIT"),
        "start": _pick("START"),
        "enable_interrupt": _pick("ENABLE", "INT") or _pick("ENABLE", "IRQ"),
        "get_tick": _pick("GET", "TICK") or _pick("READ", "COUNTER"),
        "get_time_ms": _pick("TIME", "MS") or _pick("MILLIS") or _pick("TIMESTAMP"),
        "elapsed_ms": _pick("ELAPSED", "MS"),
    }


def _resolve_rti_irq(irq_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    data = _as_dict(irq_data)
    irqs = data.get("irqs", [])
    if not isinstance(irqs, list):
        return {"name": "", "number": None}

    candidates: List[Dict[str, Any]] = []
    for irq in irqs:
        if not isinstance(irq, dict):
            continue
        name = str(irq.get("name") or "").strip()
        number = irq.get("number")
        if "RTI" not in name.upper():
            continue
        candidates.append({"name": name, "number": number})

    if not candidates:
        return {"name": "", "number": None}

    for preferred in ("RTI_COMPARE0", "RTI_COMP0", "RTI_COMPARE1", "RTI_COMP1"):
        for candidate in candidates:
            if preferred in str(candidate.get("name", "")).upper():
                return candidate
    return candidates[0]


def _pick_vim_apis(vim_symbols: List[str]) -> Dict[str, Optional[str]]:
    names = [name for name in vim_symbols if isinstance(name, str)]
    upper_map = {name.upper(): name for name in names}

    def _pick(*tokens: str) -> Optional[str]:
        for upper_name, original in upper_map.items():
            if all(token in upper_name for token in tokens):
                return original
        return None

    return {
        "register_isr": _pick("REGISTER", "ISR") or _pick("SET", "ISR"),
        "enable_irq": _pick("ENABLE", "IRQ") or _pick("ENABLE", "CHANNEL"),
    }


def resolve_app_intent_timing_recipe(
    *,
    bringup_contract: Optional[Dict[str, Any]],
    api_contract_manifest: Optional[Dict[str, Any]],
    driver_source_symbols: Optional[Dict[str, List[str]]] = None,
    irq_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Resolve preferred app-intent timing source from bringup contract + API contract.
    """
    policy = _get_timing_policy(bringup_contract)
    module_name = str(policy.get("preferred_module", "RTI")).upper()
    module_contract = _get_module_contract(api_contract_manifest, module_name)
    module_symbols = _extract_timer_symbol_candidates(
        module_name=module_name,
        module_contract=module_contract,
        driver_source_symbols=driver_source_symbols,
    )
    selected_apis = _pick_timer_apis(module_symbols)
    rti_irq = _resolve_rti_irq(irq_data)

    vim_contract = _get_module_contract(api_contract_manifest, "VIM")
    vim_symbols = _extract_timer_symbol_candidates(
        module_name="VIM",
        module_contract=vim_contract,
        driver_source_symbols=driver_source_symbols,
    )
    vim_apis = _pick_vim_apis(vim_symbols)

    selected_source = "software_divider"
    if bool(policy.get("prefer_hardware_timer", True)) and module_symbols:
        selected_source = "hardware_timer"
    elif str(policy.get("fallback")) == "none":
        selected_source = "none"

    wiring_requirements = {
        "requires_irq_path": bool(selected_source == "hardware_timer"),
        "rti_irq_name": str(rti_irq.get("name") or ""),
        "rti_irq_number": rti_irq.get("number"),
        "rti_enable_interrupt_api": selected_apis.get("enable_interrupt"),
        "vim_register_isr_api": vim_apis.get("register_isr"),
        "vim_enable_irq_api": vim_apis.get("enable_irq"),
    }

    return {
        "policy": policy,
        "selected_source": selected_source,
        "selected_module": module_name,
        "module_symbols": module_symbols,
        "selected_apis": selected_apis,
        "wiring_requirements": wiring_requirements,
        "fallback_used": selected_source != "hardware_timer",
    }


def build_app_intent_timing_recipe_text(recipe: Dict[str, Any]) -> str:
    """
    Render deterministic timing recipe text for prompt context.
    """
    policy = _as_dict(recipe.get("policy"))
    selected_source = str(recipe.get("selected_source", "software_divider"))
    selected_module = str(recipe.get("selected_module", "RTI"))
    selected_apis = _as_dict(recipe.get("selected_apis"))
    wiring = _as_dict(recipe.get("wiring_requirements"))
    module_symbols = recipe.get("module_symbols", [])
    if not isinstance(module_symbols, list):
        module_symbols = []

    lines: List[str] = [
        f"timing.prefer_hardware_timer: {bool(policy.get('prefer_hardware_timer', True))}",
        f"timing.preferred_module: {selected_module}",
        f"timing.fallback: {policy.get('fallback', 'software_divider')}",
        f"timing.heartbeat_hz: {policy.get('heartbeat_hz', 1.0)}",
        f"timing.blink_on_ms: {policy.get('blink_on_ms', 150)}",
        f"timing.blink_off_ms: {policy.get('blink_off_ms', 150)}",
        f"timing.selected_source: {selected_source}",
    ]

    if selected_source == "hardware_timer":
        lines.extend(
            [
                f"{selected_module}.api.init: {selected_apis.get('init') or '<optional>'}",
                f"{selected_module}.api.start: {selected_apis.get('start') or '<optional>'}",
                f"{selected_module}.api.enable_interrupt: {selected_apis.get('enable_interrupt') or '<optional>'}",
                f"{selected_module}.api.get_tick: {selected_apis.get('get_tick') or '<missing>'}",
                f"{selected_module}.api.get_time_ms: {selected_apis.get('get_time_ms') or '<missing>'}",
                f"{selected_module}.api.elapsed_ms: {selected_apis.get('elapsed_ms') or '<optional>'}",
                f"{selected_module}.symbols_available: {', '.join(module_symbols[:20]) if module_symbols else '<none>'}",
                f"{selected_module}.irq.name: {wiring.get('rti_irq_name') or '<missing>'}",
                f"{selected_module}.irq.number: {wiring.get('rti_irq_number') if wiring.get('rti_irq_number') is not None else '<missing>'}",
                f"VIM.api.register_isr: {wiring.get('vim_register_isr_api') or '<optional>'}",
                f"VIM.api.enable_irq: {wiring.get('vim_enable_irq_api') or '<optional>'}",
                "wiring.rule: when RTI hardware timer mode is used, include complete RTI->VIM->IRQ path and keep APP_INTENT_Step non-blocking",
            ]
        )
    elif selected_source == "software_divider":
        lines.extend(
            [
                "fallback.strategy: software_divider",
                "fallback.rule: use monotonic step counter with conservative divider for visible cadence",
                "fallback.rule: keep APP_INTENT_Step non-blocking",
            ]
        )
    else:
        lines.append("fallback.strategy: none")

    return "\n".join(lines)


def validate_rti_vim_wiring_in_app_intent(app_intent_text: str, timing_recipe: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate that hardware-timer timing recipe requirements are reflected in app_intent.c.
    """
    text = str(app_intent_text or "")
    selected_source = str(_as_dict(timing_recipe).get("selected_source", "")).strip().lower()
    if selected_source != "hardware_timer":
        return {
            "required": False,
            "passed": True,
            "failures": [],
            "checks": [],
        }

    selected_apis = _as_dict(_as_dict(timing_recipe).get("selected_apis"))
    wiring = _as_dict(_as_dict(timing_recipe).get("wiring_requirements"))
    failures: List[str] = []
    checks: List[str] = []

    timer_api_candidates = [
        str(selected_apis.get("get_time_ms") or ""),
        str(selected_apis.get("get_tick") or ""),
        str(selected_apis.get("elapsed_ms") or ""),
    ]
    timer_api_candidates = [name for name in timer_api_candidates if name]
    timer_api_used = any(re.search(rf"\b{re.escape(name)}\s*\(", text) for name in timer_api_candidates)
    checks.append(f"timer_api_used={timer_api_used}")
    if not timer_api_used:
        failures.append("Hardware timer mode selected but app_intent.c does not call resolved RTI time APIs.")

    rti_enable_api = str(wiring.get("rti_enable_interrupt_api") or "")
    if rti_enable_api:
        used = re.search(rf"\b{re.escape(rti_enable_api)}\s*\(", text) is not None
        checks.append(f"{rti_enable_api}={used}")
        if not used:
            failures.append(f"Missing RTI interrupt enable call: {rti_enable_api}().")

    vim_register_api = str(wiring.get("vim_register_isr_api") or "")
    if vim_register_api:
        used = re.search(rf"\b{re.escape(vim_register_api)}\s*\(", text) is not None
        checks.append(f"{vim_register_api}={used}")
        if not used:
            failures.append(f"Missing VIM ISR registration call: {vim_register_api}().")

    vim_enable_api = str(wiring.get("vim_enable_irq_api") or "")
    if vim_enable_api:
        used = re.search(rf"\b{re.escape(vim_enable_api)}\s*\(", text) is not None
        checks.append(f"{vim_enable_api}={used}")
        if not used:
            failures.append(f"Missing VIM IRQ enable call: {vim_enable_api}().")

    irq_name = str(wiring.get("rti_irq_name") or "")
    if irq_name:
        mentioned = irq_name in text
        checks.append(f"{irq_name}_mentioned={mentioned}")
        if not mentioned:
            failures.append(f"Missing reference to resolved RTI IRQ name {irq_name} in wiring path.")

    return {
        "required": True,
        "passed": len(failures) == 0,
        "failures": failures,
        "checks": checks,
    }
