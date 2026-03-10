from modules.intent.post_generation_prompt import build_post_generation_firmware_prompt


def test_build_post_generation_prompt_uses_board_header_as_source_of_truth():
    prompt = build_post_generation_firmware_prompt(
        intent_text="Blink LED2 and echo button presses over terminal",
        board_capabilities_header="#define BOARD_LED2_MCU_PIN 142U\n#define BOARD_TERMINAL_UART_OVER_LIN 1U",
    )

    assert "single source of truth" in prompt
    assert "Do NOT use board.yaml" in prompt
    assert "===== BEGIN BOARD_CAPABILITIES_H =====" in prompt
    assert "#define BOARD_LED2_MCU_PIN 142U" in prompt
    assert "===== FILE: include/app_intent.h =====" in prompt
    assert "===== FILE: source/app_intent.c =====" in prompt


def test_build_post_generation_prompt_includes_task_library_when_present():
    prompt = build_post_generation_firmware_prompt(
        intent_text="Print hello",
        board_capabilities_header="#define BOARD_TERMINAL_UART_OVER_LIN 1U",
        task_library_text="tasks:\n  - id: blink",
        task_library_source="app/yaml_in/firmware_tasks.yaml",
    )

    assert "===== BEGIN FIRMWARE_TASK_LIBRARY =====" in prompt
    assert "# source: app/yaml_in/firmware_tasks.yaml" in prompt
    assert "tasks:" in prompt


def test_build_post_generation_prompt_includes_contract_and_main_context():
    prompt = build_post_generation_firmware_prompt(
        intent_text="Stream UART status",
        board_capabilities_header="#define BOARD_TERMINAL_UART_OVER_LIN 1U",
        api_contract_manifest_json='{"modules":{"LIN":{"functions":{"LIN_Init":{"arity":1}}}}}',
        bringup_contract_yaml="serial:\n  baud_default: 9600",
        generation_profile_yaml="app_intent:\n  generate_firmware_pass: true",
        existing_main_c="int main(void)\n{\n    while (1) {}\n}",
    )

    assert "===== BEGIN API_CONTRACT_MANIFEST_JSON =====" in prompt
    assert "===== BEGIN BRINGUP_CONTRACT_YAML =====" in prompt
    assert "===== BEGIN GENERATION_PROFILE_YAML =====" in prompt
    assert "===== BEGIN EXISTING_MAIN_C =====" in prompt


def test_build_post_generation_prompt_includes_api_first_policy_and_header_context():
    prompt = build_post_generation_firmware_prompt(
        intent_text="Blink LED2",
        board_capabilities_header="#define BOARD_LED2_PRESENT 1U",
        api_contract_manifest_json='{"modules":{"LIN":{"functions":{"LIN_Init":{"arity":1},"LIN_SendByte":{"arity":1}}}}}',
        driver_headers_context="===== BEGIN HEADER: include/lin_driver.h =====\nlin_status_t LIN_Init(const lin_config_t *);\n===== END HEADER: include/lin_driver.h =====",
        app_intent_api_usage_recipe="LIN.tx.preferred: LIN_SendData (tx_buffer)",
        app_intent_timing_recipe="timing.selected_source: hardware_timer\nRTI.api.get_tick: RTI_GetTickCount",
    )

    assert "API-first implementation policy" in prompt
    assert "Do NOT include reg_* headers" in prompt
    assert "Use exact symbol names from API/header/source-symbol context" in prompt
    assert "LIN_MODE_SCI (not LIN_MODE_LIN)" in prompt
    assert "LIN_EnablePins" in prompt
    assert "Do NOT define or redefine any function whose name appears in DRIVER_SOURCE_SYMBOLS" in prompt
    assert "BOARD_*_GIO_PORT is a character code and BOARD_*_GIO_PORT_INDEX is numeric" in prompt
    assert "Do NOT rely on a lone global init flag" in prompt
    assert "User-facing LED naming must use LED A / LED B semantics" in prompt
    assert "BOARD_USER_LED_A_* / BOARD_USER_LED_B_*" in prompt
    assert "APP_INTENT_TIMING_RECIPE" in prompt
    assert "RTI.api.get_tick: RTI_GetTickCount" in prompt
    assert "API shortlist extracted from contract" in prompt
    assert "- LIN: LIN_Init, LIN_SendByte" in prompt
    assert "===== BEGIN DRIVER_HEADERS_CONTEXT =====" in prompt
    assert "===== BEGIN APP_INTENT_API_USAGE_RECIPE =====" in prompt
    assert "LIN.tx.preferred: LIN_SendData (tx_buffer)" in prompt
