from pathlib import Path


def test_install_script_has_required_scheduler_contract():
    text = Path("scripts/install-task.ps1").read_text(encoding="utf-8-sig")
    for token in [
        "07:30",
        "StartWhenAvailable",
        "IgnoreNew",
        "autody.exe",
        "Register-ScheduledTask",
        "-ErrorAction Stop",
        "Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop",
    ]:
        assert token in text


def test_remove_script_uses_same_task_name():
    install = Path("scripts/install-task.ps1").read_text(encoding="utf-8-sig")
    remove = Path("scripts/remove-task.ps1").read_text(encoding="utf-8-sig")
    assert '$TaskName = "AutoDy-DailySpark"' in install
    assert '"AutoDy-DailySpark"' in remove
    assert '"AutoDy-Health-Daily"' in remove
    assert '"AutoDy-Health-Weekly"' in remove


def test_scheduler_wrappers_log_and_notify():
    run = Path("scripts/run-scheduled.ps1").read_text(encoding="utf-8-sig")
    health = Path("scripts/health-check.ps1").read_text(encoding="utf-8-sig")
    install = Path("scripts/install-task.ps1").read_text(encoding="utf-8-sig")
    for token in ["scheduler.log", "data\\notifications", "MessageBox"]:
        assert token in run
    for token in ["health-check", "data\\notifications", "MessageBox"]:
        assert token in health
    assert "Desktop" not in run
    assert "Desktop" not in health
    assert "RedirectStandardOutput" in run
    assert "RedirectStandardOutput" in health
    for token in ["AutoDy-Health-Daily", "07:20", "AutoDy-Health-Weekly", "20:00"]:
        assert token in install


def test_scheduler_wrappers_set_portable_playwright_environment():
    for path in [Path("scripts/run-scheduled.ps1"), Path("scripts/health-check.ps1")]:
        text = path.read_text(encoding="utf-8-sig")
        for token in ["AUTODY_HOME", "PLAYWRIGHT_BROWSERS_PATH", "PLAYWRIGHT_SKIP_BROWSER_GC"]:
            assert token in text


def test_every_scheduled_task_uses_ignore_new_policy():
    text = Path("scripts/install-task.ps1").read_text(encoding="utf-8-sig")
    assert "-MultipleInstances IgnoreNew" in text
    assert text.count("-Settings $Settings") == 3
