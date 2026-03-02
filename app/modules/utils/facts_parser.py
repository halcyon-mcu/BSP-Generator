#!/usr/bin/env python3
"""
facts_parser.py

Data structures and parsing utilities for FACTS MIRROR validation.

This module provides:
- Dataclasses for representing FACTS MIRROR entries and extracted constants
- Regex patterns for parsing FACTS MIRROR blocks and C code
- Parsing functions for extracting validation data
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Tuple


# ==============================================================================
# REGEX PATTERNS
# ==============================================================================

# Matches the entire FACTS MIRROR block
FACTS_MIRROR_BLOCK_RE = re.compile(
    r"===== FACTS MIRROR =====\s*(.*?)\s*===== END FACTS MIRROR =====",
    re.DOTALL
)

# Matches individual facts entries (supports TODO prefix)
# Examples:
#   GIO_BASE = 0xFFF7BC00 (from YAML)
#   TODO: UART_BAUD = unknown (register not documented)
FACTS_ENTRY_RE = re.compile(
    r"^(?:TODO:\s*)?(\w+)\s*=\s*([^\s()]+)\s*(?:\((.+?)\))?$",
    re.MULTILINE
)

# Matches #define statements in C code
# Example: #define GIO_BASE 0xFFF7BC00
DEFINE_RE = re.compile(
    r"^\s*#define\s+(\w+)\s+(.+?)(?://.*)?$",
    re.MULTILINE
)

# Matches hexadecimal values
HEX_VALUE_RE = re.compile(r"0x[0-9A-Fa-f]+")

# Matches decimal values
DEC_VALUE_RE = re.compile(r"\b\d+\b")

# Matches register access patterns in C code
# Example: *(volatile uint32_t*)(0xFFF7BC00 + 0x00)
REGISTER_ACCESS_RE = re.compile(
    r"\*\s*\(\s*volatile\s+uint32_t\s*\*\s*\)\s*\(([^)]+)\)",
    re.DOTALL
)

# Matches register struct member access
# Example: gioREG->GCR0
STRUCT_MEMBER_ACCESS_RE = re.compile(
    r"(\w+REG(?:\d+)?)\s*->\s*(\w+)",
    re.MULTILINE
)


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class FactsMirrorEntry:
    """
    Single entry from a FACTS MIRROR block.

    Represents a constant that should appear in generated code.
    """
    name: str                    # Constant name (e.g., "GIO_BASE")
    value: str                   # Value (e.g., "0xFFF7BC00")
    source: str                  # Source annotation (e.g., "from YAML")
    is_todo: bool = False        # True if marked as TODO
    todo_message: str = ""       # Error description if TODO
    is_verified: bool = False    # True if verified against code
    verification_note: str = ""  # Note about verification (e.g., "verified in gio.c")

    def __str__(self) -> str:
        if self.is_todo:
            return f"TODO: {self.name} = {self.value} ({self.todo_message})"
        status = " [VERIFIED]" if self.is_verified else ""
        return f"{self.name} = {self.value} ({self.source}){status}"


@dataclass
class FactsMirror:
    """
    Parsed FACTS MIRROR block from LLM output.

    Contains all constants that should be validated against generated code
    and source YAML.
    """
    entries: List[FactsMirrorEntry] = field(default_factory=list)
    raw_text: str = ""           # Original FACTS MIRROR block text

    @property
    def has_todos(self) -> bool:
        """True if any entry is marked as TODO."""
        return any(e.is_todo for e in self.entries)

    @property
    def total_facts(self) -> int:
        """Total number of facts (excluding TODOs)."""
        return len([e for e in self.entries if not e.is_todo])

    @property
    def verified_facts(self) -> int:
        """Number of verified facts."""
        return len([e for e in self.entries if e.is_verified and not e.is_todo])

    def get_conflicts(self) -> List[str]:
        """Return list of TODO messages (conflicts/issues)."""
        return [e.todo_message for e in self.entries if e.is_todo and e.todo_message]

    def get_entry(self, name: str) -> Optional[FactsMirrorEntry]:
        """Get entry by constant name."""
        for entry in self.entries:
            if entry.name == name:
                return entry
        return None

    def __str__(self) -> str:
        lines = ["FACTS MIRROR:"]
        for entry in self.entries:
            lines.append(f"  {entry}")
        lines.append(f"Total: {self.total_facts}, Verified: {self.verified_facts}, TODOs: {len(self.get_conflicts())}")
        return "\n".join(lines)


@dataclass
class CConstant:
    """
    A constant extracted from C code (#define or other).
    """
    name: str                    # Constant name
    value: str                   # Value as string
    location: str                # File and line (e.g., "gio.h:42")
    context: str                 # Full line of code (for debugging)

    def __str__(self) -> str:
        return f"{self.name} = {self.value} [{self.location}]"


@dataclass
class RegisterAccess:
    """
    A register access pattern found in C code.
    """
    expression: str              # Full expression (e.g., "0xFFF7BC00 + 0x00")
    base: Optional[str] = None   # Base address if extractable
    offset: Optional[str] = None # Offset if extractable
    location: str = ""           # File and line

    def __str__(self) -> str:
        if self.base and self.offset:
            return f"*({self.base} + {self.offset}) [{self.location}]"
        return f"*({self.expression}) [{self.location}]"


@dataclass
class ExtractedConstants:
    """
    All constants and patterns extracted from a single C file.
    """
    filename: str
    defines: List[CConstant] = field(default_factory=list)
    register_accesses: List[RegisterAccess] = field(default_factory=list)
    struct_accesses: List[Tuple[str, str]] = field(default_factory=list)  # (struct_name, member)

    def get_define(self, name: str) -> Optional[CConstant]:
        """Get a #define constant by name."""
        for define in self.defines:
            if define.name == name:
                return define
        return None

    def get_all_values(self) -> Dict[str, str]:
        """Get all #define values as a dictionary."""
        return {d.name: d.value for d in self.defines}

    def __str__(self) -> str:
        return (f"ExtractedConstants from {self.filename}: "
                f"{len(self.defines)} defines, "
                f"{len(self.register_accesses)} register accesses, "
                f"{len(self.struct_accesses)} struct accesses")


# ==============================================================================
# PARSING FUNCTIONS
# ==============================================================================

def parse_facts_mirror(text: str) -> FactsMirror:
    """
    Extract and parse FACTS MIRROR block from LLM output.

    The FACTS MIRROR block format:
        ===== FACTS MIRROR =====
        GIO_BASE = 0xFFF7BC00 (from YAML)
        GIO_GCR0_OFFSET = 0x0000 (from YAML, verified in gio.c)
        TODO: GIO_INT_ENABLE = unknown (register not documented)
        ===== END FACTS MIRROR =====

    Args:
        text: Full LLM output text (may contain FACTS MIRROR or not)

    Returns:
        FactsMirror object with parsed entries
    """
    mirror = FactsMirror()

    # Extract FACTS MIRROR block
    match = FACTS_MIRROR_BLOCK_RE.search(text)
    if not match:
        # No FACTS MIRROR found - not necessarily an error (some prompts don't require it)
        return mirror

    mirror.raw_text = match.group(0)
    facts_content = match.group(1).strip()

    # Parse individual entries
    for line in facts_content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('//'):
            continue

        # Check if line starts with TODO:
        is_todo = line.upper().startswith("TODO:")
        if is_todo:
            # Extract TODO message
            todo_match = re.match(r"TODO:\s*(.+)", line, re.IGNORECASE)
            if todo_match:
                todo_text = todo_match.group(1).strip()

                # Try to parse as fact entry
                entry_match = FACTS_ENTRY_RE.search(todo_text)
                if entry_match:
                    name = entry_match.group(1)
                    value = entry_match.group(2)
                    annotation = entry_match.group(3) or ""

                    entry = FactsMirrorEntry(
                        name=name,
                        value=value,
                        source="",
                        is_todo=True,
                        todo_message=annotation or todo_text
                    )
                    mirror.entries.append(entry)
                else:
                    # Couldn't parse as fact, just store as generic TODO
                    entry = FactsMirrorEntry(
                        name="UNKNOWN",
                        value="",
                        source="",
                        is_todo=True,
                        todo_message=todo_text
                    )
                    mirror.entries.append(entry)
        else:
            # Regular fact entry
            entry_match = FACTS_ENTRY_RE.match(line)
            if entry_match:
                name = entry_match.group(1)
                value = entry_match.group(2)
                annotation = entry_match.group(3) or ""

                # Check if annotation indicates verification
                is_verified = "verified" in annotation.lower()

                entry = FactsMirrorEntry(
                    name=name,
                    value=value,
                    source=annotation,
                    is_todo=False,
                    is_verified=is_verified,
                    verification_note=annotation if is_verified else ""
                )
                mirror.entries.append(entry)

    return mirror


def extract_constants_from_c_code(
    source_code: str,
    filename: str,
    include_line_numbers: bool = True
) -> ExtractedConstants:
    """
    Extract all #define constants and register access patterns from C code.

    Args:
        source_code: C source or header file content
        filename: Name of the file (for location tracking)
        include_line_numbers: If True, include line numbers in locations

    Returns:
        ExtractedConstants object with all found patterns
    """
    extracted = ExtractedConstants(filename=filename)

    lines = source_code.split('\n')

    # Extract #define constants
    for line_num, line in enumerate(lines, start=1):
        # Skip comments
        if line.strip().startswith('//') or line.strip().startswith('/*'):
            continue

        match = DEFINE_RE.match(line)
        if match:
            name = match.group(1)
            value = match.group(2).strip()

            # Clean up value (remove trailing comments)
            if '//' in value:
                value = value.split('//')[0].strip()
            if '/*' in value:
                value = value.split('/*')[0].strip()

            location = f"{filename}:{line_num}" if include_line_numbers else filename

            constant = CConstant(
                name=name,
                value=value,
                location=location,
                context=line.strip()
            )
            extracted.defines.append(constant)

    # Extract register access patterns
    for line_num, line in enumerate(lines, start=1):
        for match in REGISTER_ACCESS_RE.finditer(line):
            expression = match.group(1).strip()
            location = f"{filename}:{line_num}" if include_line_numbers else filename

            # Try to parse base + offset
            base = None
            offset = None
            if '+' in expression:
                parts = expression.split('+')
                if len(parts) == 2:
                    base = parts[0].strip()
                    offset = parts[1].strip()

            access = RegisterAccess(
                expression=expression,
                base=base,
                offset=offset,
                location=location
            )
            extracted.register_accesses.append(access)

    # Extract struct member accesses (e.g., gioREG->GCR0)
    for line_num, line in enumerate(lines, start=1):
        for match in STRUCT_MEMBER_ACCESS_RE.finditer(line):
            struct_name = match.group(1)
            member_name = match.group(2)
            extracted.struct_accesses.append((struct_name, member_name))

    return extracted


def _strip_outer_parentheses(expr: str) -> str:
    """Strip balanced outer parentheses repeatedly."""
    text = expr.strip()
    while text.startswith("(") and text.endswith(")"):
        depth = 0
        balanced = True
        for i, ch in enumerate(text):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i != len(text) - 1:
                    balanced = False
                    break
            if depth < 0:
                balanced = False
                break
        if not balanced or depth != 0:
            break
        text = text[1:-1].strip()
    return text


def _strip_c_numeric_suffixes(expr: str) -> str:
    """Strip C integer suffixes (U/L) from literals inside an expression."""
    return re.sub(r'\b(0x[0-9A-Fa-f]+|\d+)([uUlL]+)\b', r'\1', expr)


def _strip_c_casts(expr: str) -> str:
    """Remove simple C-style casts from an expression."""
    text = expr
    cast_pattern = re.compile(r'\(\s*[A-Za-z_][A-Za-z0-9_\s\*]*\s*\)')
    prev = None
    while prev != text:
        prev = text
        text = cast_pattern.sub('', text)
    return text


def _safe_eval_numeric_expression(expr: str) -> Optional[int]:
    """
    Safely evaluate a constrained numeric expression.

    Allowed operators: +, -, <<, >>, &, |, ^
    """
    text = _strip_outer_parentheses(expr)
    text = _strip_c_casts(text)
    text = _strip_c_numeric_suffixes(text)
    text = _strip_outer_parentheses(text)

    if not text:
        return None

    # Reject pointer and dereference/address operators.
    if "*" in text or "/" in text or "%" in text:
        return None

    # Reject identifiers after cast stripping; allow 'x' only as part of 0x hex.
    scrubbed = re.sub(r'0x[0-9A-Fa-f]+', '', text)
    if re.search(r'[A-Za-z_]', scrubbed):
        return None

    if re.search(r'[^0-9a-fA-FxX\(\)\+\-\<\>\&\|\^\s]', text):
        return None

    try:
        node = ast.parse(text, mode='eval')
    except SyntaxError:
        return None

    def _eval(n: ast.AST) -> int:
        if isinstance(n, ast.Expression):
            return _eval(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, int):
            return int(n.value)
        if isinstance(n, ast.UnaryOp):
            value = _eval(n.operand)
            if isinstance(n.op, ast.USub):
                return -value
            if isinstance(n.op, ast.UAdd):
                return value
            raise ValueError("unsupported unary operator")
        if isinstance(n, ast.BinOp):
            left = _eval(n.left)
            right = _eval(n.right)
            if isinstance(n.op, ast.Add):
                return left + right
            if isinstance(n.op, ast.Sub):
                return left - right
            if isinstance(n.op, ast.LShift):
                return left << right
            if isinstance(n.op, ast.RShift):
                return left >> right
            if isinstance(n.op, ast.BitAnd):
                return left & right
            if isinstance(n.op, ast.BitOr):
                return left | right
            if isinstance(n.op, ast.BitXor):
                return left ^ right
            raise ValueError("unsupported binary operator")
        raise ValueError("unsupported expression")

    try:
        return _eval(node)
    except Exception:
        return None


def normalize_value(value: str) -> str:
    """
    Normalize a constant value/expression for comparison.

    Supports casted pointer forms and simple arithmetic expressions.
    """
    raw = (value or "").strip()
    if not raw:
        return raw

    parsed_int = _safe_eval_numeric_expression(raw)
    if parsed_int is not None:
        if parsed_int < 0:
            return str(parsed_int)
        return f"0x{parsed_int:x}"

    # Fallback to legacy normalization behavior.
    raw = _strip_c_numeric_suffixes(raw)
    raw = _strip_outer_parentheses(raw)
    if raw.startswith('0x') or raw.startswith('0X'):
        raw = raw.lower()
    return raw


def compare_values(val1: str, val2: str) -> bool:
    """
    Compare two constant values for equality.

    Handles different formats (hex, decimal, with/without suffixes).
    """
    norm1 = normalize_value(val1)
    norm2 = normalize_value(val2)

    # Direct comparison
    if norm1 == norm2:
        return True

    # Try to convert both normalized values to integers for numeric comparison.
    try:
        if norm1.startswith('0x') and norm2.startswith('0x'):
            return int(norm1, 16) == int(norm2, 16)
        int1 = int(norm1, 0)  # Auto-detect base
        int2 = int(norm2, 0)
        return int1 == int2
    except (ValueError, TypeError):
        pass

    return False


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def find_preamble_file(artifacts_dir: Path) -> Optional[Path]:
    """
    Find the most recent preamble file in the artifacts directory.

    Args:
        artifacts_dir: Path to _artifacts directory

    Returns:
        Path to most recent llm_preamble_*.txt file, or None if not found
    """
    if not artifacts_dir.exists():
        return None

    preamble_files = sorted(artifacts_dir.glob("llm_preamble_*.txt"))
    if preamble_files:
        return preamble_files[-1]  # Return most recent

    return None


def extract_preamble_from_response(response_text: str) -> str:
    """
    Extract the preamble (text before first FILE separator) from LLM response.

    Args:
        response_text: Full LLM response text

    Returns:
        Preamble text, or empty string if no separators found
    """
    file_sep_pattern = r"^===== FILE: (.+) =====\s*$"
    match = re.search(file_sep_pattern, response_text, re.MULTILINE)

    if match:
        return response_text[:match.start()].strip()

    return ""
