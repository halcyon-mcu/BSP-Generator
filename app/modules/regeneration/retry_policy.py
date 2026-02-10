"""
Retry policy for automatic regeneration of failed modules.

Handles different failure modes with appropriate retry strategies:
- Token truncation: Double tokens up to 32K
- FACTS MIRROR TODOs: Retry once with more context
- Validation errors: Retry once with error feedback
- Transient errors: Retry immediately
"""

from dataclasses import dataclass
from enum import Enum


class FailureReason(Enum):
    """Types of failures that can occur during generation"""
    TOKEN_TRUNCATION = "truncation"
    FACTS_MIRROR_TODO = "facts_todo"
    VALIDATION_ERROR = "validation"
    COMPILATION_ERROR = "compilation"
    TRANSIENT_ERROR = "transient"


@dataclass
class RetryPolicy:
    """
    Policy for retrying failed module generation.

    Attributes:
        max_retries: Maximum number of retry attempts (default: 3)
        token_escalation: Whether to increase tokens on retry (default: True)
    """
    max_retries: int = 3
    token_escalation: bool = True

    def should_retry(
        self,
        attempt: int,
        failure_reason: FailureReason,
        previous_token_count: int
    ) -> tuple[bool, int]:
        """
        Determine if module generation should be retried.

        Args:
            attempt: Current attempt number (1-indexed)
            failure_reason: The reason for failure
            previous_token_count: Token count from previous attempt

        Returns:
            Tuple of (should_retry: bool, new_max_tokens: int)
        """
        if attempt >= self.max_retries:
            return (False, previous_token_count)

        # Token truncation: Double tokens each retry (cap at 32K)
        if failure_reason == FailureReason.TOKEN_TRUNCATION:
            new_tokens = previous_token_count * 2
            new_tokens = min(new_tokens, 32000)  # Cap at 32K
            return (True, new_tokens)

        # FACTS MIRROR TODOs: Retry once with more context
        if failure_reason == FailureReason.FACTS_MIRROR_TODO:
            if attempt == 1:
                # First retry: add more YAML context
                new_tokens = previous_token_count + 4000
                return (True, new_tokens)
            else:
                # If still TODOs after retry, likely missing from YAML
                return (False, previous_token_count)

        # Validation errors: Retry once with explicit prompt
        if failure_reason == FailureReason.VALIDATION_ERROR:
            if attempt == 1:
                new_tokens = previous_token_count + 2000
                return (True, new_tokens)
            else:
                return (False, previous_token_count)

        # Transient errors (API timeouts): Always retry with same tokens
        if failure_reason == FailureReason.TRANSIENT_ERROR:
            return (True, previous_token_count)

        # Compilation errors: Don't retry (indicates YAML data issue)
        if failure_reason == FailureReason.COMPILATION_ERROR:
            return (False, previous_token_count)

        # Default: don't retry
        return (False, previous_token_count)
