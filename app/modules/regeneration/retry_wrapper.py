"""
Simple retry wrapper for discovery and implementation passes.

Provides retry logic that works with raw LLM text output,
allowing existing parsing logic to remain unchanged.
"""

from typing import Optional, Callable, Any
from .retry_policy import RetryPolicy, FailureReason
from .truncation_detector import detect_simple_truncation


async def invoke_with_retry(
    invoke_func: Callable,
    initial_max_tokens: int,
    retry_policy: Optional[RetryPolicy] = None,
    module_name: str = "unknown"
) -> tuple[Any, bool]:
    """
    Generic retry wrapper for LLM invocations.

    Args:
        invoke_func: Async function that takes max_tokens and returns response
        initial_max_tokens: Initial token allocation
        retry_policy: Retry policy (default: RetryPolicy())
        module_name: Module name for logging

    Returns:
        Tuple of (result, success)
            - result: Return value from invoke_func (could be text, JSON, etc.)
            - success: True if generation succeeded, False otherwise
    """
    if retry_policy is None:
        retry_policy = RetryPolicy()

    max_tokens = initial_max_tokens

    for attempt in range(retry_policy.max_retries + 1):
        if attempt > 0:
            print(f"[retry] Attempt {attempt + 1} for {module_name} (tokens: {max_tokens})")

        try:
            # Invoke the generation function
            result = await invoke_func(max_tokens)

            # If result is string, check for truncation
            if isinstance(result, str):
                truncation_reason = detect_simple_truncation(result)
                if truncation_reason:
                    print(f"[warn] Truncation detected: {truncation_reason}")
                    should_retry, max_tokens = retry_policy.should_retry(
                        attempt + 1,
                        FailureReason.TOKEN_TRUNCATION,
                        max_tokens
                    )
                    if should_retry:
                        continue
                    else:
                        return (result, False)

            # Success
            return (result, True)

        except Exception as e:
            # Transient error
            print(f"[warn] Error in {module_name}: {e}")
            should_retry, max_tokens = retry_policy.should_retry(
                attempt + 1,
                FailureReason.TRANSIENT_ERROR,
                max_tokens
            )
            if should_retry:
                continue
            else:
                return (None, False)

    # Max retries exceeded
    return (None, False)


def create_retry_wrapper(invoke_model_func, model, messages_or_prompt):
    """
    Helper to create a closure for invoke_with_retry.

    Args:
        invoke_model_func: The invoke_model function from prompt.py
        model: Model enum
        messages_or_prompt: Either messages list or prompt string

    Returns:
        Async function that takes max_tokens and returns response
    """
    async def wrapped(max_tokens: int):
        if isinstance(messages_or_prompt, str):
            messages = [{"role": "user", "content": messages_or_prompt}]
        else:
            messages = messages_or_prompt
        return await invoke_model_func(model, max_tokens, messages)

    return wrapped
