from pathlib import Path

import pytest

from autody.state import AppState, StateStore


def test_state_round_trip_is_atomic(tmp_path: Path):
    store = StateStore(tmp_path / "state.json")
    state = AppState()
    state.daily["2026-06-18"] = {"message": "早安", "succeeded": ["小明"]}
    store.save(state)
    assert store.load() == state
    assert not (tmp_path / "state.json.tmp").exists()


def test_corrupt_state_is_preserved_and_rejected(tmp_path: Path):
    path = tmp_path / "state.json"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="state file is corrupt"):
        StateStore(path).load()
    assert path.read_text(encoding="utf-8") == "{broken"
