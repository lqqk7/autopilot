from __future__ import annotations

from autopilot.backends.base import BackendResult, ErrorType


def exponential_backoff(attempt: int, base: float = 10.0) -> float:
    """Return wait seconds: min(base * 2^attempt, 120.0)."""
    return min(base * (2 ** attempt), 120.0)


def handle_error(result: BackendResult, retry_count: int) -> tuple[bool, float]:
    """Return (should_retry, wait_seconds) based on error type and retry count.

    Args:
        result: The failed BackendResult.
        retry_count: How many times this error type has already been retried (0-indexed).
    """
    et = result.error_type

    if et == ErrorType.rate_limit:
        if retry_count < 3:
            return True, exponential_backoff(retry_count)
        return False, 0.0

    if et == ErrorType.quota_exhausted:
        return False, 0.0

    if et == ErrorType.server_error:
        if retry_count < 3:
            return True, exponential_backoff(retry_count)
        return False, 0.0

    if et == ErrorType.context_overflow:
        return False, 0.0

    if et == ErrorType.timeout:
        # Allow 1 local retry (transient infra hiccup), then give up.
        # Callers should set generous timeouts — repeated timeout = real failure.
        if retry_count < 1:
            return True, 0.0
        return False, 0.0

    if et == ErrorType.parse_error:
        if retry_count < 3:
            return True, 0.0
        return False, 0.0

    # unknown or None
    return True, 0.0


#: Error types that are retried locally within run_phase (not via phase_retries)
LOCAL_RETRY_TYPES: tuple[ErrorType, ...] = (
    ErrorType.rate_limit,
    ErrorType.server_error,
    ErrorType.parse_error,
    ErrorType.timeout,
)
