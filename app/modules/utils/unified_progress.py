#!/usr/bin/env python3
"""
unified_progress.py

Unified progress tracking system for BSP Generator.
Provides hierarchical progress display with global and per-pass tracking.
"""

from __future__ import annotations

import os
import sys
import time
import shutil
import threading
import platform
from enum import Enum, auto
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

# Note: We don't use ProgressTracker as it has a different API than what we need
# from .progress_tracker import ProgressTracker, ProgressLevel


# ==============================================================================
# Status and Configuration
# ==============================================================================

class PassStatus(Enum):
    """Status of a generation pass."""
    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETE = auto()
    FAILED = auto()
    SKIPPED = auto()


@dataclass
class PassInfo:
    """Information about a generation pass."""
    name: str                          # "Pass 1: Discovery"
    short_name: str                    # "Discovery"
    status: PassStatus = PassStatus.PENDING
    progress: float = 0.0              # 0.0 to 1.0
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    tracker: Optional['SimpleProgressTracker'] = None


class SimpleProgressTracker:
    """Simple progress tracker for pass-level progress tracking."""

    def __init__(self, name: str = "", total: int = 0, update_callback=None):
        """
        Initialize tracker.

        Args:
            name: Name of the pass
            total: Total number of tasks
            update_callback: Optional callback to trigger display updates
        """
        self.name = name
        self.total_tasks = total
        self.completed_tasks = 0
        self.success_count = 0
        self.failure_count = 0
        self.current_task_name = ""
        self.messages: List[tuple] = []  # (timestamp, level, message)
        self._update_callback = update_callback

    def set_total_tasks(self, total: int):
        """Set the total number of tasks."""
        self.total_tasks = total
        if self._update_callback:
            self._update_callback()

    def increment_success(self):
        """Increment successful task count."""
        self.success_count += 1
        self.completed_tasks += 1
        # Update callback is called less frequently due to rate limiting
        if self._update_callback:
            try:
                self._update_callback()
            except:
                pass  # Don't let display errors block progress

    def increment_failure(self):
        """Increment failed task count."""
        self.failure_count += 1
        self.completed_tasks += 1
        # Update callback is called less frequently due to rate limiting
        if self._update_callback:
            try:
                self._update_callback()
            except:
                pass  # Don't let display errors block progress

    def add_message(self, message: str, level: str = "info"):
        """
        Add a message to the tracker.

        Args:
            message: Message text
            level: Message level (info, warning, error, success)
        """
        self.messages.append((time.time(), level, message))
        if self._update_callback:
            self._update_callback()

    def update_task_name(self, name: str):
        """Update the current task name."""
        self.current_task_name = name
        if self._update_callback:
            self._update_callback()

    def get_progress(self) -> float:
        """Get current progress as fraction (0.0 to 1.0)."""
        if self.total_tasks == 0:
            return 0.0
        return min(1.0, self.completed_tasks / self.total_tasks)


# ==============================================================================
# Visual Elements
# ==============================================================================

class VisualElements:
    """Terminal visual elements with Unicode and ASCII fallbacks."""

    # Box drawing characters
    BOX_UTF8 = {
        'tl': '\u2554', 'tr': '\u2557', 'bl': '\u255a', 'br': '\u255d',
        'h': '\u2550', 'v': '\u2551',
        'ml': '\u2560', 'mr': '\u2563', 'mt': '\u2566', 'mb': '\u2569'
    }

    # Box drawing fallback (ASCII)
    BOX_ASCII = {
        'tl': '+', 'tr': '+', 'bl': '+', 'br': '+',
        'h': '=', 'v': '|',
        'ml': '+', 'mr': '+', 'mt': '+', 'mb': '+'
    }

    # Progress bar characters
    PROGRESS_FILLED = '\u2588'
    PROGRESS_EMPTY = '\u2591'
    PROGRESS_ASCII_FILLED = '#'
    PROGRESS_ASCII_EMPTY = '-'

    # Status symbols
    STATUS_PENDING = '\u25cb'
    STATUS_IN_PROGRESS = '\u27f3'
    STATUS_COMPLETE = '\u2713'
    STATUS_FAILED = '\u2717'
    STATUS_SKIPPED = '-'

    # Spinner frames (Braille Unicode)
    SPINNER = ['\u280b', '\u2819', '\u2839', '\u2838', '\u283c', '\u2834', '\u2826', '\u2827', '\u2807', '\u280f']
    SPINNER_ASCII = ['|', '/', '-', '\\']

    # ANSI color codes (optional)
    COLOR_RESET = '\033[0m'
    COLOR_SUCCESS = '\033[32m'
    COLOR_ERROR = '\033[31m'
    COLOR_WARNING = '\033[33m'
    COLOR_INFO = '\033[36m'
    COLOR_DIM = '\033[2m'

    def __init__(self, use_unicode: bool = True, use_color: bool = False):
        """
        Initialize visual elements.

        Args:
            use_unicode: Use Unicode characters (box drawing, symbols)
            use_color: Use ANSI color codes
        """
        self.use_unicode = use_unicode
        self.use_color = use_color

        # Select box drawing set
        self.box = self.BOX_UTF8 if use_unicode else self.BOX_ASCII

        # Select progress bar characters
        self.filled = self.PROGRESS_FILLED if use_unicode else self.PROGRESS_ASCII_FILLED
        self.empty = self.PROGRESS_EMPTY if use_unicode else self.PROGRESS_ASCII_EMPTY

        # Select spinner
        self.spinner = self.SPINNER if use_unicode else self.SPINNER_ASCII

    def status_symbol(self, status: PassStatus) -> str:
        """Get status symbol for a pass status with optional color."""
        if not self.use_unicode:
            symbol = {
                PassStatus.PENDING: ' ',
                PassStatus.IN_PROGRESS: '*',
                PassStatus.COMPLETE: '+',
                PassStatus.FAILED: 'X',
                PassStatus.SKIPPED: '-',
            }.get(status, ' ')
        else:
            symbol = {
                PassStatus.PENDING: self.STATUS_PENDING,
                PassStatus.IN_PROGRESS: self.STATUS_IN_PROGRESS,
                PassStatus.COMPLETE: self.STATUS_COMPLETE,
                PassStatus.FAILED: self.STATUS_FAILED,
                PassStatus.SKIPPED: self.STATUS_SKIPPED,
            }.get(status, self.STATUS_PENDING)

        # Apply color if enabled
        if self.use_color:
            if status == PassStatus.COMPLETE:
                return self.colorize(symbol, self.COLOR_SUCCESS)
            elif status == PassStatus.FAILED:
                return self.colorize(symbol, self.COLOR_ERROR)
            elif status == PassStatus.SKIPPED:
                return self.colorize(symbol, self.COLOR_WARNING)
            elif status == PassStatus.IN_PROGRESS:
                return self.colorize(symbol, self.COLOR_INFO)
            elif status == PassStatus.PENDING:
                return self.colorize(symbol, self.COLOR_DIM)

        return symbol

    def progress_bar(self, progress: float, width: int = 30) -> str:
        """
        Render a progress bar with optional color.

        Args:
            progress: Progress value (0.0 to 1.0)
            width: Width of progress bar in characters

        Returns:
            Rendered progress bar string
        """
        filled_width = int(progress * width)
        filled_part = self.filled * filled_width
        empty_part = self.empty * (width - filled_width)

        # Colorize the filled portion if colors enabled
        if self.use_color and filled_width > 0:
            # Use cyan for progress bar
            filled_part = self.colorize(filled_part, self.COLOR_INFO)

        return filled_part + empty_part

    def colorize(self, text: str, color_code: str) -> str:
        """Apply color to text if colors enabled."""
        if not self.use_color:
            return text
        return f"{color_code}{text}{self.COLOR_RESET}"

    @staticmethod
    def visible_length(text: str) -> int:
        """Calculate visible length of string, excluding ANSI escape codes."""
        import re
        # Remove ANSI escape sequences
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return len(ansi_escape.sub('', text))


# ==============================================================================
# Progress Logger
# ==============================================================================

class ProgressLogger:
    """Logs all progress events to a timestamped file."""

    def __init__(self, output_dir: Path):
        """
        Initialize logger with timestamped log file.

        Args:
            output_dir: Directory to create log file in
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = output_dir / f"generation_log_{timestamp}.txt"

        try:
            self.log_handle = open(self.log_file, 'w', encoding='utf-8')
            self._write_header()
        except Exception as e:
            print(f"[warn] Could not create log file: {e}")
            self.log_handle = None

    def _write_header(self):
        """Write log file header."""
        if not self.log_handle:
            return

        self.log_handle.write("=" * 67 + "\n")
        self.log_handle.write("BSP Generator - Generation Log\n")
        self.log_handle.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.log_handle.write("=" * 67 + "\n\n")
        self.log_handle.flush()

    def log_event(self, event_type: str, message: str, level: str = "INFO"):
        """
        Log a general event.

        Args:
            event_type: Type of event (e.g., "CONFIG", "START", "COMPLETE")
            message: Event message
            level: Severity level (INFO, WARNING, ERROR, SUCCESS)
        """
        if not self.log_handle:
            return

        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_handle.write(f"[{timestamp}] [{level}] {message}\n")
        self.log_handle.flush()

    def log_config(self, config: Dict[str, Any]):
        """Log generation configuration."""
        self.log_event("CONFIG", "Configuration:")
        for key, value in config.items():
            self.log_handle.write(f"  - {key}: {value}\n")
        self.log_handle.write("\n")
        self.log_handle.flush()

    def log_pass_start(self, pass_name: str):
        """Log start of a generation pass."""
        if not self.log_handle:
            return

        self.log_handle.write("-" * 67 + "\n")
        self.log_handle.write(f"{pass_name.upper()}\n")
        self.log_handle.write(f"Started: {datetime.now().strftime('%H:%M:%S')}\n")
        self.log_handle.write("-" * 67 + "\n")
        self.log_handle.flush()

    def log_pass_complete(self, pass_name: str, duration: float, success: bool):
        """
        Log completion of a generation pass.

        Args:
            pass_name: Name of the pass
            duration: Duration in seconds
            success: Whether pass completed successfully
        """
        if not self.log_handle:
            return

        status = "COMPLETE" if success else "FAILED"
        timestamp = datetime.now().strftime("%H:%M:%S")

        self.log_handle.write(f"\n[{timestamp}] [{status}] {pass_name} finished in {duration:.1f}s\n\n")
        self.log_handle.flush()

    def log_module_progress(self, module_name: str, status: str, details: str = ""):
        """Log progress for a specific module."""
        message = f"{module_name}: {status}"
        if details:
            message += f" - {details}"
        self.log_event("MODULE", message)

    def log_error(self, error: str, traceback: str = ""):
        """Log an error with optional traceback."""
        self.log_event("ERROR", error, level="ERROR")
        if traceback:
            self.log_handle.write(f"{traceback}\n")
            self.log_handle.flush()

    def log_metrics(self, tokens: int, cost: float, model: str):
        """Log token usage and cost metrics."""
        self.log_event("METRICS", f"Tokens: {tokens:,} | Cost: ${cost:.2f} | Model: {model}")

    def log_summary(self, summary: Dict[str, Any]):
        """Write final generation summary."""
        if not self.log_handle:
            return

        self.log_handle.write("\n" + "=" * 67 + "\n")
        self.log_handle.write("GENERATION COMPLETE\n")
        self.log_handle.write(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        if "duration" in summary:
            mins, secs = divmod(int(summary["duration"]), 60)
            self.log_handle.write(f"Total Duration: {mins}m {secs}s\n")

        if "tokens" in summary:
            self.log_handle.write(f"Total Tokens: {summary['tokens']:,}\n")

        if "cost" in summary:
            self.log_handle.write(f"Total Cost: ${summary['cost']:.2f}\n")

        self.log_handle.write("=" * 67 + "\n")
        self.log_handle.flush()

    def close(self):
        """Close the log file."""
        if self.log_handle:
            self.log_handle.close()
            self.log_handle = None


# ==============================================================================
# Unified Progress Manager
# ==============================================================================

class UnifiedProgressManager:
    """
    Unified progress tracking manager for BSP generation.

    Provides hierarchical progress display with:
    - Global progress across all passes
    - Per-pass detailed progress with spinner/bar
    - Resource metrics (tokens, cost, time)
    - Comprehensive logging to file
    """

    def __init__(
        self,
        passes: List[str],
        output_dir: Path,
        enable_fancy: bool = True,
        enable_color: bool = False,
        cost_tracker=None
    ):
        """
        Initialize unified progress manager.

        Args:
            passes: List of pass names (e.g., ["Discovery", "Implementation", "Platform"])
            output_dir: Output directory for log file
            enable_fancy: Enable fancy terminal UI with box drawing
            enable_color: Enable ANSI color codes
            cost_tracker: Optional cost tracker to query for real-time token/cost updates
        """
        self.passes: List[PassInfo] = []
        self.cost_tracker = cost_tracker
        for name in passes:
            short_name = name.replace("Pass ", "").replace(":", "")
            self.passes.append(PassInfo(
                name=f"Pass {len(self.passes) + 1}: {short_name}",
                short_name=short_name
            ))

        self.current_pass_idx: Optional[int] = None
        self.enable_fancy = enable_fancy
        self.start_time = time.time()

        # Determine terminal capabilities
        self.terminal_width, self.terminal_height = shutil.get_terminal_size(fallback=(80, 24))
        self.is_tty = sys.stdout.isatty()
        self.supports_ansi = self._check_ansi_support()
        self.supports_unicode = self._check_unicode_support()

        # Visual elements
        use_unicode = enable_fancy and self.supports_ansi and self.supports_unicode
        self.visuals = VisualElements(use_unicode=use_unicode, use_color=enable_color)

        # Metrics
        self.total_tokens = 0
        self.total_cost = 0.0
        self.model_name = "Unknown"

        # Logger
        self.logger = ProgressLogger(output_dir)

        # Display control
        self.lock = threading.RLock()  # Reentrant lock to allow nested acquisition
        self.last_update = 0.0
        self.update_interval = 0.033  # Update at 30 FPS for smooth spinner animation
        self.last_line_count = 0  # Track lines printed for clearing
        self.first_render_done = False  # Track if we've done initial render
        self.stopped = False  # Flag to completely stop rendering

        # Animation frame tracking for smooth spinner
        self.animation_frame = 0  # Frame counter

        # Detect OS and set appropriate FPS
        # Windows terminals can be slower, Linux terminals are faster
        # 10 FPS provides smooth animation without excessive flicker on both
        self.is_windows = platform.system() == 'Windows'
        self.target_fps = 10  # 10 FPS for smooth animation without excessive flicker
        self.frame_time = 1.0 / self.target_fps  # Target: 0.1s per frame

        # Display mode
        self.mode = self._determine_mode()

        # Animation thread for smooth spinner (in fancy mode)
        self.animation_thread = None
        self.animation_stop_event = threading.Event()
        self.render_paused = False
        self._pause_depth = 0

        # DON'T clear screen in __init__ - let main.py clear after user confirmation
        # Start animation thread for smooth spinner (in fancy mode)
        if self.mode == "fancy":
            self.animation_stop_event.clear()
            self.animation_thread = threading.Thread(target=self._animation_loop, daemon=True)
            self.animation_thread.start()

    def _check_ansi_support(self) -> bool:
        """Check if terminal supports ANSI escape codes."""
        if not self.is_tty:
            return False

        # Windows detection
        if sys.platform == 'win32':
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
                if handle in (0, -1):
                    return False
                mode = ctypes.c_uint()
                if kernel32.GetConsoleMode(handle, ctypes.byref(mode)) == 0:
                    return False
                enable_vt = 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
                processed = 0x0001  # ENABLE_PROCESSED_OUTPUT
                new_mode = mode.value | enable_vt | processed
                if kernel32.SetConsoleMode(handle, new_mode) == 0:
                    return False
                return True
            except Exception:
                return False

        return True

    def _check_unicode_support(self) -> bool:
        """Best-effort check for Unicode glyph support on stdout."""
        encoding = (getattr(sys.stdout, "encoding", None) or "").lower()
        if not encoding:
            return False
        if "utf" in encoding or "65001" in encoding:
            return True
        return False

    def _determine_mode(self) -> str:
        """Determine display mode based on environment and capabilities."""
        env_mode = os.getenv("BSP_PROGRESS_MODE", "").lower()

        if env_mode == "quiet":
            return "quiet"
        elif env_mode == "simple" or not self.enable_fancy:
            return "simple"
        elif not self.is_tty:
            return "simple"  # Piped output
        elif not self.supports_ansi:
            return "simple"  # No ANSI support
        else:
            return "fancy"

    def _animation_loop(self):
        """Background thread for smooth 30 FPS animation with adaptive timing."""
        while not self.animation_stop_event.is_set():
            frame_start = time.time()

            # Update display if there's an active pass and not stopped
            if self.current_pass_idx is not None and not self.stopped and not self.render_paused:
                # Increment frame counter with lock
                with self.lock:
                    self.animation_frame += 1

                # Force update for smooth animation
                self._update_display(force=True)

            # Calculate adaptive sleep time to maintain 30 FPS
            frame_elapsed = time.time() - frame_start
            sleep_time = max(0.001, self.frame_time - frame_elapsed)  # At least 1ms

            # Wait before next frame
            self.animation_stop_event.wait(sleep_time)

    def _find_pass_index(self, pass_name: str) -> Optional[int]:
        needle = str(pass_name).strip().replace("Pass ", "").replace(":", "")
        for idx, pass_info in enumerate(self.passes):
            if pass_info.short_name == needle or pass_info.name == pass_name:
                return idx
        return None

    def _ensure_optional_pass(self, pass_name: str) -> int:
        idx = self._find_pass_index(pass_name)
        if idx is not None:
            return idx
        short_name = str(pass_name).strip().replace("Pass ", "").replace(":", "")
        pass_info = PassInfo(
            name=f"Pass {len(self.passes) + 1}: {short_name}",
            short_name=short_name,
        )
        self.passes.append(pass_info)
        return len(self.passes) - 1

    def start_pass(self, pass_name: str, optional: bool = False) -> Optional[SimpleProgressTracker]:
        """
        Start a generation pass.

        Args:
            pass_name: Short name of the pass (e.g., "Discovery")
            optional: If True, add pass dynamically when missing.

        Returns:
            SimpleProgressTracker instance for this pass, or None if pass not found
        """
        with self.lock:
            idx = self._find_pass_index(pass_name)
            if idx is None and optional:
                idx = self._ensure_optional_pass(pass_name)
            if idx is None:
                return None

            pass_info = self.passes[idx]
            pass_info.status = PassStatus.IN_PROGRESS
            pass_info.start_time = time.time()
            pass_info.tracker = SimpleProgressTracker(
                name=f"{pass_info.name}",
                total=0,
                update_callback=self._update_display
            )
            self.current_pass_idx = idx

            # Log pass start
            self.logger.log_pass_start(pass_info.name)

            # Update display
            self._update_display()

            return pass_info.tracker

    def start_optional_pass(self, pass_name: str) -> Optional[SimpleProgressTracker]:
        """Start an optional pass, creating it if needed."""
        return self.start_pass(pass_name, optional=True)

    def complete_pass(self, pass_name: str, success: bool = True):
        """
        Mark a pass as complete.

        Args:
            pass_name: Short name of the pass
            success: Whether pass completed successfully
        """
        with self.lock:
            idx = self._find_pass_index(pass_name)
            if idx is None:
                return
            pass_info = self.passes[idx]
            pass_info.status = PassStatus.COMPLETE if success else PassStatus.FAILED
            pass_info.end_time = time.time()
            pass_info.progress = 1.0

            # Log pass completion
            if pass_info.start_time:
                duration = pass_info.end_time - pass_info.start_time
                self.logger.log_pass_complete(pass_info.name, duration, success)

            # Force immediate display update to show completion
            self._update_display(force=True)

            # Longer pause to let user see completion state
            import time as time_module
            time_module.sleep(1.0)

            # Reset current pass
            self.current_pass_idx = None

    def skip_pass(self, pass_name: str, reason: str = "") -> None:
        """Mark a pass as skipped."""
        with self.lock:
            idx = self._ensure_optional_pass(pass_name)
            pass_info = self.passes[idx]
            now = time.time()
            pass_info.status = PassStatus.SKIPPED
            pass_info.start_time = pass_info.start_time or now
            pass_info.end_time = now
            pass_info.progress = 1.0
            pass_info.tracker = None
            if reason:
                self.logger.log_event("SKIP", f"{pass_info.name}: {reason}", level="INFO")
            self._update_display(force=True)

    def set_current_task(self, task_name: str) -> None:
        """Update current task label for active pass."""
        with self.lock:
            if self.current_pass_idx is None:
                return
            pass_info = self.passes[self.current_pass_idx]
            if pass_info.tracker is None:
                pass_info.tracker = SimpleProgressTracker(
                    name=f"{pass_info.name}",
                    total=0,
                    update_callback=self._update_display,
                )
            pass_info.tracker.update_task_name(task_name)

    def pause_for_input(self) -> None:
        """Pause rendering before interactive prompts to prevent flicker."""
        if self.mode != "fancy":
            return
        with self.lock:
            self._pause_depth += 1
            if self._pause_depth > 1:
                return
            self.render_paused = True
            if self.supports_ansi:
                sys.stdout.write('\033[2J')
                sys.stdout.write('\033[H')
                sys.stdout.write('\033[?25h')
                sys.stdout.flush()

    def resume_after_input(self) -> None:
        """Resume rendering after interactive prompts."""
        if self.mode != "fancy":
            return
        with self.lock:
            if self._pause_depth <= 0:
                return
            self._pause_depth -= 1
            if self._pause_depth > 0:
                return
            self.render_paused = False
        self._update_display(force=True)

    def add_cost_info(self, tokens: int, cost: float, model: str = ""):
        """
        Update resource metrics.

        Args:
            tokens: Total tokens used
            cost: Total cost in USD
            model: Model name
        """
        with self.lock:
            self.total_tokens = tokens
            self.total_cost = cost
            if model:
                self.model_name = model

            # Log metrics
            self.logger.log_metrics(tokens, cost, model or self.model_name)

            # Update display
            self._update_display()

    def _update_display(self, force: bool = False):
        """
        Update the terminal display based on current mode.

        Args:
            force: If True, bypass rate limiting (for animation)
        """
        # Check if we've been stopped/paused - if so, don't render anything
        if self.stopped or self.render_paused:
            return

        current_time = time.time()

        # Rate limit updates (check without lock for performance)
        if not force and current_time - self.last_update < self.update_interval:
            return

        # Try to acquire lock with timeout to avoid deadlocks
        # If we can't get the lock quickly, skip this update
        if not self.lock.acquire(blocking=True, timeout=0.05):
            return

        try:
            # Double-check after acquiring lock (unless forced)
            if not force and current_time - self.last_update < self.update_interval:
                return

            self.last_update = current_time

            if self.mode == "fancy":
                self._render_fancy()
            elif self.mode == "simple":
                self._render_simple()
            # quiet mode: no output
        finally:
            self.lock.release()

    def _render_fancy(self):
        """Render fancy hierarchical progress display."""
        lines = []
        v = self.visuals

        # Top border
        lines.append(v.box['tl'] + v.box['h'] * (self.terminal_width - 2) + v.box['tr'])

        # Title
        title = "BSP Generator - TI Hercules RM46"
        padding = (self.terminal_width - 2 - len(title)) // 2
        lines.append(v.box['v'] + ' ' * padding + title + ' ' * (self.terminal_width - 2 - padding - len(title)) + v.box['v'])

        # Divider
        lines.append(v.box['ml'] + v.box['h'] * (self.terminal_width - 2) + v.box['mr'])

        # Global progress
        completed = sum(
            1 for p in self.passes
            if p.status in {PassStatus.COMPLETE, PassStatus.FAILED, PassStatus.SKIPPED}
        )
        total = len(self.passes)
        global_progress = completed / total if total > 0 else 0.0
        progress_bar_width = min(30, self.terminal_width - 40)
        progress_bar = v.progress_bar(global_progress, progress_bar_width)

        progress_line = f"Overall Progress: {progress_bar} {int(global_progress * 100)}% ({completed}/{total} passes)"
        padding = self.terminal_width - 3 - v.visible_length(progress_line)
        lines.append(v.box['v'] + ' ' + progress_line + ' ' * padding + v.box['v'])

        # Pass status grid (2 passes per line)
        for i in range(0, len(self.passes), 2):
            line_parts = []
            for j in range(2):
                idx = i + j
                if idx < len(self.passes):
                    p = self.passes[idx]
                    symbol = v.status_symbol(p.status)
                    pass_text = f"{symbol} {p.name}"
                    line_parts.append(pass_text)

            line = '   '.join(line_parts)
            padding = self.terminal_width - 3 - v.visible_length(line)
            lines.append(v.box['v'] + ' ' + line + ' ' * padding + v.box['v'])

        # Divider
        lines.append(v.box['ml'] + v.box['h'] * (self.terminal_width - 2) + v.box['mr'])

        # Current pass details
        if self.current_pass_idx is not None:
            current = self.passes[self.current_pass_idx]
            tracker = current.tracker

            current_line = f"Current: {current.name}"
            padding = self.terminal_width - 3 - v.visible_length(current_line)
            lines.append(v.box['v'] + ' ' + current_line + ' ' * padding + v.box['v'])

            if tracker:
                # Spinner and task info
                spinner_frame = v.spinner[self.animation_frame % len(v.spinner)]
                task_info = f"{spinner_frame} Generating: {tracker.completed_tasks}/{tracker.total_tasks}"
                if tracker.total_tasks > 0:
                    pct = int((tracker.completed_tasks / tracker.total_tasks) * 100)
                    task_info += f" ({pct}%)"

                # Success/Failure counts (with spacing and colors for readability)
                success_symbol = v.colorize(v.STATUS_COMPLETE, v.COLOR_SUCCESS) if v.use_color else v.STATUS_COMPLETE
                failure_symbol = v.colorize(v.STATUS_FAILED, v.COLOR_ERROR) if v.use_color else v.STATUS_FAILED
                task_info += f" {success_symbol} {tracker.success_count} {failure_symbol} {tracker.failure_count}"

                # Time info with labels
                elapsed = int(time.time() - (current.start_time or time.time()))
                elapsed_mins, elapsed_secs = divmod(elapsed, 60)
                task_info += f" [Elapsed: {elapsed_mins:02d}:{elapsed_secs:02d}"

                # ETA - show total elapsed time at completion (MM:SS format)
                if tracker.total_tasks > 0 and tracker.completed_tasks > 0:
                    rate = tracker.completed_tasks / elapsed if elapsed > 0 else 0
                    remaining = tracker.total_tasks - tracker.completed_tasks
                    remaining_secs = int(remaining / rate) if rate > 0 else 0

                    # Calculate total elapsed time at completion
                    total_elapsed_secs = elapsed + remaining_secs
                    eta_mins, eta_secs = divmod(total_elapsed_secs, 60)
                    task_info += f" | ETA: {eta_mins:02d}:{eta_secs:02d}"

                task_info += "]"
                padding = self.terminal_width - 3 - v.visible_length(task_info)
                lines.append(v.box['v'] + ' ' + task_info + ' ' * padding + v.box['v'])

                if tracker.current_task_name:
                    step_line = f"Step: {tracker.current_task_name}"
                    padding = self.terminal_width - 3 - v.visible_length(step_line)
                    lines.append(v.box['v'] + ' ' + step_line + ' ' * padding + v.box['v'])

                # Progress bar for current pass
                if tracker.total_tasks > 0:
                    pass_progress = tracker.get_progress()
                    bar_width = min(40, self.terminal_width - 20)
                    progress_bar = v.progress_bar(pass_progress, bar_width)
                    bar_line = f"  {progress_bar} {int(pass_progress * 100)}%"
                    padding = self.terminal_width - 3 - v.visible_length(bar_line)
                    lines.append(v.box['v'] + ' ' + bar_line + ' ' * padding + v.box['v'])
        else:
            empty_line = ' ' * (self.terminal_width - 2)
            lines.append(v.box['v'] + empty_line + v.box['v'])
            lines.append(v.box['v'] + empty_line + v.box['v'])

        # Divider
        lines.append(v.box['ml'] + v.box['h'] * (self.terminal_width - 2) + v.box['mr'])

        # Metrics (query cost tracker for real-time updates)
        tokens = self.total_tokens
        cost = self.total_cost
        if self.cost_tracker:
            try:
                stats = self.cost_tracker.get_stats()
                tokens = stats.get("total_tokens", tokens)
                cost = stats.get("cost_usd", cost)
            except:
                pass  # Use cached values if query fails

        metrics_line = f"Tokens: {tokens:,} used | Est. Cost: ${cost:.2f} | Model: {self.model_name}"
        lines.append(v.box['v'] + ' ' + metrics_line + ' ' * (self.terminal_width - 3 - v.visible_length(metrics_line)) + v.box['v'])

        # Bottom border
        lines.append(v.box['bl'] + v.box['h'] * (self.terminal_width - 2) + v.box['br'])

        # Position cursor and render
        # NOTE: ANSI escape codes used here are standard VT100/ANSI sequences
        # that work reliably on both Windows (10+) and Linux terminals:
        # - \033[?25l/h: Hide/show cursor (DECTCEM)
        # - \033[{N}A: Move up N lines
        # - \033[0G: Move to column 0
        # - \033[J: Clear from cursor to end
        # - \033[2J: Clear entire screen
        # - \033[H: Move to home (top-left)
        if self.supports_ansi:
            # Hide cursor for cleaner display
            sys.stdout.write('\033[?25l')

            if self.last_line_count > 0:
                # Move to beginning of current line, then move up N lines
                sys.stdout.write('\r')  # Carriage return to start of line
                sys.stdout.write(f'\033[{self.last_line_count}A')  # Move up N lines
                sys.stdout.write('\033[0G')  # Move to column 0
                sys.stdout.write('\033[J')  # Clear from cursor to end of screen
            else:
                # First render - clear entire screen and position at top
                sys.stdout.write('\033[2J')  # Clear entire screen
                sys.stdout.write('\033[H')   # Move to home position (top-left)

        # Write the entire display
        output = '\n'.join(lines)
        sys.stdout.write(output)
        sys.stdout.flush()

        # Track number of lines for next update
        self.last_line_count = len(lines)

    def _render_simple(self):
        """Render simple line-based progress."""
        completed = sum(
            1 for p in self.passes
            if p.status in {PassStatus.COMPLETE, PassStatus.FAILED, PassStatus.SKIPPED}
        )
        total = len(self.passes)

        if self.current_pass_idx is not None:
            current = self.passes[self.current_pass_idx]
            tracker = current.tracker

            if tracker and tracker.total_tasks > 0:
                progress = f"[{current.short_name}] {tracker.completed_tasks}/{tracker.total_tasks}"
                print(f"\r{progress}", end='', flush=True)

    def should_suppress_prints(self) -> bool:
        """
        Check if print statements should be suppressed.

        Returns True in fancy mode to avoid cluttering the display.
        """
        return self.mode == "fancy"

    def log_or_print(self, message: str, level: str = "INFO"):
        """
        Log message to file in fancy mode, print to console otherwise.

        Args:
            message: Message to log/print
            level: Log level (INFO, WARN, ERROR, DEBUG, SUCCESS)
        """
        self.emit_message(message, level=level, force_console=False)

    def emit_message(self, message: str, level: str = "INFO", force_console: bool = False):
        """
        Emit a message via logger and optionally force console output in fancy mode.
        """
        self.logger.log_event("MESSAGE", message, level)
        if self.mode == "fancy" and not force_console:
            return
        if self.mode == "fancy" and force_console:
            self.pause_for_input()
            try:
                print(message)
            finally:
                self.resume_after_input()
            return
        print(message)

    def cleanup(self):
        """Clean up resources and finalize display."""
        # STEP 1: Stop animation thread FIRST (before anything else)
        # Set stopped flag immediately to prevent any more rendering
        self.stopped = True
        self.render_paused = True

        # Stop animation thread and wait for it to fully exit
        if self.animation_thread and self.animation_thread.is_alive():
            self.animation_stop_event.set()
            self.animation_thread.join(timeout=2.0)  # Wait for thread to exit

        # STEP 2: Do one final render to show completion state
        with self.lock:
            if self.mode == "fancy":
                self._render_fancy()  # Show final completion
                sys.stdout.flush()

        # STEP 3: Pause briefly so user sees the completion
        import time as time_module
        time_module.sleep(0.5)

        # STEP 4: Clear the display completely for validation/cost output
        with self.lock:
            if self.mode == "fancy" and self.supports_ansi:
                # Clear entire screen and position cursor at top
                sys.stdout.write('\033[2J')  # Clear entire screen
                sys.stdout.write('\033[H')   # Move to top-left
                sys.stdout.write('\033[?25h')  # Show cursor
                sys.stdout.flush()
            elif self.mode == "simple":
                print()  # Newline to finish the line

            # Write summary to log
            total_duration = time.time() - self.start_time
            self.logger.log_summary({
                "duration": total_duration,
                "tokens": self.total_tokens,
                "cost": self.total_cost
            })

            # Close log
            self.logger.close()

            # Print log location
            if self.mode != "quiet":
                print(f"\n[info] Generation log saved to: {self.logger.log_file}")

