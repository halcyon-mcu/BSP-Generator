from modules.intent.board_capabilities import (
    build_board_capability_header,
    build_board_capability_manifest,
    format_allowed_references_for_console,
    validate_led_alias_macro_consistency,
    validate_led_alias_bindings_with_pinmux,
    validate_intent_references,
)


def _sample_board() -> dict:
    return {
        "leds": [
            {
                "designator": "LED2",
                "function": "USER LED",
                "color": "GRN",
                "active_state": "LOW",
                "gpio": "GIOB[2]",
                "mcu_pin": 55,
            },
            {
                "designator": "LED3",
                "function": "HEARTBEAT LED",
                "color": "BLU",
                "active_state": "LOW",
                "gpio": "GIOB[1]",
                "mcu_pin": 133,
            },
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


def _sample_bringup_contract() -> dict:
    return {
        "app_intent": {
            "led_aliases": {
                "LED_A": {"source": "LED2", "active_low_override": None},
                "LED_B": {"source": "LED3", "active_low_override": None},
            }
        }
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
    manifest = build_board_capability_manifest(
        _sample_board(),
        bringup_contract=_sample_bringup_contract(),
    )
    header = build_board_capability_header(
        _sample_board(),
        capability_manifest=manifest,
        bringup_contract=_sample_bringup_contract(),
    )

    assert "#define BOARD_TERMINAL_UART_OVER_LIN 1U" in header
    assert "#define BOARD_TERMINAL_UART_MODE_SCI 1U" in header
    assert "#define BOARD_LED2_HAS_GIO 1U" in header
    assert "#define BOARD_LED2_GIO_PORT 'B'" in header
    assert "#define BOARD_LED2_GIO_PORT_INDEX 1U" in header
    assert "#define BOARD_LED2_GIO_PIN 2U" in header
    assert "#define BOARD_USER_LED_A_SOURCE \"LED2\"" in header
    assert "#define BOARD_USER_LED_A_ACTIVE_LOW 1U" in header
    assert "#define BOARD_USER_LED_A_GIO_PORT 'B'" in header
    assert "#define BOARD_USER_LED_A_GIO_PIN 2U" in header
    assert "#define BOARD_USER_LED_A_MCU_PIN 55U" in header
    assert "#define BOARD_USER_LED_B_SOURCE \"LED3\"" in header
    assert "#define BOARD_USER_LED_B_GIO_PORT 'B'" in header
    assert "#define BOARD_USER_LED_B_GIO_PIN 1U" in header
    assert "#define BOARD_USER_LED_B_MCU_PIN 133U" in header
    assert "#define BOARD_USER_LED_B_ACTIVE_LOW 1U" in header


def test_manifest_includes_led_alias_references():
    manifest = build_board_capability_manifest(
        _sample_board(),
        bringup_contract=_sample_bringup_contract(),
    )
    allowed_ids = {entry["canonical_id"] for entry in manifest["allowed_references"]}
    aliases = manifest["reference_aliases"]

    assert "LED_A" in allowed_ids
    assert "LED_B" in allowed_ids
    assert "led a" in aliases
    assert "LED_A" in aliases["led a"]


def test_led_alias_validation_detects_pinmux_conflict():
    board = _sample_board()
    board["leds"][0]["mcu_pin"] = 99
    pinmux = {
        "pins": [
            {"package_pin": 55, "functions": [{"signal": "GIOB[2]"}]},
            {"package_pin": 133, "functions": [{"signal": "GIOB[1]"}]},
        ]
    }
    result = validate_led_alias_bindings_with_pinmux(
        board,
        pinmux_data=pinmux,
        bringup_contract={"app_intent": {"led_aliases": {"LED_A": {"source": "LED2"}, "LED_B": {"source": "LED3"}}}},
    )
    assert result["passed"] is False
    assert any("LED_A" in msg for msg in result["conflicts"])


def test_led_alias_macro_consistency_passes_for_locked_mapping():
    board = _sample_board()
    manifest = build_board_capability_manifest(
        board,
        bringup_contract=_sample_bringup_contract(),
    )
    header = build_board_capability_header(
        board,
        capability_manifest=manifest,
        bringup_contract=_sample_bringup_contract(),
    )
    result = validate_led_alias_macro_consistency(
        header,
        board,
        bringup_contract=_sample_bringup_contract(),
    )
    assert result["passed"] is True
    assert result["failures"] == []


def test_led_alias_macro_consistency_detects_alias_gpio_swap():
    board = _sample_board()
    manifest = build_board_capability_manifest(
        board,
        bringup_contract=_sample_bringup_contract(),
    )
    header = build_board_capability_header(
        board,
        capability_manifest=manifest,
        bringup_contract=_sample_bringup_contract(),
    )
    broken = header.replace(
        "#define BOARD_USER_LED_A_GIO_PIN 2U",
        "#define BOARD_USER_LED_A_GIO_PIN 1U",
    )
    result = validate_led_alias_macro_consistency(
        broken,
        board,
        bringup_contract=_sample_bringup_contract(),
    )
    assert result["passed"] is False
    assert any("LED_A" in msg and "GPIO pin mismatch" in msg for msg in result["failures"])
