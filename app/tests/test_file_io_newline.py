"""
Unit tests for generated file newline normalization.
"""

import re
from pathlib import Path

from modules.utils.file_io import normalize_generated_text


def test_normalize_generated_text_adds_missing_newline():
    content = "int main(void) { return 0; }"
    out = normalize_generated_text(content, Path("main.c"))
    assert out.endswith("\n")
    assert "int main(void) { return 0; }\n" in out
    assert "BSP-GEN-META:" in out.splitlines()[0]


def test_normalize_generated_text_enforces_single_trailing_newline():
    content = "void init(void) {}\n\n\n"
    path = Path("output_20260302_125540/include/driver.h")
    out = normalize_generated_text(content, path)
    assert out.endswith("\n")
    assert not out.endswith("\n\n")
    first = out.splitlines()[0]
    assert "BSP-GEN-META:" in first
    assert "output_folder=output_20260302_125540" in first
    assert "output_tag=20260302_125540" in first
    assert re.search(r"created_at=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", first)


def test_normalize_generated_text_does_not_duplicate_metadata_header():
    path = Path("output_20260302_125540/include/driver.h")
    once = normalize_generated_text("void init(void) {}", path)
    twice = normalize_generated_text(once, path)
    assert twice.count("BSP-GEN-META:") == 1
    assert twice.endswith("\n")


def test_normalize_generated_text_ignores_non_generated_extensions():
    content = "key: value"
    out = normalize_generated_text(content, Path("config.yaml"))
    assert out == "key: value"
