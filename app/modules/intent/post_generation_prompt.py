"""
Post-generation firmware prompt builder.
"""

from __future__ import annotations

import json


def build_post_generation_firmware_prompt(
    *,
    intent_text: str,
    board_capabilities_header: str,
    api_contract_manifest_json: str = "",
    bringup_contract_yaml: str = "",
    generation_profile_yaml: str = "",
    existing_main_c: str = "",
    task_library_text: str = "",
    task_library_source: str = "",
    driver_headers_context: str = "",
) -> str:
    """
    Build a deterministic firmware-generation prompt from app intent.

    Board mappings must come only from board_capabilities.h content.
    """
    intent = str(intent_text or "").strip()
    header_text = str(board_capabilities_header or "").strip()
    contract_json = str(api_contract_manifest_json or "").strip()
    bringup_yaml = str(bringup_contract_yaml or "").strip()
    profile_yaml = str(generation_profile_yaml or "").strip()
    main_c_text = str(existing_main_c or "").strip()
    tasks = str(task_library_text or "").strip()
    task_source = str(task_library_source or "").strip()
    header_ctx = str(driver_headers_context or "").strip()

    api_shortlist_lines = _extract_api_shortlist(contract_json)

    lines = [
        "You are generating firmware additions for an already-generated BSP project.",
        "",
        "App intent:",
        intent or "<empty>",
        "",
        "Authoritative board mapping source (single source of truth):",
        "- Use ONLY the macros in include/board_capabilities.h below.",
        "- Do NOT use board.yaml, schematic assumptions, or inferred pin mapping.",
        "- If a mapping is not represented by a BOARD_* macro, emit a TODO and stop.",
        "",
        "Required behavior:",
        "- Generate code that initializes app-level behavior for the intent.",
        "- Ensure UART/terminal path works from board capabilities (LIN-vs-SCI route).",
        "- Use only APIs/prototypes from the API contract manifest.",
        "- Do not reconfigure system PLL/clock tree directly in app code.",
        "",
        "API-first implementation policy (hard requirements):",
        "- Prefer existing BSP peripheral driver APIs over manual protocol/register operations.",
        "- Do NOT include reg_* headers and do NOT access peripheral registers directly.",
        "- Do NOT invent new peripheral API names; only call functions that exist in provided contract/header context.",
        "- APP_INTENT_Step must be non-blocking (no delay loops / no infinite TX wait loops).",
        "- For terminal output path, use the provided driver API route (LIN-vs-SCI) from board macros.",
        "- If BOARD_TERMINAL_UART_OVER_LIN == 1 and BOARD_TERMINAL_UART_MODE_SCI == 1 and LIN_MODE_SCI exists, configure LIN with LIN_MODE_SCI (not LIN_MODE_LIN).",
        "- If LIN_EnablePins (or equivalent LIN pin-enable API) is present in provided API/header/source symbol context, call it once before LIN_Init.",
        "- Prefer buffered send APIs (e.g. LIN_Send/LIN_SendData) for strings when available.",
        "- Minimize mutable file-scope globals; prefer function-local/static state where practical.",
        "- Do NOT rely on a lone global init flag (e.g., s_initialized). If persistent state is required, use a single static state struct with an explicit guard value set in APP_INTENT_Init and checked in APP_INTENT_Step before use.",
        "- If no safe API exists for a needed action, emit a TODO and return safely instead of raw register code.",
        "",
        "Required output format (strict):",
        "1. FACTS MIRROR listing every BOARD_* macro used.",
        "2. FILE blocks only (===== FILE: <path> =====).",
        "3. Emit exactly TWO files:",
        "   - ===== FILE: include/app_intent.h =====",
        "   - ===== FILE: source/app_intent.c =====",
        "4. Public API in header MUST be:",
        "   - void APP_INTENT_Init(void);",
        "   - void APP_INTENT_Step(void);",
        "",
        "===== BEGIN BOARD_CAPABILITIES_H =====",
        header_text,
        "===== END BOARD_CAPABILITIES_H =====",
    ]

    if api_shortlist_lines:
        lines.extend(
            [
                "",
                "API shortlist extracted from contract (use these when available):",
                *api_shortlist_lines,
            ]
        )

    if contract_json:
        lines.extend(
            [
                "",
                "===== BEGIN API_CONTRACT_MANIFEST_JSON =====",
                contract_json,
                "===== END API_CONTRACT_MANIFEST_JSON =====",
            ]
        )

    if bringup_yaml:
        lines.extend(
            [
                "",
                "===== BEGIN BRINGUP_CONTRACT_YAML =====",
                bringup_yaml,
                "===== END BRINGUP_CONTRACT_YAML =====",
            ]
        )

    if profile_yaml:
        lines.extend(
            [
                "",
                "===== BEGIN GENERATION_PROFILE_YAML =====",
                profile_yaml,
                "===== END GENERATION_PROFILE_YAML =====",
            ]
        )

    if main_c_text:
        lines.extend(
            [
                "",
                "===== BEGIN EXISTING_MAIN_C =====",
                main_c_text,
                "===== END EXISTING_MAIN_C =====",
            ]
        )

    if header_ctx:
        lines.extend(
            [
                "",
                "===== BEGIN DRIVER_HEADERS_CONTEXT =====",
                header_ctx,
                "===== END DRIVER_HEADERS_CONTEXT =====",
            ]
        )

    if tasks:
        lines.extend(
            [
                "",
                "===== BEGIN FIRMWARE_TASK_LIBRARY =====",
                f"# source: {task_source or '<inline>'}",
                tasks,
                "===== END FIRMWARE_TASK_LIBRARY =====",
            ]
        )

    lines.append("")
    return "\n".join(lines)


def _extract_api_shortlist(contract_json: str) -> list[str]:
    text = str(contract_json or "").strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except Exception:
        return []

    modules = payload.get("modules", {})
    if not isinstance(modules, dict):
        return []

    priority = ["SYSTEM", "PCR", "IOMM", "PLL", "VIM", "SCI", "GIO", "LIN"]
    ordered = [name for name in priority if name in modules]
    ordered.extend(name for name in modules.keys() if name not in ordered)

    lines: list[str] = []
    for module_name in ordered:
        module = modules.get(module_name, {})
        if not isinstance(module, dict):
            continue
        funcs = module.get("functions", {})
        if not isinstance(funcs, dict) or not funcs:
            continue
        fn_names = sorted(str(name) for name in funcs.keys() if isinstance(name, str))
        if not fn_names:
            continue
        preview = ", ".join(fn_names[:20])
        suffix = " ..." if len(fn_names) > 20 else ""
        lines.append(f"- {module_name}: {preview}{suffix}")
    return lines
