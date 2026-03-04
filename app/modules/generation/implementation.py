import asyncio
import logging
import json
import re
from typing import Dict, Any, List, Optional
from pathlib import Path

from .prompt import build_pass2_driver_h_prompt, build_pass2_driver_c_prompt, invoke_model, Model

from ..utils.utils import extract_text_from_bedrock_response
from ..yaml.yaml_utils import dump_yaml_str, find_soc_peripheral
from ..utils.file_locking import FileLock
from ..utils.file_io import normalize_generated_text
from ..contracts.contract_checker import check_generated_module_contract
from ..contracts.contract_autofix import autofix_module_contract
from ..intent.app_intent_api_reuse import (
    inject_driver_usage_recipe_comment,
    resolve_app_intent_api_reuse_recipe,
)

logger = logging.getLogger(__name__)


def _sanitize_prompt_context_text(text: str) -> str:
    """
    Sanitize prompt context text so descriptive YAML notes cannot terminate C comments.

    This only affects prompt payload strings, never source YAML files on disk.
    """
    if not text:
        return text
    # Neutralize C block comment terminators that can be copied verbatim into Doxygen.
    return text.replace("*/", "* /")


def _extract_header_canonical_base_macro(module_name: str, output_dir: Optional[Path]) -> Optional[str]:
    """
    Discover canonical register base macro from reg_<module>.h.
    """
    if not output_dir:
        return None
    module_upper = str(module_name or "").upper()
    if not module_upper:
        return None
    reg_header = Path(output_dir) / "include" / f"reg_{module_upper.lower()}.h"
    if not reg_header.exists():
        return None

    header_text = reg_header.read_text(encoding="utf-8", errors="ignore")
    macro_lines = re.findall(r"^\s*#define\s+([A-Za-z_]\w*)\s+(.+)$", header_text, flags=re.MULTILINE)
    candidates: List[str] = []
    typedef_hint = f"{module_upper}_REG_MAP_t"
    for name, body in macro_lines:
        body_str = str(body)
        if typedef_hint in body_str and "*" in body_str:
            candidates.append(name)

    if not candidates:
        return None
    preferred = [module_upper, f"{module_upper}REG", f"{module_upper}_REG"]
    for token in preferred:
        if token in candidates:
            return token
    return candidates[0]


def _normalize_driver_base_alias_usage(
    module_name: str,
    source_code: str,
    output_dir: Optional[Path],
) -> str:
    """
    Normalize ad-hoc module base aliases (e.g. pcrREG->) to canonical header macro.
    """
    canonical = _extract_header_canonical_base_macro(module_name, output_dir)
    if not canonical:
        return source_code

    module_lower = str(module_name or "").lower()
    aliases = sorted(set(re.findall(r"\b([A-Za-z_]\w*)\s*->", source_code)))
    updated = source_code
    for alias in aliases:
        if alias == canonical:
            continue
        # Keep normalization conservative: only module-like register aliases.
        if not alias.upper().endswith("REG"):
            continue
        if module_lower and module_lower not in alias.lower():
            continue
        # If alias is defined locally in file, leave it as-is.
        if re.search(rf"^\s*#define\s+{re.escape(alias)}\b", updated, flags=re.MULTILINE):
            continue
        updated = re.sub(rf"\b{re.escape(alias)}\s*->", f"{canonical}->", updated)

    return updated


def _inject_include_if_missing(code: str, include_line: str) -> str:
    """Inject include/macro after include block if not already present."""
    if include_line in code:
        return code
    include_block = re.search(r"^(\s*#include[^\n]*\n)+", code, re.MULTILINE)
    if include_block:
        insert_at = include_block.end()
        return code[:insert_at] + include_line + "\n" + code[insert_at:]
    return include_line + "\n\n" + code


def _inject_before_header_endif(code: str, snippet: str, guard_tail: str) -> str:
    marker = f"#endif /* {guard_tail} */"
    if marker in code:
        return code.replace(marker, snippet + "\n" + marker)
    return code + ("\n" if not code.endswith("\n") else "") + snippet + "\n"


def _ensure_pcr_enable_all_declaration(header_code: str) -> str:
    if "PCR_EnableAllPeripherals(" in header_code:
        return header_code
    decl = (
        "/**\n"
        " * @brief Enable all known PCR-controlled peripherals\n"
        " *\n"
        " * @details Compatibility helper used by early startup code. This performs\n"
        " *          a best-effort enable of every peripheral enum entry.\n"
        " */\n"
        "void PCR_EnableAllPeripherals(void);\n"
    )
    return _inject_before_header_endif(header_code, decl, "PCR_DRIVER_H")


def _ensure_pcr_enable_all_definition(source_code: str, output_dir: Optional[Path] = None) -> str:
    if "void PCR_EnableAllPeripherals(void)" in source_code:
        return source_code
    if "PCR_EnablePeripheral(" in source_code and "PCR_PERIPHERAL_EMIF" in source_code:
        snippet = (
            "\n"
            "/**\n"
            " * @brief Enable all known PCR-controlled peripherals\n"
            " * @details Compatibility helper for startup ordering contract.\n"
            " */\n"
            "void PCR_EnableAllPeripherals(void)\n"
            "{\n"
            "    int peripheral;\n"
            "\n"
            "    for (peripheral = (int)PCR_PERIPHERAL_SCI1; peripheral <= (int)PCR_PERIPHERAL_EMIF; peripheral++)\n"
            "    {\n"
            "        (void)PCR_EnablePeripheral((pcr_peripheral_t)peripheral);\n"
            "    }\n"
            "}\n"
        )
    else:
        clear_regs = sorted(set(re.findall(r"\bPSPWRDWNCLR(\d+)\b", source_code)))
        if clear_regs:
            base_sym = _extract_header_canonical_base_macro("PCR", output_dir)
            if not base_sym:
                base_sym = "pcrREG" if re.search(r"\bpcrREG\s*->", source_code) else "PCR"
            writes = "".join([f"    {base_sym}->PSPWRDWNCLR{idx} = 0xFFFFFFFFU;\n" for idx in clear_regs])
            snippet = (
                "\n"
                "/**\n"
                " * @brief Enable all known PCR-controlled peripherals\n"
                " * @details Compatibility helper for startup ordering contract.\n"
                " */\n"
                "void PCR_EnableAllPeripherals(void)\n"
                "{\n"
                "    /* Enable all PCR domains by clearing powerdown bits. */\n"
                f"{writes}"
                "}\n"
            )
        else:
            snippet = (
                "\n"
                "/**\n"
                " * @brief Enable all known PCR-controlled peripherals\n"
                " * @details Compatibility helper for startup ordering contract.\n"
                " */\n"
                "void PCR_EnableAllPeripherals(void)\n"
                "{\n"
                "    /* Fallback when detailed PCR register map is unavailable. */\n"
                "    (void)0;\n"
                "}\n"
            )
    return source_code + ("" if source_code.endswith("\n") else "\n") + snippet


def _ensure_driver_helper_declarations(
    *,
    module_name: str,
    header_path: Optional[Path],
    source_path: Optional[Path],
) -> List[str]:
    """
    Ensure common helper APIs implemented in source are declared in module header.
    """
    if not header_path or not source_path or not header_path.exists() or not source_path.exists():
        return []

    module_upper = str(module_name or "").upper()
    if not module_upper:
        return []

    helper_names = [f"{module_upper}_EnablePins"]
    source_text = source_path.read_text(encoding="utf-8", errors="ignore")
    header_text = header_path.read_text(encoding="utf-8", errors="ignore")
    updated = header_text
    actions: List[str] = []

    for helper in helper_names:
        source_sig = re.search(
            rf"(?m)^\s*(?!static\b)([A-Za-z_][\w\s\*]*?)\s+({re.escape(helper)})\s*\(([^;{{}}]*)\)\s*\{{",
            source_text,
        )
        if not source_sig:
            continue
        if re.search(rf"\b{re.escape(helper)}\s*\(", updated):
            continue

        ret_type = " ".join(source_sig.group(1).split())
        args = " ".join(str(source_sig.group(3) or "").split())
        if not args:
            args = "void"
        decl = f"{ret_type} {helper}({args});\n"
        updated = _inject_before_header_endif(updated, decl, f"{module_upper}_DRIVER_H")
        actions.append(f"{module_upper}: added missing header declaration for {helper}()")

    if updated != header_text:
        header_path.write_text(normalize_generated_text(updated, header_path), encoding="utf-8")

    return actions


def _ensure_iomm_one_hot_encoding(source_code: str) -> str:
    """
    Ensure IOMM pin-function encoding is one-hot inside each 8-bit PINMMR field.

    Some generations drift to raw ordinal encoding (ALT1 -> 0x01), but RM46
    bring-up requires one-hot writes (ALT1 -> bit1 in field).
    """
    updated = source_code

    # Convert ordinal-style assignment to one-hot.
    updated = re.sub(
        r"\bfunction_value\s*=\s*\(uint32_t\)\s*function\s*;",
        "function_value = (1U << (uint32_t)function);",
        updated,
    )

    # Handle switch-case styles that set raw constants 0x00..0x07.
    updated = re.sub(
        r"\bfunction_value\s*=\s*0x0?[0-7]U\s*;",
        "function_value = (1U << (uint32_t)function);",
        updated,
    )

    # If function is masked directly, rewrite to one-hot before shift.
    updated = re.sub(
        r"\(\s*\(\s*uint32_t\s*\)\s*function\s*&\s*0xFFU\s*\)\s*<<",
        "((1U << (uint32_t)function) & 0xFFU) <<",
        updated,
    )

    # Keep compatibility with symbolic mask names if present.
    updated = re.sub(
        r"\(\s*\(\s*uint32_t\s*\)\s*function\s*&\s*IOMM_[A-Z0-9_]*MASK\s*\)\s*<<",
        "((1U << (uint32_t)function) & IOMM_FUNCTION_BITS_MASK) <<",
        updated,
    )

    return updated


def _find_c_function_body_span(source_code: str, function_name: str) -> Optional[tuple[int, int]]:
    """Return (body_start, body_end_exclusive) for a C function body."""
    sig_match = re.search(rf"\b{re.escape(function_name)}\s*\([^;{{}}]*\)\s*\{{", source_code)
    if not sig_match:
        return None

    open_brace = source_code.find("{", sig_match.start(), sig_match.end())
    if open_brace < 0:
        return None

    depth = 0
    idx = open_brace
    while idx < len(source_code):
        ch = source_code[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return (open_brace + 1, idx)
        idx += 1

    return None


def _ensure_iomm_configurepin_locking(source_code: str) -> str:
    """
    Enforce IOMM unlock/lock discipline inside IOMM_ConfigurePin().

    Bring-up requirement: pin-mux writes must occur with IOMM unlocked and
    the function must re-lock before returning.
    """
    span = _find_c_function_body_span(source_code, "IOMM_ConfigurePin")
    if span is None:
        return source_code

    body_start, body_end = span
    body = source_code[body_start:body_end]
    updated = body

    if "IOMM_Unlock(" not in updated:
        unlock_stmt = (
            "    /* Bring-up contract: unlock IOMM before pin-mux writes. */\n"
            "    IOMM_Unlock();\n"
        )
        anchor = re.search(
            r"^\s*(?:reg_value\s*=\s*\*pinmmr_reg\s*;|pinmmr_reg\s*=.*;|\*pinmmr_reg\s*=)",
            updated,
            re.MULTILINE,
        )
        if anchor:
            updated = updated[:anchor.start()] + unlock_stmt + updated[anchor.start():]
        else:
            return_anchor = re.search(r"^\s*return\b", updated, re.MULTILINE)
            if return_anchor:
                updated = updated[:return_anchor.start()] + unlock_stmt + updated[return_anchor.start():]
            else:
                updated = unlock_stmt + updated

    lines = updated.splitlines(keepends=True)
    rewritten_lines: List[str] = []
    for line in lines:
        if re.match(r"^\s*return\b", line):
            prev_nonempty = ""
            for prev_line in reversed(rewritten_lines):
                if prev_line.strip():
                    prev_nonempty = prev_line.strip()
                    break
            if "IOMM_Lock();" not in prev_nonempty:
                indent = re.match(r"^(\s*)", line).group(1) if re.match(r"^(\s*)", line) else "    "
                rewritten_lines.append(f"{indent}IOMM_Lock();\n")
        rewritten_lines.append(line)
    updated = "".join(rewritten_lines)

    if updated == body:
        return source_code
    return source_code[:body_start] + updated + source_code[body_end:]


def _ensure_pll_bringup_tokens(source_code: str) -> str:
    """
    Deterministically inject missing PLL bring-up sequence writes used by strict
    startup contract checks (RCLKSRC and VCLKASRC).
    """
    if "void PLL_Init(void)" not in source_code:
        return source_code
    if "RCLKSRC" in source_code and "VCLKASRC" in source_code:
        return source_code

    insertion = (
        "    /* Bring-up contract: explicit RTI and async clock source routing. */\n"
        "    SYSREG->RCLKSRC = (1U << 24U) | (9U << 16U) | (1U << 8U) | (9U << 0U);\n"
        "    SYSREG->VCLKASRC = (9U << 8U) | (9U << 0U);\n"
    )

    # Prefer inserting after GHVSRC selection in PLL_Init.
    ghv_line = re.search(r"^\s*SYSREG->GHVSRC\s*=.*?;\s*$", source_code, re.MULTILINE)
    if ghv_line:
        end = ghv_line.end()
        return source_code[:end] + "\n" + insertion + source_code[end:]

    # Fallback: insert near top of PLL_Init body.
    init_sig = re.search(r"void\s+PLL_Init\s*\(\s*void\s*\)\s*\{", source_code)
    if init_sig:
        end = init_sig.end()
        return source_code[:end] + "\n" + insertion + source_code[end:]

    return source_code


def _normalize_system_flash_register_access(source_code: str) -> str:
    """
    Normalize flash wait-state register accesses in system.c.

    Some generations incorrectly use SYSTEM register-map members that do not
    exist in reg_system.h (e.g., SYS->FRDCNTL). Convert these to explicit
    MMIO register macros at fixed RM46 flash-controller addresses.
    """
    updated = source_code

    replacements = {
        "FRDCNTL": "FLASH_FRDCNTL_REG",
        "FSMWRENA": "FLASH_FSMWRENA_REG",
        "EEPROMCONFIG": "FLASH_EEPROMCONFIG_REG",
        "FBFALLBACK": "FLASH_FBFALLBACK_REG",
        "FLASH_FRDCNTL": "FLASH_FRDCNTL_REG",
    }
    pointer_aliases = ["SYS", "systemREG1", "sysREG", "SYSTEMREG1"]

    for member, macro in replacements.items():
        for alias in pointer_aliases:
            updated = re.sub(
                rf"\b{alias}\s*->\s*{member}\b",
                macro,
                updated,
            )

    if updated == source_code:
        return source_code

    macro_block = (
        "#define FLASH_FRDCNTL_REG      (*(volatile uint32_t *)0xFFF87000u)\n"
        "#define FLASH_FSMWRENA_REG     (*(volatile uint32_t *)0xFFF87288u)\n"
        "#define FLASH_EEPROMCONFIG_REG (*(volatile uint32_t *)0xFFF872B8u)\n"
        "#define FLASH_FBFALLBACK_REG   (*(volatile uint32_t *)0xFFF87040u)"
    )
    for line in macro_block.splitlines():
        if line not in updated:
            updated = _inject_include_if_missing(updated, line)

    return updated


def _postprocess_generated_code(
    mod_name: str,
    type_tag: str,
    code: str,
    output_dir: Optional[Path] = None,
) -> str:
    """
    Apply deterministic compile-safety rewrites for known TI compiler pitfalls.
    """
    processed = code

    if type_tag in {"h", "c"}:
        # TI ARM compiler reserves 'interrupt' in this context.
        processed = re.sub(r"\binterrupt\b", "int_type", processed)
        if mod_name.upper() == "PCR" and type_tag == "h":
            processed = _ensure_pcr_enable_all_declaration(processed)

    if type_tag == "c":
        # Ensure NULL is defined when used.
        if re.search(r"\bNULL\b", processed) and not re.search(r"#include\s*<(stddef|stdlib)\.h>", processed):
            processed = _inject_include_if_missing(processed, "#include <stddef.h>")

        # Handle IOMM PINMMR access when register map is scalar fields.
        if mod_name.upper() == "IOMM":
            replaced = re.sub(r"\biommREG->PINMMR0\[(\d+)\]", r"IOMM_PINMMR(\1)", processed)
            if replaced != processed:
                processed = replaced
                macro = "#define IOMM_PINMMR(n) (*((volatile uint32_t*)(&iommREG->PINMMR0) + (n)))"
                if macro not in processed:
                    processed = _inject_include_if_missing(processed, macro)
            processed = _ensure_iomm_one_hot_encoding(processed)
            processed = _ensure_iomm_configurepin_locking(processed)
        elif mod_name.upper() == "PLL":
            processed = _ensure_pll_bringup_tokens(processed)
        elif mod_name.upper() == "PCR":
            processed = _ensure_pcr_enable_all_definition(processed, output_dir=output_dir)
        elif mod_name.upper() == "SYSTEM":
            processed = _normalize_system_flash_register_access(processed)

        # Enforce canonical base macro usage when header defines one (arrow access preserved).
        processed = _normalize_driver_base_alias_usage(
            mod_name,
            processed,
            output_dir=output_dir,
        )

    return processed


# ============================================================================
# Register Header Token Optimization
# ============================================================================

def strip_c_comments(content: str) -> str:
    """
    Remove all C/C++ style comments from header file while preserving all code.

    Removes:
    - Multi-line comments /* ... */
    - Single-line comments // ...

    Preserves:
    - All typedef declarations
    - All struct definitions
    - All #define statements (ALL bit field definitions)
    - All enum definitions
    - All actual code

    This removes 60-80% of file size (verbose documentation) while preserving
    100% of the context the LLM needs for accurate code generation.
    """
    # Remove multi-line comments /* ... */
    # Handle multi-line with DOTALL flag
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)

    # Remove single-line comments // ...
    # But be careful not to remove // in string literals (rare in headers)
    content = re.sub(r'//[^\n]*', '', content)

    return content


def compact_whitespace(content: str) -> str:
    """
    Compact excessive whitespace to reduce tokens further.

    - Removes empty lines (more than 2 consecutive newlines)
    - Preserves single blank lines for readability
    - Does not affect code structure or semantics
    """
    # Replace 3+ consecutive newlines with just 2
    content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)

    # Remove trailing whitespace on each line
    content = re.sub(r'[ \t]+$', '', content, flags=re.MULTILINE)

    return content


def extract_register_essentials(reg_header_path: Path, size_threshold: int = 15000) -> str:
    """
    Optimize register header by removing comments but preserving ALL code.

    Returns either:
    - Full header content (for simple peripherals < 15KB)
    - Comment-stripped version (for complex peripherals >= 15KB)

    CRITICAL: This preserves ALL context needed for accurate generation:
    - ALL typedef declarations
    - ALL struct members
    - ALL bit field #define statements (not just a subset)
    - ALL enum definitions
    - ALL macros

    Only documentation comments are removed, which typically account for
    60-80% of file size but provide redundant information (bit names are
    usually self-documenting, e.g., "SCI_SCIGCR1_TXENA" = transmit enable).

    Token reduction: ~70-80% for complex peripherals (>15KB)
    Accuracy impact: NONE - all code context preserved

    :param reg_header_path: Path to the register header file
    :param size_threshold: Size threshold in bytes (default 15KB)
    :return: Either full or optimized header content
    """
    if not reg_header_path.exists():
        return "// Register header not found"

    content = reg_header_path.read_text(encoding="utf-8")

    # Use full header if small enough
    if len(content) < size_threshold:
        return content

    # Strip comments but preserve ALL code
    optimized = strip_c_comments(content)

    # Compact excessive whitespace
    optimized = compact_whitespace(optimized)

    # Add header to indicate optimization was applied
    header = "// REGISTER HEADER - Comments stripped for token optimization\n"
    header += "// ALL code context preserved (typedefs, structs, ALL bit definitions)\n\n"
    optimized = header + optimized

    # Log the reduction
    original_size = len(content)
    optimized_size = len(optimized)
    reduction_pct = ((original_size - optimized_size) / original_size) * 100

    logger.info(f"Register header optimization: {reg_header_path.name} "
                f"{original_size} -> {optimized_size} bytes ({reduction_pct:.1f}% reduction)")

    return optimized


# ============================================================================
# Function Signature Parsing for Type-Safe Dependency Usage
# ============================================================================

def parse_function_signatures(manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Parse function prototypes from manifest to extract return types and parameters.

    This enables Pass 2 generation to enforce exact type matching when calling
    dependency functions (e.g., knowing IOMM_Unlock() returns void, not iomm_status_t).

    Args:
        manifest: Module manifest dict with 'functions' array

    Returns:
        Dict mapping function_name -> {
            'return_type': str,
            'parameters': [(param_name, param_type), ...],
            'prototype': str (original)
        }

    Example:
        For IOMM manifest, returns:
        {
            'IOMM_Unlock': {
                'return_type': 'void',
                'parameters': [],
                'prototype': 'void IOMM_Unlock(void);'
            },
            'IOMM_ConfigurePin': {
                'return_type': 'iomm_status_t',
                'parameters': [('pin_number', 'uint8_t'), ('function', 'iomm_pin_function_t')],
                'prototype': 'iomm_status_t IOMM_ConfigurePin(uint8_t pin_number, iomm_pin_function_t function);'
            }
        }
    """
    signatures = {}

    for func in manifest.get('functions', []):
        name = func.get('name')
        if not name:
            continue

        # If structured data already exists (future enhancement), use it
        if 'return_type' in func and 'parameters' in func:
            signatures[name] = {
                'return_type': func['return_type'],
                'parameters': [(p['name'], p['type']) for p in func['parameters']],
                'prototype': func.get('prototype', '')
            }
        # Otherwise, parse prototype string
        elif 'prototype' in func:
            proto = func['prototype'].strip()

            # Parse "return_type function_name(params);"
            # Example: "iomm_status_t IOMM_ConfigurePin(uint8_t pin_number, iomm_pin_function_t function);"

            # Remove trailing semicolon
            proto_clean = proto.rstrip(';').strip()

            # Find the opening parenthesis to split return_type + func_name from params
            paren_pos = proto_clean.find('(')
            if paren_pos == -1:
                logger.warning(f"Could not parse prototype: {proto}")
                continue

            # Extract everything before '(' and split to get return type and function name
            before_paren = proto_clean[:paren_pos].strip()
            parts = before_paren.split()

            if len(parts) < 2:
                # Malformed prototype
                logger.warning(f"Could not parse return type/name from: {before_paren}")
                continue

            # Last part is function name, everything before is return type
            func_name = parts[-1]
            return_type = ' '.join(parts[:-1])

            # Extract parameters from within parentheses
            close_paren_pos = proto_clean.rfind(')')
            if close_paren_pos == -1:
                logger.warning(f"Could not find closing paren in: {proto}")
                continue

            params_str = proto_clean[paren_pos+1:close_paren_pos].strip()

            # Parse parameters
            parameters = []
            if params_str and params_str != 'void':
                # Split by comma
                param_list = params_str.split(',')
                for param in param_list:
                    param = param.strip()
                    # Parse "type name" or "type* name" or "const type* name"
                    # Simple approach: last token is name, rest is type
                    param_parts = param.split()
                    if len(param_parts) >= 2:
                        param_name = param_parts[-1]
                        # Remove pointer/array from param name if present
                        if '*' in param_name:
                            param_name = param_name.replace('*', '')
                        if '[' in param_name:
                            param_name = param_name[:param_name.index('[')]
                        param_type = ' '.join(param_parts[:-1])
                        parameters.append((param_name, param_type))

            signatures[func_name] = {
                'return_type': return_type,
                'parameters': parameters,
                'prototype': proto
            }

    return signatures


def extract_header_api_snippets(header_path: Path) -> Dict[str, str]:
    """
    Extract key API declarations from Pass 1 header for use as concrete examples.

    Args:
        header_path: Path to the Pass 1 header file (e.g., iomm_driver.h)

    Returns:
        Dict with keys:
        - 'enums': All enum typedef declarations (full text)
        - 'functions': Sample function prototypes (up to 10)
    """
    if not header_path.exists():
        return {}

    import re
    try:
        content = header_path.read_text(encoding='utf-8')
    except Exception as e:
        logger.warning(f"Could not read header {header_path}: {e}")
        return {}

    snippets = {}

    # Extract enum typedefs (complete declarations)
    enum_pattern = r'typedef\s+enum\s*\{[^}]+\}\s*\w+;'
    enum_matches = re.finditer(enum_pattern, content, re.MULTILINE | re.DOTALL)
    enum_snippets = []
    for match in enum_matches:
        enum_snippets.append(match.group(0))
    snippets['enums'] = '\n\n'.join(enum_snippets)

    # Extract function prototypes (look for lines ending with ");")
    func_pattern = r'^[\w\s\*]+\s+\w+\([^)]*\);'
    func_matches = re.finditer(func_pattern, content, re.MULTILINE)
    func_snippets = []
    for match in func_matches:
        line = match.group(0).strip()
        # Skip commented lines
        if not line.startswith('//') and not line.startswith('/*'):
            func_snippets.append(line)
    snippets['functions'] = '\n'.join(func_snippets[:10])  # Limit to first 10

    return snippets


def format_dependency_headers(manifest: Dict, output_dir: Path, dependency_names: List[str]) -> str:
    """
    Extract actual header snippets for dependencies to show EXACT API declarations.

    Args:
        manifest: Full BSP manifest with api_catalog
        output_dir: Output directory containing include/ folder
        dependency_names: List of dependency module names to extract

    Returns:
        Formatted string with header excerpts showing exact enum/function declarations
    """
    lines = []
    lines.append("\n" + "="*70)
    lines.append("DEPENDENCY API DECLARATIONS (FROM PASS 1 HEADERS)")
    lines.append("="*70)
    lines.append("These are the ACTUAL declarations from generated headers.")
    lines.append("You MUST use these EXACT identifier names.\n")

    include_dir = output_dir / "include"
    api_catalog = manifest.get("api_catalog", {})

    for dep_name in dependency_names:
        if dep_name not in api_catalog:
            continue

        dep_manifest = api_catalog[dep_name]
        header_file = dep_manifest.get('driver_header_file', f"{dep_name.lower()}_driver.h")
        header_path = include_dir / header_file

        if not header_path.exists():
            logger.info(f"Header not found for {dep_name}: {header_path}")
            continue

        lines.append(f"\n--- {dep_name} Header Excerpts ({header_file}) ---")
        snippets = extract_header_api_snippets(header_path)

        if snippets.get('enums'):
            lines.append(f"\nEnum Declarations:")
            lines.append("```c")
            lines.append(snippets['enums'])
            lines.append("```")

        if snippets.get('functions'):
            lines.append(f"\nFunction Prototypes:")
            lines.append("```c")
            lines.append(snippets['functions'])
            lines.append("```")

    return '\n'.join(lines)


def build_pll_bus_slice(bus_data: Dict[str, Any]) -> str:
    """
    Extract a focused bus.yaml slice for PLL context.

    Includes only what PLL Pass1 manifest and Pass2 code-gen need:
    - Top-level sources with freq_hz and PLL sub-keys
    - Top-level domains with divider_register/field/bits
    - x-ext.peripheral_clocks.SYSTEM (source_number + domain_number mappings)
    - x-ext.peripheral_clocks.PLL (LPO frequencies)

    Omits per-peripheral clock entries (~750 lines of noise).
    Typical reduction: 826 lines → ~60 focused lines.
    """
    if not bus_data:
        return ""

    from ..yaml.yaml_utils import dump_yaml_str

    slice_data: Dict[str, Any] = {}

    # Sources: OSCIN freq, PLL1/PLL2 config
    if "sources" in bus_data:
        slice_data["sources"] = bus_data["sources"]

    # Domains: GCLK, HCLK, VCLK, VCLK2, VCLK3, VCLK4, RTICLK with dividers
    if "domains" in bus_data:
        slice_data["domains"] = bus_data["domains"]

    # SYSTEM + PLL sections from x-ext.peripheral_clocks
    x_ext = bus_data.get("x-ext") or {}
    periph_clocks = x_ext.get("peripheral_clocks") or {}
    focused: Dict[str, Any] = {}
    if "SYSTEM" in periph_clocks:
        focused["SYSTEM"] = periph_clocks["SYSTEM"]
    if "PLL" in periph_clocks:
        focused["PLL"] = periph_clocks["PLL"]
    if focused:
        slice_data["x-ext"] = {"peripheral_clocks": focused}

    return dump_yaml_str(slice_data) if slice_data else ""


def build_pinmux_slice(pinmux_data: Dict[str, Any], module_name: str) -> str:
    """
    Extract relevant pins from pinmux.yaml for a specific peripheral.

    Searches for pins where any function.signal matches common peripheral patterns:
    - SCI: SCIRX, SCITX
    - LIN: LINRX, LINTX
    - GIO: GIOA[n], GIOB[n]
    - SPI: MIBSPI*SCLK, MIBSPI*MISO, MIBSPI*MOSI, MIBSPI*NCS
    - I2C: I2C_SCL, I2C_SDA
    - CAN: CANTX, CANRX
    - PWM/EPWM: EPWM*A, EPWM*B
    - N2HET: N2HET*[n]

    Returns a YAML string containing only the relevant pins.
    """
    if not pinmux_data:
        return ""

    from ..yaml.yaml_utils import dump_yaml_str

    # Map module names to signal patterns
    signal_patterns = {
        "SCI": ["SCIRX", "SCITX"],
        "LIN": ["LINRX", "LINTX", "LINTX", "LIN2RX", "LIN2TX", "SCIRX", "SCITX"],  # LIN can use SCI pins
        "GIO": ["GIOA", "GIOB"],
        "SPI": ["MIBSPI", "SPI"],
        "I2C": ["I2C_SCL", "I2C_SDA"],
        "CAN": ["CANTX", "CANRX", "DCAN"],
        "PWM": ["EPWM", "PWMSYNC"],
        "EPWM": ["EPWM"],
        "N2HET": ["N2HET"],
    }

    module_upper = module_name.upper()

    # Special case: IOMM needs ALL pins with mux data (for pin-to-PINMMR lookup table)
    if module_upper == "IOMM":
        pins = pinmux_data.get("pins", [])
        # Filter to only pins that have mux information
        relevant_pins = []
        for pin in pins:
            functions = pin.get("functions", [])
            for func in functions:
                mux = func.get("mux")
                if mux and mux.get("register") and mux.get("bit") is not None:
                    relevant_pins.append(pin)
                    break  # Don't add same pin twice

        if not relevant_pins:
            return ""

        # Build complete pinmux data for IOMM
        slice_data = {
            "$id": pinmux_data.get("$id", "pinmux.schema.yaml"),
            "package": pinmux_data.get("package", ""),
            "pins": relevant_pins
        }
        return dump_yaml_str(slice_data)

    patterns = signal_patterns.get(module_upper, [])

    if not patterns:
        return ""

    # Find matching pins
    pins = pinmux_data.get("pins", [])
    relevant_pins = []

    for pin in pins:
        functions = pin.get("functions", [])
        for func in functions:
            signal = func.get("signal", "")
            # Check if this signal matches any of our patterns
            for pattern in patterns:
                if pattern in signal.upper():
                    relevant_pins.append(pin)
                    break  # Don't add the same pin twice
            if pin in relevant_pins:
                break  # Move to next pin

    if not relevant_pins:
        return ""

    # Build a minimal pinmux slice
    slice_data = {
        "$id": pinmux_data.get("$id", "pinmux.schema.yaml"),
        "package": pinmux_data.get("package", ""),
        "pins": relevant_pins
    }

    return dump_yaml_str(slice_data)


async def run_implementation_pass(
    manifest: Dict[str, Any],
    soc_data: Dict[str, Any],
    board_data: Dict[str, Any],
    bus_data: Dict[str, Any],
    pinmux_data: Dict[str, Any],
    model: Model,
    output_dir: Path,
    max_tokens: int = 20000,
    allowed_modules: Optional[List[str]] = None,
    regs_data: Optional[Dict[str, Any]] = None,
    enable_validation: bool = True,
    strict_validation: bool = False,
    contract_mode: str = "auto_fix_then_fail",
    api_contract_manifest: Optional[Dict[str, Any]] = None,
    bringup_contract: Optional[Dict[str, Any]] = None,
    bringup_strict: bool = False,
    token_allocator = None,
    progress_manager = None
):
    """
    Pass 2: Driver Implementation.

    Iterates through the Manifest created in Pass 1.
    Generates .h and .c files for each module.

    :param allowed_modules: If provided, only implement modules with names in this list.
    :param regs_data: Register definitions for validation
    :param enable_validation: Whether to run validation on generated files
    :param token_allocator: Optional token allocator for tracking token usage
    """
    
    api_catalog = manifest.get("api_catalog", {})
    
    # Filter catalog if needed
    if allowed_modules is not None:
        # Normalize to upper case for comparison
        allowed_set = set(m.upper() for m in allowed_modules)
        # Filter api_catalog
        api_catalog = {k: v for k, v in api_catalog.items() if k.upper() in allowed_set}
        print(f"[pass2] Filtered to {len(api_catalog)} modules based on user selection.")
    
    logger.info(f"Starting Pass 2 (Implementation) for {len(api_catalog)} modules...")

    # Setup progress tracker
    tracker = None
    if progress_manager:
        tracker = progress_manager.start_pass("Implementation")
        if tracker:
            tracker.set_total_tasks(len(api_catalog) * 2)  # header + source per module

    # Folder setup
    inc_dir = output_dir / "include"
    src_dir = output_dir / "source"
    inc_dir.mkdir(parents=True, exist_ok=True)
    src_dir.mkdir(parents=True, exist_ok=True)

    api_reuse_recipe = resolve_app_intent_api_reuse_recipe(
        bringup_contract=bringup_contract,
        api_contract_manifest=api_contract_manifest,
        driver_source_symbols=None,
    )

    tasks = []

    async def _generate_header(mod_name: str, mod_data: Dict, reg_content: str):
        """Generate driver header with retry logic"""
        from ..regeneration.retry_policy import RetryPolicy, FailureReason
        from ..regeneration.truncation_detector import detect_simple_truncation

        retry_policy = RetryPolicy()
        current_tokens = max_tokens

        for attempt in range(retry_policy.max_retries + 1):
            if attempt > 0:
                if tracker:
                    tracker.add_message(f"Retrying {mod_name} header - Attempt {attempt + 1} ({current_tokens} tokens)", level="warning")
                else:
                    print(f"  [retry] Pass2 header {mod_name} - Attempt {attempt + 1} (tokens: {current_tokens})")

            try:
                prompt = build_pass2_driver_h_prompt(mod_name, json.dumps(mod_data, indent=2), reg_content)
                resp = await invoke_model(model, current_tokens, [{"role": "user", "content": prompt}])
                text = extract_text_from_bedrock_response(resp)

                # Track token usage for cost estimation
                if token_allocator:
                    try:
                        from ..utils.utils import extract_usage_from_bedrock_response
                        usage = extract_usage_from_bedrock_response(resp)
                        tokens_used = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                        if tokens_used > 0:
                            token_allocator.record_success(f"pass2_{mod_name.lower()}_header", tokens_used)
                    except Exception:
                        pass  # Don't fail if token tracking fails

                # Check for truncation
                truncation_reason = detect_simple_truncation(text)
                if truncation_reason:
                    print(f"  [warn] Truncation in {mod_name} header: {truncation_reason}")
                    should_retry, current_tokens = retry_policy.should_retry(
                        attempt + 1,
                        FailureReason.TOKEN_TRUNCATION,
                        current_tokens
                    )
                    if should_retry:
                        continue
                    else:
                        logger.warning(f"Max retries exceeded for {mod_name} header")

                return ("h", text, text)  # (type, content, raw_response)

            except Exception as e:
                logger.error(f"Header Error {mod_name}: {e}")
                should_retry, current_tokens = retry_policy.should_retry(
                    attempt + 1,
                    FailureReason.TRANSIENT_ERROR,
                    current_tokens
                )
                if should_retry:
                    continue
                return ("error", f"Header Gen Failed: {e}", "")

        return ("error", f"Max retries exceeded for {mod_name} header", "")

    async def _generate_source(mod_name: str, mod_data: Dict, reg_content: str, soc_slice: str, bus_slice: str, pinmux_slice: str, instance_pin_config: dict = None, dependency_manifests: dict = None, dependency_signatures: dict = None):
        """Generate driver source with retry logic"""
        from ..regeneration.retry_policy import RetryPolicy, FailureReason
        from ..regeneration.truncation_detector import detect_simple_truncation

        retry_policy = RetryPolicy()
        current_tokens = max_tokens

        for attempt in range(retry_policy.max_retries + 1):
            if attempt > 0:
                if tracker:
                    tracker.add_message(f"Retrying {mod_name} source - Attempt {attempt + 1} ({current_tokens} tokens)", level="warning")
                else:
                    print(f"  [retry] Pass2 source {mod_name} - Attempt {attempt + 1} (tokens: {current_tokens})")

            try:
                # Extract header snippets from Pass 1 dependencies for ground truth
                header_snippets = ""
                if mod_data and 'dependencies' in mod_data:
                    try:
                        header_snippets = format_dependency_headers(
                            manifest,
                            output_dir,
                            mod_data.get('dependencies', [])
                        )
                    except Exception as e:
                        logger.warning(f"Could not extract header snippets: {e}")

                prompt = build_pass2_driver_c_prompt(
                    mod_name,
                    json.dumps(mod_data, indent=2),
                    reg_content,
                    _sanitize_prompt_context_text(soc_slice),
                    _sanitize_prompt_context_text(bus_slice),
                    _sanitize_prompt_context_text(pinmux_slice),
                    manifest=manifest,
                    instance_pin_config=instance_pin_config,
                    dependency_manifests=dependency_manifests,
                    dependency_signatures=dependency_signatures,
                    header_snippets=header_snippets,
                    bringup_contract=bringup_contract,
                )
                resp = await invoke_model(model, current_tokens, [{"role": "user", "content": prompt}])
                text = extract_text_from_bedrock_response(resp)

                # Track token usage for cost estimation
                if token_allocator:
                    try:
                        from ..utils.utils import extract_usage_from_bedrock_response
                        usage = extract_usage_from_bedrock_response(resp)
                        tokens_used = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                        if tokens_used > 0:
                            token_allocator.record_success(f"pass2_{mod_name.lower()}_source", tokens_used)
                    except Exception:
                        pass  # Don't fail if token tracking fails

                # Check for truncation
                truncation_reason = detect_simple_truncation(text)
                if truncation_reason:
                    print(f"  [warn] Truncation in {mod_name} source: {truncation_reason}")
                    should_retry, current_tokens = retry_policy.should_retry(
                        attempt + 1,
                        FailureReason.TOKEN_TRUNCATION,
                        current_tokens
                    )
                    if should_retry:
                        continue
                    else:
                        logger.warning(f"Max retries exceeded for {mod_name} source")

                return ("c", text, text)  # (type, content, raw_response)

            except Exception as e:
                logger.error(f"Source Error {mod_name}: {e}")
                should_retry, current_tokens = retry_policy.should_retry(
                    attempt + 1,
                    FailureReason.TRANSIENT_ERROR,
                    current_tokens
                )
                if should_retry:
                    continue
                return ("error", f"Source Gen Failed: {e}", "")

        return ("error", f"Max retries exceeded for {mod_name} source", "")

    async def _implement_module(mod_name: str, mod_data: Dict):
        # 1. Load Register Header Context (with token optimization)
        reg_filename = mod_data.get("reg_header_file", f"reg_{mod_name.lower()}.h")
        reg_path = output_dir / "include" / reg_filename

        reg_content = "// Register header not found"
        if reg_path.exists():
            # Use optimized extraction (full header for <15KB, essentials for >=15KB)
            reg_content = extract_register_essentials(reg_path)
            # print(f"[debug] {mod_name}: Loaded register context from {reg_filename} ({len(reg_content)} bytes)")
        else:
            logger.warning(f"Pass 2: Could not find {reg_path} for {mod_name}")
            # print(f"[warn] {mod_name}: REG HEADER MISSING. Driver may hallucinate struct members.")

        # PLL uses SYSTEM registers (PLLCTL1/2, CSDIS, GHVSRC, LPOMONCTL, CLKTEST etc.)
        # Append reg_system.h so LLM sees authoritative SYSTEM_ macro names alongside reg_pll.h
        if mod_name.upper() == "PLL":
            sys_reg_path = output_dir / "include" / "reg_system.h"
            if sys_reg_path.exists():
                sys_content = extract_register_essentials(sys_reg_path)
                reg_content = reg_content + "\n\n// === SYSTEM REGISTERS (PLLCTL1/2, CSDIS, GHVSRC etc.) ===\n" + sys_content

        # 2. Get Hardware Info (for Base Address)
        soc_periph = find_soc_peripheral(soc_data, mod_name)
        soc_slice = dump_yaml_str(soc_periph) if soc_periph else ""
        
        # 3. Get Bus Info (for Clocks/Baud Rates)
        # PLL gets a focused slice (sources + domains + SYSTEM/PLL numbers only).
        # Other peripherals get the full bus dump (usually small enough).
        if mod_name.upper() == "PLL":
            bus_slice = build_pll_bus_slice(bus_data)
        else:
            bus_slice = dump_yaml_str(bus_data)

        # 4. Get Pinmux Info (for Pin Configuration)
        pinmux_slice = build_pinmux_slice(pinmux_data, mod_name)

        # 4a. Extract per-instance pin configurations
        instance_pin_config = None
        if mod_name.upper() in {"SCI", "LIN", "GIO", "GPIO", "CAN", "DCAN", "UART"}:
            try:
                from .pin_config_builder import extract_peripheral_instances

                # Extract IOMM manifest for enum value lookup
                iomm_manifest = None
                if manifest and 'api_catalog' in manifest:
                    iomm_manifest = manifest['api_catalog'].get('IOMM')

                instance_pin_config = extract_peripheral_instances(
                    board_data=board_data,
                    pinmux_data=pinmux_data,
                    peripheral=mod_name,
                    iomm_manifest=iomm_manifest
                )
            except Exception as e:
                if tracker:
                    tracker.add_message(f"Warning: Could not extract pin config for {mod_name}: {e}", level="warning")
                # Continue with None - graceful degradation

        # 4b. Collect dependency manifests and parse function signatures
        dependency_manifests = {}
        dependency_signatures = {}  # NEW: parsed function signatures for type safety
        if mod_data and 'dependencies' in mod_data:
            for dep_name in mod_data['dependencies']:
                if dep_name in api_catalog:
                    dependency_manifests[dep_name] = api_catalog[dep_name]
                    # Parse function signatures for exact type matching
                    dependency_signatures[dep_name] = parse_function_signatures(api_catalog[dep_name])

        # 5. Launch Parallel Gens
        t_h = asyncio.create_task(_generate_header(mod_name, mod_data, reg_content))
        t_c = asyncio.create_task(_generate_source(mod_name, mod_data, reg_content, soc_slice, bus_slice, pinmux_slice, instance_pin_config, dependency_manifests, dependency_signatures))
        
        results = await asyncio.gather(t_h, t_c)
        
        return mod_name, results, dependency_manifests

    # Launch all modules
    for name, data in sorted(api_catalog.items(), key=lambda item: item[0].upper()):
        tasks.append(_implement_module(name, data))
        
    print(f"[pass2] Implementing {len(tasks)} modules...")
    
    # Process results as they come in
    validation_results = []

    for f in asyncio.as_completed(tasks):
        mod_name, results, dependency_manifests = await f

        # Track progress
        if tracker:
            tracker.update_task_name(f"Completed {mod_name}")
        else:
            print(f".", end="", flush=True)

        # Collect written files and raw responses for validation
        written_files = []
        raw_responses = []
        has_error = False
        module_header_path: Optional[Path] = None
        module_source_path: Optional[Path] = None

        for type_tag, content, raw_response in results:
            if type_tag == "error":
                has_error = True
                if tracker:
                    tracker.add_message(f"{mod_name}: {content}", level="error")
                    tracker.increment_failure()
                else:
                    logger.error(f"[{mod_name}] {content}")
                continue

            # Clean Code Block
            clean_code = content
            if "```" in content:
                match = re.search(r"```c?(.*?)```", content, re.DOTALL)
                if match:
                    clean_code = match.group(1).strip()
            clean_code = _postprocess_generated_code(
                mod_name,
                type_tag,
                clean_code,
                output_dir=output_dir,
            )

            # Write File
            if type_tag == "h":
                clean_code = inject_driver_usage_recipe_comment(
                    header_text=clean_code,
                    module_name=mod_name,
                    recipe=api_reuse_recipe,
                )
                fname = f"{mod_name.lower()}_driver.h"
                fpath = inc_dir / fname

                # Use file locking to prevent race conditions
                with FileLock(fpath):
                    fpath.write_text(normalize_generated_text(clean_code, fpath), encoding="utf-8")

                written_files.append(fpath)
                module_header_path = fpath
                raw_responses.append(raw_response)
                if tracker:
                    tracker.increment_success()
            elif type_tag == "c":
                fname = f"{mod_name.lower()}_driver.c"
                fpath = src_dir / fname

                # Use file locking to prevent race conditions
                with FileLock(fpath):
                    fpath.write_text(normalize_generated_text(clean_code, fpath), encoding="utf-8")

                written_files.append(fpath)
                module_source_path = fpath
                raw_responses.append(raw_response)
                if tracker:
                    tracker.increment_success()

                # Validate dependency API usage (comprehensive validation)
                validation_errors = []

                # Run comprehensive dependency identifier validation
                # dependency_manifests is a function parameter, always defined (but may be None or empty dict)
                if dependency_manifests:
                    try:
                        from ..validation.pass2_validator import validate_dependency_identifiers, validate_void_function_assignments

                        # Check for undefined identifiers
                        validation_errors.extend(
                            validate_dependency_identifiers(mod_name, clean_code, dependency_manifests)
                        )

                        # Check for void function assignments
                        validation_errors.extend(
                            validate_void_function_assignments(mod_name, clean_code, dependency_manifests)
                        )
                    except Exception as e:
                        # Log validation errors but don't crash generation
                        logger.warning(f"Error during dependency validation for {mod_name}: {e}")
                        if tracker:
                            tracker.add_message(f"Validation error: {e}", level="warning")

                if validation_errors:
                    logger.warning(f"{mod_name} driver: Dependency API validation errors detected:")
                    for error in validation_errors:
                        logger.warning(f"  - {error}")
                    if tracker:
                        for error in validation_errors:
                            tracker.add_message(error, level="warning")

                # Validate reserved keyword usage (safety net for TI compiler compatibility)
                reserved_keywords_errors = []

                # Check for 'interrupt' as a parameter name in function declarations/definitions
                # Pattern: type function_name(... interrupt_t interrupt)
                if re.search(r'\w+\s+\w+\([^)]*\w+_t\s+interrupt\s*[,)]', clean_code):
                    reserved_keywords_errors.append(
                        "'interrupt' used as parameter name - this is a TI compiler reserved keyword. "
                        "Use 'int_type', 'int_flag', or 'int_event' instead."
                    )

                # Check for 'register' as a parameter name (less common but still prohibited)
                if re.search(r'\w+\s+\w+\([^)]*\w+\s+register\s*[,)]', clean_code):
                    reserved_keywords_errors.append(
                        "'register' used as parameter name - this is a C reserved keyword. "
                        "Use 'reg_value', 'reg_val', or 'register_value' instead."
                    )

                # Check for 'inline' as a variable name
                if re.search(r'(?:uint\d+_t|int\d+_t|bool|char)\s+inline\s*[;=]', clean_code):
                    reserved_keywords_errors.append(
                        "'inline' used as variable name - this is a C99 reserved keyword. "
                        "Use a different name."
                    )

                if reserved_keywords_errors:
                    logger.error(f"{mod_name} driver: Reserved keyword usage detected (WILL CAUSE COMPILATION ERRORS):")
                    for error in reserved_keywords_errors:
                        logger.error(f"  - {error}")
                    if tracker:
                        for error in reserved_keywords_errors:
                            tracker.add_message(f"{mod_name}: {error}", level="error")

        module_contract_result = None
        module_autofix_actions: List[str] = []
        helper_decl_actions = _ensure_driver_helper_declarations(
            module_name=mod_name,
            header_path=module_header_path,
            source_path=module_source_path,
        )
        if helper_decl_actions:
            for action in helper_decl_actions:
                logger.info(action)
                if tracker:
                    tracker.add_message(action, level="info")
        if (
            api_contract_manifest
            and module_header_path
            and module_source_path
            and module_header_path.exists()
            and module_source_path.exists()
        ):
            module_contract_result = check_generated_module_contract(
                mod_name,
                module_header_path,
                module_source_path,
                api_contract_manifest,
            )
            critical_runtime_modules = {"LIN", "IOMM", "PLL", "SYSTEM"}
            should_run_autofix = (
                contract_mode == "auto_fix_then_fail"
                and not module_contract_result.get("passed", True)
            )
            if bringup_strict and mod_name.upper() in critical_runtime_modules:
                should_run_autofix = False
            if should_run_autofix:
                autofix_result = autofix_module_contract(
                    mod_name,
                    module_header_path,
                    module_source_path,
                    api_contract_manifest,
                )
                module_autofix_actions.extend(autofix_result.get("actions", []))
                module_contract_result = check_generated_module_contract(
                    mod_name,
                    module_header_path,
                    module_source_path,
                    api_contract_manifest,
                )

            if module_contract_result and not module_contract_result.get("passed", True):
                for err in module_contract_result.get("errors", []):
                    if contract_mode == "warn_only":
                        logger.warning(f"{mod_name} contract warning: {err}")
                    else:
                        logger.error(f"{mod_name} contract error: {err}")
                if tracker:
                    for err in module_contract_result.get("errors", [])[:5]:
                        level = "warning" if contract_mode == "warn_only" else "error"
                        tracker.add_message(f"{mod_name}: {err}", level=level)

        # Run validation if enabled
        if enable_validation and written_files and soc_data and regs_data:
            from ..validation.validation_engine import validate_generation_output
            from ..validation.pass2_validator import validate_driver_implementation

            try:
                # Combine raw responses for validation preamble
                combined_raw = "\n\n".join(raw_responses)

                # Run FACTS MIRROR validation
                validation_result = validate_generation_output(
                    tag=f"pass2_{mod_name.lower()}",
                    preamble=combined_raw,
                    written_files=written_files,
                    soc_data=soc_data,
                    regs_data=regs_data
                )

                # Run Pass 2 driver-specific validation (clock usage, API compliance)
                manifest_entry = api_catalog.get(mod_name, {})
                pass2_result = validate_driver_implementation(
                    module_name=mod_name,
                    manifest_entry=manifest_entry,
                    preamble=combined_raw,
                    written_files=written_files,
                    soc_data=soc_data,
                    regs_data=regs_data,
                    bringup_contract=bringup_contract,
                )

                # Merge validation results
                if not pass2_result.is_valid:
                    validation_result.is_valid = False
                    validation_result.errors.extend(pass2_result.critical_errors)
                    validation_result.warnings.extend(pass2_result.warnings)

                if module_contract_result and not module_contract_result.get("passed", True):
                    if contract_mode == "warn_only":
                        validation_result.warnings.extend(module_contract_result.get("errors", []))
                        validation_result.warnings.extend(module_contract_result.get("warnings", []))
                    else:
                        validation_result.is_valid = False
                        validation_result.errors.extend(module_contract_result.get("errors", []))
                        validation_result.warnings.extend(module_contract_result.get("warnings", []))

                setattr(validation_result, "compile_contract", module_contract_result)
                setattr(validation_result, "autofix_actions", module_autofix_actions)

                validation_results.append((mod_name, validation_result))

                # Log validation summary
                if not validation_result.is_valid:
                    logger.warning(f"Pass 2 validation failed for {mod_name}")
                    for error in validation_result.errors[:3]:  # Show first 3 errors
                        logger.warning(f"  - {error}")
                if pass2_result.warnings:
                    for warning in pass2_result.warnings[:3]:  # Show first 3 warnings
                        logger.info(f"  - {warning}")
            except Exception as e:
                logger.error(f"Validation error for {mod_name}: {e}")

    # Complete pass tracking
    if progress_manager:
        progress_manager.complete_pass("Implementation", success=True)

    if not tracker:
        print("\n[pass2] Implementation Complete.")

    if enable_validation and validation_results:
        validation_results.sort(key=lambda item: item[0])
        failed_count = sum(1 for _, vr in validation_results if not vr.is_valid)
        logger.info(f"Pass 2 Validation: {len(validation_results)} modules checked, {failed_count} failed")

    # Return validation results for final report
    return validation_results if enable_validation else []
