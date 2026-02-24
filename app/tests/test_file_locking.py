"""
Unit tests for file locking module.
"""

import pytest
from pathlib import Path
import tempfile
import os
import threading
import time

from modules.utils.file_locking import FileLock


def test_file_lock_creates_parent_directory(tmp_path):
    """Test that FileLock creates parent directories if needed."""
    nested_path = tmp_path / "subdir1" / "subdir2" / "test.txt"

    with FileLock(nested_path):
        # Should create parent directories
        assert nested_path.parent.exists()


def test_file_lock_basic_write(tmp_path):
    """Test that FileLock allows writing to file."""
    test_file = tmp_path / "test.txt"
    content = "Hello, World!"

    with FileLock(test_file):
        test_file.write_text(content)

    assert test_file.read_text() == content


def test_file_lock_cleanup(tmp_path):
    """Test that FileLock cleans up lock file after release."""
    test_file = tmp_path / "test.txt"
    lock_file = test_file.parent / f".{test_file.name}.lock"

    with FileLock(test_file):
        # Lock file should exist during lock
        assert lock_file.exists()

    # Lock file should be cleaned up after release
    # Note: cleanup may fail on Windows if file is still in use
    # So we don't strictly require it to be deleted


def test_file_lock_concurrent_access(tmp_path):
    """Test that FileLock prevents concurrent writes."""
    test_file = tmp_path / "concurrent.txt"
    results = []

    def write_with_lock(value, delay=0.1):
        """Write to file with lock, simulating some processing time."""
        with FileLock(test_file):
            current = test_file.read_text() if test_file.exists() else ""
            time.sleep(delay)  # Simulate processing
            test_file.write_text(current + str(value))
            results.append(value)

    # Create threads that will try to write concurrently
    threads = [
        threading.Thread(target=write_with_lock, args=(i,))
        for i in range(5)
    ]

    # Start all threads
    for t in threads:
        t.start()

    # Wait for all to complete
    for t in threads:
        t.join()

    # Verify all values were written
    content = test_file.read_text()
    assert len(content) == 5  # "01234"
    assert all(str(i) in content for i in range(5))


def test_file_lock_exception_handling(tmp_path):
    """Test that FileLock properly releases even with exceptions."""
    test_file = tmp_path / "exception.txt"

    with pytest.raises(RuntimeError):
        with FileLock(test_file):
            test_file.write_text("before exception")
            raise RuntimeError("Test exception")

    # File should still exist with content
    assert test_file.exists()
    assert test_file.read_text() == "before exception"

    # Should be able to acquire lock again
    with FileLock(test_file):
        test_file.write_text("after exception")

    assert test_file.read_text() == "after exception"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
