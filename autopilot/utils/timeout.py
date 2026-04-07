from __future__ import annotations

import threading
from typing import Callable, TypeVar

T = TypeVar("T")


class TimeoutError(Exception):
    """Raised when a function exceeds the timeout."""


def run_with_timeout(fn: Callable[[], T], timeout_seconds: int) -> T:
    """Run fn in a thread; raise TimeoutError if it doesn't finish in time."""
    result: list[T] = []
    exception: list[BaseException] = []

    def target() -> None:
        try:
            result.append(fn())
        except Exception as e:
            exception.append(e)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)

    if thread.is_alive():
        raise TimeoutError(f"Function did not complete within {timeout_seconds}s")
    if exception:
        raise exception[0]
    return result[0]
