#!/usr/bin/env python3
"""
Test script to validate Doxygen documentation generation.
"""
from pathlib import Path
import sys

def test_doxygen_output(docs_dir: Path) -> tuple[bool, list[str]]:
    """
    Validate Doxygen documentation output.

    Returns:
        Tuple of (success: bool, issues: list[str])
    """
    issues = []
    html_dir = docs_dir / "html"

    # Test 1: HTML directory exists
    if not html_dir.exists():
        issues.append("HTML output directory not found")
        return False, issues

    # Test 2: index.html exists
    index_file = html_dir / "index.html"
    if not index_file.exists():
        issues.append("index.html not found")
        return False, issues

    # Test 3: Sufficient HTML files generated
    html_files = list(html_dir.glob("*.html"))
    if len(html_files) < 20:
        issues.append(f"Only {len(html_files)} HTML files generated (expected 50+)")

    # Test 4: Key module pages exist
    expected_modules = ["gio", "sci", "lin", "pcr", "iomm", "vim", "pll"]
    for module in expected_modules:
        module_files = list(html_dir.glob(f"*{module}*.html"))
        if not module_files:
            issues.append(f"No documentation found for {module} module")

    # Test 5: Source browser files exist
    source_files = list(html_dir.glob("*_source.html"))
    if len(source_files) < 10:
        issues.append(f"Only {len(source_files)} source browser files (expected 20+)")

    # Test 6: Navigation files exist
    nav_files = ["navtreedata.js", "navtreeindex0.js"]
    for nav_file in nav_files:
        if not (html_dir / nav_file).exists():
            issues.append(f"Navigation file {nav_file} not found")

    # Test 7: Search index exists
    search_dir = html_dir / "search"
    if not search_dir.exists():
        issues.append("Search directory not found")
    else:
        search_files = list(search_dir.glob("*.js"))
        if len(search_files) < 5:
            issues.append(f"Only {len(search_files)} search files (expected 10+)")

    success = len(issues) == 0
    return success, issues


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_doxygen.py <output_directory>")
        sys.exit(1)

    output_dir = Path(sys.argv[1])
    docs_dir = output_dir / "docs"

    print(f"Testing Doxygen output in: {docs_dir}")
    success, issues = test_doxygen_output(docs_dir)

    if success:
        print("[PASS] All tests passed!")
        print(f"   Documentation appears complete and comprehensive.")

        # Print statistics
        html_dir = docs_dir / "html"
        html_files = list(html_dir.glob("*.html"))
        source_files = list(html_dir.glob("*_source.html"))

        print(f"\nStatistics:")
        print(f"   Total HTML files: {len(html_files)}")
        print(f"   Source browser pages: {len(source_files)}")

        sys.exit(0)
    else:
        print("[FAIL] Documentation validation failed!")
        print("\nIssues found:")
        for issue in issues:
            print(f"   - {issue}")
        sys.exit(1)
