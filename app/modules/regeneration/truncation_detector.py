"""
Truncation detection for LLM outputs.

Detects various types of truncation:
- Unclosed braces/comments
- File markers without content
- Incomplete function definitions
- Doxygen comments cut mid-block
"""

import re
from pathlib import Path
from typing import List, Optional


def detect_truncation(llm_output: str, written_files: List[Path]) -> Optional[str]:
    """
    Detect if LLM output was truncated.

    Args:
        llm_output: Raw text output from LLM
        written_files: List of files that were written from the output

    Returns:
        Reason string if truncated, None otherwise
    """
    # Check 1: Unclosed braces in output
    brace_count = llm_output.count('{') - llm_output.count('}')
    if brace_count > 0:
        return f"Unclosed braces in output ({brace_count} unmatched)"

    # Check 2: Output ends mid-comment
    if re.search(r'/\*[^*]*$', llm_output):
        return "Output ends mid-comment"

    # Check 3: File marker without content
    # Pattern: ===== FILE: foo.c ===== at end of output
    if re.search(r'===== (FILE|START):\s*\S+\s*=====\s*$', llm_output):
        return "File marker without content"

    # Check 4: Incomplete Doxygen comment
    # Pattern: /** ... with no closing */
    if re.search(r'/\*\*(?:[^*]|\*(?!/))*$', llm_output):
        return "Truncated Doxygen comment"

    # Check 5: Parse generated .c files for structural issues
    for file_path in written_files:
        if not file_path.exists():
            continue

        if file_path.suffix == '.c':
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')

                # Count braces in file
                if content.count('{') != content.count('}'):
                    return f"Unmatched braces in {file_path.name}"

                # Check if file ends properly
                # C files should end with closing brace or semicolon
                stripped = content.rstrip()
                if stripped and not re.search(r'[};]\s*$', stripped):
                    return f"File {file_path.name} doesn't end properly"

            except Exception as e:
                # If we can't read the file, consider it potentially truncated
                return f"Could not validate {file_path.name}: {e}"

    # No truncation detected
    return None


def detect_facts_mirror_todos(preamble: str) -> bool:
    """
    Check if FACTS MIRROR block contains TODO items.

    Args:
        preamble: The preamble text from LLM output

    Returns:
        True if TODOs found in FACTS MIRROR, False otherwise
    """
    if "FACTS MIRROR" not in preamble:
        return False

    # Extract FACTS MIRROR block
    facts_pattern = re.compile(
        r'===== FACTS MIRROR =====\s*(.*?)\s*===== END FACTS MIRROR =====',
        re.DOTALL
    )

    match = facts_pattern.search(preamble)
    if not match:
        return False

    facts_block = match.group(1)

    # Check for TODO: markers
    return "TODO:" in facts_block


def detect_simple_truncation(text: str) -> Optional[str]:
    """
    Simpler truncation detection that works on raw LLM output
    before file parsing. Use this for discovery/implementation passes.

    Args:
        text: Raw LLM output text

    Returns:
        Reason string if truncated, None otherwise
    """
    if not text or not text.strip():
        return "Empty output"

    # Check 1: Unclosed braces
    brace_count = text.count('{') - text.count('}')
    if brace_count > 5:  # Allow some tolerance
        return f"Unclosed braces in output ({brace_count} unmatched)"

    # Check 2: Output ends mid-comment
    if re.search(r'/\*[^*]*$', text):
        return "Output ends mid-comment"

    # Check 3: Incomplete JSON (for manifest generation)
    if text.strip().startswith('{') and not text.strip().endswith('}'):
        return "Incomplete JSON output"

    # Check 4: Code block without closing
    if '```' in text:
        code_blocks = text.count('```')
        if code_blocks % 2 != 0:
            return "Unclosed code block (markdown)"

    return None
