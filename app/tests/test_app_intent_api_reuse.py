from pathlib import Path

from modules.intent.app_intent_api_reuse import (
    build_app_intent_api_recipe_text,
    inject_driver_usage_recipe_comment,
    lint_app_intent_api_reuse,
    resolve_app_intent_init_gate_contract,
    resolve_app_intent_api_reuse_recipe,
    sanitize_app_intent_generated_source,
    validate_intent_behavior_alignment,
)


def _bringup_contract() -> dict:
    return {
        "serial": {"primary_path": "LIN_SCI_MODE", "primary_tx_only": "LIN", "baud_default": 9600},
        "app_intent": {
            "api_reuse": {
                "mode": "warn_only",
                "docs_target": "both",
                "pin_init": {
                    "prefer_enable_pins": True,
                    "call_enable_pins_before_init": True,
                    "allow_iomm_fallback": True,
                },
                "tx_string": {
                    "prefer_capability": "tx_buffer",
                    "fallback_capability": "tx_byte",
                    "forbid_manual_byte_loop_when_tx_buffer_exists": True,
                    "forbid_busy_wait_loops_in_step_path": True,
                },
            }
        },
    }


def _api_contract() -> dict:
    return {
        "modules": {
            "LIN": {
                "capabilities": {
                    "init": "LIN_Init",
                    "tx_buffer": "LIN_SendData",
                    "tx_byte": "LIN_SendByte",
                    "tx_ready": "LIN_IsTxReady",
                    "rx_ready": "LIN_IsRxReady",
                },
                "functions": {"LIN_Init": {}, "LIN_SendData": {}, "LIN_SendByte": {}},
            },
            "SCI": {
                "capabilities": {
                    "init": "SCI_Init",
                    "tx_buffer": "SCI_SendData",
                    "tx_byte": "SCI_SendByte",
                    "tx_ready": "SCI_IsTxReady",
                    "rx_ready": "SCI_IsRxReady",
                },
                "functions": {"SCI_Init": {}, "SCI_SendData": {}, "SCI_SendByte": {}},
            },
            "IOMM": {
                "capabilities": {"init": "IOMM_Init"},
                "functions": {"IOMM_Init": {}},
            },
        }
    }


def test_resolve_recipe_prefers_bringup_and_contract_capabilities():
    recipe = resolve_app_intent_api_reuse_recipe(
        bringup_contract=_bringup_contract(),
        api_contract_manifest=_api_contract(),
        driver_source_symbols={"lin_driver.c": ["LIN_EnablePins"]},
    )

    assert recipe["primary_serial_module"] == "LIN"
    assert recipe["modules"]["LIN"]["enable_pins"] == "LIN_EnablePins"
    text = build_app_intent_api_recipe_text(recipe)
    assert "LIN.tx.preferred: LIN_SendData (tx_buffer)" in text


def test_lint_warns_on_manual_byte_loop_when_buffer_api_exists():
    recipe = resolve_app_intent_api_reuse_recipe(
        bringup_contract=_bringup_contract(),
        api_contract_manifest=_api_contract(),
        driver_source_symbols={},
    )
    app_intent_text = """
static void send_string(const char* str)
{
    uint32_t i;
    for (i = 0; str[i] != '\\0'; i++) {
        LIN_SendByte((uint8_t)str[i]);
    }
}
"""
    warnings = lint_app_intent_api_reuse(app_intent_text, recipe)
    assert any("manual byte-loop TX" in item for item in warnings)


def test_lint_does_not_warn_manual_loop_when_buffer_api_missing():
    contract = _api_contract()
    contract["modules"]["LIN"]["capabilities"]["tx_buffer"] = None
    recipe = resolve_app_intent_api_reuse_recipe(
        bringup_contract=_bringup_contract(),
        api_contract_manifest=contract,
        driver_source_symbols={},
    )
    app_intent_text = """
static void send_string(const char* str)
{
    uint32_t i;
    for (i = 0; str[i] != '\\0'; i++) {
        LIN_SendByte((uint8_t)str[i]);
    }
}
"""
    warnings = lint_app_intent_api_reuse(app_intent_text, recipe)
    assert not any("manual byte-loop TX" in item for item in warnings)
    assert recipe["modules"]["LIN"]["tx_buffer_source"] == "inferred"


def test_lint_warns_on_missing_enablepins_with_direct_iomm_config():
    recipe = resolve_app_intent_api_reuse_recipe(
        bringup_contract=_bringup_contract(),
        api_contract_manifest=_api_contract(),
        driver_source_symbols={"lin_driver.c": ["LIN_EnablePins"]},
    )
    app_intent_text = """
void APP_INTENT_Init(void)
{
    IOMM_ConfigurePins(pins, 2U);
    LIN_Init(&cfg);
}
"""
    warnings = lint_app_intent_api_reuse(app_intent_text, recipe)
    assert any("without LIN_EnablePins call" in item for item in warnings)


def test_lint_warns_on_busy_wait_in_step():
    recipe = resolve_app_intent_api_reuse_recipe(
        bringup_contract=_bringup_contract(),
        api_contract_manifest=_api_contract(),
        driver_source_symbols={},
    )
    app_intent_text = """
void APP_INTENT_Step(void)
{
    while (!LIN_IsTxReady()) {
    }
}
"""
    warnings = lint_app_intent_api_reuse(app_intent_text, recipe)
    assert any("busy-wait TX-ready loop" in item for item in warnings)


def test_inject_driver_usage_recipe_comment_for_lin_header():
    recipe = resolve_app_intent_api_reuse_recipe(
        bringup_contract=_bringup_contract(),
        api_contract_manifest=_api_contract(),
        driver_source_symbols={"lin_driver.c": ["LIN_EnablePins"]},
    )
    header_text = "#ifndef LIN_DRIVER_H\n#define LIN_DRIVER_H\n\n#endif /* LIN_DRIVER_H */\n"
    patched = inject_driver_usage_recipe_comment(
        header_text=header_text,
        module_name="LIN",
        recipe=recipe,
    )
    assert "App-intent usage recipe" in patched
    assert "LIN_SendData" in patched


def test_lint_warns_on_driver_api_redefinition():
    recipe = resolve_app_intent_api_reuse_recipe(
        bringup_contract=_bringup_contract(),
        api_contract_manifest=_api_contract(),
        driver_source_symbols={"lin_driver.c": ["LIN_EnablePins"]},
    )
    app_intent_text = """
static void LIN_EnablePins(void)
{
}
"""
    warnings = lint_app_intent_api_reuse(app_intent_text, recipe)
    assert any("defines LIN_EnablePins" in item for item in warnings)


def test_lint_warns_on_char_gio_port_for_numeric_port_api():
    recipe = resolve_app_intent_api_reuse_recipe(
        bringup_contract=_bringup_contract(),
        api_contract_manifest=_api_contract(),
        driver_source_symbols={},
    )
    app_intent_text = "void APP_INTENT_Step(void) { (void)GIO_WritePin('B', 2U, true); }"
    gio_header = "gio_status_t GIO_WritePin(uint8_t port, uint8_t pin, bool value);"
    warnings = lint_app_intent_api_reuse(
        app_intent_text,
        recipe,
        gio_header_text=gio_header,
    )
    assert any("raw character port values used with uint8_t port APIs" in item for item in warnings)


def test_sanitize_removes_local_stub_and_normalizes_numeric_port(tmp_path: Path):
    out_dir = tmp_path
    source_dir = out_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "lin_driver.c").write_text("void LIN_EnablePins(void)\n{\n}\n", encoding="utf-8")

    app_text = """
#include "app_intent.h"
static void LIN_EnablePins(void)
{
    return;
}
void APP_INTENT_Init(void)
{
    LIN_EnablePins();
    (void)GIO_WritePin('B', 2U, true);
}
"""
    result = sanitize_app_intent_generated_source(
        out_dir=out_dir,
        app_intent_text=app_text,
        driver_source_symbols={"lin_driver.c": ["LIN_EnablePins"]},
        gio_header_text="gio_status_t GIO_WritePin(uint8_t port, uint8_t pin, bool value);",
    )
    updated = str(result["text"])
    assert result["changed"] is True
    assert "static void LIN_EnablePins(void)" not in updated
    assert "void LIN_EnablePins(void);" in updated
    assert "GIO_WritePin(1U, 2U, true);" in updated


def test_sanitize_adds_forward_decl_for_called_driver_symbol_missing_from_headers(tmp_path: Path):
    out_dir = tmp_path
    include_dir = out_dir / "include"
    source_dir = out_dir / "source"
    include_dir.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)

    (include_dir / "lin_driver.h").write_text("void LIN_Init(void);\n", encoding="utf-8")
    (source_dir / "lin_driver.c").write_text("void LIN_EnablePins(void)\n{\n}\n", encoding="utf-8")

    app_text = """
#include "app_intent.h"
#include "lin_driver.h"
void APP_INTENT_Init(void)
{
    LIN_EnablePins();
    LIN_Init();
}
"""
    result = sanitize_app_intent_generated_source(
        out_dir=out_dir,
        app_intent_text=app_text,
        driver_source_symbols={"lin_driver.c": ["LIN_EnablePins", "LIN_Init"]},
        gio_header_text="",
    )
    updated = str(result["text"])
    assert result["changed"] is True
    assert "void LIN_EnablePins(void);" in updated
    assert any("called driver symbol LIN_EnablePins" in action for action in result["actions"])


def test_lint_warns_on_led_toggle_without_visible_timing_gate():
    recipe = resolve_app_intent_api_reuse_recipe(
        bringup_contract=_bringup_contract(),
        api_contract_manifest=_api_contract(),
        driver_source_symbols={},
    )
    app_intent_text = """
void APP_INTENT_Step(void)
{
    GIO_TogglePin(1U, 2U);
}
"""
    warnings = lint_app_intent_api_reuse(app_intent_text, recipe)
    assert any("no visible timing gate" in item for item in warnings)


def test_lint_does_not_warn_on_led_toggle_with_counter_cadence_gate():
    recipe = resolve_app_intent_api_reuse_recipe(
        bringup_contract=_bringup_contract(),
        api_contract_manifest=_api_contract(),
        driver_source_symbols={},
    )
    app_intent_text = """
void APP_INTENT_Step(void)
{
    static uint32_t heartbeat_ticks = 0U;
    heartbeat_ticks++;
    if (heartbeat_ticks >= 1000U) {
        heartbeat_ticks = 0U;
        GIO_TogglePin(1U, 2U);
    }
}
"""
    warnings = lint_app_intent_api_reuse(app_intent_text, recipe)
    assert not any("no visible timing gate" in item for item in warnings)


def test_lint_warns_on_direct_led2_led3_macros_when_user_aliases_exist():
    recipe = resolve_app_intent_api_reuse_recipe(
        bringup_contract=_bringup_contract(),
        api_contract_manifest=_api_contract(),
        driver_source_symbols={},
    )
    app_intent_text = """
void APP_INTENT_Step(void)
{
    if (BOARD_LED2_PRESENT) {
        GIO_WritePin(BOARD_LED2_GIO_PORT_INDEX, BOARD_LED2_GIO_PIN, true);
    }
}
"""
    board_header = """
#define BOARD_USER_LED_A_PRESENT 1U
#define BOARD_USER_LED_B_PRESENT 1U
"""
    warnings = lint_app_intent_api_reuse(
        app_intent_text,
        recipe,
        board_capabilities_header_text=board_header,
    )
    assert any("BOARD_LED2_/BOARD_LED3_" in item for item in warnings)


def test_lint_warns_when_alias_polarity_macros_not_used():
    recipe = resolve_app_intent_api_reuse_recipe(
        bringup_contract=_bringup_contract(),
        api_contract_manifest=_api_contract(),
        driver_source_symbols={},
    )
    app_intent_text = """
void APP_INTENT_Step(void)
{
    GIO_WritePin(BOARD_USER_LED_A_GIO_PORT_INDEX, BOARD_USER_LED_A_GIO_PIN, true);
}
"""
    board_header = """
#define BOARD_USER_LED_A_PRESENT 1U
#define BOARD_USER_LED_B_PRESENT 1U
"""
    warnings = lint_app_intent_api_reuse(
        app_intent_text,
        recipe,
        board_capabilities_header_text=board_header,
    )
    assert any("ignore alias polarity" in item for item in warnings)


def test_lint_warns_when_hardware_timer_recipe_selected_without_timer_api_calls():
    recipe = resolve_app_intent_api_reuse_recipe(
        bringup_contract=_bringup_contract(),
        api_contract_manifest=_api_contract(),
        driver_source_symbols={},
    )
    app_intent_text = """
void APP_INTENT_Step(void)
{
    static uint32_t heartbeat_ticks = 0U;
    heartbeat_ticks++;
    if (heartbeat_ticks > 1000U) {
        heartbeat_ticks = 0U;
        GIO_TogglePin(1U, 2U);
    }
}
"""
    timing_recipe = {
        "selected_source": "hardware_timer",
        "selected_apis": {
            "get_tick": "RTI_GetTickCount",
            "get_time_ms": "RTI_GetTimeMs",
        },
    }
    warnings = lint_app_intent_api_reuse(
        app_intent_text,
        recipe,
        timing_recipe=timing_recipe,
    )
    assert any("selected hardware timer source" in item for item in warnings)


def test_sanitize_inserts_gio_init_before_use_when_missing(tmp_path: Path):
    out_dir = tmp_path
    source_dir = out_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    app_text = """
void APP_INTENT_Init(void)
{
    GIO_WritePin(1U, 2U, true);
}
"""
    init_gate = {
        "policy": {"mode": "auto_fix_then_fail", "enforce_pre_use_init": True},
        "modules": {"GIO": {"init": "GIO_Init", "arity": 0}},
    }
    result = sanitize_app_intent_generated_source(
        out_dir=out_dir,
        app_intent_text=app_text,
        driver_source_symbols={},
        module_init_contract=init_gate,
    )
    assert "GIO_Init();" in str(result["text"])
    assert not result.get("init_gate_failures")


def test_sanitize_allows_init_after_use_in_app_intent_init(tmp_path: Path):
    out_dir = tmp_path
    source_dir = out_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    app_text = """
void APP_INTENT_Init(void)
{
    GIO_WritePin(1U, 2U, true);
    GIO_Init();
}
"""
    init_gate = {
        "policy": {"mode": "auto_fix_then_fail", "enforce_pre_use_init": True},
        "modules": {"GIO": {"init": "GIO_Init", "arity": 0}},
    }
    result = sanitize_app_intent_generated_source(
        out_dir=out_dir,
        app_intent_text=app_text,
        driver_source_symbols={},
        module_init_contract=init_gate,
    )
    assert result.get("init_gate_failures") == []


def test_sanitize_accepts_init_call_outside_app_intent_init(tmp_path: Path):
    out_dir = tmp_path
    source_dir = out_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    app_text = """
static void setup_all(void)
{
    RTI_Init();
}

void APP_INTENT_Init(void)
{
    setup_all();
    RTI_EnableNotification(0U);
}
"""
    init_gate = {
        "policy": {"mode": "auto_fix_then_fail", "enforce_pre_use_init": True},
        "modules": {"RTI": {"init": "RTI_Init", "arity": 0}},
    }
    result = sanitize_app_intent_generated_source(
        out_dir=out_dir,
        app_intent_text=app_text,
        driver_source_symbols={},
        module_init_contract=init_gate,
    )
    assert result.get("init_gate_failures") == []
    assert "Inserted missing RTI_Init() in APP_INTENT_Init." not in result.get("init_gate_actions", [])


def test_init_gate_contract_resolver_includes_timing_module():
    contract = {
        "modules": {
            "GIO": {"capabilities": {"init": "GIO_Init"}, "functions": {"GIO_Init": {"arity": 0}}},
            "RTI": {"capabilities": {"init": "RTI_Init"}, "functions": {"RTI_Init": {"arity": 0}}},
        }
    }
    recipe = resolve_app_intent_init_gate_contract(
        bringup_contract={"app_intent": {"init_gate": {"mode": "auto_fix_then_fail"}}},
        api_contract_manifest=contract,
        timing_recipe={"selected_module": "RTI"},
    )
    assert recipe["modules"]["GIO"]["init"] == "GIO_Init"
    assert recipe["modules"]["RTI"]["init"] == "RTI_Init"


def test_validate_intent_behavior_alignment_uses_aliases():
    intent = "Toggle LED A and keep LED B heartbeat blinking"
    app_text = """
void APP_INTENT_Step(void)
{
    GIO_TogglePin(BOARD_USER_LED_A_GIO_PORT_INDEX, BOARD_USER_LED_A_GIO_PIN);
    GIO_TogglePin(BOARD_USER_LED_B_GIO_PORT_INDEX, BOARD_USER_LED_B_GIO_PIN);
}
"""
    header = """
#define BOARD_USER_LED_A_PRESENT 1U
#define BOARD_USER_LED_B_PRESENT 1U
"""
    status = validate_intent_behavior_alignment(
        intent_text=intent,
        app_intent_c_text=app_text,
        board_capabilities_header_text=header,
    )
    assert status["passed"] is True
