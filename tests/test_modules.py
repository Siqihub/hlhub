from pathlib import Path

import pytest

from autody.modules import (
    MODULE_ID,
    ModuleManager,
    ModulePackageError,
    build_module_archive,
)


def test_test_center_is_uninstalled_by_default(tmp_path: Path):
    manager = ModuleManager(tmp_path, core_version="1.2.0")

    status = manager.status()

    assert status["id"] == MODULE_ID
    assert status["installed"] is False
    assert not (tmp_path / "modules" / MODULE_ID).exists()


def test_valid_official_package_installs_and_uninstalls_cleanly(tmp_path: Path):
    package = build_module_archive(tmp_path / "AutoDy-Test-Center.autody-module.zip", version="1.0.0")
    manager = ModuleManager(tmp_path, core_version="1.2.0")

    installed = manager.install(package)
    module_root = tmp_path / "modules" / MODULE_ID
    (module_root / "data" / "history.jsonl").write_text("fixture", encoding="utf-8")
    (module_root / "data" / "settings.json").write_text("{}", encoding="utf-8")

    assert installed["installed"] is True
    assert (module_root / "manifest.json").is_file()
    assert manager.uninstall() is True
    assert not module_root.exists()
    assert manager.status()["installed"] is False


@pytest.mark.parametrize(
    "mutate, expected",
    [
        ("traversal", "非法文件路径"),
        ("publisher", "发布者"),
        ("checksum", "校验"),
    ],
)
def test_invalid_module_package_is_rejected_without_creating_module_data(tmp_path: Path, mutate: str, expected: str):
    package = build_module_archive(tmp_path / "invalid.autody-module.zip", version="1.0.0", mutate=mutate)
    manager = ModuleManager(tmp_path, core_version="1.2.0")

    with pytest.raises(ModulePackageError, match=expected):
        manager.install(package)

    assert manager.status()["installed"] is False
    assert not (tmp_path / "modules" / MODULE_ID).exists()
