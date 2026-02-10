"""
Regeneration module for automatic retry logic and token allocation.

This module provides:
- RetryPolicy: Determines when and how to retry failed generations
- Truncation detection: Identifies incomplete LLM outputs
- AdaptiveTokenAllocator: Learns optimal token allocation per module
- invoke_with_retry: Simple retry wrapper for discovery/implementation passes
"""

from .retry_policy import RetryPolicy, FailureReason
from .truncation_detector import detect_truncation, detect_simple_truncation
from .token_strategy import AdaptiveTokenAllocator
from .retry_wrapper import invoke_with_retry

__all__ = [
    'RetryPolicy',
    'FailureReason',
    'detect_truncation',
    'detect_simple_truncation',
    'AdaptiveTokenAllocator',
    'invoke_with_retry',
]
