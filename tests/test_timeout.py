import time
import pytest
from autopilot.utils.timeout import run_with_timeout, TimeoutError


def test_run_with_timeout_success():
    def fast_fn():
        return "done"
    result = run_with_timeout(fast_fn, timeout_seconds=5)
    assert result == "done"


def test_run_with_timeout_raises():
    def slow_fn():
        time.sleep(10)
        return "never"
    with pytest.raises(TimeoutError):
        run_with_timeout(slow_fn, timeout_seconds=1)
