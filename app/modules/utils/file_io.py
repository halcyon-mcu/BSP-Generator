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
GENERATED_TEXT_EXTENSIONS = {".c", ".h", ".s", ".S", ".cmd", ".ld"}
_METADATA_MARKER = "BSP-GEN-META:"
_METADATA_SEMICOLON_COMMENT_EXTENSIONS = {".s", ".S"}


def _now_tag() -> str:
    """Return a compact timestamp tag for directory / artifact naming."""
    return datetime.now().strftime("%Y%m%dT%H%M%S")


def _find_output_folder_name(file_path: Path | str) -> str:
    path = Path(file_path)
    try:
        path = path.resolve()
    except OSError:
        pass

    for candidate in [path.name, *[p.name for p in path.parents]]:
        if candidate.startswith("output_") and len(candidate) > len("output_"):
            return candidate
    return "output_unknown"


def _build_generation_metadata_line(file_path: Path | str) -> str:
    path = Path(file_path)
    output_folder = _find_output_folder_name(path)
    output_tag = output_folder[len("output_"):] if output_folder.startswith("output_") else "unknown"
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")

    if path.suffix in _METADATA_SEMICOLON_COMMENT_EXTENSIONS:
        prefix = ";"
    else:
        prefix = "/*"

    if prefix == ";":
        return (
            f"; {_METADATA_MARKER} created_at={created_at}; "
            f"output_folder={output_folder}; output_tag={output_tag}"
        )

    return (
        f"/* {_METADATA_MARKER} created_at={created_at}; "
        f"output_folder={output_folder}; output_tag={output_tag} */"
    )


def _prepend_generation_metadata(content: str, file_path: Path | str) -> str:
    path = Path(file_path)
    if path.suffix not in GENERATED_TEXT_EXTENSIONS:
        return content

    head_lines = "\n".join(content.splitlines()[:5])
    if _METADATA_MARKER in head_lines:
        return content

    metadata_line = _build_generation_metadata_line(path)
    if not content:
        return metadata_line
    return f"{metadata_line}\n{content}"


def _safe_relpath(s: str) -> str:
    """
    Normalize a model-provided path:
    - forbid absolute paths
    - collapse backslashes to forward slashes
    - forbid parent directory traversal ('..')
    - strip leading './'
    """
    p = str(s).strip()

    # Normalize slashes
    p = p.replace("\\", "/")

    # Remove leading './'
    if p.startswith("./"):
        p = p[2:]

    # Forbid absolute or drive-qualified paths
    if os.path.isabs(p):
        raise ValueError(f"Refusing absolute path from model: {s!r}")

    # Forbid parent traversal
    parts = PurePosixPath(p).parts
    if any(seg == ".." for seg in parts):
        raise ValueError(f"Refusing path with '..' from model: {s!r}")

    # You can optionally force a flat layout by only taking the final segment:
    # p = parts[-1] if parts else p

    return p


def normalize_generated_text(content: str, file_path: Path | str) -> str:
    """
    Normalize generated source/script text for toolchain compatibility.

    For generated code/script files, enforce exactly one trailing newline to
    avoid compiler/IDE warnings for missing EOF newline.
    """
    path = Path(file_path)
    if path.suffix in GENERATED_TEXT_EXTENSIONS:
        normalized = content.rstrip("\n")
        normalized = _prepend_generation_metadata(normalized, path)
        return normalized.rstrip("\n") + "\n"
    return content


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
        target.write_text(normalize_generated_text(content, target), encoding="utf-8")
        written.append(target)

        # Print a friendly relative path (robust across platforms)
        try:
            print("[ok] Wrote", target.relative_to(out_dir))
        except ValueError:
            print("[ok] Wrote", os.path.relpath(str(target), str(out_dir)))

    return (written, preamble)

from pathlib import Path


def _doxygen_file_id(filename: str) -> str:
    """
    Convert a filename to the default Doxygen file-page id pattern.
    Example: gio_driver.h -> gio__driver_8h
    """
    return filename.replace("_", "__").replace(".", "_8")


def _doxygen_html_page(filename: str) -> str:
    """Return the expected Doxygen HTML page name for a filename."""
    return f"{_doxygen_file_id(filename)}.html"


def write_doxygen_mainpage(out_root: Path, project_name: str = "RM46 BSP (Generated)") -> Path:
    """
    Write a curated main page so index.html has useful structure and navigation.
    """
    out_root = Path(out_root).resolve()
    include_dir = out_root / "include"
    source_dir = out_root / "source"

    header_files = sorted(p.name for p in include_dir.glob("*_driver.h")) if include_dir.exists() else []
    source_files = sorted(p.name for p in source_dir.glob("*_driver.c")) if source_dir.exists() else []

    module_names = sorted(
        {
            name.replace("_driver.h", "").replace("_driver.c", "").upper()
            for name in (header_files + source_files)
            if "_driver." in name
        }
    )

    module_lines: List[str] = []
    if header_files:
        for filename in header_files:
            module_lines.append(f" * - <a href=\"{_doxygen_html_page(filename)}\">{filename}</a>")
    else:
        module_lines.append(" * - Driver headers not found in include/")

    known_pages = []
    for candidate in ("main.c", "system.h", "board_capabilities.h", "app_intent.h"):
        if (out_root / candidate).exists() or (include_dir / candidate).exists() or (source_dir / candidate).exists():
            known_pages.append(candidate)

    key_file_lines: List[str] = []
    if known_pages:
        for filename in known_pages:
            key_file_lines.append(f" * - <a href=\"{_doxygen_html_page(filename)}\">{filename}</a>")
    else:
        key_file_lines.append(" * - <a href=\"files.html\">Browse all files</a>")

    module_summary = ", ".join(module_names) if module_names else "none detected"
    content = "\n".join(
        [
            "/**",
            f" * @mainpage {project_name} Documentation",
            " *",
            " * @section overview Overview",
            " * Auto-generated Board Support Package documentation for the latest run output.",
            f" * Detected driver modules: {module_summary}.",
            " *",
            " * @section quicklinks Quick Links",
            " * - <a href=\"files.html\">Driver Documentation Index (Files)</a>",
            " * - <a href=\"globals_func.html\">Global Function Index</a>",
            " * - <a href=\"globals_defs.html\">Macro Definitions Index</a>",
            " *",
            " * @section bringup Bring-up Sequence",
            " * 1. Call @ref system__init \"system_init()\" during startup.",
            " * 2. Initialize board/peripheral drivers in dependency order.",
            " * 3. Enter the main loop and run application intent hooks if present.",
            " *",
            " * @section modules Generated Driver Modules",
            *module_lines,
            " *",
            " * @section keyfiles Key Files",
            *key_file_lines,
            " *",
            " * @section nav Navigation Tips",
            " * - Use the Files tab for per-file API and macros.",
            " * - Use Globals for function/macro/type indexes.",
            " * - Use the Search box to jump directly to symbols.",
            " */",
            "",
        ]
    )

    path = out_root / "doxygen_mainpage.dox"
    path.write_text(content, encoding="utf-8")
    return path

def write_doxyfile(out_root: Path, project_name: str = "RM46 BSP (Generated)") -> Path:
    doxy = f"""\
            # Auto-generated by GA BSP tool
            PROJECT_NAME           = "{project_name}"
            PROJECT_BRIEF          = "Board Support Package for RM46 Microcontroller"
            OUTPUT_DIRECTORY       = docs

            # Input files - scan recursively from root
            INPUT                  = .
            FILE_PATTERNS          = *.h *.c *.dox
            RECURSIVE              = YES

            # Exclude build artifacts and docs from recursive scan
            EXCLUDE_PATTERNS       = */docs/* */_artifacts/* */.git/*

            # Documentation extraction settings
            EXTRACT_ALL            = YES
            EXTRACT_STATIC         = YES
            EXTRACT_PRIVATE        = NO
            HIDE_UNDOC_MEMBERS     = NO
            JAVADOC_AUTOBRIEF      = YES
            MARKDOWN_SUPPORT       = YES

            # Output settings
            GENERATE_HTML          = YES
            GENERATE_LATEX         = NO
            GENERATE_TREEVIEW      = YES
            OPTIMIZE_OUTPUT_FOR_C  = YES
            FULL_PATH_NAMES        = NO
            STRIP_FROM_PATH        = .
            ALPHABETICAL_INDEX     = YES
            SORT_MEMBER_DOCS       = YES
            SORT_BRIEF_DOCS        = YES

            # Source browsing
            SOURCE_BROWSER         = YES
            INLINE_SOURCES         = NO
            STRIP_CODE_COMMENTS    = NO
            REFERENCED_BY_RELATION = YES
            REFERENCES_RELATION    = YES

            # Diagrams (requires graphviz - disable by default)
            HAVE_DOT               = NO
            CALL_GRAPH             = NO
            CALLER_GRAPH           = NO

            # HTML styling
            HTML_COLORSTYLE_HUE    = 220
            HTML_COLORSTYLE_SAT    = 100
            HTML_COLORSTYLE_GAMMA  = 80
            HTML_TIMESTAMP         = YES

            # Warning settings
            QUIET                  = NO
            WARNINGS               = YES
            WARN_IF_UNDOCUMENTED   = YES
            WARN_IF_DOC_ERROR      = YES
            WARN_NO_PARAMDOC       = NO
            """
    (out_root / "Doxyfile").write_text(doxy, encoding="utf-8")
    return Path(out_root / "Doxyfile")

import subprocess

def run_doxygen(bsp_out_root: Path, doxy_path: Path) -> None:
    """
    Run Doxygen to generate documentation.

    Args:
        bsp_out_root: Root directory of BSP output (where doxygen will run)
        doxy_path: Path to the Doxyfile

    Raises:
        FileNotFoundError: If Doxyfile doesn't exist
        RuntimeError: If no source files found or doxygen fails
    """
    out_root = Path(bsp_out_root).resolve()
    doxyfile = Path(doxy_path).resolve()

    # Validate Doxyfile exists
    if not doxyfile.exists():
        raise FileNotFoundError(f"Doxyfile not found at {doxyfile}")

    # Pre-flight check: Verify there are source files to document
    source_files = list(out_root.glob("**/*.c")) + list(out_root.glob("**/*.h"))
    # Filter out docs and artifacts directories
    source_files = [
        f for f in source_files
        if not any(part in f.parts for part in ['docs', '_artifacts'])
    ]

    if not source_files:
        raise RuntimeError(
            f"No source files (*.c, *.h) found in {out_root} for documentation. "
            f"Doxygen would produce empty output."
        )

    # Ensure there is a curated main page so index.html is not effectively empty.
    write_doxygen_mainpage(out_root)

    print(f"[info] Found {len(source_files)} source files to document")

    # Run doxygen from the BSP root directory
    result = subprocess.run(
        ["doxygen", str(doxyfile)],
        cwd=out_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Doxygen failed (exit code {result.returncode}):\n{result.stdout}")

    # Check for warnings in output
    if "warning:" in result.stdout.lower():
        print("[warn] Doxygen completed with warnings. Check output for details.")


def evaluate_doxygen_output(docs_dir: Path) -> dict:
    """
    Validate Doxygen documentation output quality and return a structured report.
    This mirrors the project test expectations but is safe to run at runtime.
    """
    docs_dir = Path(docs_dir)
    html_dir = docs_dir / "html"
    issues: list[str] = []
    checks: list[dict] = []

    def _check(name: str, passed: bool, ok_detail: str = "", fail_detail: str = "") -> None:
        detail = ok_detail if passed else fail_detail
        checks.append({"name": name, "passed": bool(passed), "detail": detail})
        if not passed and detail:
            issues.append(detail)

    if not html_dir.exists():
        _check("html_dir_exists", False, "", "HTML output directory not found")
        return {
            "passes": False,
            "issues": issues,
            "checks": checks,
            "stats": {
                "html_files": 0,
                "source_pages": 0,
                "search_files": 0,
                "group_pages": 0,
            },
        }
    _check("html_dir_exists", True, "HTML output directory found", "HTML output directory not found")

    index_file = html_dir / "index.html"
    _check("index_exists", index_file.exists(), "index.html found", "index.html not found")
    index_text = index_file.read_text(encoding="utf-8", errors="ignore") if index_file.exists() else ""
    has_structured_main = any(
        marker in index_text
        for marker in ("Generated Driver Modules", "Bring-up Sequence", "<h1", "<h2")
    )
    _check(
        "index_structured_content",
        has_structured_main,
        "index.html contains structured main-page content",
        "index.html appears minimal; add curated main-page sections",
    )

    html_files = list(html_dir.glob("*.html"))
    source_files = list(html_dir.glob("*_source.html"))
    group_files = list(html_dir.glob("group__*.html"))
    search_dir = html_dir / "search"
    search_files = list(search_dir.glob("*.js")) if search_dir.exists() else []
    nav_files = ["navtreedata.js", "navtreeindex0.js"]

    _check(
        "html_files_count",
        len(html_files) >= 20,
        f"Generated {len(html_files)} HTML files",
        f"Only {len(html_files)} HTML files generated (expected >=20)",
    )
    _check(
        "source_files_count",
        len(source_files) >= 10,
        f"Generated {len(source_files)} source browser files",
        f"Only {len(source_files)} source browser files (expected >=10)",
    )
    _check(
        "group_pages_present",
        len(group_files) >= 2,
        f"Found {len(group_files)} Doxygen group pages",
        f"Only {len(group_files)} group pages found; module/group structure may be weak",
    )
    _check(
        "search_dir_exists",
        search_dir.exists(),
        "Search directory found",
        "Search directory not found",
    )
    if search_dir.exists():
        _check(
            "search_files_count",
            len(search_files) >= 5,
            f"Generated {len(search_files)} search files",
            f"Only {len(search_files)} search files (expected >=5)",
        )

    for nav_file in nav_files:
        _check(
            f"nav_{nav_file}",
            (html_dir / nav_file).exists(),
            f"Navigation file {nav_file} found",
            f"Navigation file {nav_file} not found",
        )

    expected_modules = ["gio", "sci", "lin", "pcr", "iomm", "vim", "pll"]
    for module in expected_modules:
        module_files = list(html_dir.glob(f"*{module}*.html"))
        _check(
            f"module_{module}",
            len(module_files) > 0,
            f"Documentation found for {module} module",
            f"No documentation found for {module} module",
        )

    return {
        "passes": len(issues) == 0,
        "issues": issues,
        "checks": checks,
        "stats": {
            "html_files": len(html_files),
            "source_pages": len(source_files),
            "search_files": len(search_files),
            "group_pages": len(group_files),
            "index_exists": index_file.exists(),
            "docs_dir": str(docs_dir),
        },
    }



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


def write_manifest(
    out_dir: Path,
    written_files: List[Path],
    filename: str = "generated_files_manifest.json",
) -> Path:
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

    manifest_path = out_dir / filename
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("[ok] Wrote", manifest_path.relative_to(out_dir))
    return manifest_path
