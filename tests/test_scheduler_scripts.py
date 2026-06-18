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
    assert '$TaskName = "AutoDy-DailySpark"' in remove
