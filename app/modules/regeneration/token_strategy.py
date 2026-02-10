"""
Adaptive token allocation strategy.

Learns which modules need more tokens and adjusts allocations
for future runs to minimize truncation.
"""

import json
from pathlib import Path
from typing import Dict, List


class AdaptiveTokenAllocator:
    """
    Learns optimal token allocation per module.

    Maintains history of successful token counts and provides
    adaptive initial allocations with 20% safety buffer.
    """

    def __init__(self):
        """Initialize with empty history."""
        self.module_history: Dict[str, List[int]] = {}

    def get_initial_tokens(self, module_name: str, default: int = 8000) -> int:
        """
        Get initial token allocation based on history.

        Args:
            module_name: Name of the module to generate
            default: Default token count if no history

        Returns:
            Recommended initial token count
        """
        if module_name not in self.module_history:
            return default

        history = self.module_history[module_name]
        if not history:
            return default

        # Use max tokens from previous successful runs with 20% buffer
        max_historical = max(history)
        return int(max_historical * 1.2)

    def record_success(self, module_name: str, tokens_used: int):
        """
        Record successful generation with token count.

        Args:
            module_name: Name of the module that succeeded
            tokens_used: Approximate token count used
        """
        if module_name not in self.module_history:
            self.module_history[module_name] = []

        self.module_history[module_name].append(tokens_used)

        # Keep only last 5 successful runs
        if len(self.module_history[module_name]) > 5:
            self.module_history[module_name] = self.module_history[module_name][-5:]

    def save_history(self, path: Path):
        """
        Save token history to JSON file.

        Args:
            path: Path to save history file
        """
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.module_history, f, indent=2)
        except Exception as e:
            print(f"[warn] Could not save token history: {e}")

    def load_history(self, path: Path):
        """
        Load token history from previous runs.

        Args:
            path: Path to history file
        """
        if not path.exists():
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.module_history = json.load(f)
        except Exception as e:
            print(f"[warn] Could not load token history: {e}")
            self.module_history = {}

    def get_statistics(self) -> Dict[str, Dict[str, int]]:
        """
        Get statistics about token usage.

        Returns:
            Dictionary mapping module names to stats (min, max, avg)
        """
        stats = {}

        for module_name, history in self.module_history.items():
            if history:
                stats[module_name] = {
                    'min': min(history),
                    'max': max(history),
                    'avg': int(sum(history) / len(history)),
                    'runs': len(history)
                }

        return stats
