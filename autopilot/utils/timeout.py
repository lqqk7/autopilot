from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as _FuturesTimeoutError
from typing import Callable, TypeVar

T = TypeVar("T")


class TimeoutError(Exception):
    """Raised when a function exceeds the allowed timeout."""


def run_with_timeout(fn: Callable[[], T], timeout_seconds: int) -> T:
    """Run *fn* in a thread pool; raise TimeoutError if it doesn't finish in time.

    Uses ``concurrent.futures`` so the caller gets a proper exception without
    leaking daemon threads that silently mutate shared state after the timeout.
    The underlying thread cannot be forcibly interrupted in CPython, but the
    executor is shut down (``wait=False``) so it does not block program exit.
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn)
        try:
            return future.result(timeout=timeout_seconds)
        except _FuturesTimeoutError:
            future.cancel()
            raise TimeoutError(f"Function did not complete within {timeout_seconds}s")
