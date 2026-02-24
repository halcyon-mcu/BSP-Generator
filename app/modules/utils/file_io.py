#!/usr/bin/env python3
"""
file_io.py

Helpers for:
- Splitting LLM output into files based on '===== FILE: name =====' separators.
- Writing files into a single run directory (e.g. output_20251117T203001).
- Optionally generating a Makefile or JSON manifest for the run directory.
"""

from __future__ import annotations

import os
import re
import json
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import List

# Matches lines like: ===== FILE: foo.c =====
FILE_SPLIT_RE = re.compile(r"^===== FILE: (.+) =====\s*$", re.M)


def _now_tag() -> str:
    """Return a compact timestamp tag for directory / artifact naming."""
    return datetime.now().strftime("%Y%m%dT%H%M%S")


def _safe_relpath(s: str) -> str:
    """
    Normalize a model-provided path with comprehensive security checks:
    - forbid absolute paths
    - forbid UNC paths
    - forbid null bytes
    - collapse backslashes to forward slashes
    - forbid parent directory traversal ('..')
    - enforce maximum path length
    - strip leading './'
    """
    p = str(s).strip()

    # Check for null bytes (security)
    if '\x00' in p:
        raise ValueError(f"Path contains null byte: {s!r}")

    # Reject UNC paths (Windows network shares)
    if p.startswith('\\\\') or p.startswith('//'):
        raise ValueError(f"Refusing UNC path: {s!r}")

    # Forbid absolute or drive-qualified paths (before normalization)
    if os.path.isabs(p):
        raise ValueError(f"Refusing absolute path: {s!r}")

    # Normalize slashes
    p = p.replace("\\", "/")

    # Remove leading './'
    if p.startswith("./"):
        p = p[2:]

    # Forbid parent traversal
    parts = PurePosixPath(p).parts
    if any(seg == ".." for seg in parts):
        raise ValueError(f"Refusing path with '..': {s!r}")

    # Check maximum path length (Windows limitation)
    if len(p) > 260:
        raise ValueError(f"Path too long ({len(p)} chars, max 260): {s!r}")

    # You can optionally force a flat layout by only taking the final segment:
    # p = parts[-1] if parts else p

    return p


def split_and_write_files(raw_text: str, out_dir: Path) -> tuple[List[Path], str]:
    """
    Split a single LLM response into files and write them under out_dir.

    raw_text:
      The full LLM response text, containing one or more separators of the form:
        ===== FILE: <name> =====
      Everything between separators is written as the content of that file.

    out_dir:
      The root directory for this generation run.
      This function will:
        - create out_dir if needed
        - create an '_artifacts' subdir for raw output / preamble
        - write all declared files under out_dir (respecting _safe_relpath)

    Returns:
      A tuple of (written_files, preamble_text) where:
        - written_files: List of Path objects for all files written
        - preamble_text: Text before first FILE separator (may contain FACTS MIRROR)
    """
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    artifacts = out_dir / "_artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    ts = _now_tag()
    # Save the raw LLM output for debugging
    (artifacts / f"llm_raw_{ts}.txt").write_text(raw_text, encoding="utf-8")

    matches = list(FILE_SPLIT_RE.finditer(raw_text))
    if not matches:
        print("[warn] No file separators found. Check _artifacts/ for raw output.")
        return ([], "")

    written: List[Path] = []

    # Save any preamble before the first separator
    preamble = ""
    first = matches[0]
    if first.start() > 0:
        preamble = raw_text[: first.start()].strip()
        if preamble:
            (artifacts / f"llm_preamble_{ts}.txt").write_text(
                preamble, encoding="utf-8"
            )
            print("[info] Preamble saved to _artifacts/llm_preamble_*.txt")

    for i, m in enumerate(matches):
        raw_rel = m.group(1).strip()
        rel_norm = _safe_relpath(raw_rel)

        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
        content = raw_text[start:end].lstrip("\n")

        target = (out_dir / rel_norm).resolve()

        # Ensure the resolved path is still under out_dir (defense in depth)
        try:
            target.relative_to(out_dir)
        except ValueError:
            raise RuntimeError(f"Refusing to write outside out_dir: {target}")

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(target)

        # Print a friendly relative path (robust across platforms)
        try:
            print("[ok] Wrote", target.relative_to(out_dir))
        except ValueError:
            print("[ok] Wrote", os.path.relpath(str(target), str(out_dir)))

    return (written, preamble)

from pathlib import Path

def write_doxyfile(out_root: Path, project_name: str = "RM46 BSP (Generated)") -> Path:
    doxy = f"""\
            # Auto-generated by GA BSP tool
            PROJECT_NAME           = "{project_name}"
            OUTPUT_DIRECTORY       = docs

            # Where the generated BSP lives (relative to this Doxyfile)
            INPUT                  = .
            FILE_PATTERNS          = *.h *.c *.dox
            RECURSIVE              = YES

            # Keep it simple for now
            GENERATE_HTML          = YES
            GENERATE_LATEX         = NO
            QUIET                  = NO
            WARN_IF_UNDOCUMENTED   = YES
            WARN_IF_DOC_ERROR      = YES
            """
    (out_root / "Doxyfile").write_text(doxy, encoding="utf-8")
    return Path(out_root / "Doxyfile")

import subprocess

def run_doxygen(bsp_out_root: Path, doxy_path: Path) -> None:
    out_root = Path(bsp_out_root)
    doxyfile = (doxy_path).resolve()


    if not doxyfile.exists():
        raise FileNotFoundError(f"Doxyfile not found in {out_root / 'docs'}")

    # On Windows you might need "doxygen.exe" explicitly, or use shutil.which.
    result = subprocess.run(
        ["doxygen", str(doxyfile)],
        cwd=out_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        # You can surface this back to the CLI user
        raise RuntimeError(f"Doxygen failed:\n{result.stdout}")



# --- Optional helpers for "buildable" output dirs ---------------------------

def write_makefile(out_dir: Path, elf_name: str = "app.elf") -> Path:
    """
    Generate a very simple Makefile in out_dir that:
      - builds all .c files in that directory into a single ELF,
      - uses the first .ld file as the linker script if present.

    This is toolchain-agnostic; adjust CC/CFLAGS/LDFLAGS as needed for CCS
    or arm-none-eabi-gcc.
    """
    out_dir = Path(out_dir).resolve()

    c_files = sorted(p.name for p in out_dir.glob("*.c"))
    ld_files = sorted(out_dir.glob("*.ld"))

    make_lines: List[str] = []
    make_lines.append("CC ?= arm-none-eabi-gcc")
    make_lines.append("CFLAGS ?= -O2 -g -std=c11")
    make_lines.append("LDFLAGS ?= ")
    make_lines.append("")

    if ld_files:
        ld_script_name = ld_files[0].name
        make_lines.append(f"LDSCRIPT := {ld_script_name}")
        make_lines.append("LDFLAGS += -T$(LDSCRIPT)")
        make_lines.append("")

    if c_files:
        make_lines.append("SRC := " + " ".join(c_files))
    else:
        make_lines.append("SRC := ")
    make_lines.append(f"TARGET := {elf_name}")
    make_lines.append("")
    make_lines.append("all: $(TARGET)")
    make_lines.append("$(TARGET): $(SRC)")
    make_lines.append("\t$(CC) $(CFLAGS) $(SRC) $(LDFLAGS) -o $(TARGET)")
    make_lines.append("")
    make_lines.append("clean:")
    make_lines.append("\trm -f $(TARGET) *.o")
    make_lines.append("")

    makefile_path = out_dir / "Makefile"
    makefile_path.write_text("\n".join(make_lines), encoding="utf-8")
    print("[ok] Wrote", makefile_path.relative_to(out_dir))
    return makefile_path


def write_manifest(out_dir: Path, written_files: List[Path]) -> Path:
    """
    Write a simple JSON manifest summarizing generated files in out_dir.

    The manifest is for your own tooling/scripts; CCS does NOT auto-consume it.
    """
    out_dir = Path(out_dir).resolve()
    rels = []

    for p in written_files:
        try:
            rel = p.relative_to(out_dir)
        except ValueError:
            # Skip anything outside out_dir (shouldn't happen if used correctly)
            continue
        rels.append(str(rel))

    manifest = {
        "sources": [f for f in rels if f.endswith(".c")],
        "headers": [f for f in rels if f.endswith(".h")],
        "linker": [f for f in rels if f.endswith(".ld")],
        "assembly": [f for f in rels if f.endswith(".s") or f.endswith(".S")],
        "other": [
            f
            for f in rels
            if not (
                f.endswith(".c")
                or f.endswith(".h")
                or f.endswith(".ld")
                or f.endswith(".s")
                or f.endswith(".S")
            )
        ],
    }

    manifest_path = out_dir / "bsp_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("[ok] Wrote", manifest_path.relative_to(out_dir))
    return manifest_path
