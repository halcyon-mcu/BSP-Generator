"""
Board capability manifest extraction and app-intent reference validation helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import get_close_matches
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

_ALLOWED_QUALITIES = {"proven", "schematic_only", "needs_hw_verify"}
_REFERENCE_HINT_TERMS = ("led", "button", "switch", "uart", "lin", "sci", "serial")
_COLOR_ALIAS_MAP = {
    "grn": "green",
    "green": "green",
    "red": "red",
    "ylw": "yellow",
    "yellow": "yellow",
    "blu": "blue",
    "blue": "blue",
}


@dataclass(frozen=True)
class CapabilityRef:
    canonical_id: str
    kind: str
    quality: str
    description: str
    aliases: Tuple[str, ...]
    provenance: str


def normalize_data_quality(value: Any, default: str = "proven") -> str:
    raw = str(value or "").strip().lower()
    if raw in _ALLOWED_QUALITIES:
        return raw
    return default


def _canonical_designator(value: Any, fallback_prefix: str, index: int) -> str:
    token = str(value or "").strip().upper()
    if token:
        return token
    return f"{fallback_prefix}{index}"


def _clean_aliases(aliases: Iterable[str]) -> Tuple[str, ...]:
    out: List[str] = []
    seen: Set[str] = set()
    for alias in aliases:
        normalized = str(alias or "").strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return tuple(out)


def _component_quality(
    canonical_id: str,
    *,
    item: Optional[Dict[str, Any]],
    quality_components: Dict[str, Any],
    default_quality: str,
) -> str:
    if canonical_id in quality_components:
        return normalize_data_quality(quality_components.get(canonical_id), default_quality)

    if isinstance(item, dict):
        item_ext = item.get("x-ext", {}) if isinstance(item.get("x-ext", {}), dict) else {}
        item_quality = item_ext.get("data_quality")
        if item_quality is not None:
            return normalize_data_quality(item_quality, default_quality)

    return normalize_data_quality(default_quality, "proven")


def _component_provenance(
    canonical_id: str,
    *,
    item: Optional[Dict[str, Any]],
    provenance_components: Dict[str, Any],
    default_provenance: str,
) -> str:
    if canonical_id in provenance_components:
        return str(provenance_components.get(canonical_id) or default_provenance)

    if isinstance(item, dict):
        item_ext = item.get("x-ext", {}) if isinstance(item.get("x-ext", {}), dict) else {}
        item_provenance = item_ext.get("provenance")
        if isinstance(item_provenance, str) and item_provenance.strip():
            return item_provenance.strip()

    return default_provenance


def _as_entry_dict(ref: CapabilityRef) -> Dict[str, Any]:
    return {
        "canonical_id": ref.canonical_id,
        "kind": ref.kind,
        "quality": ref.quality,
        "description": ref.description,
        "aliases": list(ref.aliases),
        "provenance": ref.provenance,
    }


def _escape_c_string(value: Any) -> str:
    text = str(value or "")
    text = text.replace("\\", "\\\\")
    text = text.replace('"', '\\"')
    return text


def _sanitize_macro_token(value: Any, fallback: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_]", "_", str(value or "").strip().upper())
    token = re.sub(r"_+", "_", token).strip("_")
    if not token:
        token = fallback
    if token[0].isdigit():
        token = f"X_{token}"
    return token


def _parse_gpio_port_pin(value: Any) -> Tuple[Optional[str], Optional[int]]:
    match = re.match(r"^\s*GIO([A-Za-z])\[(\d+)\]\s*$", str(value or ""))
    if not match:
        return (None, None)
    return (match.group(1).upper(), int(match.group(2)))


def _parse_active_low(value: Any) -> Optional[bool]:
    state = str(value or "").strip().upper()
    if state == "LOW":
        return True
    if state == "HIGH":
        return False
    return None


def _normalize_led_designator(value: Any) -> str:
    token = str(value or "").strip().upper()
    return re.sub(r"\s+", "", token)


def _extract_led_alias_policy(bringup_contract: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    contract = bringup_contract if isinstance(bringup_contract, dict) else {}
    app_intent = contract.get("app_intent", {})
    if not isinstance(app_intent, dict):
        app_intent = {}
    policy = app_intent.get("led_aliases", {})
    if not isinstance(policy, dict):
        policy = {}
    return policy


def _build_pinmux_signal_index(pinmux_data: Optional[Dict[str, Any]]) -> Tuple[Dict[str, Set[int]], Dict[int, Set[str]]]:
    signal_to_pins: Dict[str, Set[int]] = {}
    pin_to_signals: Dict[int, Set[str]] = {}
    data = pinmux_data if isinstance(pinmux_data, dict) else {}
    for pin in data.get("pins", []) if isinstance(data.get("pins", []), list) else []:
        if not isinstance(pin, dict):
            continue
        package_pin = pin.get("package_pin")
        if not isinstance(package_pin, int):
            continue
        functions = pin.get("functions", [])
        if not isinstance(functions, list):
            continue
        for fn in functions:
            if not isinstance(fn, dict):
                continue
            signal = str(fn.get("signal") or "").strip().upper()
            if not signal:
                continue
            signal_to_pins.setdefault(signal, set()).add(package_pin)
            pin_to_signals.setdefault(package_pin, set()).add(signal)
    return signal_to_pins, pin_to_signals


def validate_led_alias_bindings_with_pinmux(
    board_data: Dict[str, Any],
    *,
    pinmux_data: Optional[Dict[str, Any]] = None,
    bringup_contract: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Validate LED alias source bindings against board + pinmux signal mappings.
    """
    bindings = resolve_led_alias_bindings(board_data, bringup_contract)
    signal_to_pins, pin_to_signals = _build_pinmux_signal_index(pinmux_data)
    checks: List[Dict[str, Any]] = []
    conflicts: List[str] = []

    for alias in ("LED_A", "LED_B"):
        binding = bindings.get(alias, {})
        source_entry = binding.get("source_entry")
        source_name = str(binding.get("source") or "")
        if not isinstance(source_entry, dict):
            conflicts.append(f"{alias}: source LED {source_name or '<missing>'} not resolved in board.yaml")
            continue

        gpio_signal = str(source_entry.get("gpio") or "").strip().upper()
        mcu_pin = source_entry.get("mcu_pin")
        if not gpio_signal or not isinstance(mcu_pin, int):
            conflicts.append(f"{alias}: source {source_name} missing gpio or mcu_pin in board.yaml")
            continue

        mapped_pins = sorted(signal_to_pins.get(gpio_signal, set()))
        pin_signals = sorted(pin_to_signals.get(mcu_pin, set()))
        signal_matches_pin = mcu_pin in set(mapped_pins)
        pin_exposes_signal = gpio_signal in set(pin_signals)

        check = {
            "alias": alias,
            "source": source_name,
            "gpio_signal": gpio_signal,
            "board_pin": mcu_pin,
            "pinmux_signal_pins": mapped_pins,
            "signal_matches_board_pin": signal_matches_pin,
            "board_pin_exposes_signal": pin_exposes_signal,
        }
        checks.append(check)

        if mapped_pins and not signal_matches_pin:
            conflicts.append(
                f"{alias}: {source_name} board pin {mcu_pin} conflicts with pinmux {gpio_signal} pins {mapped_pins}"
            )
        if pin_signals and not pin_exposes_signal:
            conflicts.append(
                f"{alias}: board pin {mcu_pin} does not expose {gpio_signal} in pinmux (signals={pin_signals})"
            )
        if not mapped_pins:
            conflicts.append(f"{alias}: pinmux has no mapping for signal {gpio_signal}")

    return {
        "passed": len(conflicts) == 0,
        "checks": checks,
        "conflicts": conflicts,
    }


def resolve_led_alias_bindings(
    board_data: Dict[str, Any],
    bringup_contract: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Resolve user-facing LED aliases (LED_A / LED_B) to concrete board LEDs.
    """
    led_entries = board_data.get("leds", [])
    if not isinstance(led_entries, list):
        led_entries = []

    led_lookup: Dict[str, Dict[str, Any]] = {}
    for idx, led in enumerate(led_entries, start=1):
        if not isinstance(led, dict):
            continue
        designator = _normalize_led_designator(led.get("designator") or f"LED{idx}")
        if not designator:
            continue
        led_lookup[designator] = led

    policy = _extract_led_alias_policy(bringup_contract)
    default_roles = policy.get("default_roles", {})
    if not isinstance(default_roles, dict):
        default_roles = {}

    default_sources = {"LED_A": "LED2", "LED_B": "LED3"}
    bindings: Dict[str, Dict[str, Any]] = {}
    for alias_name, default_source in default_sources.items():
        alias_cfg = policy.get(alias_name, {})
        if not isinstance(alias_cfg, dict):
            alias_cfg = {}
        source_name = _normalize_led_designator(alias_cfg.get("source") or default_source)
        source_entry = led_lookup.get(source_name)
        inherited_active_low = _parse_active_low(source_entry.get("active_state")) if source_entry else None
        override_value = alias_cfg.get("active_low_override")
        active_low = override_value if isinstance(override_value, bool) else inherited_active_low
        role = str(default_roles.get(alias_name, "")).strip()
        if not role:
            role = "command" if alias_name == "LED_A" else "heartbeat"
        bindings[alias_name] = {
            "alias": alias_name,
            "source": source_name,
            "resolved": source_entry is not None,
            "role": role,
            "active_low": active_low,
            "source_entry": source_entry,
        }
    return bindings


def validate_led_alias_macro_consistency(
    board_capabilities_header_text: str,
    board_data: Dict[str, Any],
    *,
    bringup_contract: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Validate that emitted alias macros are coherent with alias source bindings.
    """
    text = str(board_capabilities_header_text or "")
    bindings = resolve_led_alias_bindings(board_data, bringup_contract)
    checks: List[Dict[str, Any]] = []
    failures: List[str] = []

    def _macro_int(name: str) -> Optional[int]:
        match = re.search(rf"(?m)^\s*#define\s+{re.escape(name)}\s+([0-9]+)U\s*$", text)
        return int(match.group(1)) if match else None

    def _macro_char(name: str) -> Optional[str]:
        match = re.search(rf"(?m)^\s*#define\s+{re.escape(name)}\s+'([^'])'\s*$", text)
        return str(match.group(1)).upper() if match else None

    def _macro_str(name: str) -> Optional[str]:
        match = re.search(rf'(?m)^\s*#define\s+{re.escape(name)}\s+"([^"]*)"\s*$', text)
        return str(match.group(1)).strip().upper() if match else None

    for alias in ("LED_A", "LED_B"):
        binding = bindings.get(alias, {})
        source = str(binding.get("source") or "").strip().upper()
        source_entry = binding.get("source_entry")
        alias_macro = f"BOARD_USER_{alias}"
        source_macro = f"BOARD_{source}"

        alias_source = _macro_str(f"{alias_macro}_SOURCE")
        alias_present = _macro_int(f"{alias_macro}_PRESENT")
        alias_port = _macro_char(f"{alias_macro}_GIO_PORT")
        alias_port_index = _macro_int(f"{alias_macro}_GIO_PORT_INDEX")
        alias_pin = _macro_int(f"{alias_macro}_GIO_PIN")
        alias_mcu_pin = _macro_int(f"{alias_macro}_MCU_PIN")

        source_port = _macro_char(f"{source_macro}_GIO_PORT")
        source_port_index = _macro_int(f"{source_macro}_GIO_PORT_INDEX")
        source_pin = _macro_int(f"{source_macro}_GIO_PIN")
        source_mcu_pin = _macro_int(f"{source_macro}_MCU_PIN")

        expected_port: Optional[str] = None
        expected_pin: Optional[int] = None
        expected_mcu_pin: Optional[int] = None
        expected_port_index: Optional[int] = None
        if isinstance(source_entry, dict):
            expected_port, expected_pin = _parse_gpio_port_pin(source_entry.get("gpio"))
            expected_mcu_pin = source_entry.get("mcu_pin") if isinstance(source_entry.get("mcu_pin"), int) else None
            if expected_port in {"A", "B"}:
                expected_port_index = 1 if expected_port == "B" else 0

        checks.append(
            {
                "alias": alias,
                "expected_source": source,
                "header_source": alias_source or "",
                "alias_present": alias_present,
                "alias_gpio_port": alias_port or "",
                "alias_gpio_pin": alias_pin,
                "alias_mcu_pin": alias_mcu_pin,
                "source_gpio_port": source_port or "",
                "source_gpio_pin": source_pin,
                "source_mcu_pin": source_mcu_pin,
            }
        )

        if alias_source != source:
            failures.append(f"{alias}: alias source macro mismatch (expected {source}, found {alias_source or '<missing>'})")

        if isinstance(source_entry, dict):
            if alias_present != 1:
                failures.append(f"{alias}: expected present=1U for resolved source {source}.")
            if expected_port is not None and alias_port != expected_port:
                failures.append(f"{alias}: alias GPIO port mismatch (expected {expected_port}, found {alias_port or '<missing>'}).")
            if expected_pin is not None and alias_pin != expected_pin:
                failures.append(f"{alias}: alias GPIO pin mismatch (expected {expected_pin}, found {alias_pin}).")
            if expected_port_index is not None and alias_port_index != expected_port_index:
                failures.append(
                    f"{alias}: alias GPIO port index mismatch (expected {expected_port_index}, found {alias_port_index})."
                )
            if expected_mcu_pin is not None and alias_mcu_pin != expected_mcu_pin:
                failures.append(f"{alias}: alias MCU pin mismatch (expected {expected_mcu_pin}, found {alias_mcu_pin}).")
        else:
            if alias_present not in {0, None}:
                failures.append(f"{alias}: unresolved source should emit present=0U.")

        if source_port is not None and alias_port is not None and alias_port != source_port:
            failures.append(f"{alias}: alias GPIO port does not match {source} GPIO port macro.")
        if source_port_index is not None and alias_port_index is not None and alias_port_index != source_port_index:
            failures.append(f"{alias}: alias GPIO port index does not match {source} GPIO port index macro.")
        if source_pin is not None and alias_pin is not None and alias_pin != source_pin:
            failures.append(f"{alias}: alias GPIO pin does not match {source} GPIO pin macro.")
        if source_mcu_pin is not None and alias_mcu_pin is not None and alias_mcu_pin != source_mcu_pin:
            failures.append(f"{alias}: alias MCU pin does not match {source} MCU pin macro.")

    return {
        "passed": len(failures) == 0,
        "checks": checks,
        "failures": failures,
        "bindings": bindings,
    }


def _parse_instance_index(value: Any) -> Optional[int]:
    match = re.search(r"(\d+)", str(value or ""))
    if not match:
        return None
    return int(match.group(1))


def build_board_capability_header(
    board_data: Dict[str, Any],
    *,
    capability_manifest: Optional[Dict[str, Any]] = None,
    bringup_contract: Optional[Dict[str, Any]] = None,
    pinmux_data: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Build a deterministic C header with board-level capability macros.

    The header is intended as a lightweight bridge for generated firmware/app code
    and post-generation prompt workflows.
    """
    board = board_data.get("board", {}) if isinstance(board_data.get("board", {}), dict) else {}
    board_name = str(
        board.get("name")
        or board_data.get("target_board")
        or "UNKNOWN_BOARD"
    ).strip()

    comms = board_data.get("communication", {}) if isinstance(board_data.get("communication", {}), dict) else {}
    preferred = comms.get("preferred_debug_path", {}) if isinstance(comms.get("preferred_debug_path", {}), dict) else {}
    preferred_peripheral = str(preferred.get("peripheral", "")).strip().upper()
    preferred_mode = str(preferred.get("mode", "")).strip().upper()
    preferred_instance = _parse_instance_index(preferred.get("instance"))
    preferred_rx_pin = preferred.get("rx_pin") if isinstance(preferred.get("rx_pin"), int) else None
    preferred_tx_pin = preferred.get("tx_pin") if isinstance(preferred.get("tx_pin"), int) else None
    preferred_af = preferred.get("af") if isinstance(preferred.get("af"), int) else None

    leds = board_data.get("leds", [])
    led_entries = [entry for entry in leds if isinstance(entry, dict)] if isinstance(leds, list) else []

    buttons = board_data.get("buttons", [])
    button_entries = [entry for entry in buttons if isinstance(entry, dict)] if isinstance(buttons, list) else []
    led_alias_bindings = resolve_led_alias_bindings(board_data, bringup_contract)
    alias_validation = validate_led_alias_bindings_with_pinmux(
        board_data,
        pinmux_data=pinmux_data,
        bringup_contract=bringup_contract,
    )

    allowed_refs = []
    if isinstance(capability_manifest, dict):
        refs = capability_manifest.get("allowed_references", [])
        if isinstance(refs, list):
            allowed_refs = [ref for ref in refs if isinstance(ref, dict)]

    lines: List[str] = [
        "/**",
        " * @file board_capabilities.h",
        " * @brief Auto-generated board capability map from board.yaml.",
        " *",
        " * This header provides stable macros for board pin/path metadata so",
        " * generated firmware can reference LEDs, buttons, and terminal UART routing",
        " * without duplicating board-specific parsing logic.",
        " */",
        "",
        "#ifndef BOARD_CAPABILITIES_H",
        "#define BOARD_CAPABILITIES_H",
        "",
        "#include <stdint.h>",
        "",
        f"#define BOARD_NAME \"{_escape_c_string(board_name)}\"",
        f"#define BOARD_LED_COUNT {len(led_entries)}U",
        f"#define BOARD_BUTTON_COUNT {len(button_entries)}U",
        f"#define BOARD_ALLOWED_REF_COUNT {len(allowed_refs)}U",
        "",
    ]

    terminal_present = bool(preferred)
    lines.extend(
        [
            "/* Preferred terminal/UART routing */",
            f"#define BOARD_TERMINAL_UART_PRESENT {(1 if terminal_present else 0)}U",
            f"#define BOARD_TERMINAL_UART_OVER_LIN {(1 if preferred_peripheral == 'LIN' else 0)}U",
            f"#define BOARD_TERMINAL_UART_MODE_SCI {(1 if preferred_mode == 'SCI' else 0)}U",
            f"#define BOARD_TERMINAL_UART_INSTANCE {(preferred_instance if preferred_instance is not None else 0)}U",
            f"#define BOARD_TERMINAL_UART_RX_PIN {(preferred_rx_pin if preferred_rx_pin is not None else 0)}U",
            f"#define BOARD_TERMINAL_UART_TX_PIN {(preferred_tx_pin if preferred_tx_pin is not None else 0)}U",
            f"#define BOARD_TERMINAL_UART_AF {(preferred_af if preferred_af is not None else 0)}U",
            f"#define BOARD_TERMINAL_UART_PERIPHERAL \"{_escape_c_string(preferred_peripheral)}\"",
            f"#define BOARD_TERMINAL_UART_MODE \"{_escape_c_string(preferred_mode)}\"",
            "",
        ]
    )

    for index, led in enumerate(led_entries, start=1):
        designator = str(led.get("designator") or f"LED{index}").strip().upper()
        macro = _sanitize_macro_token(designator, f"LED{index}")
        gpio_port, gpio_pin = _parse_gpio_port_pin(led.get("gpio"))
        mcu_pin = led.get("mcu_pin") if isinstance(led.get("mcu_pin"), int) else None
        active_low = _parse_active_low(led.get("active_state"))
        label = str(led.get("function") or "").strip()
        lines.extend(
            [
                f"/* LED: {designator} */",
                f"#define BOARD_{macro}_PRESENT 1U",
                f"#define BOARD_{macro}_INDEX {index}U",
                f"#define BOARD_{macro}_HAS_GIO {(1 if gpio_port is not None else 0)}U",
                f"#define BOARD_{macro}_GIO_PORT '{gpio_port if gpio_port is not None else '0'}'",
                f"#define BOARD_{macro}_GIO_PORT_INDEX {((1 if gpio_port == 'B' else 0) if gpio_port is not None else 0)}U",
                f"#define BOARD_{macro}_GIO_PIN {(gpio_pin if gpio_pin is not None else 0)}U",
                f"#define BOARD_{macro}_MCU_PIN {(mcu_pin if mcu_pin is not None else 0)}U",
                f"#define BOARD_{macro}_ACTIVE_LOW {(1 if active_low is True else 0)}U",
                f"#define BOARD_{macro}_ACTIVE_HIGH {(1 if active_low is False else 0)}U",
                f"#define BOARD_{macro}_LABEL \"{_escape_c_string(label or designator)}\"",
                "",
            ]
        )

    for index, button in enumerate(button_entries, start=1):
        designator = str(button.get("designator") or f"BTN{index}").strip().upper()
        macro = _sanitize_macro_token(designator, f"BTN{index}")
        gpio_port, gpio_pin = _parse_gpio_port_pin(button.get("gpio"))
        mcu_pin = button.get("mcu_pin") if isinstance(button.get("mcu_pin"), int) else None
        active_low = _parse_active_low(button.get("active_state"))
        label = str(button.get("function") or "").strip()
        lines.extend(
            [
                f"/* Button: {designator} */",
                f"#define BOARD_{macro}_PRESENT 1U",
                f"#define BOARD_{macro}_INDEX {index}U",
                f"#define BOARD_{macro}_HAS_GIO {(1 if gpio_port is not None else 0)}U",
                f"#define BOARD_{macro}_GIO_PORT '{gpio_port if gpio_port is not None else '0'}'",
                f"#define BOARD_{macro}_GIO_PORT_INDEX {((1 if gpio_port == 'B' else 0) if gpio_port is not None else 0)}U",
                f"#define BOARD_{macro}_GIO_PIN {(gpio_pin if gpio_pin is not None else 0)}U",
                f"#define BOARD_{macro}_MCU_PIN {(mcu_pin if mcu_pin is not None else 0)}U",
                f"#define BOARD_{macro}_ACTIVE_LOW {(1 if active_low is True else 0)}U",
                f"#define BOARD_{macro}_ACTIVE_HIGH {(1 if active_low is False else 0)}U",
                f"#define BOARD_{macro}_LABEL \"{_escape_c_string(label or designator)}\"",
                "",
            ]
        )

    for alias_name in ("LED_A", "LED_B"):
        binding = led_alias_bindings.get(alias_name, {})
        source_entry = binding.get("source_entry")
        source_name = str(binding.get("source") or "")
        macro = _sanitize_macro_token(alias_name, alias_name)
        if isinstance(source_entry, dict):
            gpio_port, gpio_pin = _parse_gpio_port_pin(source_entry.get("gpio"))
            mcu_pin = source_entry.get("mcu_pin") if isinstance(source_entry.get("mcu_pin"), int) else None
            active_low = binding.get("active_low")
            label = str(source_entry.get("function") or source_name or alias_name).strip()
            lines.extend(
                [
                    f"/* User LED alias: {alias_name} -> {source_name} */",
                    f"#define BOARD_USER_{macro}_PRESENT 1U",
                    f"#define BOARD_USER_{macro}_SOURCE \"{_escape_c_string(source_name)}\"",
                    f"#define BOARD_USER_{macro}_HAS_GIO {(1 if gpio_port is not None else 0)}U",
                    f"#define BOARD_USER_{macro}_GIO_PORT '{gpio_port if gpio_port is not None else '0'}'",
                    f"#define BOARD_USER_{macro}_GIO_PORT_INDEX {((1 if gpio_port == 'B' else 0) if gpio_port is not None else 0)}U",
                    f"#define BOARD_USER_{macro}_GIO_PIN {(gpio_pin if gpio_pin is not None else 0)}U",
                    f"#define BOARD_USER_{macro}_MCU_PIN {(mcu_pin if mcu_pin is not None else 0)}U",
                    f"#define BOARD_USER_{macro}_ACTIVE_LOW {(1 if active_low is True else 0)}U",
                    f"#define BOARD_USER_{macro}_ACTIVE_HIGH {(1 if active_low is False else 0)}U",
                    f"#define BOARD_USER_{macro}_LABEL \"{_escape_c_string(label)}\"",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    f"/* User LED alias: {alias_name} (unresolved) */",
                    f"#define BOARD_USER_{macro}_PRESENT 0U",
                    f"#define BOARD_USER_{macro}_SOURCE \"{_escape_c_string(source_name or alias_name)}\"",
                    f"#define BOARD_USER_{macro}_HAS_GIO 0U",
                    f"#define BOARD_USER_{macro}_GIO_PORT '0'",
                    f"#define BOARD_USER_{macro}_GIO_PORT_INDEX 0U",
                    f"#define BOARD_USER_{macro}_GIO_PIN 0U",
                    f"#define BOARD_USER_{macro}_MCU_PIN 0U",
                    f"#define BOARD_USER_{macro}_ACTIVE_LOW 0U",
                    f"#define BOARD_USER_{macro}_ACTIVE_HIGH 0U",
                    f"#define BOARD_USER_{macro}_LABEL \"{_escape_c_string(alias_name)}\"",
                    "",
                ]
            )

    lines.extend(
        [
            "#endif /* BOARD_CAPABILITIES_H */",
            "",
        ]
    )
    if not bool(alias_validation.get("passed", True)):
        lines.insert(-2, "/* WARN: LED alias/pinmux conflicts detected; see board_capability_manifest.json */")
    return "\n".join(lines)


def _extract_led_refs(
    board_data: Dict[str, Any],
    *,
    quality_components: Dict[str, Any],
    provenance_components: Dict[str, Any],
) -> List[CapabilityRef]:
    leds = board_data.get("leds", [])
    if not isinstance(leds, list):
        return []

    refs: List[CapabilityRef] = []
    for index, led in enumerate(leds, start=1):
        if not isinstance(led, dict):
            continue
        canonical = _canonical_designator(led.get("designator"), "LED", index)
        color = str(led.get("color", "")).strip()
        function = str(led.get("function", "")).strip()
        gpio = str(led.get("gpio", "")).strip()
        active_state = str(led.get("active_state", "")).strip()
        description = function or "Board LED"
        if gpio:
            description += f" ({gpio})"
        if active_state:
            description += f", active {active_state}"

        aliases = [
            canonical,
            canonical.replace("LED", "LED "),
            "led",
        ]
        if color:
            color_key = color.lower()
            aliases.append(f"{color_key} led")
            if color_key in _COLOR_ALIAS_MAP:
                aliases.append(f"{_COLOR_ALIAS_MAP[color_key]} led")
        if function:
            aliases.append(function.lower())

        quality = _component_quality(
            canonical,
            item=led,
            quality_components=quality_components,
            default_quality="proven",
        )
        provenance = _component_provenance(
            canonical,
            item=led,
            provenance_components=provenance_components,
            default_provenance="board.yaml:leds",
        )
        refs.append(
            CapabilityRef(
                canonical_id=canonical,
                kind="led",
                quality=quality,
                description=description,
                aliases=_clean_aliases(aliases),
                provenance=provenance,
            )
        )

    return refs


def _extract_button_refs(
    board_data: Dict[str, Any],
    *,
    quality_components: Dict[str, Any],
    provenance_components: Dict[str, Any],
) -> List[CapabilityRef]:
    buttons = board_data.get("buttons", [])
    if not isinstance(buttons, list):
        return []

    refs: List[CapabilityRef] = []
    for index, button in enumerate(buttons, start=1):
        if not isinstance(button, dict):
            continue
        canonical = _canonical_designator(button.get("designator"), "S", index)
        function = str(button.get("function", "")).strip()
        net_name = str(button.get("net_name", "")).strip()
        active_state = str(button.get("active_state", "")).strip()
        description = function or "Board button"
        if active_state:
            description += f", active {active_state}"
        if net_name:
            description += f" ({net_name})"

        aliases = [
            canonical,
            canonical.replace("S", "S "),
            "button",
            "switch",
        ]
        if function:
            aliases.append(function.lower())

        quality = _component_quality(
            canonical,
            item=button,
            quality_components=quality_components,
            default_quality="proven",
        )
        provenance = _component_provenance(
            canonical,
            item=button,
            provenance_components=provenance_components,
            default_provenance="board.yaml:buttons",
        )
        refs.append(
            CapabilityRef(
                canonical_id=canonical,
                kind="button",
                quality=quality,
                description=description,
                aliases=_clean_aliases(aliases),
                provenance=provenance,
            )
        )

    return refs


def _extract_recipe_refs(
    board_data: Dict[str, Any],
    *,
    quality_components: Dict[str, Any],
    provenance_components: Dict[str, Any],
) -> List[CapabilityRef]:
    refs: List[CapabilityRef] = []
    board_ext = board_data.get("x-ext", {}) if isinstance(board_data.get("x-ext", {}), dict) else {}
    recipes = board_ext.get("peripheral_recipes", {}) if isinstance(board_ext.get("peripheral_recipes", {}), dict) else {}

    for recipe_key, recipe in recipes.items():
        if not isinstance(recipe, dict):
            continue
        canonical = str(recipe.get("canonical_ref") or recipe_key).strip().upper()
        if not canonical:
            continue
        kind = str(recipe.get("kind") or "interface").strip().lower() or "interface"
        description = str(recipe.get("description") or f"Peripheral recipe {canonical}").strip()
        aliases: List[str] = [canonical, recipe_key]
        raw_aliases = recipe.get("aliases", [])
        if isinstance(raw_aliases, list):
            for alias in raw_aliases:
                if isinstance(alias, str):
                    aliases.append(alias)

        quality = normalize_data_quality(
            recipe.get("quality"),
            _component_quality(
                canonical,
                item=recipe,
                quality_components=quality_components,
                default_quality="schematic_only",
            ),
        )
        provenance = _component_provenance(
            canonical,
            item=recipe,
            provenance_components=provenance_components,
            default_provenance="board.yaml:x-ext.peripheral_recipes",
        )

        refs.append(
            CapabilityRef(
                canonical_id=canonical,
                kind=kind,
                quality=quality,
                description=description,
                aliases=_clean_aliases(aliases),
                provenance=provenance,
            )
        )

    return refs


def _extract_preferred_serial_path_ref(
    board_data: Dict[str, Any],
    *,
    quality_components: Dict[str, Any],
    provenance_components: Dict[str, Any],
) -> Optional[CapabilityRef]:
    comms = board_data.get("communication", {}) if isinstance(board_data.get("communication", {}), dict) else {}
    preferred = comms.get("preferred_debug_path", {}) if isinstance(comms.get("preferred_debug_path", {}), dict) else {}
    if not preferred:
        return None

    peripheral = str(preferred.get("peripheral", "")).strip().upper()
    mode = str(preferred.get("mode", "")).strip().upper()
    instance = str(preferred.get("instance", "")).strip().upper()

    if peripheral == "LIN" and mode == "SCI":
        canonical = "LIN1_SCI_PATH"
    elif peripheral and mode:
        canonical = f"{peripheral}_{mode}_PATH"
    else:
        canonical = "PREFERRED_DEBUG_PATH"

    description = str(preferred.get("note") or "Preferred board terminal path").strip()
    aliases = [
        canonical,
        "terminal",
        "uart",
        "serial",
        "debug uart",
        "lin sci",
    ]
    if instance:
        aliases.append(instance.lower())
    quality = _component_quality(
        canonical,
        item=preferred,
        quality_components=quality_components,
        default_quality="proven",
    )
    provenance = _component_provenance(
        canonical,
        item=preferred,
        provenance_components=provenance_components,
        default_provenance="board.yaml:communication.preferred_debug_path",
    )

    return CapabilityRef(
        canonical_id=canonical,
        kind="interface",
        quality=quality,
        description=description,
        aliases=_clean_aliases(aliases),
        provenance=provenance,
    )


def build_board_capability_manifest(
    board_data: Dict[str, Any],
    *,
    pinmux_data: Optional[Dict[str, Any]] = None,
    bringup_contract: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    board_ext = board_data.get("x-ext", {}) if isinstance(board_data.get("x-ext", {}), dict) else {}
    quality_cfg = board_ext.get("data_quality", {}) if isinstance(board_ext.get("data_quality", {}), dict) else {}
    provenance_cfg = board_ext.get("provenance", {}) if isinstance(board_ext.get("provenance", {}), dict) else {}
    quality_components = quality_cfg.get("components", {}) if isinstance(quality_cfg.get("components", {}), dict) else {}
    provenance_components = provenance_cfg.get("components", {}) if isinstance(provenance_cfg.get("components", {}), dict) else {}

    refs: List[CapabilityRef] = []
    refs.extend(
        _extract_led_refs(
            board_data,
            quality_components=quality_components,
            provenance_components=provenance_components,
        )
    )
    refs.extend(
        _extract_button_refs(
            board_data,
            quality_components=quality_components,
            provenance_components=provenance_components,
        )
    )
    preferred_ref = _extract_preferred_serial_path_ref(
        board_data,
        quality_components=quality_components,
        provenance_components=provenance_components,
    )
    if preferred_ref is not None:
        refs.append(preferred_ref)
    refs.extend(
        _extract_recipe_refs(
            board_data,
            quality_components=quality_components,
            provenance_components=provenance_components,
        )
    )
    led_ref_map = {
        ref.canonical_id: ref
        for ref in refs
        if ref.kind == "led"
    }
    for alias_name, binding in resolve_led_alias_bindings(board_data, bringup_contract).items():
        source_name = str(binding.get("source") or "").upper()
        source_ref = led_ref_map.get(source_name)
        alias_letter = alias_name.split("_")[-1].strip().lower()
        if source_ref is not None:
            quality = source_ref.quality
            description = f"User LED alias {alias_name.replace('_', ' ')} mapped to {source_name}"
            provenance = "bringup_contract.yaml:app_intent.led_aliases"
            aliases = _clean_aliases(
                [
                    alias_name,
                    alias_name.replace("_", " "),
                    alias_name.replace("_", "").lower(),
                    f"led {alias_letter}",
                    f"{alias_letter} led",
                    source_name,
                ]
            )
            refs.append(
                CapabilityRef(
                    canonical_id=alias_name,
                    kind="led",
                    quality=quality,
                    description=description,
                    aliases=aliases,
                    provenance=provenance,
                )
            )

    deduped: Dict[str, CapabilityRef] = {}
    for ref in refs:
        prior = deduped.get(ref.canonical_id)
        if prior is None:
            deduped[ref.canonical_id] = ref
            continue

        merged_aliases = _clean_aliases(list(prior.aliases) + list(ref.aliases))
        # Prefer stronger quality ordering when entries collide.
        order = {"proven": 0, "schematic_only": 1, "needs_hw_verify": 2}
        better = prior if order.get(prior.quality, 9) <= order.get(ref.quality, 9) else ref
        deduped[ref.canonical_id] = CapabilityRef(
            canonical_id=ref.canonical_id,
            kind=better.kind,
            quality=better.quality,
            description=better.description,
            aliases=merged_aliases,
            provenance=better.provenance,
        )

    entries = sorted(deduped.values(), key=lambda item: item.canonical_id)
    allowed_entries = [_as_entry_dict(entry) for entry in entries if entry.quality == "proven"]
    non_proven_entries = [_as_entry_dict(entry) for entry in entries if entry.quality != "proven"]

    alias_map: Dict[str, List[str]] = {}
    for entry in entries:
        for alias in entry.aliases:
            alias_map.setdefault(alias, [])
            if entry.canonical_id not in alias_map[alias]:
                alias_map[alias].append(entry.canonical_id)

    alias_validation = validate_led_alias_bindings_with_pinmux(
        board_data,
        pinmux_data=pinmux_data,
        bringup_contract=bringup_contract,
    )
    return {
        "allowed_references": allowed_entries,
        "reference_aliases": {k: sorted(v) for k, v in sorted(alias_map.items())},
        "non_proven_references": non_proven_entries,
        "quality_policy_default": "proven_only",
        "led_alias_validation": alias_validation,
    }


def _contains_reference_terms(intent_text: str) -> bool:
    lower = intent_text.lower()
    return any(term in lower for term in _REFERENCE_HINT_TERMS)


def _extract_explicit_component_candidates(intent_text: str) -> Set[str]:
    candidates: Set[str] = set()
    for match in re.finditer(r"\bled\s*([0-9]+)\b", intent_text, flags=re.IGNORECASE):
        candidates.add(f"LED{match.group(1)}")
    for match in re.finditer(r"\b(?:button|switch)\s*([0-9]+)\b", intent_text, flags=re.IGNORECASE):
        candidates.add(f"S{match.group(1)}")
    for match in re.finditer(r"\bS\s*([0-9]+)\b", intent_text, flags=re.IGNORECASE):
        candidates.add(f"S{match.group(1)}")
    return candidates


def validate_intent_references(
    intent_text: str,
    capability_manifest: Dict[str, Any],
    *,
    mode: str = "proven_only",
) -> Dict[str, Any]:
    normalized_mode = str(mode or "proven_only").strip().lower()
    if normalized_mode not in {"proven_only", "include_unverified"}:
        normalized_mode = "proven_only"

    text = str(intent_text or "")
    lowered = text.lower()

    allowed_entries = capability_manifest.get("allowed_references", [])
    non_proven_entries = capability_manifest.get("non_proven_references", [])
    alias_map = capability_manifest.get("reference_aliases", {})

    allowed_ids = {
        str(entry.get("canonical_id")).upper()
        for entry in allowed_entries
        if isinstance(entry, dict) and entry.get("canonical_id")
    }
    non_proven_ids = {
        str(entry.get("canonical_id")).upper()
        for entry in non_proven_entries
        if isinstance(entry, dict) and entry.get("canonical_id")
    }
    all_known_ids = allowed_ids | non_proven_ids

    resolved_ids: Set[str] = set()
    alias_hits: List[str] = []
    if isinstance(alias_map, dict):
        for alias in sorted(alias_map.keys(), key=len, reverse=True):
            if not alias:
                continue
            alias_pattern = rf"(?<![A-Za-z0-9_]){re.escape(alias)}(?![A-Za-z0-9_])"
            if re.search(alias_pattern, lowered):
                mapped_ids = alias_map.get(alias, [])
                if isinstance(mapped_ids, list):
                    for ref_id in mapped_ids:
                        resolved_ids.add(str(ref_id).upper())
                alias_hits.append(alias)

    rejected_refs: List[Dict[str, str]] = []
    explicit_candidates = _extract_explicit_component_candidates(text)
    for candidate in sorted(explicit_candidates):
        if candidate not in all_known_ids:
            rejected_refs.append({"reference": candidate, "reason": "unknown_reference"})

    allowed_target_ids = allowed_ids if normalized_mode == "proven_only" else all_known_ids
    recognized_refs = sorted(ref_id for ref_id in resolved_ids if ref_id in allowed_target_ids)

    for ref_id in sorted(ref_id for ref_id in resolved_ids if ref_id not in allowed_target_ids):
        rejected_refs.append(
            {
                "reference": ref_id,
                "reason": "not_allowed_in_proven_only" if normalized_mode == "proven_only" else "not_allowed",
            }
        )

    if _contains_reference_terms(text) and not recognized_refs and not rejected_refs:
        rejected_refs.append(
            {
                "reference": "<none>",
                "reason": "no_known_component_reference_detected",
            }
        )

    suggestion_pool = sorted(allowed_target_ids)
    suggestions: Dict[str, List[str]] = {}
    for rejected in rejected_refs:
        ref_text = rejected.get("reference", "")
        if not ref_text or ref_text == "<none>":
            continue
        close = get_close_matches(ref_text, suggestion_pool, n=3, cutoff=0.5)
        if close:
            suggestions[ref_text] = close

    return {
        "mode": normalized_mode,
        "valid": len(rejected_refs) == 0,
        "recognized_refs": recognized_refs,
        "rejected_refs": rejected_refs,
        "suggested_refs": suggestions,
        "matched_aliases": sorted(set(alias_hits)),
    }


def format_allowed_references_for_console(
    capability_manifest: Dict[str, Any],
    *,
    mode: str = "proven_only",
) -> List[str]:
    normalized_mode = str(mode or "proven_only").strip().lower()
    include_unverified = normalized_mode == "include_unverified"

    allowed_entries = capability_manifest.get("allowed_references", [])
    non_proven_entries = capability_manifest.get("non_proven_references", [])

    lines: List[str] = []
    lines.append("[info] You may reference these board components:")
    for entry in allowed_entries:
        if not isinstance(entry, dict):
            continue
        canonical = str(entry.get("canonical_id") or "")
        desc = str(entry.get("description") or "")
        lines.append(f"  - {canonical}: {desc}")

    if include_unverified and non_proven_entries:
        lines.append("[warn] Unverified references allowed in this mode:")
        for entry in non_proven_entries:
            if not isinstance(entry, dict):
                continue
            canonical = str(entry.get("canonical_id") or "")
            desc = str(entry.get("description") or "")
            quality = str(entry.get("quality") or "")
            lines.append(f"  - {canonical} ({quality}): {desc}")
    elif non_proven_entries:
        lines.append("[info] Not currently allowed (non-proven):")
        for entry in non_proven_entries:
            if not isinstance(entry, dict):
                continue
            canonical = str(entry.get("canonical_id") or "")
            quality = str(entry.get("quality") or "")
            lines.append(f"  - {canonical} [{quality}]")

    return lines
