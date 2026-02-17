"""
Progress Tracker Usage Examples

This file demonstrates various usage patterns for the unified ProgressTracker system.
These examples show how to replace existing _ProgressTracker and ExtractionProgress
implementations with the new unified system.
"""

import asyncio
import time
from progress_tracker import (
    ProgressTracker,
    SimpleProgressTracker,
    ProgressLevel,
    ProgressPhase,
    create_progress_tracker
)


# ==============================================================================
# Example 1: Basic Synchronous Usage (replacing _ProgressTracker)
# ==============================================================================

def example_basic_sync():
    """Basic synchronous progress tracking."""
    print("\n" + "=" * 80)
    print("Example 1: Basic Synchronous Usage")
    print("=" * 80 + "\n")

    # Create tracker for 10 tasks
    tracker = ProgressTracker(total=10, name="Driver Generation", enable_spinner=True)
    tracker.start()

    # Process tasks
    for i in range(10):
        # Simulate work
        time.sleep(0.2)

        # Update progress
        status = "success" if i % 7 != 0 else "fail"
        tracker.update(completed=1, status=status)

    # Stop and show summary
    tracker.stop()


# ==============================================================================
# Example 2: Context Manager Usage (recommended pattern)
# ==============================================================================

def example_context_manager():
    """Using context manager for automatic task tracking."""
    print("\n" + "=" * 80)
    print("Example 2: Context Manager Usage")
    print("=" * 80 + "\n")

    drivers = ["GIO", "UART", "SPI", "I2C", "ADC"]
    tracker = ProgressTracker(total=len(drivers), name="Generation")
    tracker.start()

    for driver_name in drivers:
        try:
            with tracker.task(f"Generating {driver_name}", phase="Implementation"):
                # Simulate driver generation
                time.sleep(0.3)

                # Simulate occasional error
                if driver_name == "ADC":
                    raise Exception("Simulated generation error")

        except Exception as e:
            # Error is automatically tracked by context manager
            tracker.set_status(f"{driver_name} failed: {e}", level="error")

    tracker.stop()


# ==============================================================================
# Example 3: Async Usage with Concurrent Tasks
# ==============================================================================

async def example_async_concurrent():
    """Async progress tracking with concurrent tasks."""
    print("\n" + "=" * 80)
    print("Example 3: Async Concurrent Usage")
    print("=" * 80 + "\n")

    # Create tracker
    tracker = ProgressTracker(
        total=20,
        name="Async Generation",
        enable_spinner=True,
        track_tokens=False
    )
    tracker.start()

    # Define async task
    async def generate_driver(name: str, index: int):
        await asyncio.sleep(0.1 + (index % 3) * 0.1)  # Variable duration
        status = "success" if index % 5 != 0 else "fail"
        await tracker.update_async(completed=1, status=status)

    # Run tasks concurrently
    tasks = [generate_driver(f"Driver_{i}", i) for i in range(20)]
    await asyncio.gather(*tasks, return_exceptions=True)

    tracker.stop()


# ==============================================================================
# Example 4: Token Tracking (for API usage)
# ==============================================================================

def example_token_tracking():
    """Progress tracking with API token usage monitoring."""
    print("\n" + "=" * 80)
    print("Example 4: Token Tracking")
    print("=" * 80 + "\n")

    tracker = ProgressTracker(
        total=5,
        name="API Extraction",
        enable_spinner=True,
        track_tokens=True  # Enable token tracking
    )
    tracker.start()

    for i in range(5):
        # Simulate API call with token usage
        time.sleep(0.2)

        # Track tokens (simulated)
        input_tokens = 1000 + i * 200
        output_tokens = 500 + i * 100
        tracker.add_tokens(input_tokens, output_tokens)

        # Update progress
        tracker.update(completed=1, status="success")

    tracker.stop()


# ==============================================================================
# Example 5: Status Messages and Phases
# ==============================================================================

def example_status_messages():
    """Using status messages and phases."""
    print("\n" + "=" * 80)
    print("Example 5: Status Messages and Phases")
    print("=" * 80 + "\n")

    tracker = ProgressTracker(total=4, name="Multi-Phase Build")
    tracker.start()

    # Phase 1: Discovery
    tracker.current_phase = "Discovery"
    tracker.set_status("Scanning YAML files...", level="info")
    time.sleep(0.3)
    tracker.update(completed=1, status="success")

    # Phase 2: Validation
    tracker.current_phase = "Validation"
    tracker.set_status("Validating register definitions...", level="info")
    time.sleep(0.3)
    tracker.update(completed=1, status="success")

    # Phase 3: Generation
    tracker.current_phase = "Implementation"
    tracker.set_status("Generating driver code...", level="info")
    time.sleep(0.3)
    tracker.update(completed=1, status="success")

    # Phase 4: Compilation
    tracker.current_phase = "Validation"
    tracker.set_status("Compiling generated code...", level="ok")
    time.sleep(0.3)
    tracker.update(completed=1, status="success")

    tracker.stop()


# ==============================================================================
# Example 6: SimpleProgressTracker (async-only, no spinner)
# ==============================================================================

async def example_simple_tracker():
    """Using SimpleProgressTracker for minimal overhead."""
    print("\n" + "=" * 80)
    print("Example 6: SimpleProgressTracker")
    print("=" * 80 + "\n")

    tracker = SimpleProgressTracker(total=8, name="Quick Processing")
    await tracker.start()

    for i in range(8):
        await asyncio.sleep(0.1)
        success = i % 4 != 0
        await tracker.update(success=success)

    await tracker.finish()


# ==============================================================================
# Example 7: Migration from _ProgressTracker
# ==============================================================================

def example_migration_from_old():
    """
    Migration example showing how to replace _ProgressTracker.

    OLD CODE (_ProgressTracker):
        tracker = _ProgressTracker()
        tracker.set_total(10)
        spinner = tracker.start_spinner()
        for i in range(10):
            # do work
            completed, total = tracker.increment()
            print(f"Progress: {completed}/{total}")
        tracker.stop_spinner()

    NEW CODE (ProgressTracker):
        tracker = ProgressTracker(total=10, name="Generation")
        tracker.start()
        for i in range(10):
            # do work
            tracker.update(completed=1, status="success")
        tracker.stop()
    """
    print("\n" + "=" * 80)
    print("Example 7: Migration from _ProgressTracker")
    print("=" * 80 + "\n")

    # New unified tracker
    tracker = ProgressTracker(total=10, name="Migration Example")
    tracker.start()

    for i in range(10):
        time.sleep(0.15)
        tracker.update(completed=1, status="success")

    tracker.stop()


# ==============================================================================
# Example 8: Migration from ExtractionProgress
# ==============================================================================

async def example_migration_from_extraction():
    """
    Migration example showing how to replace ExtractionProgress.

    OLD CODE (ExtractionProgress):
        progress = ExtractionProgress(total=5)
        for task in tasks:
            # do work
            success = process_task(task)
            await progress.increment(success=success)

    NEW CODE (ProgressTracker):
        tracker = ProgressTracker(total=5, name="Extraction")
        tracker.start()
        for task in tasks:
            # do work
            success = process_task(task)
            status = "success" if success else "fail"
            await tracker.update_async(completed=1, status=status)
        tracker.stop()
    """
    print("\n" + "=" * 80)
    print("Example 8: Migration from ExtractionProgress")
    print("=" * 80 + "\n")

    # New unified tracker
    tracker = ProgressTracker(total=5, name="Extraction")
    tracker.start()

    for i in range(5):
        await asyncio.sleep(0.2)
        success = i % 3 != 0
        status = "success" if success else "fail"
        await tracker.update_async(completed=1, status=status)

    tracker.stop()


# ==============================================================================
# Example 9: Factory Function Usage
# ==============================================================================

def example_factory_function():
    """Using factory function for backward compatibility."""
    print("\n" + "=" * 80)
    print("Example 9: Factory Function")
    print("=" * 80 + "\n")

    # Create tracker using factory function
    tracker = create_progress_tracker(
        total=7,
        name="Factory Test",
        enable_spinner=True,
        track_tokens=False
    )

    tracker.start()

    for i in range(7):
        time.sleep(0.15)
        tracker.update(completed=1, status="success")

    tracker.stop()


# ==============================================================================
# Example 10: Error Handling and Cleanup
# ==============================================================================

def example_error_handling():
    """Proper error handling and cleanup."""
    print("\n" + "=" * 80)
    print("Example 10: Error Handling")
    print("=" * 80 + "\n")

    tracker = ProgressTracker(total=5, name="Error Test")
    tracker.start()

    try:
        for i in range(5):
            try:
                with tracker.task(f"Task {i+1}", phase="Processing"):
                    time.sleep(0.2)

                    # Simulate error on task 3
                    if i == 2:
                        raise RuntimeError("Simulated error in task 3")

            except RuntimeError as e:
                tracker.set_status(f"Task {i+1} failed: {e}", level="error")

    finally:
        # Always stop tracker, even if exception occurs
        tracker.stop()


# ==============================================================================
# Main
# ==============================================================================

def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("PROGRESS TRACKER USAGE EXAMPLES")
    print("=" * 80)

    # Run synchronous examples
    example_basic_sync()
    example_context_manager()
    example_token_tracking()
    example_status_messages()
    example_migration_from_old()
    example_factory_function()
    example_error_handling()

    # Run async examples
    asyncio.run(example_async_concurrent())
    asyncio.run(example_simple_tracker())
    asyncio.run(example_migration_from_extraction())

    print("\n" + "=" * 80)
    print("ALL EXAMPLES COMPLETE")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
