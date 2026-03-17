# Progress Tracker Migration Guide

This guide explains how to migrate from the old incompatible progress tracking systems (`_ProgressTracker` and `ExtractionProgress`) to the new unified `ProgressTracker` system.

## Table of Contents

1. [Overview](#overview)
2. [Key Benefits](#key-benefits)
3. [Quick Start](#quick-start)
4. [Migration Patterns](#migration-patterns)
5. [API Reference](#api-reference)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

---

## Overview

### Previous Systems (Deprecated)

**_ProgressTracker** (in `prompt.py`):
- Thread-safe but synchronous only
- Basic spinner animation
- No success/fail tracking
- No ETA calculation
- No token tracking

**ExtractionProgress** (in `extract_complete_reference.py`):
- Async-aware but no spinner
- Basic success/fail tracking
- Minimal output
- No thread safety for sync contexts

### New System (Unified)

**ProgressTracker** (in `progress_tracker.py`):
- ✅ Thread-safe AND async-aware
- ✅ Success/Fail tracking
- ✅ Spinner animation
- ✅ Elapsed time + ETA
- ✅ Status messages
- ✅ Token tracking (optional)
- ✅ Context manager support
- ✅ Clean shutdown
- ✅ Windows-compatible (ASCII fallback)

---

## Key Benefits

1. **Single API**: One class replaces two incompatible systems
2. **Better Visibility**: Real-time progress with spinner, ETA, and success/fail counts
3. **Safer**: Proper thread cleanup, no hanging threads
4. **More Informative**: Tracks timing, tokens, and detailed status
5. **Easier to Use**: Context manager pattern for automatic tracking
6. **Cross-Platform**: Works on Windows and Unix with proper encoding

---

## Quick Start

### Installation

The module is already installed at:
```
app/modules/utils/progress_tracker.py
```

### Basic Usage

```python
from app.modules.utils.progress_tracker import ProgressTracker

# Create tracker
tracker = ProgressTracker(total=10, name="Generation")
tracker.start()

# Process tasks
for i in range(10):
    # Do work...
    tracker.update(completed=1, status="success")

# Stop and show summary
tracker.stop()
```

### Context Manager (Recommended)

```python
tracker = ProgressTracker(total=5, name="Generation")
tracker.start()

for task in tasks:
    with tracker.task(f"Processing {task}", phase="Implementation"):
        # Work happens here
        # Success/fail tracked automatically
        process_task(task)

tracker.stop()
```

---

## Migration Patterns

### Pattern 1: Migrate from _ProgressTracker

**OLD CODE:**
```python
from app.modules.generation.prompt import _ProgressTracker

tracker = _ProgressTracker()
tracker.set_total(total_peripherals)
spinner = tracker.start_spinner()

for peripheral in peripherals:
    # Generate code
    completed, total = tracker.increment()
    print(f"Progress: {completed}/{total}")

tracker.stop_spinner()
```

**NEW CODE:**
```python
from app.modules.utils.progress_tracker import ProgressTracker

tracker = ProgressTracker(total=len(peripherals), name="Generation")
tracker.start()

for peripheral in peripherals:
    with tracker.task(f"Generating {peripheral}", phase="Implementation"):
        # Generate code
        pass

tracker.stop()
```

**Key Changes:**
- Set total in constructor (not via `set_total()`)
- No need to manually call `start_spinner()` - handled by `start()`
- Use `update()` or context manager instead of `increment()`
- Call `stop()` instead of `stop_spinner()`
- Automatic success/fail tracking with context manager

---

### Pattern 2: Migrate from ExtractionProgress

**OLD CODE:**
```python
from app.modules.extraction.extract_complete_reference import ExtractionProgress

progress = ExtractionProgress(total=len(pdfs))

for pdf in pdfs:
    try:
        # Extract
        success = True
    except Exception:
        success = False

    await progress.increment(success=success)
```

**NEW CODE:**
```python
from app.modules.utils.progress_tracker import ProgressTracker

tracker = ProgressTracker(total=len(pdfs), name="Extraction")
tracker.start()

for pdf in pdfs:
    try:
        with tracker.task(f"Extracting {pdf.name}", phase="Processing"):
            # Extract
            pass  # Success tracked automatically
    except Exception:
        pass  # Failure tracked automatically

tracker.stop()
```

**Key Changes:**
- Use context manager for automatic success/fail tracking
- Call `start()` and `stop()` for proper lifecycle management
- Use `update_async()` if you need manual async updates
- Get visual progress with spinner (not just print statements)

---

### Pattern 3: Async Concurrent Tasks

**OLD CODE:**
```python
progress = ExtractionProgress(total=10)

async def process_task(i):
    # Work
    await progress.increment(success=True)

await asyncio.gather(*[process_task(i) for i in range(10)])
```

**NEW CODE:**
```python
tracker = ProgressTracker(total=10, name="Processing")
tracker.start()

async def process_task(i):
    # Work
    await tracker.update_async(completed=1, status="success")

try:
    await asyncio.gather(*[process_task(i) for i in range(10)])
finally:
    tracker.stop()
```

**Key Changes:**
- Use `update_async()` for async contexts
- Always call `stop()` in finally block for cleanup
- Spinner runs in background thread automatically

---

### Pattern 4: Token Tracking

**NEW FEATURE** (no direct equivalent in old systems):

```python
tracker = ProgressTracker(
    total=5,
    name="API Extraction",
    track_tokens=True  # Enable token tracking
)
tracker.start()

for task in tasks:
    # API call
    response = await call_api()

    # Track tokens
    tracker.add_tokens(
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens
    )

    # Update progress
    await tracker.update_async(completed=1, status="success")

tracker.stop()
# Summary includes token counts
```

---

## API Reference

### ProgressTracker Class

#### Constructor

```python
ProgressTracker(
    total: int,                      # Total number of tasks
    name: str = "Generation",        # Operation name
    enable_spinner: bool = True,     # Show animated spinner
    track_tokens: bool = False,      # Track API token usage
    use_unicode: Optional[bool] = None  # Use Unicode chars (auto-detect)
)
```

#### Methods

**Lifecycle:**
- `start()` - Start tracking (starts spinner thread)
- `stop()` - Stop tracking and display summary (stops spinner)

**Updates (Sync):**
- `update(completed: int = 1, status: str = "success")` - Update progress
- `add_tokens(input_tokens: int, output_tokens: int)` - Track API tokens

**Updates (Async):**
- `update_async(completed: int = 1, status: str = "success")` - Async-safe update
- `add_tokens_async(input_tokens: int, output_tokens: int)` - Async-safe token tracking

**Status:**
- `set_status(message: str, level: str = "info")` - Log a status message
  - Levels: "debug", "info", "ok", "warn", "error"

**Context Manager:**
- `task(name: str, phase: str = "Processing")` - Context manager for tasks
  - Automatically tracks success/fail based on exceptions

#### Attributes

- `completed` - Current number of completed tasks
- `success_count` - Number of successful tasks
- `fail_count` - Number of failed tasks
- `total` - Total number of tasks
- `is_running` - Whether tracking is active
- `current_phase` - Current phase name (for display)
- `current_task_name` - Current task name (for display)

### SimpleProgressTracker Class

Lightweight async-only tracker without spinner (for minimal overhead).

```python
tracker = SimpleProgressTracker(total=10, name="Processing")
await tracker.start()

for task in tasks:
    await tracker.update(success=True)

await tracker.finish()
```

---

## Best Practices

### 1. Always Use Context Manager When Possible

**Good:**
```python
with tracker.task("Generating driver", phase="Implementation"):
    generate_driver()
```

**Less Good:**
```python
try:
    generate_driver()
    tracker.update(completed=1, status="success")
except Exception:
    tracker.update(completed=1, status="fail")
```

Context manager handles exceptions automatically and ensures proper counting.

### 2. Always Stop in Finally Block

```python
tracker = ProgressTracker(total=10)
tracker.start()

try:
    for task in tasks:
        process(task)
        tracker.update(completed=1, status="success")
finally:
    tracker.stop()  # Ensures clean shutdown even on exception
```

### 3. Use Descriptive Names and Phases

```python
# Good
with tracker.task("Generating GIO driver", phase="Implementation"):
    ...

# Less informative
with tracker.task("Task 1", phase="Processing"):
    ...
```

### 4. Add Status Messages for Important Events

```python
tracker.set_status("Starting validation phase", level="info")
tracker.set_status("All tests passed", level="ok")
tracker.set_status("Warning: register offset missing", level="warn")
tracker.set_status("Fatal: cannot parse YAML", level="error")
```

### 5. Choose Appropriate Tracker Type

- **ProgressTracker**: Use for most cases (sync/async, spinner, full features)
- **SimpleProgressTracker**: Use when minimal overhead needed (async-only, no spinner)

### 6. Disable Spinner for Logged Output

If running in CI/CD or logging to file, disable spinner:

```python
tracker = ProgressTracker(total=10, name="Build", enable_spinner=False)
```

### 7. Set Phases for Multi-Stage Operations

```python
tracker.current_phase = "Discovery"
# ... discovery work ...

tracker.current_phase = "Validation"
# ... validation work ...

tracker.current_phase = "Implementation"
# ... generation work ...
```

---

## Troubleshooting

### Issue: Unicode Characters Not Displaying (Windows)

**Symptom:** Seeing `?` or boxes instead of spinner/checkmarks

**Solution:**
```python
# Force ASCII mode
tracker = ProgressTracker(total=10, use_unicode=False)
```

The tracker auto-detects Unicode support, but you can force ASCII mode.

### Issue: Spinner Not Animating

**Causes:**
1. `enable_spinner=False` in constructor
2. Not calling `start()`
3. Output redirected to file

**Solution:**
```python
# Ensure spinner is enabled
tracker = ProgressTracker(total=10, enable_spinner=True)
tracker.start()  # Don't forget this!
```

### Issue: Counts Don't Match Expected

**Cause:** Using `update(completed=N)` with wrong value

**Solution:**
```python
# For each task, increment by 1
tracker.update(completed=1, status="success")

# Don't do this unless you actually completed N tasks
# tracker.update(completed=5, status="success")
```

### Issue: Thread Not Stopping

**Cause:** Not calling `stop()`

**Solution:**
```python
# Always call stop()
try:
    # ... work ...
finally:
    tracker.stop()  # Signals thread to exit
```

The spinner runs in a daemon thread, so it won't prevent program exit, but it's good practice to stop cleanly.

### Issue: Progress Line Too Long

**Cause:** Long task names

**Solution:** Task names are automatically truncated to 40 chars, but you can manually shorten them:

```python
task_name = long_name[:30] + "..." if len(long_name) > 30 else long_name
with tracker.task(task_name):
    ...
```

---

## Migration Checklist

### For Each File Using _ProgressTracker:

- [ ] Replace import: `from app.modules.utils.progress_tracker import ProgressTracker`
- [ ] Replace `_ProgressTracker()` → `ProgressTracker(total=N, name="...")`
- [ ] Remove `set_total()` calls (pass to constructor)
- [ ] Replace `start_spinner()` → `start()`
- [ ] Replace `increment()` → `update(completed=1, status="success")`
- [ ] Replace `stop_spinner()` → `stop()`
- [ ] Consider using context manager pattern
- [ ] Add `try/finally` for cleanup

### For Each File Using ExtractionProgress:

- [ ] Replace import: `from app.modules.utils.progress_tracker import ProgressTracker`
- [ ] Replace `ExtractionProgress(total=N)` → `ProgressTracker(total=N, name="...")`
- [ ] Add `start()` call after construction
- [ ] Add `stop()` call at end (in finally block)
- [ ] Replace `increment(success=True)` → `update_async(completed=1, status="success")`
- [ ] Replace `increment(success=False)` → `update_async(completed=1, status="fail")`
- [ ] Consider using context manager pattern
- [ ] Remove manual print statements (tracker handles output)

---

## Examples

See `progress_tracker_example.py` for comprehensive usage examples.

---

## Summary

The new unified `ProgressTracker` system provides:

1. **One API** for all progress tracking needs
2. **Better visibility** into operation progress
3. **Safer execution** with proper thread management
4. **More features** (ETA, tokens, phases, status messages)
5. **Easier to use** with context managers

Migration is straightforward - most code changes are simple replacements. The context manager pattern is recommended for new code as it automatically handles success/fail tracking and exception handling.

For questions or issues, refer to the examples or API documentation.
