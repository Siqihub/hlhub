from pathlib import Path

import pytest

from autody.locking import SingleInstanceLock, TaskAlreadyRunning


def test_second_task_is_rejected_by_same_global_lock(tmp_path: Path):
    lock_path = tmp_path / "data" / "locks" / "autody.lock"

    with SingleInstanceLock(lock_path):
        with pytest.raises(TaskAlreadyRunning, match="已有 AutoDy 任务正在运行"):
            with SingleInstanceLock(lock_path):
                pass
