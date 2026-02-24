#!/usr/bin/env python3
"""
Simple validation test runner for generated BSP files.

This script:
1. Finds the latest BSP output directory
2. Lists all generated C files
3. Performs basic validation checks
4. Generates a validation report
"""

import sys
import json
from pathlib import Path
from datetime import datetime

def find_latest_output():
    """Find the latest output_* directory."""
    bsp_gen_dir = Path(__file__).parent / "bsp_gen"
    output_dirs = sorted(bsp_gen_dir.glob("output_*"))
    if not output_dirs:
        return None
    return output_dirs[-1]

def validate_bsp_output(output_dir):
    """Validate the BSP output structure and files."""
    
    print(f"\n{'='*70}")
    print(f"BSP Output Validation Report")
    print(f"{'='*70}")
    print(f"Output Directory: {output_dir}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    results = {
        "directory": str(output_dir),
        "timestamp": datetime.now().isoformat(),
        "files_found": {},
        "validation_checks": {},
        "summary": {}
    }
    
    # Expected files for a complete BSP
    expected_files = {
        "Startup Code": ["start.s", "entry.c"],
        "System Init": ["system.h", "system.c"],
        "Linker Script": ["linker.cmd"],
        "Peripheral Drivers": ["clock.h", "clock.c", "gio.h", "gio.c", "sci.h", "sci.c", "vim.h", "vim.c"],
        "Documentation": ["docs/html/index.html"],
        "Build Files": ["Makefile", "PROVENANCE.txt", "README.txt"],
    }
    
    print(f"\n{'File Validation':^70}")
    print(f"{'-'*70}")
    
    total_expected = 0
    total_found = 0
    
    for category, files in expected_files.items():
        category_results = {"expected": files, "found": [], "missing": []}
        
        for filename in files:
            file_path = output_dir / filename
            total_expected += 1
            
            if file_path.exists():
                size = file_path.stat().st_size
                category_results["found"].append(f"{filename} ({size:,} bytes)")
                total_found += 1
                status = "✓"
            else:
                category_results["missing"].append(filename)
                status = "✗"
            
            print(f"  [{status}] {filename:40} ", end="")
            if file_path.exists():
                print(f"({file_path.stat().st_size:,} bytes)")
            else:
                print("(missing)")
        
        results["files_found"][category] = category_results
    
    # Validation checks
    print(f"\n{'Validation Checks':^70}")
    print(f"{'-'*70}")
    
    checks = {}
    
    # Check 1: All core files exist
    core_files = ["start.s", "entry.c", "system.h", "system.c", "linker.cmd"]
    core_check = all((output_dir / f).exists() for f in core_files)
    checks["Core Files Present"] = core_check
    status = "✓" if core_check else "✗"
    print(f"  [{status}] Core startup files present")
    
    # Check 2: At least one peripheral driver
    periph_headers = list(output_dir.glob("*.h"))
    periph_check = len(periph_headers) > 0
    checks["Peripherals Generated"] = periph_check
    status = "✓" if periph_check else "✗"
    print(f"  [{status}] Peripheral drivers generated ({len(periph_headers)} headers found)")
    
    # Check 3: Documentation generated
    docs_index = output_dir / "docs/html/index.html"
    docs_check = docs_index.exists()
    checks["Documentation Generated"] = docs_check
    status = "✓" if docs_check else "✗"
    print(f"  [{status}] Doxygen documentation generated")
    
    # Check 4: Artifacts preserved
    artifacts_dir = output_dir / "_artifacts"
    artifacts_check = artifacts_dir.exists() and len(list(artifacts_dir.glob("*.txt"))) > 0
    checks["Artifacts Preserved"] = artifacts_check
    status = "✓" if artifacts_check else "✗"
    artifact_count = len(list(artifacts_dir.glob("*.txt"))) if artifacts_dir.exists() else 0
    print(f"  [{status}] Artifacts preserved ({artifact_count} files)")
    
    # Check 5: C files are not empty
    c_files = list(output_dir.glob("*.c"))
    c_check = all((output_dir / f).stat().st_size > 0 for f in c_files if f.is_file())
    checks["C Files Not Empty"] = c_check
    status = "✓" if c_check else "✗"
    print(f"  [{status}] C source files have content ({len(c_files)} files)")
    
    # Check 6: Header files have guards
    h_files = list(output_dir.glob("*.h"))
    guards_count = 0
    for hfile in h_files:
        content = hfile.read_text(encoding="utf-8", errors="ignore")
        if "#ifndef" in content and "#define" in content and "#endif" in content:
            guards_count += 1
    guards_check = guards_count == len(h_files) if h_files else False
    checks["Header Guards Present"] = guards_check
    status = "✓" if guards_check else "✗"
    print(f"  [{status}] Header files have include guards ({guards_count}/{len(h_files)})")
    
    results["validation_checks"] = checks
    
    # Summary
    print(f"\n{'Summary':^70}")
    print(f"{'-'*70}")
    print(f"  Files Found:     {total_found}/{total_expected}")
    print(f"  Checks Passed:   {sum(checks.values())}/{len(checks)}")
    print(f"  Status:          {'✓ PASS' if sum(checks.values()) == len(checks) else '⚠ PARTIAL'}")
    
    results["summary"] = {
        "files_found": total_found,
        "files_expected": total_expected,
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "overall_status": "PASS" if sum(checks.values()) == len(checks) else "PARTIAL"
    }
    
    print(f"\n{'Peripheral Files':^70}")
    print(f"{'-'*70}")
    
    peripherals = set()
    for hfile in h_files:
        base = hfile.stem
        if base not in ["system", "entry"]:
            peripherals.add(base)
            c_file = output_dir / f"{base}.c"
            status = "✓" if c_file.exists() else "✗"
            print(f"  [{status}] {base:20} ({hfile.stat().st_size:6,} bytes H, {c_file.stat().st_size if c_file.exists() else 0:6,} bytes C)")
    
    results["peripherals"] = sorted(peripherals)
    
    # Write report
    report_file = output_dir / "validation_report.json"
    report_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\n[ok] Validation report saved: {report_file}")
    
    return results

if __name__ == "__main__":
    output_dir = find_latest_output()
    
    if not output_dir:
        print("[error] No BSP output directory found in bsp_gen/")
        sys.exit(1)
    
    try:
        results = validate_bsp_output(output_dir)
        
        # Exit with success if all checks passed
        if results["summary"]["overall_status"] == "PASS":
            print(f"\n✓ All validation checks passed!")
            sys.exit(0)
        else:
            print(f"\n⚠ Some validation checks did not pass")
            sys.exit(1)
            
    except Exception as e:
        print(f"[error] Validation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
