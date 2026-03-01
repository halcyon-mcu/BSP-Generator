"""
Adaptive token allocation strategy.

Learns which modules need more tokens and adjusts allocations
for future runs to minimize truncation.
"""

import json
import statistics
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
        # Pass-specific histories (v3 format with metadata)
        # Pass 1: List of {"tokens": int, "num_modules": int} dicts (cumulative operation)
        self.pass1_history: List[Dict[str, int]] = []
        # Pass 2: Dict mapping module names to token lists (per-module operations)
        self.pass2_history: Dict[str, List[int]] = {}
        # Pass 3: Dict mapping file names to token lists (fixed overhead)
        self.pass3_history: Dict[str, List[int]] = {}

        # Legacy history (v1/v2 format) - kept for backwards compatibility
        self.module_history: Dict[str, List[int]] = {}

        # Conservative bounds to reject corrupted/outlier history values.
        self._pass1_per_module_max = 50_000
        self._pass2_token_max = 120_000
        self._pass3_token_max = 120_000

    def get_initial_tokens(self, module_name: str, default: int = 8000) -> int:
        """
        Get initial token allocation based on history.

        Args:
            module_name: Name of the module to generate
            default: Default token count if no history

        Returns:
            Recommended initial token count
        """
        # Pass 1 tokens are managed as a cumulative run-level metric and should
        # not adapt per-module from historical max values.
        if module_name.startswith("pass1_"):
            return default

        if module_name not in self.module_history:
            return default

        history = self.module_history[module_name]
        if not history:
            return default

        # Use robust median (not max) with modest buffer to avoid runaway growth.
        median_historical = int(statistics.median(history))
        return int(median_historical * 1.15)

    def record_success(self, module_name: str, tokens_used: int, num_modules: int = 1):
        """
        Record successful generation with token count.

        Categorizes by pass type based on naming convention:
        - pass1_*: Pass 1 (manifest + header generation) - cumulative operation
        - pass2_*: Pass 2 (driver implementation) - per-module operation
        - pass3_*: Pass 3 (platform files) - fixed overhead

        Args:
            module_name: Name of the module that succeeded
            tokens_used: Approximate token count used
            num_modules: Number of modules (only relevant for Pass 1)
        """
        if not isinstance(tokens_used, int) or tokens_used <= 0:
            return

        # Detect pass type from naming convention
        if module_name.startswith("pass1_") or (not module_name.startswith("pass2_") and not module_name.startswith("pass3_")):
            # Pass 1: Store as cumulative operation with module count
            # Only record once per pass (not per module)
            if module_name.startswith("pass1_"):
                if num_modules <= 0:
                    return

                # Reject clearly corrupted pass1 entries.
                per_module = tokens_used / max(num_modules, 1)
                if per_module > self._pass1_per_module_max:
                    return

                # This should be one cumulative record per run.
                if not self.pass1_history or self.pass1_history[-1]["tokens"] != tokens_used:
                    self.pass1_history.append({
                        "tokens": tokens_used,
                        "num_modules": num_modules
                    })
                    # Keep only last 5 runs
                    if len(self.pass1_history) > 5:
                        self.pass1_history = self.pass1_history[-5:]
        elif module_name.startswith("pass2_"):
            if tokens_used > self._pass2_token_max:
                return
            # Pass 2: Store per-module
            if module_name not in self.pass2_history:
                self.pass2_history[module_name] = []
            self.pass2_history[module_name].append(tokens_used)
            # Keep only last 5 runs
            if len(self.pass2_history[module_name]) > 5:
                self.pass2_history[module_name] = self.pass2_history[module_name][-5:]
        elif module_name.startswith("pass3_"):
            if tokens_used > self._pass3_token_max:
                return
            # Pass 3: Store per-file
            if module_name not in self.pass3_history:
                self.pass3_history[module_name] = []
            self.pass3_history[module_name].append(tokens_used)
            # Keep only last 5 runs
            if len(self.pass3_history[module_name]) > 5:
                self.pass3_history[module_name] = self.pass3_history[module_name][-5:]

        # Also update legacy module_history for backwards compatibility
        # Legacy module history should not track pass1 entries (they caused
        # feedback loops in token sizing). Keep for pass2/pass3 only.
        if not module_name.startswith("pass1_"):
            if module_name not in self.module_history:
                self.module_history[module_name] = []
            self.module_history[module_name].append(tokens_used)
            if len(self.module_history[module_name]) > 5:
                self.module_history[module_name] = self.module_history[module_name][-5:]

    def save_history(self, path: Path):
        """
        Save token history to JSON file (v3 format with module counts for Pass 1).

        Args:
            path: Path to save history file
        """
        try:
            data = {
                "version": 3,  # Version identifier
                "pass1": self.pass1_history,  # List of {"tokens": int, "num_modules": int}
                "pass2": self.pass2_history,  # Dict[str, List[int]]
                "pass3": self.pass3_history,  # Dict[str, List[int]]
                "legacy": self.module_history  # Backwards compatibility
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[warn] Could not save token history: {e}")

    def load_history(self, path: Path):
        """
        Load token history from previous runs (auto-migrates from v1/v2 to v3).

        Args:
            path: Path to history file
        """
        if not path.exists():
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            version = data.get("version", 1) if isinstance(data, dict) else 1

            if version == 3:
                # V3 FORMAT: Pass 1 is list of dicts with module counts
                self.pass1_history = data.get("pass1", [])
                self.pass2_history = data.get("pass2", {})
                self.pass3_history = data.get("pass3", {})
                self.module_history = data.get("legacy", {})
                self._sanitize_histories()
            elif version == 2:
                # V2 FORMAT: Pass 1 is dict with duplicate values - convert to v3
                pass1_dict = data.get("pass1", {})
                self.pass2_history = data.get("pass2", {})
                self.pass3_history = data.get("pass3", {})
                self.module_history = data.get("legacy", {})

                # Convert v2 Pass 1 to v3: extract unique token values with estimated module counts
                if pass1_dict:
                    # Get all token values from all modules (they should be the same for each run)
                    all_values = []
                    for history in pass1_dict.values():
                        all_values.extend(history)

                    # Find unique values (each represents a distinct run)
                    unique_tokens = sorted(set(all_values))

                    # Estimate num_modules from how many entries had same token count
                    self.pass1_history = []
                    for tokens in unique_tokens[-5:]:  # Keep only last 5
                        # Count how many modules recorded this value
                        count = sum(1 for history in pass1_dict.values() if tokens in history)
                        self.pass1_history.append({
                            "tokens": tokens,
                            "num_modules": count  # Estimate from duplicate count
                        })
                self._sanitize_histories()
            else:
                # V1 FORMAT: Flat dict - migrate to v3
                self.module_history = data if isinstance(data, dict) else {}
                self.pass1_history = []
                self.pass2_history = {}
                self.pass3_history = {}

                # Auto-categorize based on naming convention
                for name, history in self.module_history.items():
                    if name.startswith("pass2_"):
                        self.pass2_history[name] = history
                    elif name.startswith("pass3_"):
                        self.pass3_history[name] = history
                    # Skip pass1_ entries - they'll be re-recorded properly in v3 format
                self._sanitize_histories()
        except Exception as e:
            print(f"[warn] Could not load token history: {e}")
            self.module_history = {}
            self.pass1_history = []
            self.pass2_history = {}
            self.pass3_history = {}

    def _sanitize_histories(self):
        """Drop stale/outlier entries so estimates remain stable."""
        cleaned_pass1 = []
        for entry in self.pass1_history:
            if not isinstance(entry, dict):
                continue
            tokens = int(entry.get("tokens", 0) or 0)
            modules = int(entry.get("num_modules", 0) or 0)
            if tokens <= 0 or modules <= 0:
                continue
            if (tokens / modules) > self._pass1_per_module_max:
                continue
            cleaned_pass1.append({"tokens": tokens, "num_modules": modules})
        self.pass1_history = cleaned_pass1[-5:]

        cleaned_pass2: Dict[str, List[int]] = {}
        for name, vals in self.pass2_history.items():
            if not isinstance(vals, list):
                continue
            filtered = [int(v) for v in vals if isinstance(v, int) and 0 < v <= self._pass2_token_max]
            if filtered:
                cleaned_pass2[name] = filtered[-5:]
        self.pass2_history = cleaned_pass2

        cleaned_pass3: Dict[str, List[int]] = {}
        for name, vals in self.pass3_history.items():
            if not isinstance(vals, list):
                continue
            filtered = [int(v) for v in vals if isinstance(v, int) and 0 < v <= self._pass3_token_max]
            if filtered:
                cleaned_pass3[name] = filtered[-5:]
        self.pass3_history = cleaned_pass3

        cleaned_legacy: Dict[str, List[int]] = {}
        for name, vals in self.module_history.items():
            if name.startswith("pass1_") or not isinstance(vals, list):
                continue
            filtered = [int(v) for v in vals if isinstance(v, int) and 0 < v <= max(self._pass2_token_max, self._pass3_token_max)]
            if filtered:
                cleaned_legacy[name] = filtered[-5:]
        self.module_history = cleaned_legacy

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
        Estimate the cost of generating modules with accurate pass-specific calculations.

        Uses separate averages for each pass to provide realistic estimates:
        - Pass 1: Manifest + headers (cumulative: ~60-100k base + ~3k per module)
        - Pass 2: Driver implementations (~8-20k per module)
        - Pass 3: Platform files (~58-60k total fixed overhead)

        Args:
            num_modules: Number of modules to generate
            model_pricing: Tuple of (input_price_per_million, output_price_per_million)
            default_tokens: Default tokens per module if no history

        Returns:
            Dictionary with estimated input/output tokens and cost
        """
        input_price, output_price = model_pricing

        # Calculate Pass 1 total (manifest generation is ONE cumulative operation)
        # Pass 1 generates a SINGLE manifest with all modules, not per-module files
        # Use per-module average from history to scale for different project sizes
        if self.pass1_history:
            # Calculate per-module averages from historical runs
            per_module_averages = []
            for entry in self.pass1_history:
                tokens = entry.get("tokens", 0)
                modules = entry.get("num_modules", 1)
                if modules > 0:
                    per_module_averages.append(tokens / modules)

            if per_module_averages:
                # Use median per-module cost and scale to current project.
                avg_per_module = int(statistics.median(per_module_averages))
                pass1_total = avg_per_module * num_modules
                avg_pass1 = avg_per_module
            else:
                # Fallback if history is malformed
                base_tokens = 60000
                per_module_overhead = 3000
                pass1_total = base_tokens + (per_module_overhead * num_modules)
                avg_pass1 = pass1_total
        else:
            # Fallback: Pass 1 is cumulative, not per-module. Base estimate with modest scaling.
            # Typical observed: 60k-100k tokens for small projects (1-10 modules)
            base_tokens = 60000  # Base cost for manifest generation
            per_module_overhead = 3000  # Small incremental cost per additional module
            pass1_total = base_tokens + (per_module_overhead * num_modules)
            avg_pass1 = pass1_total

        # Calculate Pass 2 average (driver implementations - these ARE per-module)
        if self.pass2_history:
            pass2_tokens_list = [token for history in self.pass2_history.values() for token in history]
            avg_pass2 = int(statistics.median(pass2_tokens_list))
        else:
            # Fallback: Typical observed Pass 2 usage is 8-20k tokens per driver
            avg_pass2 = 12000  # Conservative middle estimate

        # Calculate Pass 3 total (platform files - fixed set of 5 files)
        if self.pass3_history:
            # Use median per platform file to avoid outlier spikes.
            pass3_overhead = sum(int(statistics.median(history)) for history in self.pass3_history.values() if history)
        else:
            # Fallback: Conservative estimate for 5 platform files
            pass3_overhead = 60_000

        # Calculate Pass 2 total (per-module generation)
        pass2_total = num_modules * avg_pass2

        total_estimated_tokens = pass1_total + pass2_total + pass3_overhead

        # Apply bounded safety factor so pre-run estimate better reflects retry
        # overhead and prompt variability without drifting per run.
        has_history = bool(self.pass1_history or self.pass2_history or self.pass3_history)
        safety_factor = 1.25 if has_history else 1.5
        total_estimated_tokens = int(total_estimated_tokens * safety_factor)

        # Input/output ratio (observed: 75/25)
        estimated_input_tokens = int(total_estimated_tokens * 0.75)
        estimated_output_tokens = int(total_estimated_tokens * 0.25)

        # Calculate costs
        input_cost = (estimated_input_tokens / 1_000_000) * input_price
        output_cost = (estimated_output_tokens / 1_000_000) * output_price
        total_cost = input_cost + output_cost

        return {
            "num_modules": num_modules,
            "total_tokens": total_estimated_tokens,
            "input_tokens": estimated_input_tokens,
            "output_tokens": estimated_output_tokens,
            "cost_usd": total_cost,
            "has_history": has_history,
            "breakdown": {
                "pass1_tokens": pass1_total,
                "pass1_note": "cumulative (one manifest for all modules)",
                "pass2_tokens": pass2_total,
                "pass2_avg": avg_pass2,
                "pass3_tokens": pass3_overhead,
                "safety_factor": safety_factor,
            }
        }
