from pathlib import Path
import time

import pytest

from autody.locking import SingleInstanceLock, TaskAlreadyRunning


def test_second_task_is_rejected_by_same_global_lock(tmp_path: Path):
    lock_path = tmp_path / "data" / "locks" / "autody.lock"

    with SingleInstanceLock(lock_path):
        with pytest.raises(TaskAlreadyRunning, match="已有 AutoDy 任务正在运行"):
            with SingleInstanceLock(lock_path):
                pass


def test_lock_wait_has_a_bounded_timeout(tmp_path: Path):
    lock_path = tmp_path / "data" / "locks" / "autody.lock"

    with SingleInstanceLock(lock_path):
        started = time.monotonic()
        with pytest.raises(TaskAlreadyRunning):
            with SingleInstanceLock(lock_path, timeout_seconds=0.04, poll_interval=0.01):
                pass

    assert time.monotonic() - started >= 0.03


def test_keyboard_interrupt_releases_the_browser_lock(tmp_path: Path):
    lock_path = tmp_path / "data" / "locks" / "autody.lock"

    with pytest.raises(KeyboardInterrupt):
        with SingleInstanceLock(lock_path):
            raise KeyboardInterrupt

    with SingleInstanceLock(lock_path):
        pass
