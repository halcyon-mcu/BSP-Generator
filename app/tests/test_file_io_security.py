"""
Unit tests for file_io path traversal protection.
"""

import pytest
from modules.utils.file_io import _safe_relpath


class TestSafeRelpath:
    """Test path traversal protection in _safe_relpath."""

    def test_valid_simple_path(self):
        """Test that valid simple paths are accepted."""
        assert _safe_relpath("file.txt") == "file.txt"
        assert _safe_relpath("subdir/file.txt") == "subdir/file.txt"
        assert _safe_relpath("a/b/c/file.txt") == "a/b/c/file.txt"

    def test_leading_dotslash_stripped(self):
        """Test that leading ./ is stripped."""
        assert _safe_relpath("./file.txt") == "file.txt"
        assert _safe_relpath("./subdir/file.txt") == "subdir/file.txt"

    def test_backslash_normalization(self):
        """Test that backslashes are normalized to forward slashes."""
        assert _safe_relpath(r"subdir\file.txt") == "subdir/file.txt"
        assert _safe_relpath(r"a\b\c\file.txt") == "a/b/c/file.txt"

    def test_null_byte_rejected(self):
        """Test that paths with null bytes are rejected."""
        with pytest.raises(ValueError, match="null byte"):
            _safe_relpath("file\x00hidden.txt")

        with pytest.raises(ValueError, match="null byte"):
            _safe_relpath("path/to\x00/file.txt")

    def test_absolute_path_rejected(self):
        """Test that absolute paths are rejected."""
        import sys

        # Test platform-specific absolute paths
        if sys.platform == 'win32':
            # On Windows, /etc/passwd is NOT absolute, but C:\ paths are
            with pytest.raises(ValueError, match="absolute path"):
                _safe_relpath("C:\\Windows\\System32\\config\\SAM")

            with pytest.raises(ValueError, match="absolute path"):
                _safe_relpath("C:/Windows/System32/config/SAM")
        else:
            # On Unix, /etc/passwd IS absolute
            with pytest.raises(ValueError, match="absolute path"):
                _safe_relpath("/etc/passwd")

    def test_unc_path_rejected(self):
        """Test that UNC paths are rejected."""
        with pytest.raises(ValueError, match="UNC path"):
            _safe_relpath(r"\\server\share\file.txt")

        with pytest.raises(ValueError, match="UNC path"):
            _safe_relpath("//server/share/file.txt")

    def test_parent_traversal_rejected(self):
        """Test that parent directory traversal is rejected."""
        with pytest.raises(ValueError, match="'..'"):
            _safe_relpath("../etc/passwd")

        with pytest.raises(ValueError, match="'..'"):
            _safe_relpath("subdir/../../etc/passwd")

        with pytest.raises(ValueError, match="'..'"):
            _safe_relpath("a/b/../../../etc/passwd")

    def test_hidden_parent_traversal_rejected(self):
        """Test that hidden parent traversal patterns are rejected."""
        # Even with normalization, .. in any segment should be rejected
        with pytest.raises(ValueError, match="'..'"):
            _safe_relpath("normal/../etc/passwd")

    def test_max_length_enforced(self):
        """Test that maximum path length is enforced."""
        # Create a path longer than 260 characters
        long_path = "a/" * 150  # 300 characters
        with pytest.raises(ValueError, match="too long"):
            _safe_relpath(long_path)

    def test_max_length_boundary(self):
        """Test that paths at exactly 260 chars are accepted."""
        # 260 character path (Windows limit)
        # Each "a/" is 2 chars, 130 * 2 = 260
        boundary_path = "a/" * 130  # Exactly 260 chars
        result = _safe_relpath(boundary_path)
        assert len(result) == 260

    def test_whitespace_handling(self):
        """Test that whitespace is properly stripped."""
        assert _safe_relpath("  file.txt  ") == "file.txt"
        assert _safe_relpath("  subdir/file.txt  ") == "subdir/file.txt"

    def test_mixed_malicious_patterns(self):
        """Test combinations of malicious patterns."""
        # Combination of UNC and traversal
        with pytest.raises(ValueError):
            _safe_relpath(r"\\server\..\..\..\etc\passwd")

        # Absolute path with traversal
        with pytest.raises(ValueError):
            _safe_relpath("/etc/../../../etc/passwd")


class TestSecurityEdgeCases:
    """Test edge cases for security."""

    def test_empty_path(self):
        """Test that empty paths are handled."""
        assert _safe_relpath("") == ""
        assert _safe_relpath("   ") == ""

    def test_current_directory(self):
        """Test that current directory references are handled."""
        assert _safe_relpath(".") == "."
        assert _safe_relpath("./") == ""

    def test_special_filenames(self):
        """Test special Windows filenames."""
        # These are valid relative paths on Unix but special on Windows
        # We allow them as they'll be caught by the OS if invalid
        assert _safe_relpath("CON") == "CON"
        assert _safe_relpath("PRN") == "PRN"
        assert _safe_relpath("AUX") == "AUX"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
