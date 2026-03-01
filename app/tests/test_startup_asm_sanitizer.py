from pathlib import Path

from main import _sanitize_start_asm_files


def test_startup_asm_sanitizer_rewrites_ldr_immediate_literal(tmp_path: Path):
    start_s = tmp_path / "start.s"
    start_s.write_text(
        "\n".join(
            [
                "Undef_Handler:",
                "        LDR     R0, =0x08000000",
                "        LDR     R1, =0xDEAD0001",
                "        B       Undef_Handler",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    _sanitize_start_asm_files([start_s])

    text = start_s.read_text(encoding="utf-8")
    assert "LDR     R0, =0x08000000" not in text
    assert "LDR     R1, =0xDEAD0001" not in text
    assert "MOVW    R0, #0x0000" in text
    assert "MOVT    R0, #0x0800" in text
    assert "MOVW    R1, #0x0001" in text
    assert "MOVT    R1, #0xDEAD" in text
