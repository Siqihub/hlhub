from pathlib import Path

import pytest
from pydantic import ValidationError

from autody.config import load_config


def test_loads_valid_config(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "targets:\n  - name: 小明\nmessages_file: messages.txt\n",
        encoding="utf-8",
    )

    config = load_config(path)

    assert [target.name for target in config.targets] == ["小明"]
    assert config.messages_file == tmp_path / "messages.txt"
    assert config.retry_count == 3


@pytest.mark.parametrize(
    "body",
    ["targets: []\n", "targets:\n  - name: 小明\n  - name: 小明\n"],
)
def test_rejects_empty_or_duplicate_targets(tmp_path: Path, body: str):
    path = tmp_path / "config.yaml"
    path.write_text(body, encoding="utf-8")

    with pytest.raises(ValidationError):
        load_config(path)
