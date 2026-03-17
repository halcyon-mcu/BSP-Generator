"""
Unified Progress Tracking System

A comprehensive, thread-safe, async-aware progress tracking system for BSP generation.
Replaces _ProgressTracker and ExtractionProgress with a single unified implementation.

Features:
- Thread-safe and async-aware (supports both sync and async contexts)
- Task counting (X of Y complete)
- Success/Fail tracking
- Spinner animation
- Elapsed time tracking
- ETA calculation
- Status messages
- Optional token tracking
- Context manager support
- Clean shutdown with proper thread cleanup

Usage:
    # Basic usage
    tracker = ProgressTracker(total=10, name="Generation")
    tracker.start()

    # Using context manager
    with tracker.task("Generating driver", phase="Implementation"):
        # Do work...
        pass

    # Manual update
    tracker.update(completed=1, status="success")

    # Async update
    await tracker.update_async(completed=1, status="success")

    # Stop and show summary
    tracker.stop()
"""

import asyncio
import sys
import threading
import time
from contextlib import contextmanager
from enum import Enum
from typing import Optional, Callable

# Ensure UTF-8 encoding for Windows terminals
if sys.platform == "win32":
    try:
        # Try to set UTF-8 mode for Windows console
        import os
        if hasattr(os, 'system'):
            os.system('chcp 65001 > nul 2>&1')
    except:
        pass


class ProgressLevel(Enum):
    """Log message severity levels."""
    DEBUG = "debug"
    INFO = "info"
    OK = "ok"
    WARN = "warn"
    ERROR = "error"


class ProgressPhase(Enum):
    """Generation phases."""
    DISCOVERY = "Discovery"
    IMPLEMENTATION = "Implementation"
    PLATFORM = "Platform"
    VALIDATION = "Validation"
    PROCESSING = "Processing"


class ProgressTracker:
    """
    Unified progress tracker with thread-safety, async support, and rich features.

    This class provides comprehensive progress tracking for long-running operations
    with multiple tasks. It supports both synchronous and asynchronous contexts,
    provides visual feedback with a spinner, tracks success/failure rates, calculates
    ETA, and optionally tracks API token usage.

    Thread Safety:
        All state mutations are protected by threading.Lock for sync operations
        and asyncio.Lock for async operations. The spinner runs in a daemon thread
        that safely accesses shared state.

    Attributes:
        total (int): Total number of tasks to complete
        name (str): Name of the operation (e.g., "Generation", "Extraction")
        enable_spinner (bool): Whether to show animated spinner
        completed (int): Number of tasks completed
        success_count (int): Number of successful tasks
        fail_count (int): Number of failed tasks
        start_time (float): Timestamp when tracking started
        is_running (bool): Whether tracking is currently active
    """

    # Braille spinner characters for smooth animation
    SPINNER_CHARS = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    # ASCII fallback spinner for terminals without Unicode support
    SPINNER_CHARS_ASCII = ['|', '/', '-', '\\', '|', '/', '-', '\\']

    # Unicode symbols
    SYMBOL_SUCCESS = '✓'
    SYMBOL_FAIL = '✗'
    # ASCII fallbacks
    SYMBOL_SUCCESS_ASCII = 'OK:'
    SYMBOL_FAIL_ASCII = 'X:'

    # Level prefixes for status messages
    LEVEL_PREFIXES = {
        ProgressLevel.DEBUG: "[debug]",
        ProgressLevel.INFO: "[info]",
        ProgressLevel.OK: "[ok]",
        ProgressLevel.WARN: "[warn]",
        ProgressLevel.ERROR: "[error]",
    }

    def __init__(
        self,
        total: int,
        name: str = "Generation",
        enable_spinner: bool = True,
        track_tokens: bool = False,
        use_unicode: Optional[bool] = None
    ):
        """
        Initialize progress tracker.

        Args:
            total: Total number of tasks to complete
            name: Name of the operation for display
            enable_spinner: Whether to show animated spinner (default: True)
            track_tokens: Whether to track API token usage (default: False)
            use_unicode: Whether to use Unicode characters. If None, auto-detect based on platform
        """
        # Task counting
        self.total = total
        self.completed = 0
        self.success_count = 0
        self.fail_count = 0

        # Display settings
        self.name = name
        self.enable_spinner = enable_spinner

        # Auto-detect Unicode support
        if use_unicode is None:
            # Check if stdout supports UTF-8
            try:
                encoding = sys.stdout.encoding
                self.use_unicode = encoding and 'utf' in encoding.lower()
            except:
                self.use_unicode = sys.platform != "win32"
        else:
            self.use_unicode = use_unicode

        # Token tracking (optional)
        self.track_tokens = track_tokens
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        # Timing
        self.start_time: Optional[float] = None
        self.last_update_time: Optional[float] = None

        # State management
        self.is_running = False
        self.current_phase = "Processing"
        self.current_task_name = ""

        # Thread safety
        self._lock = threading.Lock()
        self._async_lock = asyncio.Lock()
        self._stop_event = threading.Event()
        self._spinner_thread: Optional[threading.Thread] = None

        # Message queue for status messages
        self._pending_messages = []
        self._last_spinner_line = ""

    def start(self) -> None:
        """
        Start progress tracking.

        Initializes timing, starts the spinner thread if enabled, and displays
        the initial progress line.
        """
        with self._lock:
            if self.is_running:
                return

            self.is_running = True
            self.start_time = time.time()
            self.last_update_time = self.start_time
            self.completed = 0
            self.success_count = 0
            self.fail_count = 0
            self._stop_event.clear()

            # Start spinner thread
            if self.enable_spinner:
                self._spinner_thread = threading.Thread(
                    target=self._run_spinner,
                    daemon=True,
                    name="ProgressSpinner"
                )
                self._spinner_thread.start()

    def stop(self) -> None:
        """
        Stop progress tracking and display final summary.

        Signals the spinner thread to stop, waits for it to finish, and displays
        a comprehensive summary of the operation including success/failure counts,
        timing information, and token usage if enabled.
        """
        with self._lock:
            if not self.is_running:
                return

            self.is_running = False
            self._stop_event.set()

        # Wait for spinner thread to finish (with timeout)
        if self._spinner_thread and self._spinner_thread.is_alive():
            self._spinner_thread.join(timeout=1.0)

        # Clear spinner line
        if self.enable_spinner:
            print("\r" + " " * 120 + "\r", end="", flush=True)

        # Print final summary
        self._print_summary()

    @contextmanager
    def task(self, name: str, phase: str = "Processing"):
        """
        Context manager for automatic task tracking.

        Automatically increments success count on successful completion or
        fail count if an exception is raised. Updates the current task name
        for display in the spinner.

        Args:
            name: Name of the task for display
            phase: Phase name (e.g., "Discovery", "Implementation")

        Yields:
            None

        Example:
            with tracker.task("Generating GIO driver", phase="Implementation"):
                generate_driver()
        """
        # Update current task info
        with self._lock:
            self.current_task_name = name
            self.current_phase = phase

        success = False
        try:
            yield
            success = True
        finally:
            # Update counts based on outcome
            self.update(completed=1, status="success" if success else "fail")

    def update(self, completed: int = 1, status: str = "success") -> None:
        """
        Update progress (thread-safe).

        Args:
            completed: Number of tasks to mark as completed (default: 1)
            status: Status of completed tasks - "success" or "fail" (default: "success")
        """
        with self._lock:
            self.completed += completed
            self.last_update_time = time.time()

            if status == "success":
                self.success_count += completed
            elif status == "fail":
                self.fail_count += completed

    async def update_async(self, completed: int = 1, status: str = "success") -> None:
        """
        Update progress (async-safe).

        Args:
            completed: Number of tasks to mark as completed (default: 1)
            status: Status of completed tasks - "success" or "fail" (default: "success")
        """
        async with self._async_lock:
            with self._lock:
                self.completed += completed
                self.last_update_time = time.time()

                if status == "success":
                    self.success_count += completed
                elif status == "fail":
                    self.fail_count += completed

    def set_status(self, message: str, level: str = "info") -> None:
        """
        Log a status message.

        Messages are queued and displayed by the spinner thread to avoid
        interfering with the progress line.

        Args:
            message: Status message to display
            level: Message level - "debug", "info", "ok", "warn", or "error"
        """
        try:
            level_enum = ProgressLevel(level)
        except ValueError:
            level_enum = ProgressLevel.INFO

        prefix = self.LEVEL_PREFIXES[level_enum]
        formatted_message = f"{prefix} {message}"

        with self._lock:
            self._pending_messages.append(formatted_message)

    def add_tokens(self, input_tokens: int, output_tokens: int) -> None:
        """
        Track API token usage (thread-safe).

        Args:
            input_tokens: Number of input tokens consumed
            output_tokens: Number of output tokens generated
        """
        if not self.track_tokens:
            return

        with self._lock:
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens

    async def add_tokens_async(self, input_tokens: int, output_tokens: int) -> None:
        """
        Track API token usage (async-safe).

        Args:
            input_tokens: Number of input tokens consumed
            output_tokens: Number of output tokens generated
        """
        if not self.track_tokens:
            return

        async with self._async_lock:
            with self._lock:
                self.total_input_tokens += input_tokens
                self.total_output_tokens += output_tokens

    def _run_spinner(self) -> None:
        """
        Spinner thread main loop.

        Continuously updates the progress line with animated spinner, task counts,
        elapsed time, and ETA. Checks stop event every 100ms.
        """
        spinner_idx = 0

        while not self._stop_event.is_set():
            # Print any pending messages
            with self._lock:
                while self._pending_messages:
                    msg = self._pending_messages.pop(0)
                    # Clear current line, print message, will redraw spinner
                    if self._last_spinner_line:
                        print("\r" + " " * len(self._last_spinner_line) + "\r", end="")
                    print(msg, flush=True)

            # Build progress line
            with self._lock:
                if not self.is_running:
                    break

                # Choose spinner and symbols based on Unicode support
                if self.use_unicode:
                    spinner_chars = self.SPINNER_CHARS
                    success_sym = self.SYMBOL_SUCCESS
                    fail_sym = self.SYMBOL_FAIL
                else:
                    spinner_chars = self.SPINNER_CHARS_ASCII
                    success_sym = self.SYMBOL_SUCCESS_ASCII
                    fail_sym = self.SYMBOL_FAIL_ASCII

                spinner_char = spinner_chars[spinner_idx % len(spinner_chars)]
                percent = int((self.completed / self.total) * 100) if self.total > 0 else 0
                elapsed = self._get_elapsed_seconds()
                eta = self._calculate_eta()

                # Format: ⠋ Pass 1: Discovery: 6/10 (60%) ✓5 ✗1 [45s ETA: 30s]
                # Or ASCII: | Pass 1: Discovery: 6/10 (60%) OK:5 X:1 [45s ETA: 30s]
                line_parts = [
                    spinner_char,
                    f"{self.name}:",
                    f"{self.current_phase}:",
                    f"{self.completed}/{self.total}",
                    f"({percent}%)",
                    f"{success_sym}{self.success_count}",
                    f"{fail_sym}{self.fail_count}",
                    f"[{elapsed}s",
                ]

                if eta is not None and eta > 0:
                    line_parts.append(f"ETA: {eta}s]")
                else:
                    line_parts.append("]")

                if self.current_task_name:
                    # Truncate long task names
                    task_display = self.current_task_name
                    if len(task_display) > 40:
                        task_display = task_display[:37] + "..."
                    line_parts.append(f"- {task_display}")

                progress_line = " ".join(line_parts)

                # Pad to 120 chars to clear previous longer lines
                progress_line = f"\r{progress_line:<120}"
                self._last_spinner_line = progress_line

            # Print progress line with safe encoding
            try:
                print(progress_line, end="", flush=True)
            except (UnicodeEncodeError, UnicodeDecodeError):
                # Final fallback - strip all non-ASCII
                ascii_line = progress_line.encode('ascii', errors='replace').decode('ascii')
                print(ascii_line, end="", flush=True)

            # Increment spinner
            spinner_idx += 1

            # Sleep briefly
            time.sleep(0.1)

    def _get_elapsed_seconds(self) -> int:
        """
        Get elapsed time since start.

        Returns:
            Elapsed time in seconds (integer)
        """
        if self.start_time is None:
            return 0
        return int(time.time() - self.start_time)

    def _calculate_eta(self) -> Optional[int]:
        """
        Calculate estimated time to completion.

        Uses current completion rate to estimate remaining time.
        Returns None if not enough data to calculate.

        Returns:
            Estimated seconds remaining, or None if cannot calculate
        """
        if self.start_time is None or self.completed == 0:
            return None

        elapsed = time.time() - self.start_time
        rate = self.completed / elapsed  # tasks per second

        if rate <= 0:
            return None

        remaining = self.total - self.completed
        eta = remaining / rate

        return int(eta)

    def _print_summary(self) -> None:
        """
        Print final summary of the operation.

        Displays total time, task counts, success rate, and optional token usage.
        """
        elapsed = self._get_elapsed_seconds()
        success_rate = (self.success_count / self.total * 100) if self.total > 0 else 0

        print()
        print("=" * 80)
        print(f"{self.name} Complete")
        print("=" * 80)
        print(f"Total tasks:     {self.completed}/{self.total}")
        print(f"Success:         {self.success_count} ({success_rate:.1f}%)")
        print(f"Failed:          {self.fail_count}")
        print(f"Duration:        {elapsed}s")

        if self.track_tokens and (self.total_input_tokens > 0 or self.total_output_tokens > 0):
            print(f"Input tokens:    {self.total_input_tokens:,}")
            print(f"Output tokens:   {self.total_output_tokens:,}")
            total_tokens = self.total_input_tokens + self.total_output_tokens
            print(f"Total tokens:    {total_tokens:,}")

        print("=" * 80)


class SimpleProgressTracker:
    """
    Simplified progress tracker for async-only contexts.

    This is a lightweight version that only supports async operations and doesn't
    include a spinner thread. Useful for scenarios where minimal overhead is desired.
    """

    def __init__(self, total: int, name: str = "Processing"):
        """
        Initialize simple progress tracker.

        Args:
            total: Total number of tasks
            name: Name of the operation
        """
        self.total = total
        self.name = name
        self.completed = 0
        self.success_count = 0
        self.fail_count = 0
        self.lock = asyncio.Lock()
        self.start_time: Optional[float] = None

    async def start(self) -> None:
        """Start tracking."""
        async with self.lock:
            self.start_time = time.time()
            self.completed = 0
            self.success_count = 0
            self.fail_count = 0

    async def update(self, success: bool = True) -> None:
        """
        Update progress.

        Args:
            success: Whether the task succeeded
        """
        async with self.lock:
            self.completed += 1
            if success:
                self.success_count += 1
            else:
                self.fail_count += 1

            # Print simple progress (with encoding safety)
            percent = int((self.completed / self.total) * 100) if self.total > 0 else 0
            try:
                print(f"{self.name}: {self.completed}/{self.total} ({percent}%) - "
                      f"✓{self.success_count} ✗{self.fail_count}")
            except (UnicodeEncodeError, UnicodeDecodeError):
                # ASCII fallback
                print(f"{self.name}: {self.completed}/{self.total} ({percent}%) - "
                      f"OK:{self.success_count} X:{self.fail_count}")

    async def finish(self) -> None:
        """Print final summary."""
        async with self.lock:
            elapsed = int(time.time() - self.start_time) if self.start_time else 0
            success_rate = (self.success_count / self.total * 100) if self.total > 0 else 0

            print()
            print(f"{self.name} Complete:")
            print(f"  {self.success_count}/{self.total} succeeded ({success_rate:.1f}%)")
            print(f"  {self.fail_count} failed")
            print(f"  Duration: {elapsed}s")


# Convenience function for backward compatibility
def create_progress_tracker(
    total: int,
    name: str = "Generation",
    enable_spinner: bool = True,
    track_tokens: bool = False,
    use_unicode: Optional[bool] = None
) -> ProgressTracker:
    """
    Factory function to create a ProgressTracker instance.

    Provides backward compatibility with code that expects a factory function.

    Args:
        total: Total number of tasks
        name: Name of the operation
        enable_spinner: Whether to show spinner animation
        track_tokens: Whether to track token usage
        use_unicode: Whether to use Unicode characters (None = auto-detect)

    Returns:
        Configured ProgressTracker instance
    """
    return ProgressTracker(
        total=total,
        name=name,
        enable_spinner=enable_spinner,
        track_tokens=track_tokens,
        use_unicode=use_unicode
    )


# Example usage and testing
if __name__ == "__main__":
    import random

    print("Testing ProgressTracker\n")

    # Test 1: Basic usage with context manager
    print("Test 1: Context manager usage")
    tracker = ProgressTracker(total=10, name="Test Generation")
    tracker.start()

    for i in range(10):
        with tracker.task(f"Task {i+1}", phase="Implementation"):
            time.sleep(0.3)
            # Simulate occasional failure
            if random.random() < 0.2:
                raise Exception("Simulated failure")

    tracker.stop()

    print("\n" + "-" * 80 + "\n")

    # Test 2: Manual updates
    print("Test 2: Manual updates")
    tracker2 = ProgressTracker(total=5, name="Manual Test")
    tracker2.start()

    for i in range(5):
        tracker2.set_status(f"Processing item {i+1}", level="info")
        time.sleep(0.2)
        status = "success" if random.random() > 0.3 else "fail"
        tracker2.update(completed=1, status=status)
        time.sleep(0.3)

    tracker2.stop()

    print("\n" + "-" * 80 + "\n")

    # Test 3: With token tracking
    print("Test 3: Token tracking")
    tracker3 = ProgressTracker(total=3, name="API Test", track_tokens=True)
    tracker3.start()

    for i in range(3):
        time.sleep(0.2)
        tracker3.add_tokens(input_tokens=1000 + i*100, output_tokens=500 + i*50)
        tracker3.update(completed=1, status="success")
        time.sleep(0.2)

    tracker3.stop()

    print("\n" + "-" * 80 + "\n")

    # Test 4: Async usage
    print("Test 4: Async operations")

    async def async_test():
        tracker = SimpleProgressTracker(total=5, name="Async Test")
        await tracker.start()

        for i in range(5):
            await asyncio.sleep(0.2)
            success = random.random() > 0.3
            await tracker.update(success=success)

        await tracker.finish()

    asyncio.run(async_test())
