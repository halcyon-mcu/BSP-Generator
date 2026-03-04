from pathlib import Path

from modules.generation.implementation import (
    _ensure_driver_helper_declarations,
    _postprocess_generated_code,
    _sanitize_prompt_context_text,
)


def test_prompt_context_sanitizer_neutralizes_comment_terminator():
    text = "init_note: do not write PSPWRDWNSET*/PCSPWRDWNSET* during init"
    sanitized = _sanitize_prompt_context_text(text)
    assert "*/" not in sanitized
    assert "* /" in sanitized


def test_postprocess_normalizes_pcr_alias_to_header_macro(tmp_path: Path):
    include_dir = tmp_path / "include"
    include_dir.mkdir(parents=True, exist_ok=True)
    (include_dir / "reg_pcr.h").write_text(
        "typedef struct { volatile unsigned int PSPWRDWNCLR0; } PCR_REG_MAP_t;\n"
        "#define PCR ((PCR_REG_MAP_t *)0xFFFFE000U)\n",
        encoding="utf-8",
    )

    source = (
        '#include "pcr_driver.h"\n'
        '#include "reg_pcr.h"\n'
        "void PCR_Init(void)\n"
        "{\n"
        "    pcrREG->PSPWRDWNCLR0 = 0xFFFFFFFFU;\n"
        "}\n"
    )

    processed = _postprocess_generated_code("PCR", "c", source, output_dir=tmp_path)
    assert "pcrREG->" not in processed
    assert "PCR->PSPWRDWNCLR0" in processed


def test_ensure_driver_helper_declarations_adds_enablepins_prototype(tmp_path: Path):
    include_dir = tmp_path / "include"
    source_dir = tmp_path / "source"
    include_dir.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)

    header_path = include_dir / "lin_driver.h"
    source_path = source_dir / "lin_driver.c"

    header_path.write_text(
        "#ifndef LIN_DRIVER_H\n#define LIN_DRIVER_H\n\n#endif /* LIN_DRIVER_H */\n",
        encoding="utf-8",
    )
    source_path.write_text(
        "void LIN_EnablePins(void)\n{\n}\n",
        encoding="utf-8",
    )

    actions = _ensure_driver_helper_declarations(
        module_name="LIN",
        header_path=header_path,
        source_path=source_path,
    )
    patched = header_path.read_text(encoding="utf-8")
    assert actions
    assert "void LIN_EnablePins(void);" in patched
