from pathlib import Path


def test_installer_creates_environment_browser_and_shortcut():
    text = Path("scripts/install.ps1").read_text(encoding="utf-8-sig")
    for token in [
        "python -m venv",
        'pip install -e "."',
        "playwright install chromium",
        "AutoDy-管理台.cmd",
        "config.example.yaml",
    ]:
        assert token in text

    for token in ["AUTODY_HOME", "PLAYWRIGHT_BROWSERS_PATH", "PLAYWRIGHT_SKIP_BROWSER_GC"]:
        assert token in text
    launcher = Path("install.cmd").read_text(encoding="utf-8-sig")
    for token in ["AUTODY_HOME", "PLAYWRIGHT_BROWSERS_PATH", "PLAYWRIGHT_SKIP_BROWSER_GC"]:
        assert token in launcher


def test_repair_script_uses_project_local_browser_directory():
    text = Path("scripts/repair-playwright.ps1").read_text(encoding="utf-8-sig")
    for token in [
        "AUTODY_HOME",
        "PLAYWRIGHT_BROWSERS_PATH",
        "PLAYWRIGHT_SKIP_BROWSER_GC",
        "repair-playwright",
    ]:
        assert token in text


def test_portable_builder_excludes_sensitive_data():
    text = Path("scripts/build-portable.ps1").read_text(encoding="utf-8-sig")
    for token in [".venv", "browser-profile", "config.yaml", "data", "node_modules"]:
        assert token in text
    assert "Compress-Archive" in text
