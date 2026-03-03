from pathlib import Path

from modules.utils.file_io import evaluate_doxygen_output, write_doxygen_mainpage


def _touch(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_evaluate_doxygen_output_fails_when_html_dir_missing(tmp_path: Path):
    report = evaluate_doxygen_output(tmp_path / "docs")
    assert report["passes"] is False
    assert any("HTML output directory not found" in issue for issue in report["issues"])


def test_evaluate_doxygen_output_passes_on_minimum_expected_structure(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    html_dir = docs_dir / "html"
    search_dir = html_dir / "search"
    search_dir.mkdir(parents=True, exist_ok=True)

    module_names = ["gio", "sci", "lin", "pcr", "iomm", "vim", "pll"]
    filler_count = 20 - len(module_names)

    _touch(html_dir / "index.html", "<html><body><h1>Generated Driver Modules</h1></body></html>")
    _touch(html_dir / "navtreedata.js", "var navTreeData = [];")
    _touch(html_dir / "navtreeindex0.js", "var navTreeIndex0 = [];")
    _touch(html_dir / "group__core.html", "<html></html>")
    _touch(html_dir / "group__peripherals.html", "<html></html>")

    for idx in range(filler_count):
        _touch(html_dir / f"page_{idx}.html", "<html></html>")
    for module in module_names:
        _touch(html_dir / f"{module}_driver.html", "<html></html>")

    for idx in range(10):
        _touch(html_dir / f"source_{idx}_source.html", "<html></html>")
    for idx in range(5):
        _touch(search_dir / f"searchdata_{idx}.js", "var x = 1;")

    report = evaluate_doxygen_output(docs_dir)
    assert report["passes"] is True
    assert report["stats"]["index_exists"] is True
    assert report["stats"]["html_files"] >= 20
    assert report["stats"]["source_pages"] >= 10
    assert report["stats"]["search_files"] >= 5


def test_evaluate_doxygen_output_reports_missing_module_docs(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    html_dir = docs_dir / "html"
    search_dir = html_dir / "search"
    search_dir.mkdir(parents=True, exist_ok=True)

    _touch(html_dir / "index.html", "<html><body><h1>Generated Driver Modules</h1></body></html>")
    _touch(html_dir / "navtreedata.js", "var navTreeData = [];")
    _touch(html_dir / "navtreeindex0.js", "var navTreeIndex0 = [];")
    _touch(html_dir / "group__core.html", "<html></html>")
    _touch(html_dir / "group__peripherals.html", "<html></html>")
    for idx in range(25):
        _touch(html_dir / f"page_{idx}.html", "<html></html>")
    for idx in range(10):
        _touch(html_dir / f"src_{idx}_source.html", "<html></html>")
    for idx in range(5):
        _touch(search_dir / f"s_{idx}.js", "var x = 1;")

    report = evaluate_doxygen_output(docs_dir)
    assert report["passes"] is False
    assert any("No documentation found for gio module" in issue for issue in report["issues"])


def test_write_doxygen_mainpage_includes_driver_doc_links(tmp_path: Path):
    out_root = tmp_path / "out"
    include_dir = out_root / "include"
    source_dir = out_root / "source"
    include_dir.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)
    _touch(include_dir / "gio_driver.h", "/* h */")
    _touch(source_dir / "gio_driver.c", "/* c */")
    _touch(out_root / "main.c", "/* main */")

    mainpage_path = write_doxygen_mainpage(out_root)
    text = mainpage_path.read_text(encoding="utf-8")

    assert '<a href="files.html">Driver Documentation Index (Files)</a>' in text
    assert '<a href="gio__driver_8h.html">gio_driver.h</a>' in text
    assert '<a href="main_8c.html">main.c</a>' in text
