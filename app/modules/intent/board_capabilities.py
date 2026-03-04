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


def _parse_instance_index(value: Any) -> Optional[int]:
    match = re.search(r"(\d+)", str(value or ""))
    if not match:
        return None
    return int(match.group(1))


def build_board_capability_header(
    board_data: Dict[str, Any],
    *,
    capability_manifest: Optional[Dict[str, Any]] = None,
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

    lines.extend(
        [
            "#endif /* BOARD_CAPABILITIES_H */",
            "",
        ]
    )
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


def build_board_capability_manifest(board_data: Dict[str, Any]) -> Dict[str, Any]:
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

    return {
        "allowed_references": allowed_entries,
        "reference_aliases": {k: sorted(v) for k, v in sorted(alias_map.items())},
        "non_proven_references": non_proven_entries,
        "quality_policy_default": "proven_only",
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
