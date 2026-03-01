"""
Unit tests for generated file newline normalization.
"""

from pathlib import Path

from modules.utils.file_io import normalize_generated_text


def test_normalize_generated_text_adds_missing_newline():
    content = "int main(void) { return 0; }"
    out = normalize_generated_text(content, Path("main.c"))
    assert out.endswith("\n")
    assert out == "int main(void) { return 0; }\n"


def test_normalize_generated_text_enforces_single_trailing_newline():
    content = "void init(void) {}\n\n\n"
    out = normalize_generated_text(content, Path("driver.h"))
    assert out == "void init(void) {}\n"


def test_normalize_generated_text_ignores_non_generated_extensions():
    content = "key: value"
    out = normalize_generated_text(content, Path("config.yaml"))
    assert out == "key: value"
