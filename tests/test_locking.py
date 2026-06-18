from pathlib import Path

import pytest

from autody.locking import SingleInstanceLock


def test_second_lock_is_rejected(tmp_path: Path):
    path = tmp_path / "run.lock"
    with SingleInstanceLock(path):
        with pytest.raises(RuntimeError, match="already running"):
            with SingleInstanceLock(path):
                pass
    assert not path.exists()
