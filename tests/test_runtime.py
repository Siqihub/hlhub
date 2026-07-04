import os
from pathlib import Path

from autody.runtime import configure_runtime


def test_configure_runtime_uses_project_local_playwright_directory(
    tmp_path: Path, monkeypatch
):
    for name in (
        "AUTODY_HOME",
        "PLAYWRIGHT_BROWSERS_PATH",
        "PLAYWRIGHT_SKIP_BROWSER_GC",
    ):
        monkeypatch.delenv(name, raising=False)

    runtime = configure_runtime(tmp_path)

    assert runtime.home == tmp_path.resolve()
    assert runtime.browsers_path == tmp_path.resolve() / "data" / "ms-playwright"
    assert os.environ["AUTODY_HOME"] == str(tmp_path.resolve())
    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == str(runtime.browsers_path)
    assert os.environ["PLAYWRIGHT_SKIP_BROWSER_GC"] == "1"


def test_configure_runtime_overrides_appdata_playwright_path(
    tmp_path: Path, monkeypatch
):
    default_path = r"C:\Users\Administrator\AppData\Local\ms-playwright"
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", default_path)

    runtime = configure_runtime(tmp_path)

    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == str(runtime.browsers_path)
    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] != default_path
