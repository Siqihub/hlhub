from pathlib import Path
import threading

import pytest

from autody.web_actions import ActionAlreadyRunning, ActionManager


def test_action_manager_rejects_second_browser_action_while_first_runs(tmp_path: Path):
    started = threading.Event()
    release = threading.Event()

    def execute(_command, **_kwargs):
        started.set()
        release.wait(timeout=5)
        return type("Completed", (), {"returncode": 0})()

    manager = ActionManager(tmp_path, tmp_path / "config.yaml", executor=execute)
    manager.start("run")
    assert started.wait(timeout=2)

    for action in ["health-check", "login", "scan-friends", "refresh-friend-avatars", "repair-playwright"]:
        with pytest.raises(ActionAlreadyRunning):
            manager.start(action)

    release.set()
