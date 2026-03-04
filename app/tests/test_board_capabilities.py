from modules.intent.board_capabilities import (
    build_board_capability_header,
    build_board_capability_manifest,
    format_allowed_references_for_console,
    validate_intent_references,
)


def _sample_board() -> dict:
    return {
        "leds": [
            {"designator": "LED2", "function": "USER LED", "color": "GRN", "active_state": "LOW", "gpio": "GIOB[2]"},
            {"designator": "LED1", "function": "ERROR LED", "color": "RED", "active_state": "LOW"},
        ],
        "buttons": [
            {"designator": "S3", "function": "USER button", "active_state": "LOW"},
        ],
        "communication": {
            "preferred_debug_path": {
                "peripheral": "LIN",
                "mode": "SCI",
                "instance": "lin1",
                "note": "Preferred terminal output path",
            }
        },
        "x-ext": {
            "data_quality": {
                "components": {
                    "LED2": "proven",
                    "LED1": "needs_hw_verify",
                    "S3": "proven",
                    "LIN1_SCI_PATH": "proven",
                }
            },
            "peripheral_recipes": {
                "terminal_uart": {
                    "canonical_ref": "LIN1_SCI_PATH",
                    "kind": "interface",
                    "quality": "proven",
                    "description": "Terminal path recipe",
                    "aliases": ["terminal", "uart", "serial"],
                }
            },
        },
    }


def test_build_manifest_has_proven_allowed_and_non_proven_lists():
    manifest = build_board_capability_manifest(_sample_board())

    allowed_ids = {entry["canonical_id"] for entry in manifest["allowed_references"]}
    blocked_ids = {entry["canonical_id"] for entry in manifest["non_proven_references"]}

    assert "LED2" in allowed_ids
    assert "S3" in allowed_ids
    assert "LIN1_SCI_PATH" in allowed_ids
    assert "LED1" in blocked_ids


def test_reference_aliases_include_ambiguous_green_led_mapping():
    manifest = build_board_capability_manifest(_sample_board())
    aliases = manifest["reference_aliases"]

    assert "green led" in aliases
    assert "LED2" in aliases["green led"]


def test_validate_intent_rejects_unverified_in_proven_only_mode():
    manifest = build_board_capability_manifest(_sample_board())

    result = validate_intent_references(
        "Blink LED1 and print over terminal",
        manifest,
        mode="proven_only",
    )

    assert result["valid"] is False
    assert any(item.get("reference") == "LED1" for item in result["rejected_refs"])


def test_validate_intent_accepts_unverified_in_include_unverified_mode():
    manifest = build_board_capability_manifest(_sample_board())

    result = validate_intent_references(
        "Blink LED1 and print over terminal",
        manifest,
        mode="include_unverified",
    )

    assert result["valid"] is True
    assert "LED1" in result["recognized_refs"]
    assert "LIN1_SCI_PATH" in result["recognized_refs"]


def test_console_format_lists_proven_and_non_proven_sections():
    manifest = build_board_capability_manifest(_sample_board())

    lines = format_allowed_references_for_console(manifest, mode="proven_only")
    text = "\n".join(lines)

    assert "You may reference" in text
    assert "Not currently allowed" in text
    assert "LED2" in text
    assert "LED1" in text


def test_build_board_capability_header_contains_terminal_uart_and_led_macros():
    manifest = build_board_capability_manifest(_sample_board())
    header = build_board_capability_header(_sample_board(), capability_manifest=manifest)

    assert "#define BOARD_TERMINAL_UART_OVER_LIN 1U" in header
    assert "#define BOARD_TERMINAL_UART_MODE_SCI 1U" in header
    assert "#define BOARD_LED2_HAS_GIO 1U" in header
    assert "#define BOARD_LED2_GIO_PORT 'B'" in header
    assert "#define BOARD_LED2_GIO_PORT_INDEX 1U" in header
    assert "#define BOARD_LED2_GIO_PIN 2U" in header
