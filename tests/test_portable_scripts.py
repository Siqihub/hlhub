from pathlib import Path


def test_installer_creates_environment_browser_and_shortcut():
    text = Path("scripts/install.ps1").read_text(encoding="utf-8-sig")
    for token in [
        "python -m venv",
        'pip install -e "."',
        "playwright install chromium",
        "install-shortcut.ps1",
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


def test_dashboard_launcher_and_shortcut_are_portable_and_use_icon():
    launcher = Path("scripts/start-dashboard.cmd").read_text(encoding="utf-8-sig")
    for token in [
        "%~dp0..",
        "AUTODY_HOME",
        "PLAYWRIGHT_BROWSERS_PATH",
        "PLAYWRIGHT_SKIP_BROWSER_GC",
        ".venv\\Scripts\\autody.exe",
        "请先运行 install.cmd",
    ]:
        assert token in launcher

    shortcut = Path("scripts/install-shortcut.ps1").read_text(encoding="utf-8-sig")
    for token in [
        "WScript.Shell",
        "AutoDy 管理台.lnk",
        "start-dashboard.cmd",
        "assets\\icons\\autody.ico",
        "AutoDy-重新登录.cmd",
        "AutoDy-需要处理.txt",
    ]:
        assert token in shortcut
    assert "C:\\Users\\Administrator" not in shortcut


def test_custom_icon_exists_and_is_included_with_message_packs():
    icon = Path("assets/icons/autody.ico")
    assert icon.is_file()
    assert icon.stat().st_size > 1000
    builder = Path("scripts/build-portable.ps1").read_text(encoding="utf-8-sig")
    assert '"assets"' in builder
    assert '"message-packs"' in builder


def test_portable_builder_excludes_sensitive_data():
    text = Path("scripts/build-portable.ps1").read_text(encoding="utf-8-sig")
    for token in [".venv", "browser-profile", "config.yaml", "data", "node_modules"]:
        assert token in text
    assert "Compress-Archive" in text
