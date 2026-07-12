from datetime import date
from pathlib import Path

from autody.history import TaskHistoryStore, TaskRunRecord, bootstrap_legacy_daily_history


def record(run_id: str, day: str, status: str = "completed", task_type: str = "daily_send"):
    return TaskRunRecord(
        run_id=run_id,
        date=day,
        task_type=task_type,
        trigger_source="manual",
        start_time=f"{day}T07:30:00",
        end_time=f"{day}T07:30:01",
        duration=1,
        total_targets=2,
        success_count=2,
        final_status=status,
    )


def test_task_history_writes_jsonl_and_filters(tmp_path: Path):
    store = TaskHistoryStore(tmp_path / "task-runs.jsonl")
    store.append(record("one", "2026-07-10"))
    store.append(record("two", "2026-07-11", "partial_failed"))
    store.append(record("three", "2026-07-12", task_type="health_check"))

    page = store.query(
        start_date=date(2026, 7, 10),
        end_date=date(2026, 7, 11),
        status="partial_failed",
        task_type="daily_send",
    )

    assert page.total == 1
    assert page.items[0].run_id == "two"
    assert store.integrity() == {"valid": True, "record_count": 3, "invalid_count": 0}


def test_task_history_reports_corrupt_lines_without_losing_valid_records(tmp_path: Path):
    path = tmp_path / "task-runs.jsonl"
    store = TaskHistoryStore(path)
    store.append(record("one", "2026-07-10"))
    with path.open("a", encoding="utf-8") as handle:
        handle.write("not-json\n")

    assert store.query().total == 1
    assert store.integrity()["invalid_count"] == 1


def test_legacy_daily_state_is_bootstrapped_once_without_friend_names(tmp_path: Path):
    store = TaskHistoryStore(tmp_path / "task-runs.jsonl")
    daily = {
        "2026-07-12": {
            "message": "早安",
            "succeeded": ["小明"],
            "failures": {"小红": "not found"},
            "consumed": False,
        }
    }

    assert bootstrap_legacy_daily_history(store, daily, 2) == 1
    assert bootstrap_legacy_daily_history(store, daily, 2) == 0
    raw = store.path.read_text(encoding="utf-8")
    assert "小明" not in raw
    assert "小红" not in raw
