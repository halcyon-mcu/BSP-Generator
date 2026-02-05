#!/usr/bin/env python3
"""
pdf_to_yaml_extractor.py

Main script for concurrent extraction of register definitions from TRM PDFs.
Processes all peripheral PDFs in TRM_split folder and generates individual
regs.yaml files conforming to regs.schema.yaml.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import boto3
import yaml
from botocore.config import Config

# Import our custom modules
from ..registers.register_extraction_prompt import (
    build_register_extraction_system_prompt,
    build_register_extraction_user_prompt,
)
from .pdf_text_extractor import (
    extract_text_from_pdf,
    extract_peripheral_name_from_filename,
    should_skip_pdf,
    validate_pdf_for_register_extraction,
)
from ..yaml.yaml_validator import (
    load_schema,
    validate_yaml_against_schema,
)
from ..yaml.yaml_formatter import format_regs_yaml_manual
from ..registers.register_scanner import (
    scan_for_registers,
    format_scan_summary,
    validate_extraction,
)
from ..registers.register_discovery import (
    discover_registers,
    format_discovery_summary,
)
from ..generation.prompt import Model  # Reuse existing Model enum


# Configure boto3 client
config = Config(
    read_timeout=300,
    connect_timeout=10,
    retries={'max_attempts': 3}
)

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
    client = session.client(
        service_name="bedrock-runtime",
        config=config,
    )
    print(f"Using AWS_BEARER_TOKEN_BEDROCK for authentication (region: {region})")
elif access_key and secret_key:
    # Use explicit credentials without session token
    client = boto3.client(
        service_name="bedrock-runtime",
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=config,
    )
    print(f"Using AWS credentials from environment variables (region: {region})")
else:
    # Fall back to default credential chain (IAM role, ~/.aws/credentials, etc.)
    client = boto3.client(
        service_name="bedrock-runtime",
        region_name=region,
        config=config,
    )
    print(f"Using default AWS credential chain (region: {region})")


class ExtractionResult:
    """Result of extracting registers from a single PDF."""

    def __init__(
        self,
        pdf_name: str,
        peripheral_name: str,
        success: bool,
        yaml_content: Optional[str] = None,
        yaml_data: Optional[Dict[str, Any]] = None,
        validation_errors: Optional[List[str]] = None,
        error_message: Optional[str] = None,
    ):
        self.pdf_name = pdf_name
        self.peripheral_name = peripheral_name
        self.success = success
        self.yaml_content = yaml_content
        self.yaml_data = yaml_data
        self.validation_errors = validation_errors or []
        self.error_message = error_message


class ExtractionProgress:
    """Thread-safe progress tracker for concurrent extraction."""

    def __init__(self, total: int, verbose: bool = False):
        self.total = total
        self.completed = 0
        self.successful = 0
        self.failed = 0
        self.lock = asyncio.Lock()
        self.verbose = verbose
        self.current_files = {}  # Track which files are currently being processed

        # Token tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    async def increment(self, success: bool):
        async with self.lock:
            self.completed += 1
            if success:
                self.successful += 1
            else:
                self.failed += 1
            self._print_progress()

    async def add_tokens(self, input_tokens: int, output_tokens: int):
        """Track token usage from API calls."""
        async with self.lock:
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens

    async def get_stats(self) -> Tuple[int, int, int]:
        async with self.lock:
            return self.completed, self.successful, self.failed

    async def get_token_stats(self) -> Tuple[int, int]:
        """Get total token usage."""
        async with self.lock:
            return self.total_input_tokens, self.total_output_tokens

    async def set_current_file(self, peripheral: str, status: str):
        """Update current processing status for a peripheral."""
        async with self.lock:
            self.current_files[peripheral] = status

    async def remove_current_file(self, peripheral: str):
        """Remove peripheral from active processing list."""
        async with self.lock:
            self.current_files.pop(peripheral, None)

    def _print_progress(self):
        """Print progress bar."""
        if self.completed == 0:
            return

        # Calculate progress
        percent = (self.completed / self.total) * 100
        filled = int(percent / 2)  # 50 character bar
        bar = "█" * filled + "░" * (50 - filled)

        # Status line
        print(f"\r  Progress: [{bar}] {self.completed}/{self.total} ({percent:.0f}%) | ✓ {self.successful} ✗ {self.failed}", end="", flush=True)

        # Print newline when complete
        if self.completed == self.total:
            print()


# Global semaphore to limit concurrent API calls (respect rate limits)
_model_semaphore = None


async def invoke_model(
    model: Model,
    max_tokens: int,
    system_prompt: str,
    user_prompt: str,
) -> Tuple[str, int, int]:
    """
    Invoke the Bedrock model with concurrency limiting.

    Args:
        model: Model to use
        max_tokens: Maximum tokens for response
        system_prompt: System prompt
        user_prompt: User prompt

    Returns:
        Tuple of (response_text, input_tokens, output_tokens)

    Raises:
        Exception: If API call fails
    """
    global _model_semaphore
    if _model_semaphore is None:
        # Limit concurrent requests to respect API rate limits
        # Adjust this value based on your Bedrock quota:
        # - 2 = Safe, respects rate limits (default)
        # - 4 = Faster, may hit rate limits on large batches
        # - 8 = Very fast, requires high quota
        _model_semaphore = asyncio.Semaphore(4)  # Increased from 2 to 4

    async with _model_semaphore:
        body = {
            "max_tokens": max_tokens,
            "anthropic_version": "bedrock-2023-05-31",
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
        }

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.invoke_model(
                modelId=model.get_model_id(),
                body=json.dumps(body)
            )
        )

        # Parse response
        response_body = json.loads(response['body'].read())
        content = response_body.get('content', [])

        if not content:
            raise ValueError("Empty response from model")

        # Extract text from first content block
        text = content[0].get('text', '')

        # Extract token usage
        usage = response_body.get('usage', {})
        input_tokens = usage.get('input_tokens', 0)
        output_tokens = usage.get('output_tokens', 0)

        return text, input_tokens, output_tokens


def extract_yaml_from_response(response_text: str) -> Optional[str]:
    """
    Extract YAML content from model response.

    The model might wrap YAML in markdown code fences or include
    extra text. This function extracts just the YAML content.

    Args:
        response_text: Full response from model

    Returns:
        Extracted YAML string, or None if extraction fails
    """
    # Try to find YAML in markdown code fences
    yaml_fence_pattern = r'```(?:yaml)?\s*\n(.*?)\n```'
    match = re.search(yaml_fence_pattern, response_text, re.DOTALL)

    if match:
        return match.group(1).strip()

    # If no code fence, check if the entire response looks like YAML
    # (starts with a common YAML pattern)
    stripped = response_text.strip()
    if stripped.startswith('ir_schema_version:') or stripped.startswith('peripherals:'):
        return stripped

    # Try to find YAML by looking for the ir_schema_version key
    schema_pattern = r'(ir_schema_version:.*)'
    match = re.search(schema_pattern, response_text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Couldn't extract YAML
    return None


async def extract_registers_from_pdf(
    pdf_path: Path,
    output_dir: Path,
    schema_yaml_str: str,
    model: Model,
    progress: ExtractionProgress,
    max_retries: int = 2,
) -> ExtractionResult:
    """
    Extract register definitions from a single PDF with smart retry on validation errors.

    Args:
        pdf_path: Path to PDF file
        output_dir: Directory to save output YAML
        schema_yaml_str: regs.schema.yaml content as string
        model: Model to use for extraction
        progress: Progress tracker
        max_retries: Maximum retry attempts on validation errors

    Returns:
        ExtractionResult object
    """
    pdf_name = pdf_path.name
    peripheral_abbrev, peripheral_full = extract_peripheral_name_from_filename(pdf_name)
    verbose = progress.verbose

    try:
        # Extract text from PDF (only once)
        if verbose:
            print(f"  [{progress.completed + 1}/{progress.total}] {peripheral_abbrev}: Extracting text from {pdf_name}...")
        await progress.set_current_file(peripheral_abbrev, "Extracting text")
        pdf_text = extract_text_from_pdf(pdf_path)

        # Truncate if too long (Claude has token limits)
        # SYSTEM peripheral needs more space for multiple register blocks (SYS, SYS2, etc.)
        if peripheral_abbrev.upper() == 'SYSTEM':
            max_chars = 300000  # ~75k tokens - SYSTEM has many register blocks
        else:
            max_chars = 180000  # ~45k tokens for text content

        original_length = len(pdf_text)
        if len(pdf_text) > max_chars:
            if verbose:
                print(f"    {peripheral_abbrev}: Warning - PDF text is large ({len(pdf_text)} chars), truncating to {max_chars} chars")
            pdf_text = pdf_text[:max_chars] + "\n\n[... content truncated due to length ...]"

        # Use Claude to discover registers (more robust than regex)
        print(f"\n    {peripheral_abbrev}: Discovering registers with Claude...")
        discovery = await discover_registers(
            pdf_text=pdf_text,
            peripheral_name=peripheral_abbrev,
            invoke_model_func=invoke_model,
            model=model,
            progress=progress,
        )

        if 'error' in discovery:
            print(f"    {peripheral_abbrev}: Warning - Discovery had issues: {discovery['error']}")
        elif discovery['count'] > 0:
            print(f"    {peripheral_abbrev}: Discovered {discovery['count']} registers")
            if verbose or discovery['count'] < 10:
                print(f"      Registers: {', '.join(discovery['register_names'][:15])}")
                if discovery['count'] > 15:
                    print(f"      ... and {discovery['count'] - 15} more")

            # Check for expected register patterns for SYSTEM
            if peripheral_abbrev.upper() == 'SYSTEM':
                has_sys = any('SYS_' in name for name in discovery['register_names'])
                has_sys2 = any('SYS2' in name or 'CLK2' in name for name in discovery['register_names'])
                if not has_sys:
                    print(f"    {peripheral_abbrev}: ⚠ Warning - No SYS_ registers found in discovery")
                if not has_sys2:
                    print(f"    {peripheral_abbrev}: ⚠ Warning - No SYS2 block registers found in discovery")
                    print(f"    {peripheral_abbrev}: This may indicate the PDF was truncated or SYS2 is deeper in the document")
        else:
            print(f"    {peripheral_abbrev}: Warning - No registers found in discovery")

        schema = yaml.safe_load(schema_yaml_str)
        system_prompt = build_register_extraction_system_prompt()

        # Try extraction with retries on validation errors
        for attempt in range(max_retries + 1):
            is_retry = attempt > 0

            if is_retry:
                await progress.set_current_file(peripheral_abbrev, f"Retry {attempt}/{max_retries}")
                print(f"\n    {peripheral_abbrev}: Retry {attempt}/{max_retries} with validation feedback...")

            # Build user prompt (includes validation errors on retry and pre-scan results)
            base_prompt = build_register_extraction_user_prompt(
                pdf_text=pdf_text,
                peripheral_name=peripheral_abbrev,
                schema_yaml=schema_yaml_str,
            )

            # Add discovery results to help Claude
            if discovery['count'] > 0:
                discovery_hint = format_discovery_summary(discovery)
                base_prompt = discovery_hint + "\n" + base_prompt

            if is_retry and 'validation_errors' in locals():
                # Build retry prompt with validation error feedback
                error_summary = "\n".join(f"  - {error}" for error in validation_errors[:15])

                # Check if we're missing registers from discovery
                missing_regs = []
                if discovery['count'] > 0 and 'yaml_data' in locals():
                    discovered_names = set(discovery['register_names'])
                    extracted_names = set()
                    if yaml_data and 'peripherals' in yaml_data:
                        for periph_data in yaml_data['peripherals'].values():
                            if 'registers' in periph_data:
                                extracted_names = set(periph_data['registers'].keys())
                    missing_regs = list(discovered_names - extracted_names)

                missing_hint = ""
                if missing_regs:
                    missing_hint = f"""
CRITICAL: You are missing {len(missing_regs)} registers that were found in the PDF:
{', '.join(missing_regs[:20])}
{'... and more' if len(missing_regs) > 20 else ''}

You MUST include ALL {discovery['count']} registers from the discovery list above.
"""

                retry_prompt = f"""
VALIDATION ERRORS FROM PREVIOUS ATTEMPT:
{error_summary}
{'... and more errors' if len(validation_errors) > 15 else ''}
{missing_hint}
Please fix these validation errors and regenerate the YAML. Make sure to:
1. Ensure ALL required fields are present (ir_schema_version, peripherals, base_address, registers)
2. Use correct field names matching the schema exactly
3. Include 'reset' values for all fields (use "0x00000000" if unknown)
4. Ensure peripheral name matches '{peripheral_abbrev}' exactly
5. Use proper YAML syntax - all hex values must be quoted strings like "0xFFF7E500"
6. Include ALL {discovery['count']} registers from the discovery results
7. {'IMPORTANT: This is the SYSTEM module with multiple register blocks (SYS, SYS2, etc.). Include ALL of them.' if peripheral_abbrev.upper() == 'SYSTEM' else ''}

ORIGINAL REQUEST:
"""
                user_prompt = retry_prompt + base_prompt
            else:
                user_prompt = base_prompt

            # Call model - use more tokens for SYSTEM peripheral
            max_output_tokens = 24000 if peripheral_abbrev.upper() == 'SYSTEM' else 16000

            await progress.set_current_file(peripheral_abbrev, "Calling Claude API")
            response, input_tokens, output_tokens = await invoke_model(
                model=model,
                max_tokens=max_output_tokens,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )

            # Track token usage
            await progress.add_tokens(input_tokens, output_tokens)

            # Extract and parse YAML
            await progress.set_current_file(peripheral_abbrev, "Parsing response")
            yaml_content = extract_yaml_from_response(response)
            if yaml_content is None:
                if attempt == max_retries:
                    await progress.increment(False)
                    return ExtractionResult(
                        pdf_name=pdf_name,
                        peripheral_name=peripheral_abbrev,
                        success=False,
                        error_message="Failed to extract YAML from model response",
                    )
                continue

            try:
                yaml_data = yaml.safe_load(yaml_content)
            except yaml.YAMLError as e:
                if attempt == max_retries:
                    await progress.increment(False)
                    return ExtractionResult(
                        pdf_name=pdf_name,
                        peripheral_name=peripheral_abbrev,
                        success=False,
                        yaml_content=yaml_content,
                        error_message=f"Invalid YAML generated: {e}",
                    )
                continue

            # Validate against schema
            await progress.set_current_file(peripheral_abbrev, "Validating")
            is_valid, validation_errors = validate_yaml_against_schema(yaml_data, schema)

            if is_valid:
                # Success! Break retry loop
                if is_retry and verbose:
                    print(f"    {peripheral_abbrev}: ✓ Validation passed after retry!")

                # Validate against discovery results
                if discovery['count'] > 0:
                    disc_valid, disc_warnings = validate_extraction(discovery, yaml_data)
                    if not disc_valid:
                        print(f"\n    {peripheral_abbrev}: Discovery discrepancy warnings:")
                        for warning in disc_warnings[:5]:
                            print(f"      - {warning}")
                        if len(disc_warnings) > 5:
                            print(f"      ... and {len(disc_warnings) - 5} more warnings")

                break
            else:
                # Validation failed
                if attempt < max_retries:
                    if verbose:
                        print(f"    {peripheral_abbrev}: Validation failed ({len(validation_errors)} errors), retrying...")
                else:
                    # Final attempt failed
                    print(f"\n    {peripheral_abbrev}: ⚠ Validation has {len(validation_errors)} errors after {max_retries} retries")
                    if verbose:
                        for error in validation_errors[:3]:
                            print(f"      - {error}")
                        if len(validation_errors) > 3:
                            print(f"      ... and {len(validation_errors) - 3} more errors")

        # Format YAML with inline field style
        await progress.set_current_file(peripheral_abbrev, "Formatting")
        try:
            formatted_yaml = format_regs_yaml_manual(yaml_data)
            yaml_content = formatted_yaml
        except Exception as e:
            if verbose:
                print(f"    {peripheral_abbrev}: Warning - Formatting failed ({e}), using original YAML")

        # Write file immediately
        await progress.set_current_file(peripheral_abbrev, "Writing file")
        if is_valid:
            output_file = output_dir / f"{peripheral_abbrev.lower()}_regs.yaml"
        else:
            output_file = output_dir / f"{peripheral_abbrev.lower()}_regs.invalid.yaml"

        output_file.write_text(yaml_content, encoding='utf-8')

        await progress.remove_current_file(peripheral_abbrev)

        if is_valid:
            print(f"\n  ✓ {peripheral_abbrev}: {output_file.name}")
        else:
            print(f"\n  ⚠ {peripheral_abbrev}: {output_file.name} (validation errors)")

        await progress.increment(is_valid)

        return ExtractionResult(
            pdf_name=pdf_name,
            peripheral_name=peripheral_abbrev,
            success=is_valid,
            yaml_content=yaml_content,
            yaml_data=yaml_data,
            validation_errors=validation_errors if not is_valid else None,
        )

    except Exception as e:
        print(f"\n  ✗ {peripheral_abbrev}: Extraction failed - {e}")
        await progress.remove_current_file(peripheral_abbrev)
        await progress.increment(False)
        return ExtractionResult(
            pdf_name=pdf_name,
            peripheral_name=peripheral_abbrev,
            success=False,
            error_message=f"Extraction failed: {e}",
        )


async def process_all_pdfs(
    pdf_dir: Path,
    output_dir: Path,
    schema_path: Path,
    model: Model = Model.SONNET_4_5,
    skip_validation_check: bool = False,
    skip_existing: bool = True,
    verbose: bool = False,
) -> List[ExtractionResult]:
    """
    Process all PDFs in the TRM_split directory.

    Args:
        pdf_dir: Directory containing TRM PDFs
        output_dir: Directory to save generated YAML files
        schema_path: Path to regs.schema.yaml
        model: Model to use for extraction
        skip_validation_check: If True, skip pre-validation of PDFs
        skip_existing: If True, skip PDFs that already have generated output files
        verbose: If True, show detailed progress messages

    Returns:
        List of ExtractionResult objects
    """
    # Load schema
    schema_yaml_str = schema_path.read_text(encoding='utf-8')

    # Find all PDFs
    pdf_files = sorted(pdf_dir.glob("*.pdf"))

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Filter out non-peripheral PDFs and already-processed files
    peripheral_pdfs = []
    skipped_existing = []

    for pdf_file in pdf_files:
        # Check if should skip based on filename and content
        if should_skip_pdf(pdf_file.name, pdf_file):
            print(f"Skipping (non-peripheral): {pdf_file.name}")
            continue

        # Check if output file already exists
        if skip_existing:
            peripheral_abbrev, _ = extract_peripheral_name_from_filename(pdf_file.name)
            output_file = output_dir / f"{peripheral_abbrev.lower()}_regs.yaml"
            output_file_invalid = output_dir / f"{peripheral_abbrev.lower()}_regs.invalid.yaml"

            if output_file.exists() or output_file_invalid.exists():
                existing_file = output_file if output_file.exists() else output_file_invalid
                print(f"Skipping (already exists): {pdf_file.name} -> {existing_file.name}")
                skipped_existing.append(pdf_file.name)
                continue

        # Optional: Pre-validate that PDF contains register info
        if not skip_validation_check:
            is_valid, reason = validate_pdf_for_register_extraction(pdf_file)
            if not is_valid:
                print(f"Skipping (validation): {pdf_file.name}: {reason}")
                continue

        peripheral_pdfs.append(pdf_file)

    if not peripheral_pdfs:
        if skipped_existing:
            print(f"\n✓ All {len(skipped_existing)} PDFs already processed! No new files to extract.")
        else:
            print("\nNo peripheral PDFs found to process!")
        return []

    print(f"\nFound {len(peripheral_pdfs)} peripheral PDFs to process")
    if skipped_existing:
        print(f"Skipped {len(skipped_existing)} already-processed PDFs")
    print("=" * 80)

    # Initialize progress tracker
    progress = ExtractionProgress(total=len(peripheral_pdfs), verbose=verbose)

    # Process all PDFs concurrently
    start_time = time.time()

    tasks = [
        extract_registers_from_pdf(pdf_file, output_dir, schema_yaml_str, model, progress)
        for pdf_file in peripheral_pdfs
    ]

    results = await asyncio.gather(*tasks)

    elapsed = time.time() - start_time
    completed, successful, failed = await progress.get_stats()

    # Get token stats
    input_tokens, output_tokens = await progress.get_token_stats()
    total_tokens = input_tokens + output_tokens

    # Calculate cost based on model
    # Pricing (as of 2025): https://aws.amazon.com/bedrock/pricing/
    if model == Model.SONNET_4_5:
        # Claude Sonnet 4.5: $3 per MTok input, $15 per MTok output
        input_cost = (input_tokens / 1_000_000) * 3.0
        output_cost = (output_tokens / 1_000_000) * 15.0
    else:  # Haiku 4.5
        # Claude Haiku 4.5: $0.80 per MTok input, $4 per MTok output
        input_cost = (input_tokens / 1_000_000) * 0.80
        output_cost = (output_tokens / 1_000_000) * 4.0

    total_cost = input_cost + output_cost

    # Print summary
    print("\n" + "=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)
    print(f"Total PDFs processed: {completed}/{len(peripheral_pdfs)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    if skipped_existing:
        print(f"Already existed (skipped): {len(skipped_existing)}")
    print(f"Time elapsed: {elapsed:.1f}s ({elapsed/completed:.1f}s per PDF)" if completed > 0 else "Time elapsed: 0s")
    print()
    print("Token Usage:")
    print(f"  Input tokens:  {input_tokens:,} ({input_tokens/1000:.1f}K)")
    print(f"  Output tokens: {output_tokens:,} ({output_tokens/1000:.1f}K)")
    print(f"  Total tokens:  {total_tokens:,} ({total_tokens/1000:.1f}K)")
    print()
    print(f"Estimated Cost: ${total_cost:.2f}")
    print(f"  Input:  ${input_cost:.2f}")
    print(f"  Output: ${output_cost:.2f}")
    print(f"  Avg per PDF: ${total_cost/completed:.2f}" if completed > 0 else "")
    print("=" * 80)

    return results


def main():
    """Main entry point."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Extract register definitions from TRM PDFs to YAML files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use default directories
  python pdf_to_yaml_extractor.py

  # Specify custom input directory
  python pdf_to_yaml_extractor.py --input /path/to/pdfs

  # Specify both input and output
  python pdf_to_yaml_extractor.py --input ./pdfs --output ./output

  # Enable verbose logging
  python pdf_to_yaml_extractor.py --verbose

  # Force re-process all files
  python pdf_to_yaml_extractor.py --force
        """
    )

    script_dir = Path(__file__).parent

    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=script_dir / "modules" / "pdfs" / "TRM_split",
        help="Input directory containing PDF files (default: ./modules/pdfs/TRM_split)"
    )

    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=script_dir / "yaml_out" / "extracted_regs",
        help="Output directory for generated YAML files (default: ./yaml_out/extracted_regs)"
    )

    parser.add_argument(
        "--schema", "-s",
        type=Path,
        default=script_dir / "yaml_schemas" / "regs.schema.yaml",
        help="Path to regs.schema.yaml file (default: ./yaml_schemas/regs.schema.yaml)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging (show detailed progress for each stage)"
    )

    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force re-processing of all PDFs (ignore existing output files)"
    )

    parser.add_argument(
        "--model",
        choices=["sonnet4.5", "haiku4.5"],
        default="sonnet4.5",
        help="Claude model to use (default: sonnet4.5)"
    )

    args = parser.parse_args()

    # Convert paths to absolute
    pdf_dir = args.input.resolve()
    output_dir = args.output.resolve()
    schema_path = args.schema.resolve()

    # Select model
    model = Model.SONNET_4_5 if args.model == "sonnet4.5" else Model.HAIKU_4_5

    # Check paths
    if not pdf_dir.exists():
        print(f"Error: PDF directory not found: {pdf_dir}")
        print(f"Please create the directory or specify a different path with --input")
        sys.exit(1)

    if not schema_path.exists():
        print(f"Error: Schema file not found: {schema_path}")
        print(f"Please specify a valid schema path with --schema")
        sys.exit(1)

    print("=" * 80)
    print("TRM PDF to YAML Register Extractor")
    print("=" * 80)
    print(f"PDF directory: {pdf_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Schema: {schema_path}")
    print(f"Model: {model.value}")
    print(f"Verbose: {args.verbose}")
    print(f"Force re-process: {args.force}")
    print("=" * 80)

    # Run async processing
    results = asyncio.run(process_all_pdfs(
        pdf_dir=pdf_dir,
        output_dir=output_dir,
        schema_path=schema_path,
        model=model,
        skip_validation_check=True,  # Skip pre-validation - process all PDFs
        skip_existing=not args.force,  # Skip existing files unless --force is used
        verbose=args.verbose,
    ))

    # Exit with appropriate code
    failed_count = sum(1 for r in results if not r.success)
    sys.exit(0 if failed_count == 0 else 1)


if __name__ == "__main__":
    main()
