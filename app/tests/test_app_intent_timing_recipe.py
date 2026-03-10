from modules.intent.app_intent_timing_recipe import (
    build_app_intent_timing_recipe_text,
    resolve_app_intent_timing_recipe,
    validate_rti_vim_wiring_in_app_intent,
)


def _bringup_contract() -> dict:
    return {
        "app_intent": {
            "timing": {
                "prefer_hardware_timer": True,
                "preferred_module": "RTI",
                "fallback": "software_divider",
                "heartbeat_hz": 1.0,
                "blink_on_ms": 120,
                "blink_off_ms": 180,
            }
        }
    }


def test_timing_recipe_prefers_hardware_timer_when_rti_symbols_exist():
    api_contract = {
        "modules": {
            "RTI": {
                "capabilities": {
                    "init": "RTI_Init",
                    "time_ms": "RTI_GetTimeMs",
                },
                "functions": {
                    "RTI_Init": {},
                    "RTI_Start": {},
                    "RTI_GetTimeMs": {},
                    "RTI_GetTickCount": {},
                },
            }
        }
    }
    recipe = resolve_app_intent_timing_recipe(
        bringup_contract=_bringup_contract(),
        api_contract_manifest=api_contract,
        driver_source_symbols={},
    )
    text = build_app_intent_timing_recipe_text(recipe)
    assert recipe["selected_source"] == "hardware_timer"
    assert "timing.selected_source: hardware_timer" in text
    assert "RTI.api.get_time_ms: RTI_GetTimeMs" in text


def test_timing_recipe_uses_software_divider_fallback_without_rti_module():
    recipe = resolve_app_intent_timing_recipe(
        bringup_contract=_bringup_contract(),
        api_contract_manifest={"modules": {"LIN": {"functions": {"LIN_Init": {}}}}},
        driver_source_symbols={},
    )
    text = build_app_intent_timing_recipe_text(recipe)
    assert recipe["selected_source"] == "software_divider"
    assert "fallback.strategy: software_divider" in text


def test_timing_recipe_includes_rti_irq_context_when_available():
    api_contract = {
        "modules": {
            "RTI": {
                "capabilities": {"init": "RTI_Init"},
                "functions": {
                    "RTI_Init": {},
                    "RTI_GetTickCount": {},
                    "RTI_EnableInterrupt": {},
                },
            },
            "VIM": {
                "functions": {
                    "VIM_RegisterISR": {},
                    "VIM_EnableIRQ": {},
                },
            },
        }
    }
    irq_data = {
        "irqs": [
            {"name": "RTI_COMPARE0", "number": 2},
        ]
    }
    recipe = resolve_app_intent_timing_recipe(
        bringup_contract=_bringup_contract(),
        api_contract_manifest=api_contract,
        driver_source_symbols={},
        irq_data=irq_data,
    )
    text = build_app_intent_timing_recipe_text(recipe)
    assert "RTI.irq.name: RTI_COMPARE0" in text
    assert "VIM.api.register_isr: VIM_RegisterISR" in text


def test_validate_rti_vim_wiring_fails_when_required_calls_missing():
    recipe = {
        "selected_source": "hardware_timer",
        "selected_apis": {"get_tick": "RTI_GetTickCount"},
        "wiring_requirements": {
            "rti_irq_name": "RTI_COMPARE0",
            "rti_enable_interrupt_api": "RTI_EnableInterrupt",
            "vim_register_isr_api": "VIM_RegisterISR",
            "vim_enable_irq_api": "VIM_EnableIRQ",
        },
    }
    status = validate_rti_vim_wiring_in_app_intent(
        "void APP_INTENT_Step(void) { (void)0; }",
        recipe,
    )
    assert status["required"] is True
    assert status["passed"] is False
    assert any("RTI_EnableInterrupt" in item for item in status["failures"])
