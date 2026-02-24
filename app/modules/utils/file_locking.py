"""
Cross-platform file locking for concurrent file writes.

Provides a context manager for exclusive file locking to prevent
race conditions when multiple tasks write to the same file.
"""

import sys
import os
from pathlib import Path
from typing import Union

# Platform-specific imports
if sys.platform == 'win32':
    import msvcrt
else:
    import fcntl


class FileLock:
    """
    Cross-platform file locking context manager.

    Acquires an exclusive lock on a file to prevent concurrent writes.
    The lock is automatically released when exiting the context.

    Example:
        with FileLock(file_path):
            file_path.write_text(content)
    """

    def __init__(self, path: Union[str, Path]):
        """
        Initialize file lock.

        Args:
            path: Path to file to lock
        """
        self.path = Path(path)
        self.handle = None
        self.lock_path = None

    def __enter__(self):
        """Acquire exclusive file lock."""
        # Create parent directory if it doesn't exist
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Use a separate lock file to avoid conflicts with actual file operations
        self.lock_path = self.path.parent / f".{self.path.name}.lock"

        # Open lock file for locking
        self.handle = open(self.lock_path, 'a')

        # Acquire platform-specific lock
        if sys.platform == 'win32':
            # Windows: use msvcrt locking
            # Lock 1 byte at position 0
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            # Unix/Linux: use fcntl locking
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release file lock."""
        if self.handle:
            try:
                # Release platform-specific lock
                if sys.platform == 'win32':
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            finally:
                self.handle.close()

                # Clean up lock file
                try:
                    if self.lock_path and self.lock_path.exists():
                        self.lock_path.unlink()
                except Exception:
                    # Ignore errors cleaning up lock file
                    pass

        return False  # Don't suppress exceptions
