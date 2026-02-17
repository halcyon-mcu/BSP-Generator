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

    def estimate_cost(self, num_modules: int, model_pricing: tuple, default_tokens: int = 20000) -> dict:
        """
        Estimate the cost of generating modules based on historical data.

        Args:
            num_modules: Number of modules to generate
            model_pricing: Tuple of (input_price_per_million, output_price_per_million)
            default_tokens: Default tokens per module if no history

        Returns:
            Dictionary with estimated input/output tokens and cost
        """
        input_price, output_price = model_pricing

        # Calculate average tokens from history
        if self.module_history:
            all_tokens = [token for history in self.module_history.values() for token in history]
            avg_tokens_per_module = int(sum(all_tokens) / len(all_tokens)) if all_tokens else default_tokens
        else:
            avg_tokens_per_module = default_tokens

        # Estimate token usage (rough approximation: 60% input, 40% output ratio)
        estimated_input_tokens = int(num_modules * avg_tokens_per_module * 0.6)
        estimated_output_tokens = int(num_modules * avg_tokens_per_module * 0.4)

        # Calculate costs
        input_cost = (estimated_input_tokens / 1_000_000) * input_price
        output_cost = (estimated_output_tokens / 1_000_000) * output_price
        total_cost = input_cost + output_cost

        return {
            "input_tokens": estimated_input_tokens,
            "output_tokens": estimated_output_tokens,
            "total_tokens": estimated_input_tokens + estimated_output_tokens,
            "cost_usd": total_cost,
            "avg_tokens_per_module": avg_tokens_per_module,
            "num_modules": num_modules,
            "has_history": bool(self.module_history)
        }
