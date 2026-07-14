from pathlib import Path
import subprocess
import sys


def test_cli_import_has_no_missing_internal_diagnostics_dependency():
    completed = subprocess.run(
        [sys.executable, "-c", "import autody.cli; print('ok')"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "ok"


def test_portable_builder_copies_entire_autody_package_without_diagnostics_import():
    source_modules = {path.name for path in Path("src/autody").glob("*.py")}
    builder = Path("scripts/build-portable.ps1").read_text(encoding="utf-8-sig")
    cli = Path("src/autody/cli.py").read_text(encoding="utf-8")

    assert "\"src\"" in builder
    assert "autody.diagnostics" not in cli
    assert "cli.py" in source_modules
