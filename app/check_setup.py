#!/usr/bin/env python3
"""
check_setup.py

Verify that the environment is correctly set up for PDF extraction.
Checks dependencies, AWS credentials, file paths, etc.
"""

import sys
from pathlib import Path


def check_dependencies():
    """Check if all required Python packages are installed."""
    print("Checking Python dependencies...")
    required = {
        'boto3': 'AWS SDK for Python',
        'yaml': 'YAML parser (PyYAML)',
        'fitz': 'PDF processing (PyMuPDF)',
        'jsonschema': 'JSON Schema validator (optional but recommended)',
    }

    missing = []
    for package, description in required.items():
        try:
            __import__(package)
            print(f"  ✓ {package:15s} - {description}")
        except ImportError:
            print(f"  ✗ {package:15s} - {description} (MISSING)")
            missing.append(package)

    if missing:
        print("\nMissing packages. Install with:")
        if 'yaml' in missing:
            print("  pip install PyYAML")
            missing.remove('yaml')
        if 'fitz' in missing:
            print("  pip install pymupdf")
            missing.remove('fitz')
        if missing:
            print(f"  pip install {' '.join(missing)}")
        return False

    return True


def check_aws_credentials():
    """Check if AWS credentials are configured."""
    print("\nChecking AWS credentials...")
    try:
        import os
        import boto3
        from botocore.exceptions import NoCredentialsError, ClientError

        # Check for custom bearer token in environment
        bearer_token = os.environ.get('AWS_BEARER_TOKEN_BEDROCK')
        access_key = os.environ.get('AWS_ACCESS_KEY_ID')
        secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        region = os.environ.get('AWS_REGION', 'us-east-2')

        # Create boto3 client with authentication
        if bearer_token:
            # Use bearer token as session token with explicit credentials
            session = boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                aws_session_token=bearer_token,
                region_name=region,
            )
            client = session.client('bedrock-runtime')
            print("  ✓ AWS credentials configured (using AWS_BEARER_TOKEN_BEDROCK)")
        elif access_key and secret_key:
            # Use explicit credentials without session token
            client = boto3.client(
                'bedrock-runtime',
                region_name=region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            )
            print("  ✓ AWS credentials configured (using environment variables)")
        else:
            # Fall back to default credential chain
            client = boto3.client('bedrock-runtime', region_name=region)
            print("  ✓ AWS credentials configured (using default credential chain)")

        print(f"  ✓ Region: {region}")
        return True

    except NoCredentialsError:
        print("  ✗ No AWS credentials found")
        print("\n  Configure credentials with:")
        print("    Option 1: Set environment variables:")
        print("      export AWS_ACCESS_KEY_ID=<your_key>")
        print("      export AWS_SECRET_ACCESS_KEY=<your_secret>")
        print("      export AWS_BEARER_TOKEN_BEDROCK=<your_token>  # Optional")
        print("    Option 2: Use AWS CLI:")
        print("      aws configure")
        return False

    except Exception as e:
        print(f"  ⚠ Warning: Could not verify AWS credentials: {e}")
        print("  Credentials may be configured but not accessible")
        return True  # Don't fail on this


def check_paths():
    """Check if required directories and files exist."""
    print("\nChecking file paths...")

    script_dir = Path(__file__).parent
    checks = {
        "PDF directory": script_dir / "modules" / "pdfs" / "TRM_split",
        "Schema file": script_dir / "yaml_schemas" / "regs.schema.yaml",
    }

    all_exist = True
    for name, path in checks.items():
        if path.exists():
            if path.is_dir():
                # Count files
                file_count = len(list(path.glob("*.pdf"))) if "PDF" in name else len(list(path.iterdir()))
                print(f"  ✓ {name:20s} - {path} ({file_count} files)")
            else:
                print(f"  ✓ {name:20s} - {path}")
        else:
            print(f"  ✗ {name:20s} - {path} (NOT FOUND)")
            all_exist = False

    return all_exist


def check_module_imports():
    """Check if custom modules can be imported."""
    print("\nChecking custom modules...")

    modules = [
        'modules.register_extraction_prompt',
        'modules.pdf_text_extractor',
        'modules.yaml_validator',
        'modules.prompt',
    ]

    all_ok = True
    for module_name in modules:
        try:
            __import__(module_name)
            short_name = module_name.split('.')[-1]
            print(f"  ✓ {short_name}")
        except ImportError as e:
            print(f"  ✗ {module_name} - {e}")
            all_ok = False

    return all_ok


def test_pdf_extraction():
    """Test PDF extraction on a sample file."""
    print("\nTesting PDF extraction...")

    script_dir = Path(__file__).parent
    pdf_dir = script_dir / "modules" / "pdfs" / "TRM_split"

    # Find first PDF that isn't an intro/preface
    from modules.pdf_text_extractor import should_skip_pdf

    test_pdf = None
    for pdf_file in pdf_dir.glob("*.pdf"):
        if not should_skip_pdf(pdf_file.name):
            test_pdf = pdf_file
            break

    if test_pdf is None:
        print("  ⚠ No suitable test PDF found")
        return True

    try:
        from modules.pdf_text_extractor import extract_text_from_pdf, extract_peripheral_name_from_filename

        # Extract text from first page only (fast test)
        text = extract_text_from_pdf(test_pdf, max_pages=1)
        peripheral_abbrev, peripheral_full = extract_peripheral_name_from_filename(test_pdf.name)

        print(f"  ✓ PDF extraction working")
        print(f"    Test file: {test_pdf.name}")
        print(f"    Peripheral: {peripheral_abbrev}")
        print(f"    Extracted: {len(text)} chars from page 1")
        return True

    except Exception as e:
        print(f"  ✗ PDF extraction failed: {e}")
        return False


def main():
    """Run all checks."""
    print("=" * 80)
    print("PDF to YAML Extractor - Setup Check")
    print("=" * 80)

    checks = [
        ("Dependencies", check_dependencies),
        ("AWS Credentials", check_aws_credentials),
        ("File Paths", check_paths),
        ("Module Imports", check_module_imports),
        ("PDF Extraction", test_pdf_extraction),
    ]

    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"\n  Error during {name} check: {e}")
            results[name] = False

    # Print summary
    print("\n" + "=" * 80)
    print("SETUP CHECK SUMMARY")
    print("=" * 80)

    all_passed = True
    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status:8s} - {name}")
        if not passed:
            all_passed = False

    print("=" * 80)

    if all_passed:
        print("\n✓ All checks passed! You're ready to run the extractor.")
        print("\nNext steps:")
        print("  1. Test single PDF extraction:")
        print("     python extract_single_pdf.py \"modules/pdfs/TRM_split/<your_pdf>.pdf\"")
        print()
        print("  2. Run full extraction:")
        print("     python pdf_to_yaml_extractor.py")
        sys.exit(0)
    else:
        print("\n✗ Some checks failed. Please fix the issues above before running the extractor.")
        sys.exit(1)


if __name__ == "__main__":
    main()
